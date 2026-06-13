import gc
import html
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.core.settings import Settings
from app.models.appointment import AppointmentIntent
from app.models.calendar import CalendarEvent
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError
from app.services.rag import RagAnalysisService
from app.services.scheduler import SchedulerService
from app.services.sms import SmsSimulationService

REPORT_DIR = Path(__file__).resolve().parents[3] / "reports"
SUMMARY_REPORT_PATH = REPORT_DIR / "bielik_rag_scheduler_acceptance.html"
RUN_LOCAL_AI_ENV = "RUN_LOCAL_AI_TESTS"
RESULTS: list[dict[str, Any]] = []


@dataclass(frozen=True)
class ExpectedOutcome:
    """Expected observable result for one transcript scheduling case."""

    status: str
    day_iso: str | None = None
    start_time: str | None = None
    duration_minutes: int | None = None
    sms_contains: str | None = None


@dataclass(frozen=True)
class AcceptanceCase:
    """One ISTQB-style acceptance scenario for the AI scheduling flow."""

    case_id: str
    title: str
    objective: str
    transcript: str
    expected: ExpectedOutcome


CASES = [
    AcceptanceCase(
        case_id="AI-SCHED-001",
        title="Simple POZ visit with free Tuesday slot",
        objective="Verify that an explicit Polish weekday and time window are respected.",
        transcript=(
            "Dzień dobry, boli mnie gardło i mam gorączkę. "
            "Chciałbym wizytę we wtorek po godzinie dziesiątej."
        ),
        expected=ExpectedOutcome(
            status="scheduled",
            day_iso="2026-06-09",
            start_time="10:30",
            duration_minutes=30,
            sms_contains="Wizyta została umówiona",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-002",
        title="Occupied exact Monday slot",
        objective="Verify that a busy specific datetime is rejected instead of moved silently.",
        transcript=(
            "Potrzebuję krótkiej konsultacji u lekarza rodzinnego. "
            "Pasuje mi konkretnie poniedziałek o dziewiątej rano."
        ),
        expected=ExpectedOutcome(
            status="needs_callback",
            sms_contains="skontaktuje się telefonicznie",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-003",
        title="Long laboratory procedure from RAG",
        objective="Verify that OGTT is mapped to a long slot using RAG duration rules.",
        transcript=(
            "Chcę umówić krzywą cukrową OGTT. Może być we wtorek, "
            "najlepiej dowolna wolna godzina."
        ),
        expected=ExpectedOutcome(
            status="scheduled",
            day_iso="2026-06-09",
            start_time="12:30",
            duration_minutes=120,
            sms_contains="Wizyta została umówiona",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-004",
        title="USG abdomen after noon",
        objective="Verify that USG abdomen receives a short diagnostic slot from RAG.",
        transcript="Potrzebuję USG jamy brzusznej w środę po dwunastej.",
        expected=ExpectedOutcome(
            status="scheduled",
            day_iso="2026-06-10",
            start_time="12:30",
            duration_minutes=30,
            sms_contains="Wizyta została umówiona",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-005",
        title="Insufficient visit reason",
        objective="Verify that missing medical/procedural reason requires human callback.",
        transcript="Chcę się umówić na wizytę, ale nie wiem jeszcze po co. Może wtorek.",
        expected=ExpectedOutcome(
            status="needs_callback",
            sms_contains="skontaktuje się telefonicznie",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-006",
        title="Multiple day preferences and exclusion",
        objective="Verify that explicit positive weekday preferences and exclusions are respected.",
        transcript=(
            "Potrzebuję kontroli leków. Może być wtorek albo środa, ale nie czwartek. "
            "We wtorek pasuje mi po dziesiątej, a w środę nie później niż piętnasta."
        ),
        expected=ExpectedOutcome(
            status="scheduled",
            day_iso="2026-06-09",
            start_time="10:30",
            duration_minutes=30,
            sms_contains="Wizyta została umówiona",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-007",
        title="Alarm symptoms",
        objective="Verify that potentially urgent symptoms are not booked automatically.",
        transcript="Mam ból w klatce piersiowej i duszność w spoczynku. Chcę wizytę dzisiaj.",
        expected=ExpectedOutcome(
            status="needs_callback",
            sms_contains="skontaktuje się telefonicznie",
        ),
    ),
    AcceptanceCase(
        case_id="AI-SCHED-008",
        title="Full body mole check from dermatology rules",
        objective="Verify that full-body mole review receives a longer dermatology slot.",
        transcript="Chcę sprawdzić wszystkie pieprzyki u dermatologa. Najlepiej w piątek.",
        expected=ExpectedOutcome(
            status="scheduled",
            day_iso="2026-06-12",
            start_time="10:00",
            duration_minutes=60,
            sms_contains="Wizyta została umówiona",
        ),
    ),
]


@pytest.fixture(scope="session", autouse=True)
def local_ai_gate() -> None:
    """Skip local AI tests unless explicitly requested."""
    if os.getenv(RUN_LOCAL_AI_ENV) != "1":
        pytest.skip(f"Set {RUN_LOCAL_AI_ENV}=1 to run local Bielik acceptance tests.")


@pytest.fixture(scope="session")
def ai_services():
    """Create and release local AI services for the acceptance suite."""
    settings = Settings(
        retrieval_limit=4,
        llm_temperature=0.0,
        llm_max_new_tokens=700,
    )
    analyzer = RagAnalysisService(settings=settings)
    sms = SmsSimulationService()
    try:
        yield analyzer, sms
    finally:
        analyzer.llm = None
        analyzer.retriever = None
        gc.collect()
        _empty_cuda_cache()


@pytest.fixture(scope="session", autouse=True)
def html_summary_report():
    """Write a compact human-readable HTML report after the suite finishes."""
    RESULTS.clear()
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_REPORT_PATH.write_text(_render_html_report(RESULTS), encoding="utf-8")


@pytest.mark.local_ai
@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_bielik_rag_scheduler_acceptance(case: AcceptanceCase, ai_services) -> None:
    analyzer, sms = ai_services
    scheduler = SchedulerService(today=date(2026, 6, 12))

    actual = _execute_case(
        case=case,
        analyzer=analyzer,
        scheduler=scheduler,
        sms=sms,
    )
    expected = _expected_to_report(case.expected)
    passed, mismatches = _compare_expected(case.expected, actual)

    RESULTS.append(
        {
            "case_id": case.case_id,
            "title": case.title,
            "objective": case.objective,
            "input": case.transcript,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "mismatches": mismatches,
        }
    )

    assert passed, "; ".join(mismatches)


def _execute_case(
    case: AcceptanceCase,
    analyzer: RagAnalysisService,
    scheduler: SchedulerService,
    sms: SmsSimulationService,
) -> dict[str, Any]:
    try:
        intent = analyzer.analyze(
            transcript=case.transcript,
            availability_summary=scheduler.availability_summary(),
            today=scheduler.week_start,
        )
        result = scheduler.schedule_from_intent(intent)
    except (RagAnalysisError, RagDataNotReadyError) as exc:
        intent = _callback_intent(case.transcript, str(exc))
        result = scheduler.callback_result("Automatyczna analiza wymaga kontaktu telefonicznego.")

    sms_text = sms.render(result)
    return {
        "status": result.status,
        "event": _event_to_report(result.event),
        "intent": intent.model_dump(mode="json"),
        "sms_text": sms_text,
        "scheduling_explanation": result.explanation,
    }


def _callback_intent(transcript: str, explanation: str) -> AppointmentIntent:
    return AppointmentIntent(
        visit_reason="Wymagany kontakt telefoniczny",
        procedure_hint=None,
        preferred_time=None,
        urgency="nieznana",
        duration_minutes=30,
        confidence=0.0,
        requires_human_callback=True,
        explanation=f"{explanation} Transkrypcja: {transcript[:200]}",
    )


def _event_to_report(event: CalendarEvent | None) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "id": event.id,
        "title": event.title,
        "patient_label": event.patient_label,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "duration_minutes": event.duration_minutes,
        "status": event.status,
    }


def _expected_to_report(expected: ExpectedOutcome) -> dict[str, Any]:
    return {
        "status": expected.status,
        "day_iso": expected.day_iso,
        "start_time": expected.start_time,
        "duration_minutes": expected.duration_minutes,
        "sms_contains": expected.sms_contains,
    }


def _compare_expected(expected: ExpectedOutcome, actual: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    event = actual["event"]

    if actual["status"] != expected.status:
        mismatches.append(f"status expected {expected.status}, got {actual['status']}")

    if expected.day_iso is not None:
        actual_day = event["start"][:10] if event else None
        if actual_day != expected.day_iso:
            mismatches.append(f"day expected {expected.day_iso}, got {actual_day}")

    if expected.start_time is not None:
        actual_time = event["start"][11:16] if event else None
        if actual_time != expected.start_time:
            mismatches.append(f"start_time expected {expected.start_time}, got {actual_time}")

    if expected.duration_minutes is not None:
        actual_duration = event["duration_minutes"] if event else actual["intent"].get("duration_minutes")
        if actual_duration != expected.duration_minutes:
            mismatches.append(
                f"duration_minutes expected {expected.duration_minutes}, got {actual_duration}"
            )

    if expected.sms_contains and expected.sms_contains not in actual["sms_text"]:
        mismatches.append(f"sms_text does not contain {expected.sms_contains!r}")

    return not mismatches, mismatches


def _render_html_report(results: list[dict[str, Any]]) -> str:
    passed_count = sum(1 for result in results if result["passed"])
    failed_count = len(results) - passed_count
    rows = "\n".join(_render_result_row(result) for result in results)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Bielik RAG Scheduler Acceptance Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #17302b; }}
    h1 {{ margin-bottom: 4px; }}
    .summary {{ margin: 12px 0 24px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #c9ded9; padding: 10px; vertical-align: top; }}
    th {{ background: #eaf5f2; text-align: left; }}
    tr.pass {{ background: #f2fbf7; }}
    tr.fail {{ background: #fff4f4; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; margin: 0; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-weight: 700; }}
    .pass .badge {{ background: #cdeedd; color: #075f3d; }}
    .fail .badge {{ background: #ffd5d5; color: #8a1111; }}
  </style>
</head>
<body>
  <h1>Bielik + RAG + Scheduler acceptance report</h1>
  <div class="summary">Total: {len(results)} | Passed: {passed_count} | Failed: {failed_count}</div>
  <table>
    <thead>
      <tr>
        <th>Case</th>
        <th>Input transcript</th>
        <th>Expected</th>
        <th>Actual output</th>
        <th>Result</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""


def _render_result_row(result: dict[str, Any]) -> str:
    row_class = "pass" if result["passed"] else "fail"
    badge = "PASS" if result["passed"] else "FAIL"
    details = "OK" if result["passed"] else "\n".join(result["mismatches"])
    return f"""<tr class="{row_class}">
  <td><strong>{html.escape(result["case_id"])}</strong><br>{html.escape(result["title"])}<br><small>{html.escape(result["objective"])}</small></td>
  <td><pre>{html.escape(result["input"])}</pre></td>
  <td><pre>{html.escape(json.dumps(result["expected"], ensure_ascii=False, indent=2))}</pre></td>
  <td><pre>{html.escape(json.dumps(result["actual"], ensure_ascii=False, indent=2))}</pre></td>
  <td><span class="badge">{badge}</span><pre>{html.escape(details)}</pre></td>
</tr>"""


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        return
