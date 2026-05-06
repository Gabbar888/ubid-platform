"""Tests for scoring pipeline."""
import pytest
from ubid.scoring import features as feat_module
from ubid.scoring.deterministic import evaluate as det_eval


class TestDeterministicTier:
    def test_same_pan_company_is_match(self, se_record, fbis_record_same_entity):
        result = det_eval(se_record, fbis_record_same_entity)
        assert result.fired is True
        assert result.is_match is True
        assert result.probability == 1.0

    def test_different_pan_is_nonmatch(self, se_record, different_entity_record):
        result = det_eval(se_record, different_entity_record)
        assert result.fired is True
        assert result.is_match is False
        assert result.probability == 0.0

    def test_proprietorship_pan_is_soft(self):
        from ubid.schema.canonical import CanonicalRecord, SourceSystem
        a = CanonicalRecord(
            source_system=SourceSystem.EKARMIKA,
            source_record_id="SE-001",
            name_raw="Ram Store",
            name_normalized="ram store",
            pan="ABCPD1234F",  # P = individual/proprietorship
            pan_entity_type="individual",
            pan_is_proprietorship=True,
        )
        b = CanonicalRecord(
            source_system=SourceSystem.FBIS,
            source_record_id="FAC-001",
            name_raw="Ram Enterprises",
            name_normalized="ram enterprises",
            pan="ABCPD1234F",
            pan_entity_type="individual",
            pan_is_proprietorship=True,
        )
        result = det_eval(a, b)
        assert result.fired is True
        assert result.is_match is None  # soft — route to probabilistic


class TestFeatureVector:
    def test_feature_count(self, se_record, fbis_record_same_entity):
        fv = feat_module.compute(se_record, fbis_record_same_entity)
        assert len(fv) == len(feat_module.FEATURE_NAMES)

    def test_same_pan_blocking_feature(self, se_record, fbis_record_same_entity):
        fv = feat_module.compute(se_record, fbis_record_same_entity)
        assert fv["blk_shared_pan"] == 1.0

    def test_name_similarity_high_for_same_entity(self, se_record, fbis_record_same_entity):
        fv = feat_module.compute(se_record, fbis_record_same_entity)
        assert fv["name_jaro_winkler"] > 0.7

    def test_different_entity_low_name_similarity(self, se_record, different_entity_record):
        fv = feat_module.compute(se_record, different_entity_record)
        assert fv["name_jaro_winkler"] < 0.6

    def test_same_pin_same_locality(self, se_record, fbis_record_same_entity):
        fv = feat_module.compute(se_record, fbis_record_same_entity)
        assert fv["addr_pin_eq"] == 1.0
        assert fv["addr_locality_match"] == 1.0
