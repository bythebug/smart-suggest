from sqlalchemy.orm import Session

from config import RECOMMENDATION_STRATEGIES
from models import ActionType, Item, UserInteraction
from .similarity import top_k_similar_users

# Higher-intent actions contribute more weight to the interaction matrix.
ACTION_WEIGHTS: dict[ActionType, float] = {
    ActionType.VIEW: 1.0,
    ActionType.CLICK: 3.0,
    ActionType.PURCHASE: 5.0,
}

# Score assigned to new items (zero interactions from anyone) so CF can surface
# them via content similarity rather than leaving them permanently invisible.
_COLD_ITEM_DISCOUNT = 0.05


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------


def build_user_item_matrix(db: Session) -> dict[int, dict[int, float]]:
    """
    Fetch all interactions from the DB and return a weighted user-item matrix:
      { user_id: { item_id: weighted_score, ... }, ... }
    """
    matrix: dict[int, dict[int, float]] = {}

    for interaction in db.query(UserInteraction).all():
        uid = interaction.user_id
        iid = interaction.item_id
        w = ACTION_WEIGHTS.get(interaction.action, 1.0)

        if uid not in matrix:
            matrix[uid] = {}
        matrix[uid][iid] = matrix[uid].get(iid, 0.0) + w

    return matrix


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


def get_cf_recommendations(
    db: Session,
    user_id: int,
    n: int = 10,
    n_similar_users: int = 20,
) -> list[dict]:
    """
    User-based collaborative filtering recommendations.

    Algorithm:
      1. Build the full user-item weighted interaction matrix.
      2. Find the top n_similar_users neighbours by cosine similarity.
      3. Score unseen items by summing (similarity × neighbour_weight).
      4. Cold-start fill: items with zero interactions from anyone are scored
         by content similarity to the user's liked items (discounted), so
         newly added items surface immediately instead of being invisible.
      5. Return the top-n items ranked by score.

    Returns an empty list when the user has no interaction history at all.
    """
    matrix = build_user_item_matrix(db)

    if user_id not in matrix:
        return []

    config = RECOMMENDATION_STRATEGIES["v1"]

    similar_users = top_k_similar_users(
        matrix,
        user_id,
        k=n_similar_users,
        min_similarity=config.similarity_threshold,
    )

    seen = set(matrix[user_id])
    scores: dict[int, float] = {}

    for neighbour_id, similarity in (similar_users or []):
        for item_id, weight in matrix[neighbour_id].items():
            if item_id in seen:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + similarity * weight

    # Rank CF results first.
    cf_ranked = sorted(scores, key=lambda i: scores[i], reverse=True)[:n]
    cf_set = set(cf_ranked)

    # Cold-start fill: items with zero interactions from anyone, scored by
    # content similarity to the user's liked items. Always appended after CF
    # results so they can't be crowded out by the count limit.
    all_item_ids = {row[0] for row in db.query(Item.id).all()}
    interacted_items = {iid for user_items in matrix.values() for iid in user_items}
    cold_items = all_item_ids - interacted_items - seen - cf_set

    cold_scores: dict[int, float] = {}
    if cold_items:
        from features.item_features import get_feature_matrix
        feature_matrix = get_feature_matrix(db)
        for source_id in matrix[user_id]:
            for candidate_id, sim in feature_matrix.similarity_matrix.get(source_id, {}).items():
                if candidate_id in cold_items:
                    cold_scores[candidate_id] = cold_scores.get(candidate_id, 0.0) + sim * _COLD_ITEM_DISCOUNT

    cold_ranked = sorted(cold_scores, key=lambda i: cold_scores[i], reverse=True)

    result = [{"item_id": iid, "score": round(scores[iid], 4)} for iid in cf_ranked]
    result += [{"item_id": iid, "score": round(cold_scores[iid], 4)} for iid in cold_ranked]
    return result
