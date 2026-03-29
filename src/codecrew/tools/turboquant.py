from __future__ import annotations

from dataclasses import dataclass
from math import inf
from random import Random


def _squared_l2_distance(a: list[float], b: list[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _split_vector(vector: list[float], chunk_size: int) -> list[list[float]]:
    return [vector[i : i + chunk_size] for i in range(0, len(vector), chunk_size)]


def _mean(vectors: list[list[float]], dim: int) -> list[float]:
    if not vectors:
        return [0.0] * dim
    totals = [0.0] * dim
    for vector in vectors:
        for index, value in enumerate(vector):
            totals[index] += value
    count = float(len(vectors))
    return [value / count for value in totals]


def _kmeans(subvectors: list[list[float]], clusters: int, seed: int, rounds: int) -> list[list[float]]:
    if not subvectors:
        return []
    if clusters >= len(subvectors):
        return [list(item) for item in subvectors]
    rng = Random(seed)
    centroids = [list(subvectors[rng.randrange(len(subvectors))])]
    while len(centroids) < clusters:
        distances = []
        for subvector in subvectors:
            nearest = min(_squared_l2_distance(subvector, centroid) for centroid in centroids)
            distances.append(nearest)
        total = sum(distances)
        if total <= 0.0:
            centroids.append(list(subvectors[rng.randrange(len(subvectors))]))
            continue
        pick = rng.random() * total
        cumulative = 0.0
        chosen = len(subvectors) - 1
        for idx, distance in enumerate(distances):
            cumulative += distance
            if cumulative >= pick:
                chosen = idx
                break
        centroids.append(list(subvectors[chosen]))
    dim = len(subvectors[0])
    for _ in range(rounds):
        groups: list[list[list[float]]] = [[] for _ in range(len(centroids))]
        for subvector in subvectors:
            best_idx = 0
            best_dist = inf
            for idx, centroid in enumerate(centroids):
                dist = _squared_l2_distance(subvector, centroid)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            groups[best_idx].append(subvector)
        for idx, group in enumerate(groups):
            if group:
                centroids[idx] = _mean(group, dim)
            else:
                centroids[idx] = list(subvectors[rng.randrange(len(subvectors))])
    return centroids


@dataclass(frozen=True)
class TurboQuantModel:
    dimension: int
    num_subvectors: int
    chunk_size: int
    codebook_size: int
    codebooks: list[list[list[float]]]

    def encode(self, vector: list[float]) -> list[int]:
        if len(vector) != self.dimension:
            raise ValueError(f"Expected dimension {self.dimension}, got {len(vector)}")
        chunks = _split_vector(vector, self.chunk_size)
        codes = []
        for chunk_idx, chunk in enumerate(chunks):
            codebook = self.codebooks[chunk_idx]
            best_idx = 0
            best_dist = inf
            for index, centroid in enumerate(codebook):
                dist = _squared_l2_distance(chunk, centroid)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = index
            codes.append(best_idx)
        return codes

    def decode(self, codes: list[int]) -> list[float]:
        if len(codes) != self.num_subvectors:
            raise ValueError(f"Expected {self.num_subvectors} codes, got {len(codes)}")
        decoded: list[float] = []
        for chunk_idx, code in enumerate(codes):
            codebook = self.codebooks[chunk_idx]
            if code < 0 or code >= len(codebook):
                raise ValueError(f"Code index {code} out of range for chunk {chunk_idx}")
            decoded.extend(codebook[code])
        return decoded

    def quantization_error(self, vectors: list[list[float]]) -> float:
        if not vectors:
            return 0.0
        total = 0.0
        for vector in vectors:
            reconstruction = self.decode(self.encode(vector))
            total += _squared_l2_distance(vector, reconstruction)
        return total / float(len(vectors))

    def search_top_k(self, query: list[float], encoded_vectors: list[list[int]], k: int) -> list[tuple[int, float]]:
        if len(query) != self.dimension:
            raise ValueError(f"Expected query dimension {self.dimension}, got {len(query)}")
        if k <= 0:
            raise ValueError("k must be > 0")
        query_chunks = _split_vector(query, self.chunk_size)
        lookup_tables: list[list[float]] = []
        for chunk_idx, query_chunk in enumerate(query_chunks):
            lookup_tables.append([_dot(query_chunk, centroid) for centroid in self.codebooks[chunk_idx]])
        scored: list[tuple[int, float]] = []
        for index, codes in enumerate(encoded_vectors):
            if len(codes) != self.num_subvectors:
                raise ValueError(f"Encoded vector at index {index} has invalid code length")
            score = 0.0
            for chunk_idx, code in enumerate(codes):
                score += lookup_tables[chunk_idx][code]
            scored.append((index, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: min(k, len(scored))]


def fit_turboquant(
    vectors: list[list[float]],
    num_subvectors: int = 4,
    codebook_size: int = 16,
    rounds: int = 12,
    seed: int = 7,
) -> TurboQuantModel:
    if not vectors:
        raise ValueError("vectors cannot be empty")
    dimension = len(vectors[0])
    if dimension == 0:
        raise ValueError("vector dimension cannot be 0")
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("All vectors must have the same dimension")
    if num_subvectors <= 0:
        raise ValueError("num_subvectors must be > 0")
    if dimension % num_subvectors != 0:
        raise ValueError("dimension must be divisible by num_subvectors")
    if codebook_size <= 1:
        raise ValueError("codebook_size must be > 1")
    if rounds <= 0:
        raise ValueError("rounds must be > 0")
    chunk_size = dimension // num_subvectors
    split_vectors = [_split_vector(vector, chunk_size) for vector in vectors]
    codebooks: list[list[list[float]]] = []
    for chunk_idx in range(num_subvectors):
        chunk_vectors = [parts[chunk_idx] for parts in split_vectors]
        chunk_codebook = _kmeans(
            chunk_vectors,
            clusters=min(codebook_size, len(chunk_vectors)),
            seed=seed + chunk_idx * 17,
            rounds=rounds,
        )
        codebooks.append(chunk_codebook)
    return TurboQuantModel(
        dimension=dimension,
        num_subvectors=num_subvectors,
        chunk_size=chunk_size,
        codebook_size=codebook_size,
        codebooks=codebooks,
    )


def encode_dataset(model: TurboQuantModel, vectors: list[list[float]]) -> list[list[int]]:
    return [model.encode(vector) for vector in vectors]
