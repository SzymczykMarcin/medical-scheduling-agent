import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_TRANSCRIPT = (
    "Dzień dobry, boli mnie głowa i chciałbym krótką wizytę we wtorek po 10."
)


@dataclass
class CheckResult:
    """One smoke-check result serialized into the demo report."""

    name: str
    status: str
    elapsed_ms: float
    details: dict[str, Any] = field(default_factory=dict)


def main() -> int:
    """Run a text-only smoke test against a running demo backend."""
    parser = argparse.ArgumentParser(description="Run Medical Scheduling Agent demo smoke checks.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8097")
    parser.add_argument("--transcript", default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--skip-rag-ingest", action="store_true")
    parser.add_argument(
        "--report",
        default=str(Path("reports") / "demo_smoke_report.json"),
        help="Path where the JSON report will be written.",
    )
    args = parser.parse_args()

    backend_url = args.backend_url.rstrip("/")
    checks = run_smoke_checks(
        backend_url=backend_url,
        transcript=args.transcript,
        skip_rag_ingest=args.skip_rag_ingest,
    )
    write_report(Path(args.report), backend_url, checks)
    print_summary(checks)
    return 0 if all(check.status == "pass" for check in checks) else 1


def run_smoke_checks(
    backend_url: str,
    transcript: str,
    skip_rag_ingest: bool = False,
) -> list[CheckResult]:
    """Run backend readiness checks in the same order a demo operator expects."""
    checks = [
        _check_health(backend_url),
        _check_calendar(backend_url),
    ]
    if not skip_rag_ingest:
        checks.append(_check_rag_ingest(backend_url))
    checks.append(_check_debug_analysis(backend_url, transcript))
    return checks


def write_report(path: Path, backend_url: str, checks: list[CheckResult]) -> None:
    """Write the smoke result to a local JSON report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "backend_url": backend_url,
        "generated_at_unix": int(time.time()),
        "status": "pass" if all(check.status == "pass" for check in checks) else "fail",
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "elapsed_ms": round(check.elapsed_ms, 1),
                "details": check.details,
            }
            for check in checks
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def print_summary(checks: list[CheckResult]) -> None:
    """Print a compact operator-friendly summary."""
    for check in checks:
        print(f"{check.status.upper():4} {check.name} ({check.elapsed_ms:.1f} ms)")
        if check.status != "pass":
            print(f"     {check.details.get('error', 'Unknown error')}")


def _check_health(backend_url: str) -> CheckResult:
    return _run_check("health", lambda: _json_request("GET", f"{backend_url}/health"))


def _check_calendar(backend_url: str) -> CheckResult:
    def operation() -> dict[str, Any]:
        events = _json_request("GET", f"{backend_url}/api/calendar/events")
        return {"event_count": len(events)}

    return _run_check("calendar_events", operation)


def _check_rag_ingest(backend_url: str) -> CheckResult:
    return _run_check("rag_ingest", lambda: _json_request("POST", f"{backend_url}/api/rag/ingest"))


def _check_debug_analysis(backend_url: str, transcript: str) -> CheckResult:
    def operation() -> dict[str, Any]:
        payload = {"transcript": transcript}
        response = _json_request(
            "POST",
            f"{backend_url}/api/debug/appointment-analysis",
            payload=payload,
        )
        return {
            "status": response.get("status"),
            "failed_stage": response.get("failed_stage"),
            "scheduler_status": (response.get("scheduler_result") or {}).get("status"),
        }

    return _run_check("debug_analysis", operation)


def _run_check(name: str, operation) -> CheckResult:
    started = time.perf_counter()
    try:
        details = operation()
        return CheckResult(
            name=name,
            status="pass",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            details=details if isinstance(details, dict) else {},
        )
    except Exception as exc:
        return CheckResult(
            name=name,
            status="fail",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            details={"error": str(exc)},
        )


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    http_request = request.Request(url, data=body, headers=headers, method=method)

    try:
        with request.urlopen(http_request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {response_body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
