"""RAG (Retrieval-Augmented Generation) module for CodeCrew.

Provides per-job semantic search over pipeline artifacts (spec, architecture,
generated code) so downstream agents can retrieve precise context without
overflowing their limited context windows.
"""

from .store import RAGEvaluationResult, RAGStore, RetrievalHit, RetrievalResponse

__all__ = ["RAGEvaluationResult", "RAGStore", "RetrievalHit", "RetrievalResponse"]
