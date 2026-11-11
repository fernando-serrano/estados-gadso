"""Vista consolidada `sucamec_colaboradores`: una fila por "<NEGOCIO>:<dni>" que une

  - estados_sucamec_agentes  (bot estados-gadso: estado, carne, cursos, licencia...)
  - carnet_sucamec_agentes   (bot carnet: PDF del carne en MinIO)

Es una vista (no copia datos): siempre refleja lo ultimo que escribio cada bot.
Las fechas de carnet se normalizan a Date con $toDate, que acepta tanto el texto
ISO actual ("2026-10-27", "2026-10-27T12:11:36") como Date, asi que la vista sigue
funcionando cuando el bot de carnet migre a fechas Date.
"""
from __future__ import annotations

from typing import Any

from pymongo.database import Database

VISTA = "sucamec_colaboradores"
ESTADOS = "estados_sucamec_agentes"
CARNET = "carnet_sucamec_agentes"


def _fecha(expr: str) -> dict[str, Any]:
    return {"$convert": {"input": expr, "to": "date", "onError": None, "onNull": None}}


def pipeline(prefix: str = "") -> list[dict[str, Any]]:
    estados, carnet = f"{prefix}{ESTADOS}", f"{prefix}{CARNET}"
    return [
        {"$project": {"_id": 1}},
        {"$unionWith": {"coll": carnet, "pipeline": [{"$project": {"_id": 1}}]}},
        {"$group": {"_id": "$_id"}},
        {"$lookup": {"from": estados, "localField": "_id", "foreignField": "_id", "as": "e"}},
        {"$lookup": {"from": carnet, "localField": "_id", "foreignField": "_id", "as": "c"}},
        {"$set": {"e": {"$first": "$e"}, "c": {"$first": "$c"}}},
        {"$project": {
            "negocio": {"$ifNull": ["$e.negocio", "$c.negocio"]},
            "dni": {"$ifNull": ["$e.dni", "$c.dni"]},
            "tipo_documento": {"$ifNull": ["$e.tipo_documento", "DNI"]},
            "nombre": {"$ifNull": ["$e.nombre", None]},
            # Resumen para listados / filtros rapidos
            "estado": {"$ifNull": ["$e.estado", None]},
            "estado_detalle": {"$ifNull": ["$e.estado_detalle", None]},
            "tiene_carnet_pdf": {"$cond": [{"$ifNull": ["$c.minio_key", False]}, True, False]},
            "ultima_actualizacion": {"$max": ["$e.ultima_consulta", _fecha("$c.ultima_consulta")]},
            # Fuente 1: consulta de estados SUCAMEC
            "estado_sucamec": {"$cond": [{"$ifNull": ["$e", False]}, {
                "estado": "$e.estado",
                "estado_detalle": "$e.estado_detalle",
                "estado_anterior": "$e.estado_anterior",
                "cambio_estado_en": "$e.cambio_estado_en",
                "fuente": "$e.fuente",
                "carne": "$e.carne",
                "cursos": "$e.cursos",
                "licencia": "$e.licencia",
                "historial_laboral": "$e.historial_laboral",
                "historial": "$e.historial",
                "ultimo_intento_fallido": "$e.ultimo_intento_fallido",
                "corrida": "$e.corrida",
                "ultima_consulta": "$e.ultima_consulta",
            }, None]},
            # Fuente 2: carne descargado (PDF en MinIO)
            "carnet_pdf": {"$cond": [{"$ifNull": ["$c", False]}, {
                "estado": "$c.estado_carnet",
                "fecha_emision": _fecha("$c.fecha_emision"),
                "fuente": "$c.fuente",
                "minio_bucket": "$c.minio_bucket",
                "minio_key": "$c.minio_key",
                "sha256": "$c.sha256",
                "corrida": "$c.corrida",
                "ultima_consulta": _fecha("$c.ultima_consulta"),
                "historial": {"$map": {"input": {"$ifNull": ["$c.historial", []]}, "as": "h", "in": {
                    "corrida": "$$h.corrida",
                    "consultado_en": _fecha("$$h.consultado_en"),
                    "estado": "$$h.estado",
                    "fecha_emision": _fecha("$$h.fecha_emision"),
                    "minio_key": "$$h.minio_key",
                }}},
            }, None]},
        }},
    ]


def ensure_vista(db: Database, prefix: str = "") -> None:
    """Crea o actualiza la vista (idempotente)."""
    nombre = f"{prefix}{VISTA}"
    cmd = "collMod" if nombre in db.list_collection_names(filter={"name": nombre}) else "create"
    db.command(cmd, nombre, viewOn=f"{prefix}{ESTADOS}", pipeline=pipeline(prefix))
