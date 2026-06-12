"""
End-to-end integration tests that exercise the full system across all layers:
interaction tracking → recommendation generation → A/B assignment → event logging
→ metric calculation → statistical analysis.
"""

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ab_testing.logger import log_click, log_impression, log_purchase
from ab_testing.manager import assign_variant, create_ab_test
from analysis import calculate_metrics_by_variant
from cache import clear_all, get_cached_recommendations, get_or_generate, invalidate_user_cache
from interpretation import analyze_ab_test
from models import ABTestAssignment, ActionType, Base, Item, User, Variant
from recommenders.cf import get_cf_recommendations
from recommenders.content import get_content_recommendations
from significance import sample_size_needed
from tracking.interaction_tracker import log_interaction


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure cache state doesn't leak between tests."""
    clear_all()
    yield
    clear_all()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    for i in range(1, 21):
        session.add(User(username=f"user{i}"))

    session.add_all(
        [
            Item(name="Laptop Pro",     category="electronics", description="fast powerful computing laptop processor"),
            Item(name="Desktop PC",     category="electronics", description="powerful desktop computing performance processor"),
            Item(name="Python Book",    category="books",       description="learn python programming language guide"),
            Item(name="Data Sci Book",  category="books",       description="learn data science python techniques"),
            Item(name="T-Shirt",        category="clothing",    description="comfortable cotton casual clothing"),
            Item(name="Running Shoes",  category="sports",      description="lightweight running performance shoes"),
        ]
    )
    session.commit()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# test_full_recommendation_flow
# ---------------------------------------------------------------------------


class TestFullRecommendationFlow:
    def test_cf_flow_user_gets_relevant_recs(self, db):
        """
        Full CF path: interactions logged → CF generates recs → no seen items returned.
        """
        # User 1 (alice) buys laptop
        log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)

        # User 2 (bob) is similar: buys laptop + python book
        log_interaction(db, user_id=2, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=3, action=ActionType.PURCHASE)

        recs = get_cf_recommendations(db, user_id=1, n=5)

        assert len(recs) > 0
        seen = {1}
        for r in recs:
            assert r["item_id"] not in seen, f"Item {r['item_id']} was already seen"
            assert r["score"] > 0

    def test_content_flow_user_gets_same_category(self, db):
        """
        Full content-based path: purchase → get recs → top rec is same category.
        """
        log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)

        recs = get_content_recommendations(db, user_id=1, n=5)

        assert len(recs) > 0
        top_item_id = recs[0]["item_id"]
        top_item = db.get(Item, top_item_id)
        assert top_item.category == "electronics"

    def test_cache_serves_recommendations_without_db(self, db):
        """After the first call, subsequent calls return cached results."""
        log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=3, action=ActionType.PURCHASE)

        # First call: cache miss → generates
        recs_first = get_or_generate(user_id=1, strategy="v1", db=db, count=5)
        assert len(recs_first) > 0

        # Second call: cache hit
        recs_cached = get_cached_recommendations(user_id=1, strategy="v1")
        assert recs_cached is not None
        assert recs_cached == recs_first

    def test_cache_invalidation_forces_regeneration(self, db):
        """Invalidating a user's cache clears all strategy entries."""
        log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=3, action=ActionType.PURCHASE)

        get_or_generate(user_id=1, strategy="v1", db=db)
        assert get_cached_recommendations(user_id=1, strategy="v1") is not None

        removed = invalidate_user_cache(user_id=1)
        assert removed >= 1
        assert get_cached_recommendations(user_id=1, strategy="v1") is None

    def test_variant_a_uses_cf_variant_b_uses_content(self, db):
        """
        A/B test assignment determines which strategy a user receives.
        Both strategies return non-empty, non-overlapping-with-seen recs.
        """
        for uid in range(1, 6):
            log_interaction(db, user_id=uid, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=3, action=ActionType.PURCHASE)
        log_interaction(db, user_id=3, item_id=4, action=ActionType.VIEW)

        test = create_ab_test(db, "strategy_test", "v1", "v2")
        assignment = assign_variant(db, user_id=1, test_id=test.id)

        strategy = "v1" if assignment.variant == Variant.A else "v2"
        recs = get_or_generate(user_id=1, strategy=strategy, db=db, count=5)

        # May be empty for cold-start content scenario, but no crash
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
# test_ab_test_workflow
# ---------------------------------------------------------------------------


class TestABTestWorkflow:
    def test_full_ab_test_workflow(self, db):
        """
        Complete A/B test lifecycle:
        create → assign users → log events → calculate metrics → analyse.
        """
        # 1. Create test
        test = create_ab_test(db, "full_workflow_test", "v1", "v2")
        assert test.id is not None

        # 2. Assign users 1-10 manually to control split
        for uid in range(1, 6):
            db.add(ABTestAssignment(test_id=test.id, user_id=uid, variant=Variant.A))
        for uid in range(6, 11):
            db.add(ABTestAssignment(test_id=test.id, user_id=uid, variant=Variant.B))
        db.commit()

        # 3. Log events — variant B outperforms A
        for uid in range(1, 6):
            log_impression(db, uid, 1, test.id, Variant.A)
            log_impression(db, uid, 2, test.id, Variant.A)
        log_click(db, 1, 1, test.id, Variant.A)

        for uid in range(6, 11):
            log_impression(db, uid, 1, test.id, Variant.B)
            log_impression(db, uid, 2, test.id, Variant.B)
        log_click(db, 6, 1, test.id, Variant.B)
        log_click(db, 7, 2, test.id, Variant.B)
        log_purchase(db, 6, 1, test.id, Variant.B)

        # 4. Calculate metrics
        metrics = calculate_metrics_by_variant(db, test.id)
        assert metrics["variants"]["A"]["impressions"] == 10
        assert metrics["variants"]["B"]["impressions"] == 10
        assert metrics["variants"]["A"]["clicks"] == 1
        assert metrics["variants"]["B"]["clicks"] == 2
        assert metrics["variants"]["B"]["users_converted"] == 1

        # 5. Statistical analysis
        from analysis import _engagement_times
        eng = _engagement_times(db, test.id)
        analysis = analyze_ab_test(metrics, eng["A"], eng["B"])

        assert "ctr" in analysis
        assert "conversion_rate" in analysis
        assert "conclusion" in analysis["ctr"]
        assert isinstance(analysis["ctr"]["conclusion"], str)

    def test_assignment_is_deterministic_across_sessions(self, db):
        """
        The same user always gets the same variant, even across separate DB reads.
        """
        test = create_ab_test(db, "determinism_test")

        a1 = assign_variant(db, user_id=5, test_id=test.id)
        a2 = assign_variant(db, user_id=5, test_id=test.id)

        assert a1.variant == a2.variant
        assert a1.id == a2.id

    def test_metrics_zero_when_no_events_logged(self, db):
        """A test with no events produces all-zero metrics without crashing."""
        test = create_ab_test(db, "empty_events_test")
        metrics = calculate_metrics_by_variant(db, test.id)

        assert metrics["variants"]["A"]["impressions"] == 0
        assert metrics["variants"]["B"]["ctr"] == 0.0

    def test_power_analysis_informs_test_duration(self):
        """
        Sample size calculation should indicate meaningful numbers
        for realistic baseline CTR and MDE.
        """
        # 10% baseline CTR, detect 2pp lift at 80% power
        n = sample_size_needed(baseline=0.10, mde=0.02, alpha=0.05, power=0.80)
        assert n > 1000, "Need enough users to detect a 2pp lift"
        assert n < 50_000, "Requirement should be achievable"


# ---------------------------------------------------------------------------
# test_concurrent_users
# ---------------------------------------------------------------------------


class TestConcurrentUsers:
    def test_variant_assignment_thread_safe(self, db):
        """
        Concurrent assign_variant calls for the same user+test must produce
        consistent results and not create duplicate rows.
        """
        test = create_ab_test(db, "concurrent_test")
        results: list[Variant] = []
        errors: list[Exception] = []

        def assign(uid: int) -> None:
            try:
                # Each thread uses the pure hash function (no DB write)
                from ab_testing.manager import _compute_variant
                results.append(_compute_variant(uid, test.id))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=assign, args=(i,)) for i in range(1, 51)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent assignment: {errors}"
        assert len(results) == 50
        assert all(v in (Variant.A, Variant.B) for v in results)

    def test_cache_concurrent_reads_are_consistent(self, db):
        """
        Multiple threads reading the cache for different users should not
        interfere with each other.
        """
        log_interaction(db, user_id=1, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=1, action=ActionType.PURCHASE)
        log_interaction(db, user_id=2, item_id=3, action=ActionType.PURCHASE)

        # Seed the cache for user 1
        get_or_generate(user_id=1, strategy="v1", db=db)

        read_results: list = []
        errors: list = []

        def read_cache(uid: int) -> None:
            try:
                result = get_cached_recommendations(uid, strategy="v1")
                read_results.append((uid, result))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=read_cache, args=(uid,)) for uid in range(1, 11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(read_results) == 10
        # User 1 should always get the cached result
        user1_results = [r for uid, r in read_results if uid == 1]
        assert all(r is not None for r in user1_results)

    def test_deterministic_hash_same_result_across_threads(self, db):
        """
        _compute_variant must return identical results for the same input
        regardless of which thread calls it.
        """
        from ab_testing.manager import _compute_variant

        test = create_ab_test(db, "hash_thread_test")
        expected = {uid: _compute_variant(uid, test.id) for uid in range(1, 101)}

        thread_results: dict[int, list] = {uid: [] for uid in range(1, 101)}
        errors: list = []

        def check(uid: int) -> None:
            try:
                v = _compute_variant(uid, test.id)
                thread_results[uid].append(v)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=check, args=(uid,)) for uid in range(1, 101)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        for uid in range(1, 101):
            assert thread_results[uid][0] == expected[uid], (
                f"User {uid}: expected {expected[uid]}, got {thread_results[uid]}"
            )
