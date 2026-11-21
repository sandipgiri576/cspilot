"""Tests for deterministic literature ingestion and retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from typer.testing import CliRunner

from cspilot import rag
from cspilot.cli import app


class FakeIndex:
    """Small in-memory inner-product index used instead of FAISS in unit tests."""

    def __init__(self, dimensions: int) -> None:
        """Initialize an empty vector matrix."""
        self.dimensions = dimensions
        self.vectors = np.empty((0, dimensions), dtype="float32")

    def add(self, vectors: np.ndarray[Any, Any]) -> None:
        """Store vectors in insertion order."""
        self.vectors = vectors

    def search(
        self, query: np.ndarray[Any, Any], count: int
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """Return descending inner-product matches."""
        scores = self.vectors @ query[0]
        positions = np.argsort(scores)[::-1][:count]
        return scores[positions][None, :], positions[None, :]


class FakeModel:
    """Produce deterministic two-dimensional keyword embeddings."""

    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray[Any, Any]:
        """Embed water-related text separately from catalysis-related text."""
        del kwargs
        vectors = []
        for text in texts:
            vector = np.array(
                [float("water" in text.lower()), float("catal" in text.lower())],
                dtype="float32",
            )
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm else np.array([0.5, 0.5], dtype="float32"))
        return np.stack(vectors)


class FakeFaiss:
    """Persist fake indexes by path for build-and-retrieve tests."""

    IndexFlatIP = FakeIndex
    indexes: dict[str, FakeIndex] = {}

    @classmethod
    def write_index(cls, index: FakeIndex, path: str) -> None:
        """Store an index and create its expected artifact."""
        cls.indexes[path] = index
        Path(path).write_bytes(b"fake-faiss")

    @classmethod
    def read_index(cls, path: str) -> FakeIndex:
        """Load an index previously stored by ``write_index``."""
        return cls.indexes[path]


def _install_fake_vectors(monkeypatch: Any) -> None:
    monkeypatch.setattr(rag, "_load_vector_dependencies", lambda model: (FakeFaiss, FakeModel()))


def test_load_and_chunk_json_preserves_citation_metadata(tmp_path: Path) -> None:
    source = tmp_path / "abstracts.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "C001",
                    "title": "Water catalysis",
                    "abstract": "Water supports this catalytic reaction.",
                    "doi": "10.1/demo",
                }
            ]
        ),
        encoding="utf-8",
    )

    documents = rag.load_documents([source])
    chunks = rag.chunk_documents(documents, chunk_size=100, chunk_overlap=10)

    assert chunks[0]["document_id"] == "C001"
    assert chunks[0]["doi"] == "10.1/demo"
    assert chunks[0]["source"] == str(source.resolve())


def test_build_and_retrieve_index(tmp_path: Path, monkeypatch: Any) -> None:
    _install_fake_vectors(monkeypatch)
    source = tmp_path / "abstracts.json"
    source.write_text(
        json.dumps(
            [
                {"id": "water", "title": "Water", "abstract": "Water solvent study."},
                {"id": "cat", "title": "Catalysis", "abstract": "Catalytic cycle study."},
            ]
        ),
        encoding="utf-8",
    )
    index_dir = tmp_path / "rag"

    built = rag.build_index([source], index_dir, chunk_size=100, chunk_overlap=10)
    result = rag.retrieve("Which study uses water?", index_dir, top_k=1)

    assert built["success"] is True
    assert (index_dir / "index.faiss").exists()
    assert result["success"] is True
    assert result["matches"][0]["document_id"] == "water"


def test_openalex_normalization_restores_abstract() -> None:
    result = rag._normalize_openalex_work(
        {
            "id": "https://openalex.org/W1",
            "title": "Demo",
            "abstract_inverted_index": {"Water": [0], "works": [1]},
            "authorships": [],
            "primary_location": {},
        }
    )

    assert result["id"] == "W1"
    assert result["abstract"] == "Water works"


def test_answer_uses_openrouter_and_returns_retrieved_sources(
    tmp_path: Path, monkeypatch: Any
) -> None:
    async def create(**kwargs: Any) -> Any:
        assert "[1] Water paper" in kwargs["messages"][1]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Water is supported [1]."))]
        )

    class FakeClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        rag,
        "retrieve",
        lambda *args, **kwargs: {
            "success": True,
            "matches": [{"title": "Water paper", "text": "Water evidence.", "page": 2}],
        },
    )
    monkeypatch.setattr(rag, "create_openrouter_client", lambda **kwargs: FakeClient())

    result = rag.answer_question_sync("What uses water?", tmp_path, model="demo/model")

    assert result["answer"] == "Water is supported [1]."
    assert result["model"] == "demo/model"
    assert result["matches"][0]["page"] == 2
    assert result["citations"][0]["title"] == "Water paper"


def test_rag_cli_retrieve_only_prints_and_saves_result(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "cspilot.cli.retrieve",
        lambda *args, **kwargs: {
            "success": True,
            "tool": "retrieve_literature",
            "error": None,
            "metadata": {},
            "matches": [],
        },
    )

    result = CliRunner().invoke(
        app,
        ["rag", "query", "water", "--index-dir", str(tmp_path), "--retrieve-only"],
    )

    assert result.exit_code == 0
    assert "retrieve_literature" in result.stdout
    assert (tmp_path / "query_result.json").exists()
