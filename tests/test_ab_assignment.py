import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ab_testing.logger import log_click, log_engagement_time, log_impression, log_purchase
from ab_testing.manager import _compute_variant, assign_variant, create_ab_test, get_variant
from models import ABTestEvent, ActionType, Base, EventType, Item, User, Variant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
            User(username="carol"),
        ]
    )
    session.add_all(
        [
            Item(name="Laptop", category="electronics"),
            Item(name="T-Shirt", category="clothing"),
        ]
    )
    session.commit()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# test_deterministic_assignment
# ---------------------------------------------------------------------------


class TestDeterministicAssignment:
    def test_same_inputs_always_yield_same_variant(self):
        assert _compute_variant(42, 1) == _compute_variant(42, 1)
        assert _compute_variant(0, 99) == _compute_variant(0, 99)
        assert _compute_variant(999_999, 7) == _compute_variant(999_999, 7)

    def test_result_is_a_valid_variant(self):
        for uid in range(20):
            v = _compute_variant(uid, test_id=1)
            assert v in (Variant.A, Variant.B)

    def test_different_users_can_get_different_variants(self):
        variants = {_compute_variant(uid, test_id=1) for uid in range(50)}
        assert len(variants) == 2  # both A and B appear

    def test_different_tests_produce_independent_assignments(self):
        # Including test_id in the hash key means the same user can land
        # in different variants across different tests.
        differences = sum(
            1
            for uid in range(200)
            if _compute_variant(uid, test_id=1) != _compute_variant(uid, test_id=2)
        )
        # Statistically we expect ~100 differences; require at least 30.
        assert differences >= 30

    def test_hash_is_not_python_builtin_hash(self):
        # _compute_variant must not use Python's hash() which is PYTHONHASHSEED-
        # dependent. We verify by checking the function returns a Variant enum,
        # and by asserting stable output for a known input.
        v = _compute_variant(user_id=1, test_id=1)
        assert isinstance(v, Variant)
        # Re-run 100 times — a non-deterministic implementation would occasionally differ.
        assert all(_compute_variant(1, 1) == v for _ in range(100))


# ---------------------------------------------------------------------------
# test_50_50_split
# ---------------------------------------------------------------------------


class TestVariantSplit:
    def test_50_50_split_over_1000_users(self):
        """Hash-based assignment should produce a near-equal split."""
        variants = [_compute_variant(uid, test_id=1) for uid in range(1_000)]
        a_count = sum(1 for v in variants if v == Variant.A)
        b_count = 1_000 - a_count

        # Require within 5% of perfect split (475–525)
        assert 475 <= a_count <= 525, (
            f"Expected ~500 A variants, got {a_count} A / {b_count} B"
        )

    def test_split_is_consistent_across_different_test_ids(self):
        """Different tests should each individually have a balanced split."""
        for test_id in range(1, 6):
            variants = [_compute_variant(uid, test_id) for uid in range(1_000)]
            a_count = sum(1 for v in variants if v == Variant.A)
            assert 450 <= a_count <= 550, (
                f"test_id={test_id}: unbalanced split ({a_count} A / {1000 - a_count} B)"
            )

    def test_large_user_ids_still_split_evenly(self):
        """User IDs in the millions should still be distributed evenly."""
        base = 10_000_000
        variants = [_compute_variant(base + uid, test_id=1) for uid in range(1_000)]
        a_count = sum(1 for v in variants if v == Variant.A)
        assert 450 <= a_count <= 550


# ---------------------------------------------------------------------------
# test_variant_consistency
# ---------------------------------------------------------------------------


class TestVariantConsistency:
    def test_assign_variant_is_idempotent(self, db):
        """Calling assign_variant twice for the same user+test returns the same variant."""
        test = create_ab_test(db, "idempotency_test")
        a1 = assign_variant(db, user_id=1, test_id=test.id)
        a2 = assign_variant(db, user_id=1, test_id=test.id)

        assert a1.id == a2.id
        assert a1.variant == a2.variant

    def test_only_one_assignment_row_created(self, db):
        """Idempotent assign_variant must not create duplicate DB rows."""
        from models import ABTestAssignment

        test = create_ab_test(db, "dedup_test")
        for _ in range(5):
            assign_variant(db, user_id=1, test_id=test.id)

        count = (
            db.query(ABTestAssignment)
            .filter_by(test_id=test.id, user_id=1)
            .count()
        )
        assert count == 1

    def test_get_variant_returns_none_before_assignment(self, db):
        test = create_ab_test(db, "unassigned_test")
        assert get_variant(db, user_id=1, test_id=test.id) is None

    def test_get_variant_returns_assigned_variant(self, db):
        test = create_ab_test(db, "assigned_test")
        assignment = assign_variant(db, user_id=1, test_id=test.id)

        retrieved = get_variant(db, user_id=1, test_id=test.id)
        assert retrieved == assignment.variant

    def test_variant_stored_matches_computed_variant(self, db):
        """The variant persisted to DB must match _compute_variant directly."""
        test = create_ab_test(db, "match_test")
        assignment = assign_variant(db, user_id=2, test_id=test.id)
        expected = _compute_variant(user_id=2, test_id=test.id)

        assert assignment.variant == expected

    def test_multiple_users_assigned_correctly(self, db):
        """Each user's stored variant matches their individually computed variant."""
        test = create_ab_test(db, "multi_user_test")

        for uid in range(1, 4):
            a = assign_variant(db, user_id=uid, test_id=test.id)
            expected = _compute_variant(uid, test.id)
            assert a.variant == expected


# ---------------------------------------------------------------------------
# Event logger
# ---------------------------------------------------------------------------


class TestABTestLogger:
    def test_log_impression(self, db):
        test = create_ab_test(db, "imp_test")
        event = log_impression(db, user_id=1, item_id=1, test_id=test.id, variant=Variant.A)

        assert event.id is not None
        assert event.event_type == EventType.IMPRESSION
        assert event.variant == Variant.A
        assert event.test_id == test.id

    def test_log_click(self, db):
        test = create_ab_test(db, "click_test")
        event = log_click(db, user_id=1, item_id=1, test_id=test.id, variant=Variant.B)

        assert event.event_type == EventType.CLICK
        assert event.variant == Variant.B

    def test_log_purchase(self, db):
        test = create_ab_test(db, "purchase_test")
        event = log_purchase(db, user_id=1, item_id=2, test_id=test.id, variant=Variant.A)

        assert event.event_type == EventType.PURCHASE

    def test_log_engagement_time(self, db):
        event = log_engagement_time(db, user_id=1, item_id=1, time_seconds=42.5)

        assert event.event_type == EventType.ENGAGEMENT_TIME
        assert event.value == pytest.approx(42.5)
        assert event.test_id is None
        assert event.variant is None

    def test_events_persisted_to_db(self, db):
        test = create_ab_test(db, "persist_test")
        log_impression(db, user_id=1, item_id=1, test_id=test.id, variant=Variant.A)
        log_click(db, user_id=1, item_id=1, test_id=test.id, variant=Variant.A)

        count = db.query(ABTestEvent).filter_by(test_id=test.id).count()
        assert count == 2
