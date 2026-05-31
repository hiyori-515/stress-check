"""
StressCheckScorer の基本テスト
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring.calculator import StressCheckScorer
from config.scoring_rules import ALL_ITEMS


# ── フィクスチャ ──────────────────────────────────────────────

@pytest.fixture
def all_responses():
    """全項目に回答値2をセットした回答データ"""
    return {q: 2 for q in ALL_ITEMS}


@pytest.fixture
def high_stress_responses():
    """B領域(q18-46)を全て4にして高ストレス㋐を確実に発生させる回答"""
    responses = {q: 2 for q in ALL_ITEMS}
    for q in range(18, 47):
        responses[q] = 4
    return responses


@pytest.fixture
def low_stress_responses():
    """全項目1（最もストレスが低い回答）"""
    return {q: 1 for q in ALL_ITEMS}


# ── 初期化テスト ─────────────────────────────────────────────

class TestInit:
    def test_valid_versions(self):
        for v in ["120", "80", "57"]:
            scorer = StressCheckScorer(version=v)
            assert scorer.version == v

    def test_invalid_version(self):
        with pytest.raises(ValueError):
            StressCheckScorer(version="999")


# ── calculate() テスト ────────────────────────────────────────

class TestCalculate:
    def test_returns_required_keys(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        required_keys = {
            "version", "valid", "missing_items", "item_scores",
            "scale_scores", "domain_scores", "high_stress",
            "high_stress_reason", "raw_B_total", "raw_AC_total",
        }
        assert required_keys.issubset(result.keys())

    def test_version_tag_in_result(self, all_responses):
        for v in ["120", "80", "57"]:
            scorer = StressCheckScorer(version=v)
            result = scorer.calculate(all_responses)
            assert result["version"] == v

    def test_valid_when_all_answered(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        assert result["valid"] is True
        assert result["missing_items"] == []

    def test_invalid_when_missing_items(self):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate({})
        assert result["valid"] is False
        assert len(result["missing_items"]) > 0

    def test_high_stress_flag_is_bool(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        assert isinstance(result["high_stress"], bool)

    def test_high_stress_detected(self, high_stress_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(high_stress_responses)
        assert result["high_stress"] is True
        assert result["high_stress_reason"] in ("㋐", "㋑")

    def test_low_stress_not_high(self, low_stress_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(low_stress_responses)
        assert result["high_stress"] is False
        assert result["high_stress_reason"] is None

    def test_raw_totals_are_int(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        assert isinstance(result["raw_B_total"], int)
        assert isinstance(result["raw_AC_total"], int)

    def test_raw_B_range(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        # B領域は q18-46（29項目）× 1-4 = 29〜116
        assert 29 <= result["raw_B_total"] <= 116

    def test_scale_scores_range(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        for name, score in result["scale_scores"].items():
            if score is not None:
                assert 1.0 <= score <= 4.0, f"{name}: {score} is out of range"

    def test_domain_scores_keys(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        assert set(result["domain_scores"].keys()) == {"A", "B", "C"}

    @pytest.mark.parametrize("version", ["120", "80", "57"])
    def test_all_versions_run(self, version, all_responses):
        scorer = StressCheckScorer(version=version)
        result = scorer.calculate(all_responses)
        assert result["version"] == version


# ── compare_to_national() テスト ─────────────────────────────

class TestCompareToNational:
    def test_returns_dict(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        valid_scales = {k: v for k, v in result["scale_scores"].items() if v is not None}
        comparison = scorer.compare_to_national(valid_scales)
        assert isinstance(comparison, dict)

    def test_comparison_keys(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        valid_scales = {k: v for k, v in result["scale_scores"].items() if v is not None}
        comparison = scorer.compare_to_national(valid_scales)
        for scale_name, data in comparison.items():
            assert "score" in data
            assert "national_mean" in data
            assert "diff" in data
            assert "z_score" in data
            assert "level" in data

    def test_level_values(self, all_responses):
        scorer = StressCheckScorer(version="57")
        result = scorer.calculate(all_responses)
        valid_scales = {k: v for k, v in result["scale_scores"].items() if v is not None}
        comparison = scorer.compare_to_national(valid_scales)
        valid_levels = {"良好", "平均的", "やや低い", "低い"}
        for data in comparison.values():
            assert data["level"] in valid_levels
