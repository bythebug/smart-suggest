import math


# ---------------------------------------------------------------------------
# Core similarity functions
# ---------------------------------------------------------------------------


def cosine_similarity(vec1: dict[int, float], vec2: dict[int, float]) -> float:
    """
    Cosine similarity between two sparse vectors represented as {item_id: score}.

    Returns a value in [0, 1] for non-negative vectors. Returns 0.0 when either
    vector is all-zeros or when the two share no items in common.
    """
    common = set(vec1) & set(vec2)
    if not common:
        return 0.0

    dot = sum(vec1[k] * vec2[k] for k in common)
    norm1 = math.sqrt(sum(v * v for v in vec1.values()))
    norm2 = math.sqrt(sum(v * v for v in vec2.values()))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot / (norm1 * norm2)


def pearson_correlation(
    ratings1: dict[int, float],
    ratings2: dict[int, float],
) -> float:
    """
    Pearson correlation between two sparse rating vectors.

    Only items present in *both* dicts are used. Returns 0.0 when fewer than
    two co-rated items exist (correlation is undefined with n < 2).

    Pearson centres each vector by its own mean before computing the dot product,
    so it handles systematic rating-scale differences between users (e.g. one user
    who always rates 4-5 and another who uses 1-2).
    """
    common = set(ratings1) & set(ratings2)
    n = len(common)
    if n < 2:
        return 0.0

    r1 = [ratings1[k] for k in common]
    r2 = [ratings2[k] for k in common]

    mean1 = sum(r1) / n
    mean2 = sum(r2) / n

    c1 = [x - mean1 for x in r1]
    c2 = [x - mean2 for x in r2]

    numerator = sum(a * b for a, b in zip(c1, c2))
    denom = math.sqrt(sum(a * a for a in c1)) * math.sqrt(sum(b * b for b in c2))

    if denom == 0.0:
        return 0.0

    return numerator / denom


# ---------------------------------------------------------------------------
# Neighbour search
# ---------------------------------------------------------------------------


def top_k_similar_users(
    user_vectors: dict[int, dict[int, float]],
    target_user_id: int,
    k: int,
    min_similarity: float = 0.0,
) -> list[tuple[int, float]]:
    """
    Return the top-K (user_id, similarity) pairs most similar to target_user_id,
    using cosine similarity on their item-score vectors.

    Users with similarity below min_similarity are excluded.
    Returns an empty list when target_user_id is not in user_vectors.
    """
    if target_user_id not in user_vectors:
        return []

    target_vec = user_vectors[target_user_id]

    neighbours = [
        (uid, cosine_similarity(target_vec, vec))
        for uid, vec in user_vectors.items()
        if uid != target_user_id
    ]

    return sorted(
        ((uid, sim) for uid, sim in neighbours if sim >= min_similarity),
        key=lambda x: x[1],
        reverse=True,
    )[:k]
