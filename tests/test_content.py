import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from recommenders.content import get_content_recommendations
from features.item_features import (
    ItemFeatureMatrix,
    build_feature_vectors,
    build_item_feature_matrix,
    compute_similarity_matrix,
    compute_tfidf,
)
from models import ActionType, Base, Item, User, UserInteraction


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
        ]
    )
    # Electronics cluster: items 1, 2 share category + overlapping description words.
    # Books cluster: items 3, 4 share category + overlapping description words.
    # Item 5: clothing — isolated category.
    session.add_all(
        [
            Item(
                name="Laptop Pro",
                category="electronics",
                description="fast processor powerful performance computing laptop",
            ),
            Item(
                name="Desktop PC",
                category="electronics",
                description="powerful desktop computing performance processor",
            ),
            Item(
                name="Python Book",
                category="books",
                description="learn python programming language beginner guide",
            ),
            Item(
                name="Data Science Book",
                category="books",
                description="learn data science python programming techniques",
            ),
            Item(
                name="T-Shirt",
                category="clothing",
                description="comfortable cotton casual wear",
            ),
        ]
    )
    session.commit()
    yield session
    session.close()


def _interact(session, user_id: int, item_id: int, action: ActionType) -> None:
    session.add(UserInteraction(user_id=user_id, item_id=item_id, action=action))
    session.commit()


# ---------------------------------------------------------------------------
# test_item_similarity
# ---------------------------------------------------------------------------


class TestTFIDF:
    def test_same_document_has_max_similarity(self):
        docs = {1: "fast processor laptop", 2: "fast processor laptop"}
        vectors = compute_tfidf(docs)
        from recommenders.similarity import cosine_similarity
        sim = cosine_similarity(vectors[1], vectors[2])  # type: ignore[arg-type]
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_disjoint_documents_have_zero_similarity(self):
        docs = {1: "apple orange banana", 2: "rocket engine thrust"}
        vectors = compute_tfidf(docs)
        from recommenders.similarity import cosine_similarity
        sim = cosine_similarity(vectors[1], vectors[2])  # type: ignore[arg-type]
        assert sim == pytest.approx(0.0)

    def test_empty_description_produces_empty_vector(self):
        docs = {1: ""}
        vectors = compute_tfidf(docs)
        assert vectors[1] == {}

    def test_repeated_term_has_higher_tf(self):
        docs = {1: "fast fast fast computer", 2: "fast computer"}
        vectors = compute_tfidf(docs)
        # In doc 1, TF("fast") = 3/4 = 0.75; in doc 2, TF("fast") = 1/2 = 0.5
        assert vectors[1]["fast"] > vectors[2]["fast"]


class TestItemSimilarity:
    def test_same_category_items_are_more_similar_than_cross_category(self, db):
        matrix = build_item_feature_matrix(db)
        # laptop(1) vs desktop(2): same category, overlapping description
        electronics_sim = matrix.similarity_matrix[1].get(2, 0.0)
        # laptop(1) vs t-shirt(5): different category, no description overlap
        cross_sim = matrix.similarity_matrix[1].get(5, 0.0)
        assert electronics_sim > cross_sim

    def test_items_with_overlapping_descriptions_score_higher(self, db):
        matrix = build_item_feature_matrix(db)
        # python book(3) and data science book(4) both mention "python", "learn"
        books_sim = matrix.similarity_matrix[3].get(4, 0.0)
        # python book(3) vs laptop(1): no text overlap, different category
        cross_sim = matrix.similarity_matrix[3].get(1, 0.0)
        assert books_sim > cross_sim

    def test_similarity_matrix_is_symmetric(self, db):
        matrix = build_item_feature_matrix(db)
        sim_ab = matrix.similarity_matrix[1].get(2, 0.0)
        sim_ba = matrix.similarity_matrix[2].get(1, 0.0)
        assert sim_ab == pytest.approx(sim_ba)

    def test_similarity_values_between_zero_and_one(self, db):
        matrix = build_item_feature_matrix(db)
        for _, neighbours in matrix.similarity_matrix.items():
            for _, sim in neighbours.items():
                assert 0.0 <= sim <= 1.0 + 1e-9

    def test_empty_db_returns_empty_matrix(self, db):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        empty_session = sessionmaker(bind=engine)()
        matrix = build_item_feature_matrix(empty_session)
        assert matrix.feature_vectors == {}
        assert matrix.similarity_matrix == {}
        empty_session.close()

    def test_category_prefix_prevents_key_collision(self, db):
        items = db.query(Item).all()
        vectors = build_feature_vectors(items)
        for vec in vectors.values():
            cat_keys = [k for k in vec if k.startswith("__cat_")]
            assert len(cat_keys) == 1


# ---------------------------------------------------------------------------
# test_recommendation_generation
# ---------------------------------------------------------------------------


class TestRecommendationGeneration:
    def test_returns_unseen_items_only(self, db):
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)

        recs = get_content_recommendations(db, user_id=1, n=10)
        seen_ids = {1}
        for rec in recs:
            assert rec["item_id"] not in seen_ids

    def test_similar_category_items_appear_in_results(self, db):
        # Alice buys the laptop (electronics); desktop PC should be recommended.
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)

        recs = get_content_recommendations(db, user_id=1, n=10)
        item_ids = [r["item_id"] for r in recs]
        assert 2 in item_ids  # Desktop PC (also electronics)

    def test_respects_count_parameter(self, db):
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)

        recs = get_content_recommendations(db, user_id=1, n=1)
        assert len(recs) <= 1

    def test_results_sorted_descending_by_score(self, db):
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)
        _interact(db, user_id=1, item_id=2, action=ActionType.VIEW)

        recs = get_content_recommendations(db, user_id=1, n=10)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_purchase_action_contributes_more_than_view(self, db):
        # User buys item 3 (books) and views item 5 (clothing).
        # Item 4 (books) should score higher than any clothing item
        # because purchase carries more weight than view.
        _interact(db, user_id=1, item_id=3, action=ActionType.PURCHASE)
        _interact(db, user_id=1, item_id=5, action=ActionType.VIEW)

        recs = get_content_recommendations(db, user_id=1, n=10)
        item_ids = [r["item_id"] for r in recs]
        # Item 4 (similar to purchased item 3) should rank above item 1 or 2
        assert 4 in item_ids
        assert item_ids.index(4) == 0

    def test_cold_start_user_returns_empty(self, db):
        recs = get_content_recommendations(db, user_id=999, n=10)
        assert recs == []

    def test_user_with_no_interactions_returns_empty(self, db):
        # bob (user_id=2) has no interactions
        recs = get_content_recommendations(db, user_id=2, n=10)
        assert recs == []


# ---------------------------------------------------------------------------
# test_personalization
# ---------------------------------------------------------------------------


class TestPersonalization:
    def test_different_users_get_different_recommendations(self, db):
        # Alice likes electronics; Bob likes books.
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)  # laptop (electronics)
        _interact(db, user_id=2, item_id=3, action=ActionType.PURCHASE)  # python book (books)

        alice_recs = {r["item_id"] for r in get_content_recommendations(db, user_id=1, n=5)}
        bob_recs = {r["item_id"] for r in get_content_recommendations(db, user_id=2, n=5)}

        assert alice_recs != bob_recs

    def test_electronics_user_gets_electronics_recommendations(self, db):
        _interact(db, user_id=1, item_id=1, action=ActionType.PURCHASE)  # laptop

        recs = get_content_recommendations(db, user_id=1, n=5)
        top_item_id = recs[0]["item_id"]
        top_item = db.query(Item).get(top_item_id)

        assert top_item.category == "electronics"

    def test_books_user_gets_books_recommendations(self, db):
        _interact(db, user_id=2, item_id=3, action=ActionType.PURCHASE)  # python book

        recs = get_content_recommendations(db, user_id=2, n=5)
        top_item_id = recs[0]["item_id"]
        top_item = db.query(Item).get(top_item_id)

        assert top_item.category == "books"

    def test_user_taste_shift_reflected_in_recommendations(self, db):
        # Alice first only liked laptops. Then she buys a Python book.
        # After the purchase, book recommendations should appear.
        _interact(db, user_id=1, item_id=1, action=ActionType.VIEW)  # laptop — weak signal

        recs_before = {r["item_id"] for r in get_content_recommendations(db, user_id=1, n=10)}

        _interact(db, user_id=1, item_id=3, action=ActionType.PURCHASE)  # python book — strong

        recs_after = {r["item_id"] for r in get_content_recommendations(db, user_id=1, n=10)}

        # Item 4 (data science book) should appear after purchasing a book
        assert 4 in recs_after
