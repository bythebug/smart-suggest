import math

import pytest

from interpretation import (
    analyze_ab_test,
    effect_size,
    generate_conclusion,
    is_significant,
    practical_significance,
)
from significance import (
    _normal_ppf,
    _t_p_value,
    chi_square_test,
    confidence_interval,
    sample_size_needed,
    t_test,
)


# ---------------------------------------------------------------------------
# test_chi_square_test
# ---------------------------------------------------------------------------


class TestChiSquareTest:
    def test_identical_proportions_returns_zero_chi2(self):
        result = chi_square_test((10, 100), (10, 100))
        assert result["chi2"] == pytest.approx(0.0, abs=1e-6)
        assert result["p_value"] == pytest.approx(1.0, abs=0.01)
        assert not result["significant"]

    def test_large_difference_is_significant(self):
        # A: 10/100 clicks, B: 30/100 clicks — clearly different
        result = chi_square_test((10, 100), (30, 100))
        assert result["chi2"] is not None
        assert result["chi2"] > 10.0
        assert result["p_value"] < 0.05
        assert result["significant"]

    def test_zero_total_returns_none(self):
        result = chi_square_test((0, 0), (10, 100))
        assert result["chi2"] is None
        assert not result["significant"]

    def test_small_expected_counts_returns_warning(self):
        # Tiny sample — expected cell counts < 5
        result = chi_square_test((1, 5), (1, 5))
        assert result["chi2"] is None
        assert "warning" in result

    def test_borderline_case(self):
        # A: 10/100, B: 20/100 — borderline significant
        result = chi_square_test((10, 100), (20, 100))
        assert result["chi2"] is not None
        assert 0.0 < result["p_value"] < 0.1

    def test_returns_df_of_one(self):
        result = chi_square_test((20, 100), (25, 100))
        assert result["df"] == 1

    def test_p_value_between_zero_and_one(self):
        result = chi_square_test((15, 200), (25, 200))
        assert 0.0 <= result["p_value"] <= 1.0

    def test_perfect_split_low_significance(self):
        # Both variants exactly 50% — p should be ~1.0
        result = chi_square_test((50, 100), (50, 100))
        assert result["p_value"] > 0.9


# ---------------------------------------------------------------------------
# test_t_test
# ---------------------------------------------------------------------------


class TestTTest:
    def test_identical_samples_returns_zero_t(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = t_test(data, data)
        assert result["t_statistic"] == pytest.approx(0.0, abs=1e-6)
        assert not result["significant"]

    def test_very_different_means_is_significant(self):
        a = [10.0] * 50
        b = [100.0] * 50
        result = t_test(a, b)
        assert result["significant"]
        assert result["p_value"] < 0.001

    def test_too_few_samples_returns_none(self):
        result = t_test([10.0], [20.0])
        assert result["t_statistic"] is None
        assert not result["significant"]

    def test_empty_sample_returns_none(self):
        result = t_test([], [10.0, 20.0, 30.0])
        assert result["t_statistic"] is None

    def test_returns_correct_means(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = t_test(a, b)
        assert result["mean_a"] == pytest.approx(2.0)
        assert result["mean_b"] == pytest.approx(5.0)
        assert result["difference"] == pytest.approx(3.0)

    def test_p_value_between_zero_and_one(self):
        a = [10.0, 12.0, 11.0, 13.0, 9.0]
        b = [15.0, 14.0, 16.0, 13.0, 17.0]
        result = t_test(a, b)
        assert 0.0 <= result["p_value"] <= 1.0

    def test_b_lower_than_a_gives_negative_t(self):
        a = [20.0, 21.0, 22.0, 19.0, 20.0]
        b = [10.0, 11.0, 10.0, 9.0, 10.0]
        result = t_test(a, b)
        assert result["t_statistic"] < 0

    def test_welch_df_less_than_combined_n_minus_2(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0]  # very different variance
        result = t_test(a, b)
        assert result["df"] < (len(a) + len(b) - 2)


# ---------------------------------------------------------------------------
# test_confidence_interval
# ---------------------------------------------------------------------------


class TestConfidenceInterval:
    def test_50_percent_proportion(self):
        ci = confidence_interval(50, 100)
        assert ci["lower"] < 0.5 < ci["upper"]
        assert ci["center"] == pytest.approx(0.5, abs=0.02)

    def test_ci_contains_true_proportion_near_zero(self):
        ci = confidence_interval(2, 100)
        assert ci["lower"] >= 0.0
        assert ci["upper"] > ci["lower"]

    def test_ci_contains_true_proportion_near_one(self):
        ci = confidence_interval(98, 100)
        assert ci["upper"] <= 1.0
        assert ci["lower"] < ci["upper"]

    def test_zero_successes_lower_is_zero(self):
        ci = confidence_interval(0, 100)
        assert ci["lower"] == pytest.approx(0.0)

    def test_all_successes_upper_is_one(self):
        ci = confidence_interval(100, 100)
        assert ci["upper"] == pytest.approx(1.0, abs=0.01)

    def test_zero_sample_size(self):
        ci = confidence_interval(0, 0)
        assert ci["lower"] == 0.0
        assert ci["upper"] == 0.0

    def test_wider_ci_for_smaller_sample(self):
        ci_large = confidence_interval(50, 1000)
        ci_small = confidence_interval(5, 100)
        width_large = ci_large["upper"] - ci_large["lower"]
        width_small = ci_small["upper"] - ci_small["lower"]
        assert width_small > width_large

    def test_99_percent_ci_wider_than_95(self):
        ci_95 = confidence_interval(30, 100, confidence=0.95)
        ci_99 = confidence_interval(30, 100, confidence=0.99)
        assert (ci_99["upper"] - ci_99["lower"]) > (ci_95["upper"] - ci_95["lower"])

    def test_confidence_stored_in_result(self):
        ci = confidence_interval(50, 100, confidence=0.90)
        assert ci["confidence"] == 0.90


# ---------------------------------------------------------------------------
# test_power_analysis
# ---------------------------------------------------------------------------


class TestPowerAnalysis:
    def test_larger_mde_needs_fewer_users(self):
        n_small_mde = sample_size_needed(0.10, 0.01)
        n_large_mde = sample_size_needed(0.10, 0.05)
        assert n_large_mde < n_small_mde

    def test_higher_power_needs_more_users(self):
        n_80 = sample_size_needed(0.10, 0.02, power=0.80)
        n_90 = sample_size_needed(0.10, 0.02, power=0.90)
        assert n_90 > n_80

    def test_lower_alpha_needs_more_users(self):
        n_05 = sample_size_needed(0.10, 0.02, alpha=0.05)
        n_01 = sample_size_needed(0.10, 0.02, alpha=0.01)
        assert n_01 > n_05

    def test_known_value_baseline_10_mde_5pp(self):
        # baseline=0.10, mde=0.05, alpha=0.05, power=0.80
        # Expected: ~683 per variant (computed analytically)
        n = sample_size_needed(0.10, 0.05, alpha=0.05, power=0.80)
        assert 600 <= n <= 750

    def test_known_value_baseline_10_mde_2pp(self):
        # baseline=0.10, mde=0.02, alpha=0.05, power=0.80
        # Expected: ~3839 per variant
        n = sample_size_needed(0.10, 0.02, alpha=0.05, power=0.80)
        assert 3500 <= n <= 4200

    def test_returns_integer(self):
        assert isinstance(sample_size_needed(0.1, 0.02), int)

    def test_invalid_baseline_raises(self):
        with pytest.raises(ValueError):
            sample_size_needed(1.5, 0.01)

    def test_zero_mde_raises(self):
        with pytest.raises(ValueError):
            sample_size_needed(0.1, 0.0)


# ---------------------------------------------------------------------------
# test_interpretation
# ---------------------------------------------------------------------------


class TestIsSignificant:
    def test_below_alpha(self):
        assert is_significant(0.01) is True

    def test_above_alpha(self):
        assert is_significant(0.10) is False

    def test_exactly_alpha_not_significant(self):
        assert is_significant(0.05) is False

    def test_none_p_value(self):
        assert is_significant(None) is False

    def test_custom_alpha(self):
        assert is_significant(0.04, alpha=0.01) is False
        assert is_significant(0.004, alpha=0.01) is True


class TestEffectSize:
    def test_no_difference_is_negligible(self):
        result = effect_size(0.1, 0.1)
        assert result["cohens_h"] == pytest.approx(0.0, abs=1e-6)
        assert result["magnitude"] == "negligible"

    def test_large_difference_is_large(self):
        result = effect_size(0.05, 0.80)
        assert result["magnitude"] == "large"
        assert result["cohens_h"] > 0.8

    def test_relative_lift_positive_when_b_greater(self):
        result = effect_size(0.10, 0.15)
        assert result["relative_lift_pct"] == pytest.approx(50.0)

    def test_negative_effect_when_b_smaller(self):
        result = effect_size(0.20, 0.10)
        assert result["cohens_h"] < 0
        assert result["absolute_diff"] == pytest.approx(-0.10)

    def test_zero_metric_a_relative_lift_is_zero(self):
        result = effect_size(0.0, 0.1)
        assert result["relative_lift_pct"] == 0.0


class TestPracticalSignificance:
    def test_both_significant_is_worth_shipping(self):
        eff = effect_size(0.10, 0.20)
        result = practical_significance(0.001, eff)
        assert result["verdict"] == "worth_shipping"

    def test_stat_sig_negligible_effect(self):
        eff = {"magnitude": "negligible", "cohens_h": 0.01,
               "absolute_diff": 0.001, "relative_lift_pct": 0.5}
        result = practical_significance(0.001, eff)
        assert result["verdict"] == "stat_sig_but_small_effect"
        assert not result["practically_significant"]

    def test_not_stat_sig_but_meaningful_effect(self):
        eff = effect_size(0.10, 0.25)
        result = practical_significance(0.20, eff)
        assert result["verdict"] == "promising_but_underpowered"

    def test_neither_significant(self):
        eff = {"magnitude": "negligible", "cohens_h": 0.01,
               "absolute_diff": 0.001, "relative_lift_pct": 0.5}
        result = practical_significance(0.30, eff)
        assert result["verdict"] == "no_effect"


class TestGenerateConclusion:
    def test_conclusion_is_string(self):
        eff = effect_size(0.10, 0.15)
        ci = confidence_interval(15, 100)
        result = generate_conclusion("CTR", 0.10, 0.15, 0.001, ci, eff)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_conclusion_mentions_metric_name(self):
        eff = effect_size(0.10, 0.15)
        ci = confidence_interval(15, 100)
        result = generate_conclusion("CTR", 0.10, 0.15, 0.001, ci, eff)
        assert "CTR" in result

    def test_conclusion_says_not_significant_when_p_high(self):
        eff = effect_size(0.10, 0.11)
        ci = confidence_interval(11, 100)
        result = generate_conclusion("CTR", 0.10, 0.11, 0.50, ci, eff)
        assert "NOT statistically significant" in result

    def test_conclusion_says_significant_when_p_low(self):
        eff = effect_size(0.10, 0.20)
        ci = confidence_interval(20, 100)
        result = generate_conclusion("CTR", 0.10, 0.20, 0.001, ci, eff)
        assert "statistically significant" in result
        assert "NOT" not in result

    def test_conclusion_shows_lower_direction(self):
        eff = effect_size(0.20, 0.10)
        ci = confidence_interval(10, 100)
        result = generate_conclusion("CTR", 0.20, 0.10, 0.05, ci, eff)
        assert "lower" in result
