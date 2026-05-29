from __future__ import annotations

import logging
from pathlib import Path


def setup_file_logger(*, log_path: Path) -> logging.Logger:
    """파일 로거를 1회 구성해서 반환합니다."""

    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("gobang_finder")
    logger.setLevel(logging.INFO)

    # 중복 핸들러 방지
    for h in list(logger.handlers):
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path:
            return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger
