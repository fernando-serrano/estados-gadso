from __future__ import annotations

import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _max_run_dirs() -> int:
    try:
        return max(1, int(str(os.getenv("SUCAMEC_LOG_MAX_RUNS", os.getenv("SUCAMEC_LOG_MAX_FILES", "10"))).strip()))
    except Exception:
        return 10


def _prune_old_run_dirs(logs_dir: Path, keep_dirs: int, protected_dir: Path) -> int:
    protected = protected_dir.resolve()
    files = [
        path
        for path in logs_dir.iterdir()
        if path.is_dir() and path.resolve() != protected
    ]
    keep_previous = max(0, keep_dirs - 1)
    if len(files) <= keep_previous:
        return 0

    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    deleted = 0
    for old_dir in files[keep_previous:]:
        try:
            shutil.rmtree(old_dir)
            deleted += 1
        except Exception:
            continue
    return deleted


def _console_handler() -> logging.StreamHandler:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    return handler


def build_subflow_logger(run_dir: Path, subflow_name: str, console_handler: logging.Handler | None = None) -> logging.Logger:
    log_dir = run_dir / subflow_name
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_name = f"{run_dir.name}.{subflow_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    log_file = log_dir / f"{subflow_name}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console_handler is not None:
        logger.addHandler(console_handler)

    logger.info("Log de subflujo inicializado en %s", log_file)
    return logger


class RunLoggers:
    def __init__(self, logs_dir: Path, run_name: str | None = None):
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = logs_dir
        self.run_name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = logs_dir / self.run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.console_handler = _console_handler()
        self._loggers: dict[str, logging.Logger] = {}

        self._deleted_dirs = _prune_old_run_dirs(
            logs_dir,
            keep_dirs=_max_run_dirs(),
            protected_dir=self.run_dir,
        )
        self._retention_logged = False

    def get(self, subflow_name: str) -> logging.Logger:
        if subflow_name not in self._loggers:
            self._loggers[subflow_name] = build_subflow_logger(
                self.run_dir,
                subflow_name,
                console_handler=self.console_handler,
            )
            if self._deleted_dirs and not self._retention_logged:
                self._loggers[subflow_name].info(
                    "Control de logs aplicado: %s corrida(s) antigua(s) eliminada(s)",
                    self._deleted_dirs,
                )
                self._retention_logged = True
        return self._loggers[subflow_name]

    def close(self) -> None:
        for logger in self._loggers.values():
            for handler in list(logger.handlers):
                try:
                    handler.flush()
                except Exception:
                    pass
                if isinstance(handler, logging.FileHandler):
                    logger.removeHandler(handler)
                    try:
                        handler.close()
                    except Exception:
                        pass
        try:
            self.console_handler.flush()
        except Exception:
            pass


def build_logger(logs_dir: Path, name: str = "sucamec_estado") -> logging.Logger:
    """Compatibilidad: crea una corrida y retorna un logger para `name`."""
    return RunLoggers(logs_dir).get(name)
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
