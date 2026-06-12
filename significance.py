"""
Pure statistical functions — no DB dependency.
All p-values are two-tailed unless stated otherwise.
"""

import math


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------


def _normal_sf(z: float) -> float:
    """Upper-tail probability of the standard normal: P(Z > z)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def _normal_ppf(p: float) -> float:
    """
    Inverse CDF of the standard normal (rational approximation).

    Accuracy: |error| < 4.5e-4 over (0, 1).
    Reference: Abramowitz & Stegun §26.2.17.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")
    c = (2.515517, 0.802853, 0.010328)
    d = (1.432788, 0.189269, 0.001308)

    q = p if p < 0.5 else 1.0 - p
    t = math.sqrt(-2.0 * math.log(q))
    z = t - (c[0] + c[1] * t + c[2] * t**2) / (1.0 + d[0] * t + d[1] * t**2 + d[2] * t**3)
    return -z if p < 0.5 else z


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function (Lentz's method)."""
    MAXIT, EPS, FPMIN = 200, 3e-7, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < FPMIN: d = FPMIN
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < FPMIN: d = FPMIN
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    bt = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_p_value(t_stat: float, df: float) -> float:
    """Two-tailed p-value from Student's t-distribution."""
    x = df / (df + t_stat**2)
    return _betainc(df / 2.0, 0.5, x)


# ---------------------------------------------------------------------------
# Hypothesis tests
# ---------------------------------------------------------------------------


def chi_square_test(
    a_data: tuple[int, int],
    b_data: tuple[int, int],
) -> dict:
    """
    Pearson chi-square test for a 2×2 contingency table.

    a_data: (successes_a, total_a)
    b_data: (successes_b, total_b)

    Suitable for comparing proportions (CTR, conversion rate).
    Returns None statistics when any cell has an expected count < 5
    (Fisher's exact test would be more appropriate in that case).
    """
    s_a, n_a = a_data
    s_b, n_b = b_data
    f_a, f_b = n_a - s_a, n_b - s_b     # failures

    if n_a == 0 or n_b == 0:
        return {"chi2": None, "p_value": None, "df": 1, "significant": False}

    n = n_a + n_b
    # Expected counts under H₀
    e_s_a = n_a * (s_a + s_b) / n
    e_s_b = n_b * (s_a + s_b) / n
    e_f_a = n_a * (f_a + f_b) / n
    e_f_b = n_b * (f_a + f_b) / n

    if any(e < 5 for e in (e_s_a, e_s_b, e_f_a, e_f_b)):
        return {
            "chi2": None,
            "p_value": None,
            "df": 1,
            "significant": False,
            "warning": "Expected cell count < 5; use Fisher's exact test.",
        }

    chi2 = (
        (s_a - e_s_a) ** 2 / e_s_a
        + (s_b - e_s_b) ** 2 / e_s_b
        + (f_a - e_f_a) ** 2 / e_f_a
        + (f_b - e_f_b) ** 2 / e_f_b
    )

    # For df=1, chi2 = z², so p = 2 * Φ(-|z|)
    p_value = 2.0 * _normal_sf(math.sqrt(chi2))

    return {
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 4),
        "df": 1,
        "significant": p_value < 0.05,
    }


def t_test(data_a: list[float], data_b: list[float]) -> dict:
    """
    Welch's two-sample t-test (unequal variances assumed).

    Suitable for continuous metrics such as engagement time.
    Uses the exact t-distribution p-value via the regularized
    incomplete beta function (Numerical Recipes algorithm).

    Returns None statistics when either sample has fewer than 2 observations.
    """
    n_a, n_b = len(data_a), len(data_b)
    if n_a < 2 or n_b < 2:
        return {
            "t_statistic": None, "p_value": None,
            "df": None, "significant": False,
            "mean_a": None, "mean_b": None, "difference": None,
        }

    mean_a = sum(data_a) / n_a
    mean_b = sum(data_b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in data_a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in data_b) / (n_b - 1)

    se2 = var_a / n_a + var_b / n_b
    if se2 == 0.0:
        return {
            "t_statistic": None, "p_value": None,
            "df": None, "significant": False,
            "mean_a": round(mean_a, 4), "mean_b": round(mean_b, 4),
            "difference": 0.0,
        }

    t = (mean_b - mean_a) / math.sqrt(se2)

    # Welch-Satterthwaite degrees of freedom
    df = se2**2 / (
        (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    )

    p_value = _t_p_value(t, df)

    return {
        "t_statistic": round(t, 4),
        "p_value": round(p_value, 4),
        "df": round(df, 1),
        "significant": p_value < 0.05,
        "mean_a": round(mean_a, 4),
        "mean_b": round(mean_b, 4),
        "difference": round(mean_b - mean_a, 4),
    }


def confidence_interval(
    successes: int,
    n: int,
    confidence: float = 0.95,
) -> dict:
    """
    Wilson score confidence interval for a proportion.

    Preferred over the Wald (normal approximation) interval because it
    remains valid for proportions near 0 or 1 and for small sample sizes.
    """
    if n == 0:
        return {"lower": 0.0, "upper": 0.0, "center": 0.0, "confidence": confidence}

    z = _normal_ppf(1.0 - (1.0 - confidence) / 2.0)
    p_hat = successes / n
    z2n = z**2 / n

    center = (p_hat + z2n / 2.0) / (1.0 + z2n)
    margin = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + z2n / 4.0)) / (1.0 + z2n)

    return {
        "lower": round(max(0.0, center - margin), 4),
        "upper": round(min(1.0, center + margin), 4),
        "center": round(center, 4),
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Power analysis
# ---------------------------------------------------------------------------


def sample_size_needed(
    baseline: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """
    Minimum sample size *per variant* for a two-proportion z-test.

    baseline : control group proportion (e.g. 0.10 for 10% CTR)
    mde      : minimum detectable effect as an absolute change (e.g. 0.02 = +2pp)
    alpha    : Type I error rate (significance level)
    power    : 1 − β (probability of detecting a real effect)

    Formula: n = (z_α/2 + z_β)² × (p1(1−p1) + p2(1−p2)) / δ²
    where δ = mde, p2 = baseline + mde.
    """
    if not 0.0 < baseline < 1.0:
        raise ValueError(f"baseline must be in (0, 1), got {baseline}")
    if mde == 0.0:
        raise ValueError("mde must be non-zero")
    if baseline + mde <= 0.0 or baseline + mde >= 1.0:
        raise ValueError("baseline + mde must be in (0, 1)")

    p1 = baseline
    p2 = baseline + mde

    z_alpha = _normal_ppf(1.0 - alpha / 2.0)
    z_beta = _normal_ppf(power)

    n = (
        (z_alpha + z_beta) ** 2
        * (p1 * (1.0 - p1) + p2 * (1.0 - p2))
        / (p1 - p2) ** 2
    )
    return math.ceil(n)
