from __future__ import annotations

import sys
import traceback
from pathlib import Path

import webview

from backend import GobangAPI
from logging_utils import setup_file_logger

ROOT     = Path(__file__).resolve().parent
LOG_PATH = ROOT / "logs" / "app.log"
INDEX    = ROOT / "frontend" / "index.html"

logger = setup_file_logger(log_path=LOG_PATH)


def main() -> None:
    try:
        api = GobangAPI()
        webview.create_window(
            "고방 찾기  —  방극",
            str(INDEX),
            js_api=api,
            width=1160,
            height=760,
            min_size=(920, 620),
        )
        webview.start()
    except Exception:
        logger.exception("Unhandled exception in main")
        print(traceback.format_exc(), file=sys.stderr)


if __name__ == "__main__":
    main()
