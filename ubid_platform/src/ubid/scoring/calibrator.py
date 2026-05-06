"""Isotonic regression calibration + reliability diagram metrics."""
from __future__ import annotations
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.calibration import calibration_curve


def fit_isotonic(raw_probs: np.ndarray, labels: np.ndarray) -> IsotonicRegression:
    cal = IsotonicRegression(out_of_bounds="clip")
    cal.fit(raw_probs, labels)
    return cal


def calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> dict:
    """Returns ECE, MCE, and Brier score."""
    fraction_of_positives, mean_predicted = calibration_curve(labels, probs, n_bins=n_bins, strategy="uniform")
    bin_sizes = np.histogram(probs, bins=n_bins, range=(0, 1))[0]
    weights = bin_sizes / bin_sizes.sum()

    ece = float(np.sum(weights * np.abs(fraction_of_positives - mean_predicted)))
    mce = float(np.max(np.abs(fraction_of_positives - mean_predicted)))
    brier = float(np.mean((probs - labels) ** 2))

    return {
        "ece": ece,
        "mce": mce,
        "brier_score": brier,
        "fraction_of_positives": fraction_of_positives.tolist(),
        "mean_predicted": mean_predicted.tolist(),
    }
