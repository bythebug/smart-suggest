from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import ActionType, Item, UserInteraction

# Weighted importance of each action type when building a user profile.
ACTION_WEIGHTS: dict[ActionType, int] = {
    ActionType.VIEW: 1,
    ActionType.CLICK: 3,
    ActionType.PURCHASE: 5,
}


def log_interaction(
    db: Session,
    user_id: int,
    item_id: int,
    action: ActionType,
) -> UserInteraction:
    interaction = UserInteraction(user_id=user_id, item_id=item_id, action=action)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def get_user_history(
    db: Session,
    user_id: int,
    limit: int = 100,
) -> list[UserInteraction]:
    return (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_item_popularity(db: Session, item_id: int) -> dict[str, int]:
    """Return per-action counts and a total for the given item."""
    rows = (
        db.query(UserInteraction.action, func.count().label("n"))
        .filter(UserInteraction.item_id == item_id)
        .group_by(UserInteraction.action)
        .all()
    )
    counts: dict[str, int] = {a.value: 0 for a in ActionType}
    for action, n in rows:
        counts[action.value] = n
    counts["total"] = sum(counts[a.value] for a in ActionType)
    return counts


def get_user_profile(db: Session, user_id: int) -> dict[str, Any]:
    """
    Aggregate a user's interaction history into a behavioural profile.

    Categories and items are ranked by a weighted sum of interactions
    (view=1, click=3, purchase=5) so that high-intent signals dominate.
    """
    rows = (
        db.query(UserInteraction, Item)
        .join(Item, UserInteraction.item_id == Item.id)
        .filter(UserInteraction.user_id == user_id)
        .all()
    )

    category_scores: dict[str, float] = {}
    item_scores: dict[int, float] = {}
    action_counts: dict[str, int] = {a.value: 0 for a in ActionType}

    for interaction, item in rows:
        weight = ACTION_WEIGHTS.get(interaction.action, 1)
        category_scores[item.category] = category_scores.get(item.category, 0) + weight
        item_scores[item.id] = item_scores.get(item.id, 0) + weight
        action_counts[interaction.action.value] += 1

    return {
        "user_id": user_id,
        "total_interactions": len(rows),
        "action_breakdown": action_counts,
        "preferred_categories": sorted(
            category_scores, key=lambda c: category_scores[c], reverse=True
        ),
        "top_item_ids": sorted(item_scores, key=lambda i: item_scores[i], reverse=True)[
            :10
        ],
    }
