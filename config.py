from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Item categories
# ---------------------------------------------------------------------------

ITEM_CATEGORIES: List[str] = [
    "electronics",
    "clothing",
    "books",
    "home_appliances",
    "sports",
    "beauty",
    "food_and_grocery",
    "toys",
    "automotive",
    "health",
]

# ---------------------------------------------------------------------------
# Recommendation strategy configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyConfig:
    name: str
    description: str
    n_recommendations: int
    similarity_threshold: float
    # Weights must sum to 1.0
    recency_weight: float
    popularity_weight: float

    def __post_init__(self) -> None:
        total = self.recency_weight + self.popularity_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"recency_weight + popularity_weight must equal 1.0, got {total}"
            )


RECOMMENDATION_STRATEGIES: Dict[str, StrategyConfig] = {
    "v1": StrategyConfig(
        name="Collaborative Filtering v1",
        description=(
            "User-based collaborative filtering using cosine similarity "
            "on the full interaction history."
        ),
        n_recommendations=10,
        similarity_threshold=0.30,
        recency_weight=0.40,
        popularity_weight=0.60,
    ),
    "v2": StrategyConfig(
        name="Hybrid Recommender v2",
        description=(
            "Hybrid model that blends collaborative filtering signals with "
            "content-based category affinity. Favours recency over raw popularity."
        ),
        n_recommendations=10,
        similarity_threshold=0.25,
        recency_weight=0.60,
        popularity_weight=0.40,
    ),
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL: str = "sqlite:///smart_suggest.db"

# ---------------------------------------------------------------------------
# A/B testing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ABTestConfig:
    # Fraction of incoming users enrolled in the test (0.0 – 1.0).
    traffic_fraction: float
    # Probability that an enrolled user lands in variant B.
    variant_b_split: float

    def __post_init__(self) -> None:
        for attr, val in (
            ("traffic_fraction", self.traffic_fraction),
            ("variant_b_split", self.variant_b_split),
        ):
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{attr} must be between 0.0 and 1.0, got {val}")


DEFAULT_AB_TEST_CONFIG = ABTestConfig(
    traffic_fraction=0.50,
    variant_b_split=0.50,
)

# Metrics tracked per A/B test result row.
TRACKED_METRICS: List[str] = [
    "click_through_rate",
    "purchase_rate",
    "mean_session_depth",
    "revenue_per_user",
]
