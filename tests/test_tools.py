import os
import json
import pytest
from codecrew.tools.file_writer import write_file
from codecrew.tools.code_executor import execute_command
from codecrew.tools.readers import list_files_in_directory, read_file_content
from codecrew.rag.store import RAGStore, RetrievalHit, _Chunk

@pytest.fixture
def temp_output_dir(tmpdir):
    return str(tmpdir)

def test_write_file(temp_output_dir):
    result = write_file("test.md", "# Hello AgentScope", base_dir=temp_output_dir)
    assert "Successfully wrote" in result
    
    file_path = os.path.join(temp_output_dir, "test.md")
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        assert f.read() == "# Hello AgentScope"

def test_code_executor(temp_output_dir):
    # Depending on OS, echo might be different, let's just use python
    cmd = "python -c \"print('Hello World')\""
    result = execute_command(cmd, working_directory=temp_output_dir)
    assert "Hello World" in result
    
def test_directory_reader(temp_output_dir):
    write_file("file1.txt", "abc", base_dir=temp_output_dir)
    result = list_files_in_directory(temp_output_dir)
    assert "file1.txt" in result

def test_file_reader(temp_output_dir):
    write_file("file1.txt", "abc", base_dir=temp_output_dir)
    file_path = os.path.join(temp_output_dir, "file1.txt")
    result = read_file_content(file_path)
    assert result == "abc"


def test_vector_search_falls_back_when_vector_math_fails(monkeypatch):
    rag = RAGStore(embed_url="http://localhost:11434", embed_model="nomic-embed-text")
    rag._vector_ok = True
    rag._chunks = [
        _Chunk(
            doc_id="spec",
            chunk_id="spec::0",
            text="calculator service add subtract multiply divide",
            metadata={"filepath": "spec.md"},
            vector=[1.0, 1.0],
        )
    ]

    def broken_similarity(_a, _b):
        raise MemoryError("OpenBLAS allocation failed")

    monkeypatch.setattr(rag, "_embed", lambda _q: [1.0, 1.0])
    monkeypatch.setattr(rag, "_cosine_similarity", broken_similarity)

    result = rag.retrieve("calculator service interface", n_results=1)

    assert isinstance(result, str)
    assert rag._vector_ok is False


def test_index_file_extracts_html_text(tmp_path):
    html_file = tmp_path / "guide.html"
    html_file.write_text(
        "<html><body><h1>Architecture</h1><p>Customer lookup service</p></body></html>",
        encoding="utf-8",
    )

    rag = RAGStore(
        embed_url="http://localhost:11434",
        embed_model="nomic-embed-text",
        retrieval_mode="keyword",
        reranker="none",
    )
    rag._vector_ok = False

    indexed = rag.index_file("guide.html", base_dir=str(tmp_path))
    response = rag.retrieve_structured("customer lookup", n_results=1)

    assert indexed == 1
    assert response.hits[0].metadata["filepath"] == "guide.html"
    assert "Architecture" in response.hits[0].text
    assert "<h1>" not in response.hits[0].text


def test_hybrid_retrieval_merges_semantic_and_keyword_scores(monkeypatch):
    rag = RAGStore(
        embed_url="http://localhost:11434",
        embed_model="nomic-embed-text",
        retrieval_mode="hybrid",
        semantic_weight=0.4,
        keyword_weight=0.6,
        reranker="none",
    )
    rag._vector_ok = True
    rag._chunks = [
        _Chunk(
            doc_id="semantic",
            chunk_id="semantic-first",
            text="general customer support guide",
            metadata={"filepath": "semantic.md"},
            vector=[1.0, 0.0],
        ),
        _Chunk(
            doc_id="keyword",
            chunk_id="keyword-first",
            text="invoice id ABC-123 lookup instructions",
            metadata={"filepath": "keyword.md"},
            vector=[0.0, 1.0],
        ),
    ]

    semantic_hits = [
        RetrievalHit(
            chunk_id="semantic-first",
            doc_id="semantic",
            text="general customer support guide",
            metadata={"filepath": "semantic.md"},
            score=0.95,
            semantic_score=0.95,
        ),
        RetrievalHit(
            chunk_id="keyword-first",
            doc_id="keyword",
            text="invoice id ABC-123 lookup instructions",
            metadata={"filepath": "keyword.md"},
            score=0.4,
            semantic_score=0.4,
        ),
    ]
    keyword_hits = [
        RetrievalHit(
            chunk_id="keyword-first",
            doc_id="keyword",
            text="invoice id ABC-123 lookup instructions",
            metadata={"filepath": "keyword.md"},
            score=8.0,
            keyword_score=8.0,
        ),
    ]

    monkeypatch.setattr(rag, "_vector_search", lambda _query, _n: semantic_hits)
    monkeypatch.setattr(rag, "_keyword_search", lambda _query, _n: keyword_hits)

    response = rag.retrieve_structured("ABC-123", n_results=1)

    assert response.hits[0].chunk_id == "keyword-first"
    assert response.hits[0].keyword_score > response.hits[0].semantic_score


def test_retrieval_trace_and_evaluation(tmp_path):
    trace_path = tmp_path / "retrieval.jsonl"
    rag = RAGStore(
        embed_url="http://localhost:11434",
        embed_model="nomic-embed-text",
        retrieval_mode="keyword",
        reranker="none",
        trace_path=str(trace_path),
    )
    rag._vector_ok = False
    rag.index("spec", "Invoice ID ABC-123 belongs to the customer ledger.", {"filepath": "spec.md"})

    response = rag.retrieve_structured("ABC-123", n_results=1)
    evaluation = rag.evaluate("ABC-123", expected_terms=["ABC-123"], expected_sources=["spec.md"])
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])

    assert response.hits[0].metadata["filepath"] == "spec.md"
    assert evaluation.metrics["term_recall"] == 1.0
    assert evaluation.metrics["source_recall"] == 1.0
    assert payload["query"] == "ABC-123"
