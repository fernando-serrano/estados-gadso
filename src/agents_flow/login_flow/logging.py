from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def _max_log_files() -> int:
    try:
        return max(1, int(str(os.getenv("SUCAMEC_LOG_MAX_FILES", "10")).strip()))
    except Exception:
        return 10


def _prune_old_logs(logs_dir: Path, name: str, keep_files: int, protected_file: Path) -> int:
    protected = protected_file.resolve()
    files = [
        path
        for path in logs_dir.glob(f"{name}_*.log")
        if path.is_file() and path.resolve() != protected
    ]
    keep_previous = max(0, keep_files - 1)
    if len(files) <= keep_previous:
        return 0

    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    deleted = 0
    for old_file in files[keep_previous:]:
        try:
            old_file.unlink()
            deleted += 1
        except Exception:
            continue
    return deleted


def build_logger(logs_dir: Path, name: str = "sucamec_estado") -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    log_file = logs_dir / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    deleted_logs = _prune_old_logs(
        logs_dir,
        name=name,
        keep_files=_max_log_files(),
        protected_file=log_file,
    )
    logger.info("Log inicializado en %s", log_file)
    if deleted_logs:
        logger.info("Control de logs aplicado: %s log(s) antiguo(s) eliminado(s)", deleted_logs)
    return logger
