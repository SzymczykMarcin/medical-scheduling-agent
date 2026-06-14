import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_TOOL_PATH = REPO_ROOT / "tools" / "run_demo_smoke.py"


def load_smoke_tool():
    spec = importlib.util.spec_from_file_location("run_demo_smoke", SMOKE_TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_report_marks_all_passed_checks(tmp_path) -> None:
    smoke_tool = load_smoke_tool()
    checks = [
        smoke_tool.CheckResult(name="health", status="pass", elapsed_ms=1.0, details={}),
        smoke_tool.CheckResult(name="calendar", status="pass", elapsed_ms=2.0, details={}),
    ]
    report_path = tmp_path / "report.json"

    smoke_tool.write_report(report_path, "http://127.0.0.1:8097", checks)

    content = report_path.read_text(encoding="utf-8")
    assert '"status": "pass"' in content
    assert '"backend_url": "http://127.0.0.1:8097"' in content


def test_smoke_report_marks_failed_checks(tmp_path) -> None:
    smoke_tool = load_smoke_tool()
    checks = [
        smoke_tool.CheckResult(
            name="debug_analysis",
            status="fail",
            elapsed_ms=3.0,
            details={"error": "RAG is not ready"},
        )
    ]
    report_path = tmp_path / "report.json"

    smoke_tool.write_report(report_path, "http://127.0.0.1:8097", checks)

    content = report_path.read_text(encoding="utf-8")
    assert '"status": "fail"' in content
    assert "RAG is not ready" in content
