"""
Results interpretation layer — wraps significance.py functions and produces
human-readable conclusions from raw statistical outputs.
"""

import math

from significance import chi_square_test, confidence_interval, t_test


# ---------------------------------------------------------------------------
# Individual interpretation helpers
# ---------------------------------------------------------------------------


def is_significant(p_value: float | None, alpha: float = 0.05) -> bool:
    """Return True when p_value is not None and falls below alpha."""
    return p_value is not None and p_value < alpha


def effect_size(metric_a: float, metric_b: float) -> dict:
    """
    Cohen's h for two proportions.

    h = 2·arcsin(√p₂) − 2·arcsin(√p₁)

    Magnitude thresholds (Cohen 1988):
        |h| < 0.20  → negligible
        0.20 ≤ |h| < 0.50 → small
        0.50 ≤ |h| < 0.80 → medium
        |h| ≥ 0.80  → large
    """
    # Clamp to [0, 1] to guard against floating-point drift
    pa = max(0.0, min(1.0, metric_a))
    pb = max(0.0, min(1.0, metric_b))

    h = 2.0 * math.asin(math.sqrt(pb)) - 2.0 * math.asin(math.sqrt(pa))
    abs_h = abs(h)

    if abs_h < 0.20:
        magnitude = "negligible"
    elif abs_h < 0.50:
        magnitude = "small"
    elif abs_h < 0.80:
        magnitude = "medium"
    else:
        magnitude = "large"

    relative_lift_pct = (
        (metric_b - metric_a) / metric_a * 100.0 if metric_a > 0.0 else 0.0
    )

    return {
        "cohens_h": round(h, 4),
        "magnitude": magnitude,
        "absolute_diff": round(metric_b - metric_a, 4),
        "relative_lift_pct": round(relative_lift_pct, 2),
    }


def practical_significance(
    p_value: float | None,
    effect: dict,
    min_effect_size: str = "small",
) -> dict:
    """
    Determine whether a result is worth acting on.

    A result is *practically significant* when it is BOTH:
    1. Statistically significant (p < 0.05)
    2. Large enough to matter (effect magnitude ≥ min_effect_size)

    Verdicts:
    - worth_shipping             : stat + practical significance achieved
    - stat_sig_but_small_effect  : real but too small to justify effort
    - promising_but_underpowered : looks meaningful, needs more data
    - no_effect                  : neither significant nor meaningful
    """
    ORDER = {"negligible": 0, "small": 1, "medium": 2, "large": 3}
    stat_sig = is_significant(p_value)
    prac_sig = ORDER.get(effect["magnitude"], 0) >= ORDER.get(min_effect_size, 1)

    if stat_sig and prac_sig:
        verdict = "worth_shipping"
        reason = "Statistically significant and large enough to matter."
    elif stat_sig:
        verdict = "stat_sig_but_small_effect"
        reason = "Real effect detected, but too small to justify engineering investment."
    elif prac_sig:
        verdict = "promising_but_underpowered"
        reason = "Effect looks meaningful but p-value not significant yet — run longer."
    else:
        verdict = "no_effect"
        reason = "No statistically or practically significant difference detected."

    return {
        "statistically_significant": stat_sig,
        "practically_significant": prac_sig,
        "verdict": verdict,
        "reason": reason,
    }


def generate_conclusion(
    metric_name: str,
    value_a: float,
    value_b: float,
    p_value: float | None,
    ci_b: dict,
    effect: dict,
) -> str:
    """
    Generate a human-readable one-paragraph conclusion.

    Example output:
    "Variant B has 33.3% higher CTR (95% CI: 16.0%–24.0%, p=0.001).
     This is statistically significant (p<0.05) and practically important
     (medium effect, Cohen's h=0.13 — worth shipping)."
    """
    direction = "higher" if value_b >= value_a else "lower"
    lift_pct = abs(effect["relative_lift_pct"])

    p_str = f"p={p_value:.3f}" if p_value is not None else "p=N/A"
    ci_str = f"{ci_b['lower'] * 100:.1f}%–{ci_b['upper'] * 100:.1f}%"

    practical = practical_significance(p_value, effect)
    sig_text = (
        f"statistically significant ({p_str} < 0.05)"
        if is_significant(p_value)
        else f"NOT statistically significant ({p_str} ≥ 0.05)"
    )

    effect_text = (
        f"{effect['magnitude']} effect (Cohen’s h={effect['cohens_h']:.2f})"
    )
    verdict_text = practical["reason"]

    return (
        f"Variant B has {lift_pct:.1f}% {direction} {metric_name} "
        f"(95% CI: {ci_str}, {p_str}). "
        f"This is {sig_text}. "
        f"Effect size is {effect_text}. "
        f"Verdict: {verdict_text}"
    )


# ---------------------------------------------------------------------------
# Full A/B test analysis
# ---------------------------------------------------------------------------


def analyze_ab_test(metrics: dict, eng_times_a: list[float], eng_times_b: list[float]) -> dict:
    """
    Combine statistical testing and interpretation for a complete A/B analysis.

    metrics       : output of analysis.calculate_metrics_by_variant()
    eng_times_a/b : raw per-session engagement time values per variant
    """
    a = metrics["variants"]["A"]
    b = metrics["variants"]["B"]

    # ── CTR ──────────────────────────────────────────────────────────────────
    ctr_test = chi_square_test(
        (a["clicks"], a["impressions"]),
        (b["clicks"], b["impressions"]),
    )
    ctr_ci_a = confidence_interval(a["clicks"], a["impressions"])
    ctr_ci_b = confidence_interval(b["clicks"], b["impressions"])
    ctr_effect = effect_size(a["ctr"], b["ctr"])
    ctr_practical = practical_significance(ctr_test["p_value"], ctr_effect)
    ctr_conclusion = generate_conclusion(
        "CTR", a["ctr"], b["ctr"], ctr_test["p_value"], ctr_ci_b, ctr_effect
    )

    # ── Conversion rate ───────────────────────────────────────────────────────
    conv_test = chi_square_test(
        (a["users_converted"], a["users_exposed"]),
        (b["users_converted"], b["users_exposed"]),
    )
    conv_ci_a = confidence_interval(a["users_converted"], a["users_exposed"])
    conv_ci_b = confidence_interval(b["users_converted"], b["users_exposed"])
    conv_effect = effect_size(a["conversion_rate"], b["conversion_rate"])
    conv_practical = practical_significance(conv_test["p_value"], conv_effect)
    conv_conclusion = generate_conclusion(
        "conversion rate",
        a["conversion_rate"],
        b["conversion_rate"],
        conv_test["p_value"],
        conv_ci_b,
        conv_effect,
    )

    # ── Engagement time (Welch's t-test) ──────────────────────────────────────
    eng_test = (
        t_test(eng_times_a, eng_times_b)
        if len(eng_times_a) >= 2 and len(eng_times_b) >= 2
        else None
    )

    return {
        "ctr": {
            "variant_a": {"value": a["ctr"], "ci_95": ctr_ci_a},
            "variant_b": {"value": b["ctr"], "ci_95": ctr_ci_b},
            "test": ctr_test,
            "effect": ctr_effect,
            "practical": ctr_practical,
            "conclusion": ctr_conclusion,
        },
        "conversion_rate": {
            "variant_a": {"value": a["conversion_rate"], "ci_95": conv_ci_a},
            "variant_b": {"value": b["conversion_rate"], "ci_95": conv_ci_b},
            "test": conv_test,
            "effect": conv_effect,
            "practical": conv_practical,
            "conclusion": conv_conclusion,
        },
        "engagement_time": {
            "variant_a": {"mean_s": a["avg_engagement_time_s"]},
            "variant_b": {"mean_s": b["avg_engagement_time_s"]},
            "test": eng_test,
        },
    }
