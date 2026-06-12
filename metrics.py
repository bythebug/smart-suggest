import math


# ---------------------------------------------------------------------------
# Core KPI functions — all pure, no DB dependency
# ---------------------------------------------------------------------------


def ctr(impressions: int, clicks: int) -> float:
    """Click-through rate: clicks / impressions. Returns 0.0 on zero impressions."""
    if impressions == 0:
        return 0.0
    return clicks / impressions


def conversion_rate(users_exposed: int, users_converted: int) -> float:
    """Purchase conversion rate: users_converted / users_exposed."""
    if users_exposed == 0:
        return 0.0
    return users_converted / users_exposed


def avg_engagement_time(engagements: list[float]) -> float:
    """Average engagement time in seconds across a list of per-session durations."""
    if not engagements:
        return 0.0
    return sum(engagements) / len(engagements)


def avg_items_per_user(interactions_by_user: dict[int, list[int]]) -> float:
    """
    Average number of *distinct* items interacted with per user.

    interactions_by_user maps user_id → [item_id, item_id, ...].
    Duplicate item_ids for the same user are de-duplicated before averaging,
    so a user who viewed the same item 5 times counts it once.
    """
    if not interactions_by_user:
        return 0.0
    unique_per_user = [len(set(items)) for items in interactions_by_user.values()]
    return sum(unique_per_user) / len(unique_per_user)


def diversity_score(recommendations: list[int]) -> float:
    """
    Recommendation diversity: unique items / total items recommended.

    A score of 1.0 means every slot shows a different item (maximum variety).
    A score near 0 means the system is recommending the same few items repeatedly.
    """
    if not recommendations:
        return 0.0
    return len(set(recommendations)) / len(recommendations)


# ---------------------------------------------------------------------------
# Statistical testing
# ---------------------------------------------------------------------------


def _normal_sf(z: float) -> float:
    """Survival function (upper tail probability) of the standard normal distribution."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def z_test_proportions(
    n_a: int,
    p_a: float,
    n_b: int,
    p_b: float,
    alpha: float = 0.05,
) -> dict:
    """
    Two-proportion z-test: is variant B's rate significantly different from A's?

    Uses a pooled standard error under H₀: p_A = p_B.
    Returns a two-tailed p-value — the test does not assume B > A.

    Returns None for z_score and p_value when either sample is empty or the
    pooled standard error is zero (e.g. both proportions are 0.0 or 1.0).
    """
    if n_a == 0 or n_b == 0:
        return {"z_score": None, "p_value": None, "significant": False, "alpha": alpha}

    p_pool = (p_a * n_a + p_b * n_b) / (n_a + n_b)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))

    if se == 0.0:
        return {"z_score": None, "p_value": None, "significant": False, "alpha": alpha}

    z = (p_b - p_a) / se
    p_value = 2 * _normal_sf(abs(z))

    return {
        "z_score": round(z, 4),
        "p_value": round(p_value, 4),
        "significant": p_value < alpha,
        "alpha": alpha,
    }
