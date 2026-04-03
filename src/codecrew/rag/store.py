"""
RAGStore — configurable retrieval stack for CodeCrew.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# ---------------------------------------------------------------------------
# Optional numpy for vector maths
# ---------------------------------------------------------------------------
try:
    import numpy as _np  # noqa: N812

    _NUMPY_OK = True
except ImportError:  # pragma: no cover
    _np = None  # type: ignore[assignment]
    _NUMPY_OK = False


# ---------------------------------------------------------------------------
# Internal data class
# ---------------------------------------------------------------------------

class _Chunk:
    """A single indexed text chunk."""

    __slots__ = ("doc_id", "chunk_id", "text", "metadata", "vector")

    def __init__(
        self,
        doc_id: str,
        chunk_id: str,
        text: str,
        metadata: dict,
        vector: Optional[list[float]] = None,
    ) -> None:
        self.doc_id = doc_id
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata
        self.vector = vector  # None when TF-IDF-only mode


class RetrievalHit(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0


class RetrievalResponse(BaseModel):
    query: str
    strategy: str
    using_vectors: bool
    reranked: bool
    hits: list[RetrievalHit] = Field(default_factory=list)


class RAGEvaluationResult(BaseModel):
    provider: str
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RAGStore
# ---------------------------------------------------------------------------

class RAGStore:
    """Per-job RAG index.

    Usage::

        rag = RAGStore(embed_url="http://localhost:11434", embed_model="nomic-embed-text")
        rag.index("spec", spec_text)
        rag.index_file("ARCHITECTURE.md", base_dir=output_dir)
        rag.index_directory(output_dir)

        result: str = rag.retrieve("user authentication interface")
    """

    _MAX_CHUNK_CHARS = 800
    _EMBED_TIMEOUT = 20
    _TEXT_EXTENSIONS = (
        ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".json",
        ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".env", ".csv", ".rst",
        ".xml",
    )

    def __init__(
        self,
        embed_url: str,
        embed_model: str,
        retrieval_mode: str = "hybrid",
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        reranker: str = "auto",
        vector_backend: str = "memory",
        vector_backend_path: str = "",
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        trace_path: str = "",
    ) -> None:
        self._embed_url = embed_url.rstrip("/")
        self._embed_model = embed_model
        self._retrieval_mode = retrieval_mode.strip().lower() or "hybrid"
        self._semantic_weight = max(0.0, semantic_weight)
        self._keyword_weight = max(0.0, keyword_weight)
        if self._semantic_weight == 0.0 and self._keyword_weight == 0.0:
            self._semantic_weight = 0.6
            self._keyword_weight = 0.4
        self._reranker = reranker.strip().lower() or "auto"
        self._vector_backend = vector_backend.strip().lower() or "memory"
        self._vector_backend_path = vector_backend_path.strip()
        self._chunk_size = max(200, chunk_size)
        self._chunk_overlap = max(0, min(chunk_overlap, self._chunk_size // 2))
        self._trace_path = trace_path.strip()

        self._chunks: list[_Chunk] = []
        self._chunk_lookup: dict[str, _Chunk] = {}
        self._vector_ok: bool = _NUMPY_OK
        self._idf: Optional[dict[str, float]] = None
        self._bm25_doc_freq: Optional[dict[str, int]] = None
        self._avg_chunk_length: float = 0.0
        self._last_response: Optional[RetrievalResponse] = None
        self._flashrank_ranker = None
        self._chroma_collection = None
        self._lancedb_table = None
        self._init_vector_backend()

    @classmethod
    def from_env(cls, output_dir: str = "") -> "RAGStore":
        embed_url = os.getenv(
            "OLLAMA_EMBED_URL",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        trace_path = os.getenv("CODECREW_RAG_TRACE_PATH", "")
        if output_dir and not trace_path and os.getenv("CODECREW_RAG_TRACE", "false").lower() == "true":
            safe_name = Path(output_dir).name or "default"
            trace_path = str(Path.home() / ".codecrew" / "retrieval_traces" / f"{safe_name}.jsonl")
        return cls(
            embed_url=embed_url,
            embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            retrieval_mode=os.getenv("CODECREW_RAG_RETRIEVAL_MODE", "hybrid"),
            semantic_weight=float(os.getenv("CODECREW_RAG_SEMANTIC_WEIGHT", "0.6")),
            keyword_weight=float(os.getenv("CODECREW_RAG_KEYWORD_WEIGHT", "0.4")),
            reranker=os.getenv("CODECREW_RAG_RERANKER", "auto"),
            vector_backend=os.getenv("CODECREW_RAG_VECTOR_BACKEND", "memory"),
            vector_backend_path=os.getenv("CODECREW_RAG_VECTOR_BACKEND_PATH", output_dir),
            chunk_size=int(os.getenv("CODECREW_RAG_CHUNK_SIZE", "800")),
            chunk_overlap=int(os.getenv("CODECREW_RAG_CHUNK_OVERLAP", "120")),
            trace_path=trace_path,
        )

    def _init_vector_backend(self) -> None:
        if self._vector_backend == "memory":
            return
        if self._vector_backend == "chroma":
            try:
                import chromadb

                path = self._vector_backend_path or str(Path.home() / ".codecrew" / "chroma")
                client = chromadb.PersistentClient(path=path)
                collection_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(path).name or "codecrew_rag")
                self._chroma_collection = client.get_or_create_collection(name=collection_name)
                return
            except Exception as exc:
                logger.warning("RAGStore: could not initialize ChromaDB (%s); using in-memory vectors", exc)
        if self._vector_backend == "lancedb":
            try:
                import lancedb

                path = self._vector_backend_path or str(Path.home() / ".codecrew" / "lancedb")
                db = lancedb.connect(path)
                table_name = re.sub(r"[^a-zA-Z0-9_]+", "_", Path(path).name or "codecrew_rag")
                if hasattr(db, "table_names") and table_name in db.table_names():
                    self._lancedb_table = db.open_table(table_name)
                else:
                    self._lancedb_table = db.create_table(
                        table_name,
                        data=[{"chunk_id": "__seed__", "text": "", "doc_id": "", "vector": [0.0]}],
                        mode="overwrite",
                    )
                    if hasattr(self._lancedb_table, "delete"):
                        self._lancedb_table.delete("chunk_id = '__seed__'")
                return
            except Exception as exc:
                logger.warning("RAGStore: could not initialize LanceDB (%s); using in-memory vectors", exc)
        self._vector_backend = "memory"

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> Optional[list[float]]:
        """Call Ollama's /api/embeddings and return the embedding vector.

        Returns None on any error; callers must handle gracefully.
        """
        if not _NUMPY_OK:
            return None
        url = f"{self._embed_url}/api/embeddings"
        payload = json.dumps(
            {"model": self._embed_model, "prompt": text[:2048]}
        ).encode()
        req = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self._EMBED_TIMEOUT) as resp:
                data = json.loads(resp.read())
            vec = data.get("embedding") or (
                data.get("embeddings", [None])[0]
                if isinstance(data.get("embeddings"), list)
                else None
            )
            if vec and isinstance(vec, list):
                return vec
            logger.warning("RAGStore: unexpected embedding response shape: %s", data)
            return None
        except (URLError, OSError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("RAGStore: embedding call failed (%s) — switching to TF-IDF", exc)
            self._vector_ok = False
            return None

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", (text or "").lower())

    def _clean_html(self, text: str) -> str:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            return soup.get_text("\n", strip=True)
        except Exception:
            text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
            text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
            return re.sub(r"\s+", " ", text).strip()

    def _extract_pdf_documents(self, filepath: str, rel: str) -> list[tuple[str, dict[str, Any]]]:
        try:
            from unstructured.partition.auto import partition

            elements = partition(filename=filepath)
            if elements:
                text = "\n\n".join(
                    value for value in (getattr(element, "text", "") for element in elements) if value.strip()
                )
                if text.strip():
                    return [(text, {"filepath": rel, "source_type": "pdf", "extractor": "unstructured"})]
        except Exception:
            pass

        try:
            from pypdf import PdfReader

            reader = PdfReader(filepath)
            documents: list[tuple[str, dict[str, Any]]] = []
            for index, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    documents.append(
                        (
                            page_text,
                            {
                                "filepath": rel,
                                "source_type": "pdf",
                                "page_number": index,
                                "extractor": "pypdf",
                            },
                        )
                    )
            return documents
        except Exception as exc:
            logger.warning("RAGStore.index_file: PDF extraction failed for %s (%s)", rel, exc)
            return []

    def _extract_docx_documents(self, filepath: str, rel: str) -> list[tuple[str, dict[str, Any]]]:
        try:
            from unstructured.partition.auto import partition

            elements = partition(filename=filepath)
            if elements:
                text = "\n\n".join(
                    value for value in (getattr(element, "text", "") for element in elements) if value.strip()
                )
                if text.strip():
                    return [(text, {"filepath": rel, "source_type": "docx", "extractor": "unstructured"})]
        except Exception:
            pass

        try:
            from docx import Document

            document = Document(filepath)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()).strip()
            if text:
                return [(text, {"filepath": rel, "source_type": "docx", "extractor": "python-docx"})]
        except Exception as exc:
            logger.warning("RAGStore.index_file: DOCX extraction failed for %s (%s)", rel, exc)
        return []

    def _extract_plain_documents(self, filepath: str, rel: str) -> list[tuple[str, dict[str, Any]]]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            logger.warning("RAGStore.index_file: read error %s — %s", filepath, exc)
            return []

        source_type = Path(filepath).suffix.lower().lstrip(".") or "text"
        if filepath.lower().endswith((".html", ".htm", ".xml")):
            text = self._clean_html(text)
        return [(text, {"filepath": rel, "source_type": source_type, "extractor": "builtin"})]

    def _extract_documents_from_file(self, filepath: str, rel: str) -> list[tuple[str, dict[str, Any]]]:
        suffix = Path(filepath).suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_documents(filepath, rel)
        if suffix in {".docx", ".doc"}:
            return self._extract_docx_documents(filepath, rel)
        if suffix in self._TEXT_EXTENSIONS or not suffix:
            return self._extract_plain_documents(filepath, rel)
        return []

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        max_c = self._chunk_size or self._MAX_CHUNK_CHARS
        sections = re.split(r"(?m)(?=^#{1,3} )", text)
        chunks: list[str] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(section) <= max_c:
                chunks.append(section)
                continue
            # Split on blank lines
            paragraphs = re.split(r"\n\n+", section)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(current) + len(para) + 2 <= max_c:
                    current = (current + "\n\n" + para).strip() if current else para
                else:
                    if current:
                        chunks.append(current)
                    while len(para) > max_c:
                        window = para[:max_c]
                        chunks.append(window)
                        para = para[max(max_c - self._chunk_overlap, 1):]
                    current = para
            if current:
                chunks.append(current)

        return chunks if chunks else [text[:max_c]]

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Chunk *text* and add all chunks to the index.

        Args:
            doc_id:   Human-readable source identifier (e.g. "spec", "src/main.py").
            text:     Raw document text.
            metadata: Optional extra metadata stored alongside each chunk.

        Returns:
            Number of chunks indexed.
        """
        if not text or not text.strip():
            return 0
        metadata = metadata or {}
        raw_chunks = self._chunk_text(text)
        for i, chunk_text in enumerate(raw_chunks):
            vector = self._embed(chunk_text) if self._vector_ok else None
            chunk = _Chunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}::{len(self._chunks)}::{i}",
                text=chunk_text,
                metadata={**metadata, "chunk_index": i, "indexed_at": datetime.now(timezone.utc).isoformat()},
                vector=vector,
            )
            self._chunks.append(chunk)
            self._chunk_lookup[chunk.chunk_id] = chunk
            self._write_vector_backend(chunk)
        self._idf = None  # Invalidate TF-IDF cache
        self._bm25_doc_freq = None
        logger.info(
            "RAGStore: indexed %d chunks from '%s' (total=%d)",
            len(raw_chunks),
            doc_id,
            len(self._chunks),
        )
        return len(raw_chunks)

    def index_file(self, filepath: str, base_dir: str = "") -> int:
        """Read *filepath* (relative to *base_dir*) and index its content.

        Returns the number of chunks indexed, or 0 on failure.
        """
        full = os.path.join(base_dir, filepath) if base_dir else filepath
        full = os.path.normpath(full)
        if not os.path.isfile(full):
            logger.debug("RAGStore.index_file: not found — %s", full)
            return 0
        rel = filepath or full
        total = 0
        for index, (text, metadata) in enumerate(self._extract_documents_from_file(full, rel)):
            if not text.strip():
                continue
            segment_doc_id = rel
            if "page_number" in metadata:
                segment_doc_id = f"{rel}::page:{metadata['page_number']}"
            elif index > 0:
                segment_doc_id = f"{rel}::segment:{index}"
            total += self.index(doc_id=segment_doc_id, text=text, metadata=metadata)
        return total

    def index_path(self, path: str) -> int:
        if os.path.isdir(path):
            return self.index_directory(path)
        return self.index_file(path)

    def index_directory(
        self,
        directory: str,
        extensions: tuple[str, ...] = _TEXT_EXTENSIONS + (".pdf", ".doc", ".docx"),
    ) -> int:
        """Recursively index all files under *directory* matching *extensions*.

        Returns total chunks indexed.
        """
        _SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".mypy_cache"}
        total = 0
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if not any(fname.endswith(ext) for ext in extensions):
                    continue
                if fname == "job_state.json":
                    continue
                fpath = os.path.join(root, fname)
                # Store relative path as doc_id for readability
                rel = os.path.relpath(fpath, directory).replace("\\", "/")
                try:
                    total += self.index_file(rel, base_dir=directory)
                except OSError:
                    continue
        return total

    def _write_vector_backend(self, chunk: _Chunk) -> None:
        if chunk.vector is None or not self._vector_ok:
            return
        if self._vector_backend == "chroma" and self._chroma_collection is not None:
            try:
                self._chroma_collection.add(
                    ids=[chunk.chunk_id],
                    embeddings=[chunk.vector],
                    documents=[chunk.text],
                    metadatas=[{**chunk.metadata, "doc_id": chunk.doc_id}],
                )
            except Exception as exc:
                logger.warning("RAGStore: ChromaDB add failed (%s); falling back to in-memory search", exc)
                self._vector_backend = "memory"
        elif self._vector_backend == "lancedb" and self._lancedb_table is not None:
            try:
                self._lancedb_table.add(
                    [
                        {
                            "chunk_id": chunk.chunk_id,
                            "doc_id": chunk.doc_id,
                            "text": chunk.text,
                            "vector": chunk.vector,
                        }
                    ]
                )
            except Exception as exc:
                logger.warning("RAGStore: LanceDB add failed (%s); falling back to in-memory search", exc)
                self._vector_backend = "memory"

    # ------------------------------------------------------------------
    # Retrieval — vector search
    # ------------------------------------------------------------------

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        va = _np.array(a, dtype=_np.float32)
        vb = _np.array(b, dtype=_np.float32)
        na, nb = _np.linalg.norm(va), _np.linalg.norm(vb)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(_np.dot(va, vb) / (na * nb))

    def _vector_search(self, query: str, n_results: int) -> list[RetrievalHit]:
        try:
            query_vec = self._embed(query)
            if query_vec is None:
                return []
            if self._vector_backend == "chroma" and self._chroma_collection is not None:
                try:
                    result = self._chroma_collection.query(
                        query_embeddings=[query_vec],
                        n_results=n_results,
                        include=["distances", "metadatas", "documents"],
                    )
                    ids = result.get("ids", [[]])[0]
                    distances = result.get("distances", [[]])[0]
                    hits: list[RetrievalHit] = []
                    for chunk_id, distance in zip(ids, distances):
                        chunk = self._chunk_lookup.get(chunk_id)
                        if chunk is None:
                            continue
                        score = 1.0 / (1.0 + float(distance))
                        hits.append(
                            RetrievalHit(
                                chunk_id=chunk.chunk_id,
                                doc_id=chunk.doc_id,
                                text=chunk.text,
                                metadata=chunk.metadata,
                                score=score,
                                semantic_score=score,
                            )
                        )
                    return hits
                except Exception as exc:
                    logger.warning("RAGStore: ChromaDB query failed (%s); falling back to in-memory search", exc)
                    self._vector_backend = "memory"
            if self._vector_backend == "lancedb" and self._lancedb_table is not None:
                try:
                    results = self._lancedb_table.search(query_vec).limit(n_results).to_list()
                    hits: list[RetrievalHit] = []
                    for row in results:
                        chunk_id = row.get("chunk_id")
                        chunk = self._chunk_lookup.get(chunk_id)
                        if chunk is None:
                            continue
                        distance = float(row.get("_distance", 0.0))
                        score = 1.0 / (1.0 + distance)
                        hits.append(
                            RetrievalHit(
                                chunk_id=chunk.chunk_id,
                                doc_id=chunk.doc_id,
                                text=chunk.text,
                                metadata=chunk.metadata,
                                score=score,
                                semantic_score=score,
                            )
                        )
                    return hits
                except Exception as exc:
                    logger.warning("RAGStore: LanceDB query failed (%s); falling back to in-memory search", exc)
                    self._vector_backend = "memory"

            candidates = [c for c in self._chunks if c.vector is not None]
            scored = sorted(
                ((c, self._cosine_similarity(query_vec, c.vector)) for c in candidates),
                key=lambda x: x[1],
                reverse=True,
            )
            return [
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    score=score,
                    semantic_score=score,
                )
                for chunk, score in scored[:n_results]
                if score > 0.0
            ]
        except Exception as exc:
            self._vector_ok = False
            logger.warning("RAGStore: vector search failed (%s) — switching to TF-IDF", exc)
            return []

    # ------------------------------------------------------------------
    # Retrieval — TF-IDF fallback
    # ------------------------------------------------------------------

    def _build_idf(self) -> None:
        n = len(self._chunks)
        df: dict[str, int] = {}
        for chunk in self._chunks:
            for token in set(self._tokenize(chunk.text)):
                df[token] = df.get(token, 0) + 1
        self._idf = {
            token: math.log((n + 1) / (freq + 1))
            for token, freq in df.items()
        }

    def _build_bm25(self) -> None:
        df: dict[str, int] = {}
        total_length = 0
        for chunk in self._chunks:
            tokens = self._tokenize(chunk.text)
            total_length += len(tokens)
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        self._bm25_doc_freq = df
        self._avg_chunk_length = (total_length / len(self._chunks)) if self._chunks else 0.0

    def _tfidf_score(self, chunk: _Chunk, query_tokens: list[str]) -> float:
        if self._idf is None:
            self._build_idf()
        freq: dict[str, int] = {}
        for t in self._tokenize(chunk.text):
            freq[t] = freq.get(t, 0) + 1
        return sum(
            freq.get(t, 0) * self._idf.get(t, 0)  # type: ignore[index]
            for t in query_tokens
        )

    def _bm25_score(self, chunk: _Chunk, query_tokens: list[str], k1: float = 1.5, b: float = 0.75) -> float:
        if self._bm25_doc_freq is None:
            self._build_bm25()
        tokens = self._tokenize(chunk.text)
        if not tokens:
            return 0.0
        freq: dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        score = 0.0
        chunk_length = len(tokens)
        doc_count = len(self._chunks)
        avg_length = self._avg_chunk_length or 1.0
        for token in query_tokens:
            df = (self._bm25_doc_freq or {}).get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            tf = freq.get(token, 0)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * chunk_length / avg_length)
            if denominator:
                score += idf * (numerator / denominator)
        return score

    def _keyword_search(self, query: str, n_results: int) -> list[RetrievalHit]:
        if not self._chunks:
            return []
        tokens = self._tokenize(query)
        scored = sorted(
            ((c, max(self._bm25_score(c, tokens), self._tfidf_score(c, tokens))) for c in self._chunks),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                text=chunk.text,
                metadata=chunk.metadata,
                score=score,
                keyword_score=score,
            )
            for chunk, score in scored[:n_results]
            if score > 0.0
        ]

    def _normalize_scores(self, hits: list[RetrievalHit], score_field: str) -> dict[str, float]:
        if not hits:
            return {}
        max_score = max(getattr(hit, score_field) for hit in hits) or 1.0
        return {hit.chunk_id: getattr(hit, score_field) / max_score for hit in hits}

    def _heuristic_rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        query_text = query.lower().strip()
        query_tokens = set(self._tokenize(query))
        rescored: list[RetrievalHit] = []
        for hit in hits:
            text = hit.text.lower()
            overlap = len(query_tokens.intersection(set(self._tokenize(hit.text))))
            phrase_bonus = 2.0 if query_text and query_text in text else 0.0
            rerank_score = overlap + phrase_bonus
            rescored.append(
                hit.model_copy(
                    update={
                        "rerank_score": rerank_score,
                        "score": hit.score + rerank_score * 0.1,
                    }
                )
            )
        return sorted(rescored, key=lambda hit: hit.score, reverse=True)

    def _flashrank_rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if self._flashrank_ranker is None:
            from flashrank import Ranker

            model_name = os.getenv("CODECREW_RAG_FLASHRANK_MODEL", "ms-marco-MiniLM-L-12-v2")
            self._flashrank_ranker = Ranker(model_name=model_name)
        request_payload = [
            {"id": hit.chunk_id, "text": hit.text, "meta": hit.metadata}
            for hit in hits
        ]
        reranked = self._flashrank_ranker.rerank(query=query, passages=request_payload)
        by_id = {entry["id"]: entry for entry in reranked}
        rescored: list[RetrievalHit] = []
        for hit in hits:
            entry = by_id.get(hit.chunk_id, {})
            rerank_score = float(entry.get("score", 0.0))
            rescored.append(
                hit.model_copy(
                    update={
                        "rerank_score": rerank_score,
                        "score": hit.score + rerank_score,
                    }
                )
            )
        return sorted(rescored, key=lambda item: item.score, reverse=True)

    def _rerank_hits(self, query: str, hits: list[RetrievalHit]) -> tuple[list[RetrievalHit], bool]:
        if not hits or self._reranker in {"none", "off", "disabled"}:
            return hits, False
        if self._reranker in {"auto", "flashrank"}:
            try:
                return self._flashrank_rerank(query, hits), True
            except Exception as exc:
                if self._reranker == "flashrank":
                    logger.warning("RAGStore: FlashRank reranker failed (%s); using heuristic rerank", exc)
        return self._heuristic_rerank(query, hits), True

    def retrieve_structured(self, query: str, n_results: int = 5) -> RetrievalResponse:
        if not self._chunks:
            response = RetrievalResponse(
                query=query,
                strategy=self._retrieval_mode,
                using_vectors=self.using_vectors,
                reranked=False,
                hits=[],
            )
            self._record_trace(response)
            return response

        expanded_k = max(n_results * 3, n_results)
        semantic_hits = self._vector_search(query, expanded_k) if self._vector_ok and _NUMPY_OK else []
        keyword_hits = self._keyword_search(query, expanded_k)

        mode = self._retrieval_mode
        if mode not in {"semantic", "keyword", "hybrid"}:
            mode = "hybrid"

        if mode == "semantic":
            hits = semantic_hits or keyword_hits
        elif mode == "keyword":
            hits = keyword_hits
        else:
            semantic_map = self._normalize_scores(semantic_hits, "semantic_score")
            keyword_map = self._normalize_scores(keyword_hits, "keyword_score")
            merged: dict[str, RetrievalHit] = {}
            for hit in semantic_hits + keyword_hits:
                merged.setdefault(hit.chunk_id, hit)
            hits = []
            for chunk_id, hit in merged.items():
                semantic_score = semantic_map.get(chunk_id, 0.0)
                keyword_score = keyword_map.get(chunk_id, 0.0)
                combined_score = semantic_score * self._semantic_weight + keyword_score * self._keyword_weight
                hits.append(
                    hit.model_copy(
                        update={
                            "semantic_score": max(hit.semantic_score, semantic_score),
                            "keyword_score": max(hit.keyword_score, keyword_score),
                            "score": combined_score,
                        }
                    )
                )
            hits.sort(key=lambda item: item.score, reverse=True)

        reranked_hits, reranked = self._rerank_hits(query, hits[:expanded_k])
        try:
            response = RetrievalResponse(
                query=query,
                strategy=mode,
                using_vectors=self.using_vectors,
                reranked=reranked,
                hits=reranked_hits[:n_results],
            )
        except ValidationError as exc:
            logger.warning("RAGStore: retrieval response validation failed (%s)", exc)
            response = RetrievalResponse(
                query=query,
                strategy=mode,
                using_vectors=self.using_vectors,
                reranked=False,
                hits=[],
            )
        self._record_trace(response)
        return response

    # ------------------------------------------------------------------
    # Public retrieval interface
    # ------------------------------------------------------------------

    def retrieve(self, query: str, n_results: int = 5) -> str:
        response = self.retrieve_structured(query=query, n_results=n_results)
        if not response.hits:
            if self._chunks:
                return (
                    f"No relevant context found for query: '{query}'. "
                    "Use your own knowledge or the context already in the conversation."
                )
            return (
                "RAG index is empty — documents have not been indexed yet. "
                "Proceed using the information already in your context."
            )

        lines = [
            f"## Retrieved Context  ({len(response.hits)} chunk(s) matching: '{query}')",
            f"strategy={response.strategy} vectors={'on' if response.using_vectors else 'off'} reranked={'yes' if response.reranked else 'no'}",
            "",
        ]
        for i, hit in enumerate(response.hits, 1):
            source = hit.metadata.get("filepath") or hit.doc_id
            page_number = hit.metadata.get("page_number")
            source_label = f"{source} page {page_number}" if page_number else str(source)
            score_line = (
                f"score={hit.score:.3f} semantic={hit.semantic_score:.3f} "
                f"keyword={hit.keyword_score:.3f} rerank={hit.rerank_score:.3f}"
            )
            lines.append(f"### [{i}] `{source_label}`")
            lines.append(score_line)
            lines.append(hit.text)
            lines.append("")   # blank line between chunks

        return "\n".join(lines)

    def evaluate(
        self,
        query: str,
        expected_terms: Optional[list[str]] = None,
        expected_sources: Optional[list[str]] = None,
        n_results: int = 5,
    ) -> RAGEvaluationResult:
        provider = os.getenv("CODECREW_RAG_EVALUATOR", "heuristic").strip().lower() or "heuristic"
        response = self.retrieve_structured(query, n_results=n_results)
        hits = response.hits
        notes: list[str] = []
        joined = "\n".join(hit.text for hit in hits).lower()
        retrieved_sources = {
            str(hit.metadata.get("filepath") or hit.doc_id).lower()
            for hit in hits
        }
        metrics: dict[str, float] = {
            "hit_count": float(len(hits)),
            "average_score": (
                sum(hit.score for hit in hits) / len(hits)
                if hits else 0.0
            ),
        }
        if expected_terms:
            matched = sum(1 for term in expected_terms if term.lower() in joined)
            metrics["term_recall"] = matched / len(expected_terms)
        if expected_sources:
            matched_sources = sum(
                1 for source in expected_sources if source.lower() in retrieved_sources
            )
            metrics["source_recall"] = matched_sources / len(expected_sources)
        if provider in {"ragas", "deepeval"}:
            notes.append(f"{provider} is not installed in this environment; heuristic evaluation used instead.")
            provider = "heuristic"
        return RAGEvaluationResult(provider=provider, metrics=metrics, notes=notes)

    def _record_trace(self, response: RetrievalResponse) -> None:
        self._last_response = response
        if not self._trace_path:
            return
        payload = response.model_dump()
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            trace_file = Path(self._trace_path)
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            with trace_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("RAGStore: could not write trace file %s (%s)", self._trace_path, exc)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        """Total number of indexed chunks."""
        return len(self._chunks)

    @property
    def using_vectors(self) -> bool:
        """True if Ollama embedding is working and numpy is available."""
        return self._vector_ok and _NUMPY_OK

    @property
    def last_response(self) -> Optional[RetrievalResponse]:
        return self._last_response

    def __repr__(self) -> str:
        mode = f"{self._retrieval_mode}:{self._vector_backend}" if self.using_vectors else self._retrieval_mode
        return (
            f"<RAGStore chunks={self.chunk_count} mode={mode} "
            f"model={self._embed_model!r}>"
        )
