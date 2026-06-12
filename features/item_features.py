import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from models import Item
from recommenders.similarity import cosine_similarity

# Category contributes more to similarity than individual description words,
# so we give it a fixed boosted weight in the feature vector.
CATEGORY_WEIGHT: float = 3.0

# Module-level similarity cache — rebuilt on demand or after TTL expires.
_CACHE_TTL_SECONDS: float = 3600.0
_cache: "ItemFeatureMatrix | None" = None
_cache_built_at: float = 0.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ItemFeatureMatrix:
    """Pre-computed item feature vectors and their pairwise cosine similarities."""

    # item_id → {feature_name: weight}
    feature_vectors: dict[int, dict[str, float]] = field(default_factory=dict)
    # item_id → {item_id: cosine_similarity}
    similarity_matrix: dict[int, dict[int, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TF-IDF
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def compute_tfidf(documents: dict[int, str]) -> dict[int, dict[str, float]]:
    """
    Compute smoothed TF-IDF vectors for a corpus keyed by document id.

    IDF formula (matches sklearn's default):
        idf(t) = log((1 + N) / (1 + df(t))) + 1

    Smoothing prevents zero IDF for terms that appear in every document and
    avoids zero division when the corpus has a single document.
    """
    N = len(documents)
    tokenized: dict[int, list[str]] = {
        doc_id: _tokenize(text) for doc_id, text in documents.items()
    }

    # Document frequency per term
    df: dict[str, int] = {}
    for tokens in tokenized.values():
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    idf: dict[str, float] = {
        term: math.log((1 + N) / (1 + count)) + 1.0
        for term, count in df.items()
    }

    vectors: dict[int, dict[str, float]] = {}
    for doc_id, tokens in tokenized.items():
        if not tokens:
            vectors[doc_id] = {}
            continue
        tf = Counter(tokens)
        n = len(tokens)
        vectors[doc_id] = {term: (count / n) * idf[term] for term, count in tf.items()}

    return vectors


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------


def build_feature_vectors(items: list[Item]) -> dict[int, dict[str, float]]:
    """
    Combine TF-IDF on item descriptions with a weighted category indicator.

    Category keys are prefixed with `__cat_` to prevent collision with any
    description word that happens to match a category name.
    """
    descriptions = {item.id: (item.description or "") for item in items}
    tfidf = compute_tfidf(descriptions)

    vectors: dict[int, dict[str, float]] = {}
    for item in items:
        vec: dict[str, float] = dict(tfidf.get(item.id, {}))
        vec[f"__cat_{item.category}"] = CATEGORY_WEIGHT
        vectors[item.id] = vec

    return vectors


def compute_similarity_matrix(
    feature_vectors: dict[int, dict[str, float]],
) -> dict[int, dict[int, float]]:
    """
    Compute pairwise cosine similarity for all items.

    Only stores pairs with similarity > 0 to keep the matrix sparse.
    Time complexity: O(N² × F) where F is average feature vector length.
    """
    item_ids = list(feature_vectors)
    matrix: dict[int, dict[int, float]] = {iid: {} for iid in item_ids}

    for i in range(len(item_ids)):
        for j in range(i + 1, len(item_ids)):
            a, b = item_ids[i], item_ids[j]
            sim = cosine_similarity(
                feature_vectors[a],  # type: ignore[arg-type]
                feature_vectors[b],  # type: ignore[arg-type]
            )
            if sim > 0.0:
                matrix[a][b] = sim
                matrix[b][a] = sim

    return matrix


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def build_item_feature_matrix(db: Session) -> ItemFeatureMatrix:
    items = db.query(Item).all()
    if not items:
        return ItemFeatureMatrix()

    feature_vectors = build_feature_vectors(items)
    similarity_matrix = compute_similarity_matrix(feature_vectors)
    return ItemFeatureMatrix(
        feature_vectors=feature_vectors,
        similarity_matrix=similarity_matrix,
    )


def get_feature_matrix(db: Session, force_refresh: bool = False) -> ItemFeatureMatrix:
    """
    Return the cached ItemFeatureMatrix, rebuilding it when stale or missing.

    The cache avoids recomputing O(N²) pairwise similarities on every request.
    Call with force_refresh=True after bulk item ingestion.
    """
    global _cache, _cache_built_at

    now = time.monotonic()
    if _cache is None or force_refresh or (now - _cache_built_at) > _CACHE_TTL_SECONDS:
        _cache = build_item_feature_matrix(db)
        _cache_built_at = now

    return _cache
