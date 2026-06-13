from pathlib import Path

import pytest

from app.models.medical_rule import MedicalRule
from app.services.exceptions import RagDataNotReadyError
from app.services.medical_rules import MedicalRuleSourceLoader


def test_medical_rule_normalizes_duration_up_to_allowed_value() -> None:
    rule = MedicalRule(
        procedure_name="Konsultacja neurologiczna",
        specialty="Neurologia",
        duration_minutes=75,
        duration_rationale="Wymaga badania neurologicznego.",
    )

    assert rule.duration_minutes == 90


def test_loader_reads_valid_csv_rules(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.csv"
    rule_file.write_text(
        "\n".join(
            [
                "procedure_name,specialty,duration_minutes,duration_rationale,"
                "patient_preparation,contraindications_for_auto_booking,source",
                "Konsultacja internistyczna,POZ,30,Standardowa konsultacja,"
                "Lista lekow,Objawy alarmowe; silny bol,Demo",
            ]
        ),
        encoding="utf-8",
    )

    documents = MedicalRuleSourceLoader(tmp_path).load_documents()

    assert len(documents) == 1
    assert documents[0].heading == "POZ - Konsultacja internistyczna"
    assert "Czas trwania: 30 minut" in documents[0].text
    assert "Objawy alarmowe; silny bol" in documents[0].text


def test_loader_reports_invalid_csv_row_with_context(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.csv"
    rule_file.write_text(
        "\n".join(
            [
                "procedure_name,specialty,duration_minutes,duration_rationale",
                "Konsultacja internistyczna,POZ,not-a-number,Standardowa konsultacja",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RagDataNotReadyError, match=r"rules\.csv: row 2"):
        MedicalRuleSourceLoader(tmp_path).load_documents()


def test_loader_reads_valid_jsonl_rules(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.jsonl"
    rule_file.write_text(
        (
            '{"procedure_name":"Pierwsza fizjoterapia","specialty":"Fizjoterapia",'
            '"duration_minutes":60,"duration_rationale":"Wywiad i badanie funkcjonalne."}\n'
        ),
        encoding="utf-8",
    )

    documents = MedicalRuleSourceLoader(tmp_path).load_documents()

    assert len(documents) == 1
    assert documents[0].heading == "Fizjoterapia - Pierwsza fizjoterapia"
    assert "Wywiad i badanie funkcjonalne" in documents[0].text


def test_loader_reports_invalid_jsonl_line_with_context(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.jsonl"
    rule_file.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(RagDataNotReadyError, match=r"rules\.jsonl: line 1"):
        MedicalRuleSourceLoader(tmp_path).load_documents()


def test_loader_reads_structured_markdown_rules(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.md"
    rule_file.write_text(
        """
## Konsultacja stomatologiczna
procedure_name: Konsultacja stomatologiczna
specialty: Stomatologia
duration_minutes: 45
duration_rationale: Badanie jamy ustnej i plan leczenia.
patient_preparation: Dokumentacja poprzedniego leczenia.
contraindications_for_auto_booking: silny obrzęk; gorączka
source: Demo stomatologia
""".strip(),
        encoding="utf-8",
    )

    documents = MedicalRuleSourceLoader(tmp_path).load_documents()

    assert len(documents) == 1
    assert documents[0].heading == "Stomatologia - Konsultacja stomatologiczna"
    assert "Czas trwania: 60 minut" in documents[0].text


def test_loader_reports_invalid_structured_markdown_with_context(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.md"
    rule_file.write_text(
        """
## Missing duration
procedure_name: Konsultacja kontrolna
specialty: POZ
duration_rationale: Kontrola po leczeniu.
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RagDataNotReadyError, match=r"rules\.md: block 1"):
        MedicalRuleSourceLoader(tmp_path).load_documents()


def test_medical_rule_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs"):
        MedicalRule.model_validate(
            {
                "procedure_name": "Konsultacja",
                "specialty": "POZ",
                "duration_minutes": 30,
                "duration_rationale": "Standardowa konsultacja.",
                "unexpected_field": "typo",
            }
        )


def test_loader_keeps_legacy_markdown_as_source_document(tmp_path: Path) -> None:
    rule_file = tmp_path / "legacy.md"
    rule_file.write_text("# Zasady\nKonsultacja POZ trwa zwykle 30 minut.", encoding="utf-8")

    documents = MedicalRuleSourceLoader(tmp_path).load_documents()

    assert len(documents) == 1
    assert documents[0].heading == "Zasady"
    assert documents[0].text.startswith("# Zasady")


def test_loader_skips_examples_and_schema_directories(tmp_path: Path) -> None:
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "rules.csv").write_text(
        "procedure_name,specialty,duration_minutes,duration_rationale\n"
        "Example,Demo,30,Example only\n",
        encoding="utf-8",
    )
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "medical_rule.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "active.md").write_text("# Active\nKonsultacja trwa 30 minut.", encoding="utf-8")

    documents = MedicalRuleSourceLoader(tmp_path).load_documents()

    assert len(documents) == 1
    assert documents[0].path.name == "active.md"
