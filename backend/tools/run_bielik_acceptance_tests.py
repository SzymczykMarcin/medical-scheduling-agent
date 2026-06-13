import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run local Bielik RAG scheduler acceptance tests and write HTML reports."""
    backend_dir = Path(__file__).resolve().parents[1]
    repo_dir = backend_dir.parent
    reports_dir = repo_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["RUN_LOCAL_AI_TESTS"] = "1"

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/local_ai/test_bielik_rag_scheduler_acceptance.py",
        "-m",
        "local_ai",
        "-p",
        "no:cacheprovider",
        "--html",
        str(reports_dir / "bielik_rag_scheduler_pytest.html"),
        "--self-contained-html",
        "-q",
    ]
    return subprocess.call(command, cwd=backend_dir, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
