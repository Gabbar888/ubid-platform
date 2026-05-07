"""LightGBM pairwise scorer with SHAP-based explainability.

Falls back to a weighted-sum heuristic when no trained model exists.
"""
from __future__ import annotations
import logging
import math
import os
from pathlib import Path
from typing import Optional

import numpy as np

from ubid.config import get_settings
from ubid.schema.canonical import CanonicalRecord, ScoredPair
from ubid.scoring import features as feat_module
from ubid.scoring.deterministic import evaluate as det_evaluate

logger = logging.getLogger(__name__)

_MODEL_FILE = "lgbm_scorer.pkl"
_CALIBRATOR_FILE = "isotonic_calibrator.pkl"

# Fallback weights for heuristic scoring (before training)
_HEURISTIC_WEIGHTS = {
    "name_jaro_winkler":       0.25,
    "name_token_set_ratio":    0.20,
    "name_jaccard_trigram":    0.10,
    "addr_pin_eq":             0.15,
    "addr_locality_match":     0.10,
    "id_gstin_eq":             0.30,
    "id_phone_eq":             0.08,
    "id_pan_agreement":        0.40,
    "blk_shared_pan":          0.35,
    "blk_shared_derived_pan":  0.25,
    "blk_n_shared":            0.05,
}


class LightGBMScorer:
    def __init__(self):
        self._model = None
        self._calibrator = None
        self._trained = False
        self._load_if_exists()

    def _load_if_exists(self):
        import joblib
        settings = get_settings()
        model_path = Path(settings.model_dir) / _MODEL_FILE
        cal_path = Path(settings.model_dir) / _CALIBRATOR_FILE
        if model_path.exists() and cal_path.exists():
            try:
                self._model = joblib.load(model_path)
                self._calibrator = joblib.load(cal_path)
                self._trained = True
                logger.info("Loaded LightGBM scorer from %s", model_path)
            except Exception as e:
                logger.warning("Could not load scorer: %s — using heuristic fallback", e)

    def score(self, a: CanonicalRecord, b: CanonicalRecord, fast: bool = False) -> ScoredPair:
        """Score a record pair.

        fast=True skips SHAP attribution and OpenSearch shared-block lookup,
        useful for batch evaluation where per-pair explainability is not needed.
        """
        det = det_evaluate(a, b)

        if det.fired and det.is_match is not None:
            return ScoredPair(
                canonical_id_a=a.canonical_id,
                canonical_id_b=b.canonical_id,
                raw_score=det.probability,
                calibrated_probability=det.probability,
                deterministic_tier_fired=True,
                deterministic_result=det.is_match,
                feature_vector={},
                shap_contributions={"deterministic_rule": det.probability},
                shared_blocks=[],
            )

        fv = feat_module.compute(a, b)

        # Seed calibrated_probability from deterministic soft result if available
        prior = det.probability if (det.fired and det.probability > 0) else 0.5

        if self._trained:
            raw, cal, shap = self._model_score(fv, prior, with_shap=not fast)
        else:
            raw = self._heuristic_score(fv)
            cal = _sigmoid_blend(raw, prior)
            shap = {} if fast else {
                k: _HEURISTIC_WEIGHTS.get(k, 0.0) * v
                for k, v in fv.items() if v != feat_module.MISSING
            }

        if fast:
            shared = []
        else:
            from ubid.blocking.opensearch_blocker import which_blocks_shared
            shared = which_blocks_shared(a, b)

        return ScoredPair(
            canonical_id_a=a.canonical_id,
            canonical_id_b=b.canonical_id,
            raw_score=raw,
            calibrated_probability=cal,
            deterministic_tier_fired=det.fired,
            deterministic_result=None,
            feature_vector=fv,
            shap_contributions=shap,
            shared_blocks=shared,
        )

    def _model_score(self, fv: dict, prior: float, with_shap: bool = True):
        X = np.array([feat_module.to_vector(fv)])
        raw = float(self._model.predict_proba(X)[0, 1])
        cal = float(self._calibrator.predict([raw])[0])
        if not with_shap:
            return raw, cal, {}
        try:
            import shap as shap_lib
            explainer = shap_lib.TreeExplainer(self._model)
            shap_vals = explainer.shap_values(X)
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
            shap_dict = dict(zip(feat_module.FEATURE_NAMES, shap_vals[0].tolist()))
        except Exception:
            shap_dict = {}
        return raw, cal, shap_dict

    def _heuristic_score(self, fv: dict) -> float:
        total_w, weighted_sum = 0.0, 0.0
        for feat, weight in _HEURISTIC_WEIGHTS.items():
            v = fv.get(feat, feat_module.MISSING)
            if v != feat_module.MISSING:
                weighted_sum += weight * v
                total_w += weight
        return weighted_sum / total_w if total_w > 0 else 0.3

    def train(self, feature_matrix: list[list[float]], labels: list[int]):
        """Train on labelled pairs. Call after enough reviewer decisions accumulate."""
        import lightgbm as lgb
        import joblib
        from sklearn.model_selection import train_test_split
        from ubid.scoring.calibrator import fit_isotonic

        X = np.array(feature_matrix)
        y = np.array(labels)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "n_estimators": 300,
            "early_stopping_rounds": 30,
            "verbose": -1,
        }
        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            feature_name=feat_module.FEATURE_NAMES,
        )
        self._model = model

        raw_probs = model.predict_proba(X_val)[:, 1]
        calibrator = fit_isotonic(raw_probs, y_val)
        self._calibrator = calibrator
        self._trained = True

        settings = get_settings()
        os.makedirs(settings.model_dir, exist_ok=True)
        joblib.dump(model, Path(settings.model_dir) / _MODEL_FILE)
        joblib.dump(calibrator, Path(settings.model_dir) / _CALIBRATOR_FILE)
        logger.info("Trained and saved LightGBM scorer.")


def _sigmoid_blend(score: float, prior: float, alpha: float = 0.3) -> float:
    """Blend heuristic score with the deterministic prior."""
    return alpha * prior + (1 - alpha) * score


_scorer_instance: Optional[LightGBMScorer] = None


def get_scorer() -> LightGBMScorer:
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = LightGBMScorer()
    return _scorer_instance
