from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


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

    logger.info("Log inicializado en %s", log_file)
    return logger
