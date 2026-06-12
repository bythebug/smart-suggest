from sqlalchemy.orm import Session

from config import RECOMMENDATION_STRATEGIES
from models import ActionType, UserInteraction
from .similarity import top_k_similar_users

# Higher-intent actions contribute more weight to the interaction matrix.
ACTION_WEIGHTS: dict[ActionType, float] = {
    ActionType.VIEW: 1.0,
    ActionType.CLICK: 3.0,
    ActionType.PURCHASE: 5.0,
}


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------


def build_user_item_matrix(db: Session) -> dict[int, dict[int, float]]:
    """
    Fetch all interactions from the DB and return a weighted user-item matrix:
      { user_id: { item_id: weighted_score, ... }, ... }

    A user who views and then purchases the same item accumulates both weights,
    reflecting increasing intent (1 + 5 = 6 for that item).
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
      3. Collect items those neighbours liked that the target user hasn't seen.
      4. Score each candidate by summing (similarity × neighbour_weight) across
         all neighbours who interacted with it.
      5. Return the top-n items ranked by score.

    Returns an empty list when the user has no interaction history (cold start).
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

    if not similar_users:
        return []

    seen = set(matrix[user_id])
    scores: dict[int, float] = {}

    for neighbour_id, similarity in similar_users:
        for item_id, weight in matrix[neighbour_id].items():
            if item_id in seen:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + similarity * weight

    ranked = sorted(scores, key=lambda i: scores[i], reverse=True)[:n]

    return [
        {"item_id": item_id, "score": round(scores[item_id], 4)}
        for item_id in ranked
    ]
