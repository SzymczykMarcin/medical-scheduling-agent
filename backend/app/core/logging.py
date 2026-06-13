import logging
import os
from pathlib import Path
import sys


LOG_FILE_PATH = Path(__file__).resolve().parents[2] / "logs" / "runtime.log"


def configure_logging() -> None:
    """Configure concise application logging for local development."""
    stream_handler = logging.StreamHandler(sys.stdout)
    handlers: list[logging.Handler] = [stream_handler]

    if os.getenv("MEDICAL_DISABLE_FILE_LOG") != "1":
        LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )
