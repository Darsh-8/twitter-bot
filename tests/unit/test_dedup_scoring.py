from newsbot.application.services.dedup_service import _cosine_similarity


def test_identical_vectors_have_similarity_one():
    v = [1.0, 2.0, 3.0]
    assert _cosine_similarity(v, v) == 1.0


def test_orthogonal_vectors_have_similarity_zero():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_opposite_vectors_have_similarity_negative_one():
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_zero_vector_returns_zero_without_dividing_by_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_similar_but_not_identical_vectors_are_between_zero_and_one():
    score = _cosine_similarity([1.0, 1.0], [1.0, 0.9])
    assert 0.9 < score < 1.0
