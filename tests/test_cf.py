import math

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cf_recommender import build_user_item_matrix, get_cf_recommendations
from models import ActionType, Base, Item, User, UserInteraction
from similarity import cosine_similarity, pearson_correlation, top_k_similar_users


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Users: alice=1, bob=2, carol=3, dave=4 (new user, no interactions)
    session.add_all(
        [
            User(username="alice"),
            User(username="bob"),
            User(username="carol"),
            User(username="dave"),
        ]
    )
    # Items 1-6
    session.add_all(
        [
            Item(name="Laptop", category="electronics"),
            Item(name="Phone", category="electronics"),
            Item(name="T-Shirt", category="clothing"),
            Item(name="Jeans", category="clothing"),
            Item(name="Python Book", category="books"),
            Item(name="Novel", category="books"),
        ]
    )
    session.commit()
    yield session
    session.close()


def _add_interactions(session, interactions: list[tuple[int, int, ActionType]]) -> None:
    session.add_all(
        [
            UserInteraction(user_id=uid, item_id=iid, action=action)
            for uid, iid, action in interactions
        ]
    )
    session.commit()


# ---------------------------------------------------------------------------
# test_similarity_calculation
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        v = {1: 1.0, 2: 2.0, 3: 3.0}
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        # No shared keys → dot product is 0
        assert cosine_similarity({1: 1.0}, {2: 1.0}) == pytest.approx(0.0)

    def test_partial_overlap(self):
        v1 = {1: 1.0, 2: 1.0}
        v2 = {1: 1.0, 3: 1.0}
        # dot=1, |v1|=√2, |v2|=√2 → 1/2 = 0.5
        assert cosine_similarity(v1, v2) == pytest.approx(0.5)

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity({1: 0.0}, {1: 1.0}) == pytest.approx(0.0)

    def test_empty_vectors_return_zero(self):
        assert cosine_similarity({}, {}) == pytest.approx(0.0)

    def test_proportional_vectors_return_one(self):
        v1 = {1: 1.0, 2: 2.0}
        v2 = {1: 3.0, 2: 6.0}
        assert cosine_similarity(v1, v2) == pytest.approx(1.0)


class TestPearsonCorrelation:
    def test_perfect_positive_correlation(self):
        r1 = {1: 1.0, 2: 2.0, 3: 3.0}
        r2 = {1: 2.0, 2: 4.0, 3: 6.0}
        assert pearson_correlation(r1, r2) == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        r1 = {1: 1.0, 2: 2.0, 3: 3.0}
        r2 = {1: 3.0, 2: 2.0, 3: 1.0}
        assert pearson_correlation(r1, r2) == pytest.approx(-1.0)

    def test_no_common_items_returns_zero(self):
        assert pearson_correlation({1: 5.0}, {2: 5.0}) == pytest.approx(0.0)

    def test_fewer_than_two_common_items_returns_zero(self):
        # Only one shared key → correlation undefined
        assert pearson_correlation({1: 5.0}, {1: 3.0}) == pytest.approx(0.0)

    def test_constant_vector_returns_zero(self):
        # Variance = 0 in one vector → undefined, returns 0
        r1 = {1: 3.0, 2: 3.0, 3: 3.0}
        r2 = {1: 1.0, 2: 2.0, 3: 3.0}
        assert pearson_correlation(r1, r2) == pytest.approx(0.0)


class TestTopKSimilarUsers:
    def test_returns_correct_k(self):
        vectors = {
            1: {1: 1.0, 2: 1.0},
            2: {1: 1.0, 2: 1.0},
            3: {1: 1.0, 2: 0.0},
            4: {3: 1.0},
        }
        result = top_k_similar_users(vectors, target_user_id=1, k=2)
        assert len(result) == 2

    def test_excludes_target_user(self):
        vectors = {1: {1: 1.0}, 2: {1: 1.0}}
        result = top_k_similar_users(vectors, target_user_id=1, k=10)
        user_ids = [uid for uid, _ in result]
        assert 1 not in user_ids

    def test_respects_min_similarity(self):
        vectors = {
            1: {1: 1.0, 2: 1.0},
            2: {1: 1.0, 2: 1.0},   # sim = 1.0
            3: {3: 1.0},            # sim = 0.0
        }
        result = top_k_similar_users(vectors, target_user_id=1, k=10, min_similarity=0.5)
        assert all(sim >= 0.5 for _, sim in result)

    def test_unknown_user_returns_empty(self):
        assert top_k_similar_users({1: {1: 1.0}}, target_user_id=99, k=5) == []

    def test_sorted_descending(self):
        vectors = {
            1: {1: 1.0, 2: 1.0},
            2: {1: 1.0, 2: 1.0},   # sim = 1.0
            3: {1: 1.0},            # sim = 1/√2 ≈ 0.707
        }
        result = top_k_similar_users(vectors, target_user_id=1, k=10)
        sims = [sim for _, sim in result]
        assert sims == sorted(sims, reverse=True)


# ---------------------------------------------------------------------------
# test_recommendation_generation
# ---------------------------------------------------------------------------


class TestRecommendationGeneration:
    def test_returns_unseen_items_only(self, db):
        # Alice has seen items 1, 2. Bob (similar) has seen 1, 2, 3.
        _add_interactions(
            db,
            [
                (1, 1, ActionType.PURCHASE),  # alice
                (1, 2, ActionType.PURCHASE),  # alice
                (2, 1, ActionType.PURCHASE),  # bob — makes bob similar to alice
                (2, 2, ActionType.PURCHASE),  # bob
                (2, 3, ActionType.PURCHASE),  # bob — alice hasn't seen this
            ],
        )
        recs = get_cf_recommendations(db, user_id=1, n=5)
        item_ids = [r["item_id"] for r in recs]

        assert 3 in item_ids          # item bob has that alice hasn't seen
        assert 1 not in item_ids      # alice already saw item 1
        assert 2 not in item_ids      # alice already saw item 2

    def test_higher_similarity_scores_higher(self, db):
        # Alice and Bob both bought items 1+2+3 (highly similar).
        # Alice and Carol only share item 1 (less similar).
        # Bob has item 4, Carol has item 5.
        # Item 4 (from more-similar Bob) should outscore item 5.
        _add_interactions(
            db,
            [
                (1, 1, ActionType.PURCHASE),
                (1, 2, ActionType.PURCHASE),
                (1, 3, ActionType.PURCHASE),
                (2, 1, ActionType.PURCHASE),  # bob — shares 1,2,3 with alice
                (2, 2, ActionType.PURCHASE),
                (2, 3, ActionType.PURCHASE),
                (2, 4, ActionType.PURCHASE),  # only bob has item 4
                (3, 1, ActionType.VIEW),       # carol — shares only item 1 with alice
                (3, 5, ActionType.PURCHASE),  # only carol has item 5
            ],
        )
        recs = get_cf_recommendations(db, user_id=1, n=10)
        item_ids = [r["item_id"] for r in recs]

        assert item_ids.index(4) < item_ids.index(5)

    def test_respects_count_parameter(self, db):
        _add_interactions(
            db,
            [
                (1, 1, ActionType.PURCHASE),
                (2, 1, ActionType.PURCHASE),
                (2, 2, ActionType.PURCHASE),
                (2, 3, ActionType.PURCHASE),
                (2, 4, ActionType.PURCHASE),
            ],
        )
        recs = get_cf_recommendations(db, user_id=1, n=2)
        assert len(recs) <= 2

    def test_scores_are_positive(self, db):
        _add_interactions(
            db,
            [
                (1, 1, ActionType.VIEW),
                (2, 1, ActionType.VIEW),
                (2, 2, ActionType.PURCHASE),
            ],
        )
        recs = get_cf_recommendations(db, user_id=1)
        assert all(r["score"] > 0 for r in recs)

    def test_results_sorted_descending_by_score(self, db):
        _add_interactions(
            db,
            [
                (1, 1, ActionType.PURCHASE),
                (2, 1, ActionType.PURCHASE),
                (2, 2, ActionType.PURCHASE),
                (2, 3, ActionType.VIEW),
            ],
        )
        recs = get_cf_recommendations(db, user_id=1, n=10)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# test_no_cold_start_fallback
# ---------------------------------------------------------------------------


class TestColdStart:
    def test_new_user_returns_empty_list(self, db):
        # dave (user_id=4) has no interactions
        recs = get_cf_recommendations(db, user_id=4)
        assert recs == []

    def test_nonexistent_user_returns_empty_list(self, db):
        recs = get_cf_recommendations(db, user_id=9999)
        assert recs == []

    def test_user_with_no_similar_neighbours_returns_empty(self, db):
        # Alice only interacted with item 1. Bob only interacted with item 2.
        # They share nothing → cosine similarity = 0 → no neighbours above threshold.
        _add_interactions(
            db,
            [
                (1, 1, ActionType.VIEW),
                (2, 2, ActionType.VIEW),
            ],
        )
        recs = get_cf_recommendations(db, user_id=1, n=5)
        assert recs == []

    def test_matrix_is_empty_returns_empty(self, db):
        # No interactions at all in the DB
        recs = get_cf_recommendations(db, user_id=1, n=5)
        assert recs == []
