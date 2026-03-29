import pytest

from codecrew.tools.turboquant import encode_dataset, fit_turboquant


def _build_separable_vectors() -> list[list[float]]:
    chunk_a = [
        [3.0, 0.0, 0.0, 0.0],
        [0.0, 3.0, 0.0, 0.0],
        [-3.0, 0.0, 0.0, 0.0],
        [0.0, -3.0, 0.0, 0.0],
    ]
    chunk_b = [
        [2.0, 0.0, 0.0, 0.0],
        [0.0, 2.0, 0.0, 0.0],
        [-2.0, 0.0, 0.0, 0.0],
        [0.0, -2.0, 0.0, 0.0],
    ]
    vectors: list[list[float]] = []
    for first in chunk_a:
        for second in chunk_b:
            vectors.append(first + second)
    return vectors


def test_turboquant_fit_encode_decode():
    vectors = _build_separable_vectors()
    model = fit_turboquant(
        vectors=vectors,
        num_subvectors=2,
        codebook_size=4,
        rounds=20,
        seed=13,
    )
    encoded = encode_dataset(model, vectors)
    assert len(encoded) == len(vectors)
    assert all(len(codes) == 2 for codes in encoded)
    assert model.quantization_error(vectors) < 1e-9


def test_turboquant_search_top_k():
    vectors = _build_separable_vectors()
    model = fit_turboquant(vectors, num_subvectors=2, codebook_size=4, seed=5)
    encoded = encode_dataset(model, vectors)
    query = vectors[7]
    top = model.search_top_k(query=query, encoded_vectors=encoded, k=3)
    assert top[0][0] == 7
    assert len(top) == 3
    assert top[0][1] >= top[1][1] >= top[2][1]


def test_turboquant_input_validation():
    with pytest.raises(ValueError):
        fit_turboquant(vectors=[], num_subvectors=2)
    with pytest.raises(ValueError):
        fit_turboquant(vectors=[[1.0, 2.0], [1.0]], num_subvectors=1)
