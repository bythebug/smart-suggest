import hashlib

from sqlalchemy.orm import Session

from models import ABTest, ABTestAssignment, TestStatus, Variant


# ---------------------------------------------------------------------------
# Deterministic variant assignment
# ---------------------------------------------------------------------------


def _compute_variant(user_id: int, test_id: int) -> Variant:
    """
    Assign a variant using a stable MD5 hash of "{test_id}:{user_id}".

    Why MD5 over Python's built-in hash():
      Python's hash() is randomised per-process via PYTHONHASHSEED.
      Running the same assignment on two different servers (or after a restart)
      would yield different variants, breaking consistency for the same user.
      MD5 is deterministic across all environments.

    Why include test_id in the key:
      Without it, a user assigned to variant A in test 1 would always land in
      variant A in every test, making experiments correlated. Salting with
      test_id ensures each test's assignment is independent.
    """
    key = f"{test_id}:{user_id}".encode()
    digest = int(hashlib.md5(key).hexdigest(), 16)
    return Variant.A if digest % 2 == 0 else Variant.B


# ---------------------------------------------------------------------------
# Test lifecycle
# ---------------------------------------------------------------------------


def create_ab_test(
    db: Session,
    name: str,
    control_variant: str = "v1",
    treatment_variant: str = "v2",
) -> ABTest:
    """
    Create a new active A/B test.

    control_variant and treatment_variant are free-form labels that record
    which recommendation strategy each bucket runs (e.g. "v1", "v2").
    They do not affect assignment logic.
    """
    test = ABTest(
        name=name,
        status=TestStatus.ACTIVE,
        control_strategy=control_variant,
        treatment_strategy=treatment_variant,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


# ---------------------------------------------------------------------------
# User assignment
# ---------------------------------------------------------------------------


def assign_variant(db: Session, user_id: int, test_id: int) -> ABTestAssignment:
    """
    Assign a user to a variant for the given test.

    Idempotent — returns the existing assignment if one already exists.
    The UNIQUE constraint on (test_id, user_id) in the DB enforces this
    at the storage level as well.
    """
    existing = (
        db.query(ABTestAssignment)
        .filter_by(test_id=test_id, user_id=user_id)
        .first()
    )
    if existing:
        return existing

    assignment = ABTestAssignment(
        test_id=test_id,
        user_id=user_id,
        variant=_compute_variant(user_id, test_id),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_variant(db: Session, user_id: int, test_id: int) -> Variant | None:
    """Return the user's assigned variant, or None if not yet assigned."""
    assignment = (
        db.query(ABTestAssignment)
        .filter_by(test_id=test_id, user_id=user_id)
        .first()
    )
    return assignment.variant if assignment else None
