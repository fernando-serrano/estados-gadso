"""Escritura de estados SUCAMEC en MongoDB.

Colecciones (prefijo opcional para pruebas):
  - estados_sucamec_agentes : estado actual, 1 doc por "<NEGOCIO>:<dni>"
  - estados_sucamec_corridas: 1 doc por corrida y negocio (auditoria)
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.database import Database

from .mapper import ESTADOS_FALLO, build_snapshot

HISTORIAL_MAX = 50


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EstadosRepository:
    def __init__(self, db: Database, prefix: str = "") -> None:
        self.db = db
        self.agentes = db[f"{prefix}estados_sucamec_agentes"]
        self.corridas = db[f"{prefix}estados_sucamec_corridas"]

    def ensure_indexes(self) -> None:
        self.agentes.create_index([("negocio", ASCENDING), ("estado", ASCENDING)])
        self.agentes.create_index([("dni", ASCENDING)])
        self.agentes.create_index([("corrida", ASCENDING)])
        self.agentes.create_index([("nombre", ASCENDING)])
        self.agentes.create_index([("carne.fecha_emision", ASCENDING)])
        self.corridas.create_index([("negocio", ASCENDING), ("inicio", DESCENDING)])

    def guardar_resultados(
        self,
        results: Iterable[Any],
        negocio: str,
        corrida: str,
        consultado_en: datetime | None = None,
    ) -> dict[str, int]:
        consultado_en = consultado_en or _ahora()
        snapshots: dict[str, dict[str, Any]] = {}
        for result in results:
            snap = build_snapshot(result, negocio)
            if snap["dni"]:
                snapshots[snap["_id"]] = snap  # si un dni viniera repetido, gana el ultimo

        previos = {
            d["_id"]: d
            for d in self.agentes.find(
                {"_id": {"$in": list(snapshots)}}, {"estado": 1, "estado_detalle": 1}
            )
        }

        ops: list[UpdateOne] = []
        stats = Counter()
        for _id, snap in snapshots.items():
            previo = previos.get(_id)
            entrada_hist = {
                "corrida": corrida,
                "consultado_en": consultado_en,
                "estado": snap["estado"],
                "estado_detalle": snap["estado_detalle"],
            }

            # Un fallo del bot no debe borrar un estado bueno ya conocido.
            if snap["estado"] in ESTADOS_FALLO and previo and previo.get("estado") not in ESTADOS_FALLO:
                ops.append(UpdateOne({"_id": _id}, {"$set": {
                    "ultimo_intento_fallido": entrada_hist,
                    "actualizado_en": consultado_en,
                }}))
                stats["fallos_conservados"] += 1
                continue

            cambio = previo is None or (
                previo.get("estado"), previo.get("estado_detalle")
            ) != (snap["estado"], snap["estado_detalle"])

            set_fields = {k: v for k, v in snap.items() if k != "_id"}
            set_fields.update({
                "corrida": corrida,
                "ultima_consulta": consultado_en,
                "actualizado_en": consultado_en,
                "ultimo_intento_fallido": None,
            })
            update: dict[str, Any] = {
                "$set": set_fields,
                "$setOnInsert": {"creado_en": consultado_en},
            }
            if cambio:
                set_fields["estado_anterior"] = previo.get("estado") if previo else None
                set_fields["cambio_estado_en"] = consultado_en
                update["$push"] = {"historial": {"$each": [entrada_hist], "$slice": -HISTORIAL_MAX}}
                stats["nuevos" if previo is None else "cambios_estado"] += 1
            else:
                stats["sin_cambio"] += 1
            ops.append(UpdateOne({"_id": _id}, update, upsert=True))

        if ops:
            self.agentes.bulk_write(ops, ordered=False)
        stats["total"] = len(snapshots)
        return dict(stats)

    def registrar_corrida(
        self,
        results: list[Any],
        negocio: str,
        corrida: str,
        inicio: datetime | None,
        stats: dict[str, int],
        archivos: list[str] | None = None,
        status: str = "OK",
        error: str | None = None,
    ) -> None:
        negocio = negocio.strip().upper()
        conteo = Counter(build_snapshot(r, negocio)["estado"] for r in results)
        self.corridas.replace_one(
            {"_id": f"{negocio}:{corrida}"},
            {
                "_id": f"{negocio}:{corrida}",
                "negocio": negocio,
                "corrida": corrida,
                "origen_bot": "estados-gadso",
                "inicio": inicio,
                "fin": _ahora(),
                "status": status,
                "error": error,
                "total": len(results),
                "conteo_estados": dict(conteo),
                "persistencia": stats,
                "archivos": archivos or [],
            },
            upsert=True,
        )
