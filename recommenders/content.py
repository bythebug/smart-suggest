from sqlalchemy.orm import Session

from config import RECOMMENDATION_STRATEGIES
from features.item_features import get_feature_matrix
from models import UserInteraction
from tracking.interaction_tracker import ACTION_WEIGHTS


def get_content_recommendations(
    db: Session,
    user_id: int,
    n: int = 10,
) -> list[dict]:
    """
    Content-based filtering recommendations.

    Algorithm:
      1. Load the pre-computed item feature similarity matrix.
      2. Fetch the user's interaction history and accumulate weighted scores
         per item (view=1, click=3, purchase=5).
      3. For each liked item, look up its most similar items.
      4. Score each unseen candidate as:
             score(candidate) += item_similarity(source, candidate)
                                 × user_interaction_weight(source)
      5. Return the top-n candidates by score.

    Returns an empty list when the user has no interactions (cold start).
    Unlike CF, this still works for users who interacted with items that no
    other user has touched — a key advantage over collaborative filtering.
    """
    feature_matrix = get_feature_matrix(db)

    if not feature_matrix.similarity_matrix:
        return []

    interactions = (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == user_id)
        .all()
    )

    if not interactions:
        return []

    # Accumulate interaction weight per item (multiple actions on same item sum up).
    liked_items: dict[int, float] = {}
    for interaction in interactions:
        weight = ACTION_WEIGHTS.get(interaction.action, 1.0)
        liked_items[interaction.item_id] = (
            liked_items.get(interaction.item_id, 0.0) + weight
        )

    seen = set(liked_items)
    config = RECOMMENDATION_STRATEGIES["v2"]
    scores: dict[int, float] = {}

    for source_id, user_weight in liked_items.items():
        neighbours = feature_matrix.similarity_matrix.get(source_id, {})
        for candidate_id, item_sim in neighbours.items():
            if candidate_id in seen:
                continue
            if item_sim < config.similarity_threshold:
                continue
            scores[candidate_id] = (
                scores.get(candidate_id, 0.0) + item_sim * user_weight
            )

    ranked = sorted(scores, key=lambda i: scores[i], reverse=True)[:n]

    return [
        {"item_id": item_id, "score": round(scores[item_id], 4)}
        for item_id in ranked
    ]
