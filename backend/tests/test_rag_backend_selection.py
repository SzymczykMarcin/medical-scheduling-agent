import builtins
from pathlib import Path

from app.core.settings import Settings
from app.services.rag_retrieval import create_knowledge_base_retriever


def test_file_backend_selection_does_not_import_vector_store_dependencies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    (rag_dir / "rules.md").write_text("# Rules\nKonsultacja trwa 30 minut.", encoding="utf-8")
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name.startswith(("chromadb", "google.cloud")):
            raise AssertionError(f"Unexpected import in file RAG mode: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    retriever = create_knowledge_base_retriever(
        Settings(rag_backend="file", rag_document_dir=str(rag_dir))
    )
    passages = retriever.retrieve("konsultacja", limit=1)

    assert len(passages) == 1
