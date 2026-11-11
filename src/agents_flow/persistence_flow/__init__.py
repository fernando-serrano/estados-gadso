"""Persistencia de resultados de estados SUCAMEC en MongoDB (plataforma del area)."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .mapper import build_snapshot, normalizar_estado, parse_fecha
from .repository import EstadosRepository
from .vista import ensure_vista

__all__ = ["EstadosRepository", "build_snapshot", "normalizar_estado", "parse_fecha", "persist_run_results"]


def _enabled() -> bool:
    return str(os.getenv("MONGO_ENABLED", "0")).strip().lower() in {"1", "true", "yes", "si", "sí"}


def _inicio_desde_corrida(corrida: str) -> datetime | None:
    try:
        return datetime.strptime(corrida[:15], "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def get_repository() -> EstadosRepository:
    from pymongo import MongoClient

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL no configurada")
    client = MongoClient(url, serverSelectionTimeoutMS=10000, appname="estados-gadso")
    # MONGO_DATABASE manda sobre la BD del path de DATABASE_URL (los datos SUCAMEC viven en gadso_sucamec_db).
    nombre_bd = os.getenv("MONGO_DATABASE", "").strip()
    db = client[nombre_bd] if nombre_bd else client.get_default_database()
    return EstadosRepository(db, os.getenv("MONGO_COLLECTION_PREFIX", "").strip())


def persist_run_results(
    grupo: str,
    run_name: str,
    results: list[Any],
    attachments: list[Path] | None,
    logger: logging.Logger,
) -> dict[str, int] | None:
    """Guarda la corrida en Mongo. Nunca lanza: si Mongo falla, la corrida sigue (Excel + correo)."""
    if not _enabled():
        logger.info("[%s] Persistencia Mongo deshabilitada (MONGO_ENABLED=0)", grupo)
        return None
    try:
        repo = get_repository()
        repo.ensure_indexes()
        try:
            ensure_vista(repo.db, os.getenv("MONGO_COLLECTION_PREFIX", "").strip())
        except Exception as exc:  # noqa: BLE001 - sin permisos de vista igual se guardan los datos
            logger.warning("[%s] Mongo: no se pudo crear/actualizar la vista consolidada | %s", grupo, exc)
        stats = repo.guardar_resultados(results, grupo, run_name)
        repo.registrar_corrida(
            results, grupo, run_name, _inicio_desde_corrida(run_name), stats,
            archivos=[Path(p).name for p in (attachments or [])],
        )
        logger.info("[%s] Mongo: estados guardados | %s", grupo, stats)
        return stats
    except Exception as exc:  # noqa: BLE001 - la persistencia no debe tumbar la corrida
        logger.exception("[%s] Mongo: fallo la persistencia (corrida continua) | %s: %s",
                         grupo, type(exc).__name__, exc)
        return None
