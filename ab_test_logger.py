from sqlalchemy.orm import Session

from models import ABTestEvent, EventType, Variant


def _log_event(
    db: Session,
    user_id: int,
    item_id: int,
    event_type: EventType,
    test_id: int | None = None,
    variant: Variant | None = None,
    value: float | None = None,
) -> ABTestEvent:
    event = ABTestEvent(
        user_id=user_id,
        item_id=item_id,
        test_id=test_id,
        variant=variant,
        event_type=event_type,
        value=value,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def log_impression(
    db: Session,
    user_id: int,
    item_id: int,
    test_id: int,
    variant: Variant,
) -> ABTestEvent:
    """Record that a recommended item was shown to a user in a given variant."""
    return _log_event(db, user_id, item_id, EventType.IMPRESSION, test_id, variant)


def log_click(
    db: Session,
    user_id: int,
    item_id: int,
    test_id: int,
    variant: Variant,
) -> ABTestEvent:
    """Record that a user clicked a recommended item."""
    return _log_event(db, user_id, item_id, EventType.CLICK, test_id, variant)


def log_purchase(
    db: Session,
    user_id: int,
    item_id: int,
    test_id: int,
    variant: Variant,
) -> ABTestEvent:
    """Record that a user purchased a recommended item."""
    return _log_event(db, user_id, item_id, EventType.PURCHASE, test_id, variant)


def log_engagement_time(
    db: Session,
    user_id: int,
    item_id: int,
    time_seconds: float,
) -> ABTestEvent:
    """
    Record how long a user spent on an item's page.

    Not tied to a specific test at logging time — test attribution happens
    at analysis time by joining through ab_test_assignments on (user_id, test_id).
    """
    return _log_event(
        db, user_id, item_id, EventType.ENGAGEMENT_TIME, value=time_seconds
    )
