import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.medical_rule import MedicalRule
from app.services.exceptions import RagDataNotReadyError


@dataclass(frozen=True)
class SourceDocument:
    """One validated source document ready for chunking and embedding."""

    path: Path
    text: str
    heading: str | None = None
    document_id: str | None = None


class MedicalRuleSourceLoader:
    """Load user-editable medical scheduling rules from supported source files."""

    def __init__(self, document_dir: Path) -> None:
        self.document_dir = document_dir

    def load_documents(self) -> list[SourceDocument]:
        """Load all supported rule documents from the configured directory."""
        if not self.document_dir.exists():
            raise RagDataNotReadyError(f"RAG document directory does not exist: {self.document_dir}")

        documents: list[SourceDocument] = []
        for path in sorted(self.document_dir.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            if any(part in {"examples", "schema"} for part in path.relative_to(self.document_dir).parts):
                continue
            if path.suffix.lower() == ".csv":
                documents.extend(self._load_csv(path))
            elif path.suffix.lower() == ".jsonl":
                documents.extend(self._load_jsonl(path))
            elif path.suffix.lower() in {".md", ".txt"}:
                documents.extend(self._load_markdown_or_text(path))

        if not documents:
            raise RagDataNotReadyError(f"No RAG source documents found in: {self.document_dir}")

        return documents

    def _load_csv(self, path: Path) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            if not reader.fieldnames:
                raise RagDataNotReadyError(f"{path}: CSV file has no header row.")
            for row_number, row in enumerate(reader, start=2):
                rule = _validate_rule(row, path=path, location=f"row {row_number}")
                documents.append(_rule_to_document(rule, path, row_number))
        return documents

    def _load_jsonl(self, path: Path) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise RagDataNotReadyError(f"{path}: line {line_number}: invalid JSON.") from exc
            if not isinstance(payload, dict):
                raise RagDataNotReadyError(f"{path}: line {line_number}: JSON value must be an object.")
            rule = _validate_rule(payload, path=path, location=f"line {line_number}")
            documents.append(_rule_to_document(rule, path, line_number))
        return documents

    def _load_markdown_or_text(self, path: Path) -> list[SourceDocument]:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []

        if _looks_like_structured_markdown(text):
            return self._load_structured_markdown(path, text)

        return [SourceDocument(path=path, text=text, heading=_first_heading(text), document_id=path.stem)]

    def _load_structured_markdown(self, path: Path, text: str) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        for block_number, block in enumerate(_markdown_rule_blocks(text), start=1):
            payload = _parse_markdown_fields(block)
            rule = _validate_rule(payload, path=path, location=f"block {block_number}")
            documents.append(_rule_to_document(rule, path, block_number))
        return documents


def _validate_rule(payload: dict[str, Any], path: Path, location: str) -> MedicalRule:
    try:
        return MedicalRule.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise RagDataNotReadyError(f"{path}: {location}: invalid medical rule: {details}") from exc


def _rule_to_document(rule: MedicalRule, path: Path, index: int) -> SourceDocument:
    return SourceDocument(
        path=path,
        text=rule.to_rag_text(),
        heading=f"{rule.specialty} - {rule.procedure_name}",
        document_id=f"{path.stem}-{index}",
    )


def _looks_like_structured_markdown(text: str) -> bool:
    required_markers = ("procedure_name:", "specialty:", "duration_minutes:")
    lower_text = text.lower()
    return any(marker in lower_text for marker in required_markers)


def _markdown_rule_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if _looks_like_structured_markdown(block)]


def _parse_markdown_fields(block: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_key in {
            "procedure_name",
            "specialty",
            "duration_minutes",
            "duration_rationale",
            "patient_preparation",
            "contraindications_for_auto_booking",
            "source",
        }:
            payload[normalized_key] = value.strip()
    return payload


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None
