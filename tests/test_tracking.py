import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tracking.interaction_tracker import (
    get_item_popularity,
    get_user_history,
    get_user_profile,
    log_interaction,
)
from models import ActionType, Base, Item, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add_all(
        [
            User(username="alice"),
            User(username="bob"),
            Item(name="Laptop", category="electronics", description="Fast laptop"),
            Item(name="T-Shirt", category="clothing", description="Cotton tee"),
            Item(name="Python Book", category="books", description="Learn Python"),
        ]
    )
    session.commit()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# log_interaction
# ---------------------------------------------------------------------------


def test_log_interaction_persists_record(db):
    interaction = log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)

    assert interaction.id is not None
    assert interaction.user_id == 1
    assert interaction.item_id == 1
    assert interaction.action == ActionType.VIEW
    assert interaction.timestamp is not None


def test_log_interaction_all_action_types(db):
    for action in ActionType:
        result = log_interaction(db, user_id=1, item_id=1, action=action)
        assert result.action == action


def test_log_multiple_interactions_same_item(db):
    log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=1, item_id=1, action=ActionType.CLICK)
    log_interaction(db, user_id=2, item_id=1, action=ActionType.PURCHASE)

    history_alice = get_user_history(db, user_id=1)
    assert len(history_alice) == 2


# ---------------------------------------------------------------------------
# get_user_history
# ---------------------------------------------------------------------------


def test_history_retrieval_returns_most_recent_first(db):
    log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=1, item_id=2, action=ActionType.CLICK)
    log_interaction(db, user_id=1, item_id=3, action=ActionType.PURCHASE)

    history = get_user_history(db, user_id=1)

    assert len(history) == 3
    assert history[0].action == ActionType.PURCHASE  # most recent
    assert history[-1].action == ActionType.VIEW     # oldest


def test_history_retrieval_is_user_scoped(db):
    log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=2, item_id=1, action=ActionType.CLICK)

    alice_history = get_user_history(db, user_id=1)
    bob_history = get_user_history(db, user_id=2)

    assert len(alice_history) == 1
    assert len(bob_history) == 1
    assert alice_history[0].action == ActionType.VIEW
    assert bob_history[0].action == ActionType.CLICK


def test_history_retrieval_empty_for_new_user(db):
    assert get_user_history(db, user_id=999) == []


def test_history_retrieval_respects_limit(db):
    for _ in range(10):
        log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)

    assert len(get_user_history(db, user_id=1, limit=5)) == 5


# ---------------------------------------------------------------------------
# get_item_popularity
# ---------------------------------------------------------------------------


def test_popularity_calculation_counts_by_action(db):
    log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=2, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=1, item_id=1, action=ActionType.CLICK)

    stats = get_item_popularity(db, item_id=1)

    assert stats["view"] == 2
    assert stats["click"] == 1
    assert stats["purchase"] == 0
    assert stats["total"] == 3


def test_popularity_calculation_zero_counts_for_new_item(db):
    stats = get_item_popularity(db, item_id=3)

    assert stats["total"] == 0
    assert all(stats[a.value] == 0 for a in ActionType)


def test_popularity_calculation_purchase_counted_separately(db):
    log_interaction(db, user_id=1, item_id=2, action=ActionType.PURCHASE)

    stats = get_item_popularity(db, item_id=2)

    assert stats["purchase"] == 1
    assert stats["view"] == 0
    assert stats["click"] == 0
    assert stats["total"] == 1


# ---------------------------------------------------------------------------
# get_user_profile
# ---------------------------------------------------------------------------


def test_user_profile_preferred_categories_weighted(db):
    # One purchase on electronics (weight 5) vs two views on clothing (weight 1 each = 2)
    log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)  # electronics
    log_interaction(db, user_id=1, item_id=2, action=ActionType.VIEW)      # clothing
    log_interaction(db, user_id=1, item_id=2, action=ActionType.VIEW)      # clothing

    profile = get_user_profile(db, user_id=1)

    assert profile["preferred_categories"][0] == "electronics"


def test_user_profile_top_items_ordered(db):
    log_interaction(db, user_id=1, item_id=2, action=ActionType.VIEW)
    log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)  # highest weight

    profile = get_user_profile(db, user_id=1)

    assert profile["top_item_ids"][0] == 1


def test_user_profile_action_breakdown(db):
    log_interaction(db, user_id=1, item_id=1, action=ActionType.VIEW)
    log_interaction(db, user_id=1, item_id=1, action=ActionType.CLICK)
    log_interaction(db, user_id=1, item_id=2, action=ActionType.PURCHASE)

    profile = get_user_profile(db, user_id=1)

    assert profile["action_breakdown"]["view"] == 1
    assert profile["action_breakdown"]["click"] == 1
    assert profile["action_breakdown"]["purchase"] == 1
    assert profile["total_interactions"] == 3


def test_user_profile_empty_for_new_user(db):
    profile = get_user_profile(db, user_id=999)

    assert profile["total_interactions"] == 0
    assert profile["preferred_categories"] == []
    assert profile["top_item_ids"] == []
