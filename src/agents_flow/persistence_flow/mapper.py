"""Convierte un SearchResult (46 columnas planas) al documento Mongo de estados.

Convenciones alineadas con `carnet_sucamec_agentes` (bot de carnet):
  - _id = "<NEGOCIO>:<dni>"   (p.ej. "JV:41234567")
  - negocio = JV | SELVA
  - corrida = nombre de la corrida "YYYYMMDD_HHMMSS"
Diferencia deliberada: las fechas se guardan como Date (no texto) para poder
filtrar por rangos desde la plataforma.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# Estados normalizados (campo `estado`).
VIGENTE = "VIGENTE"
VENCIDO = "VENCIDO"
CESADO = "CESADO"
SIN_CARNE = "SIN_CARNE"            # tiene ficha/cursos pero SUCAMEC no muestra estado de carne
NO_ENCONTRADO = "NO_ENCONTRADO"
SIN_VER = "SIN_VER"
WORKER_ERROR = "WORKER_ERROR"

ESTADOS_FALLO = frozenset({SIN_VER, WORKER_ERROR})
ESTADOS_VALIDOS = frozenset({VIGENTE, VENCIDO, CESADO, SIN_CARNE, NO_ENCONTRADO, SIN_VER, WORKER_ERROR})

FUENTE_CONSULTAS = "SUCAMEC_CONSULTAS"
FUENTE_DSSP = "SUCAMEC_DSSP"

_FECHA_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def _txt(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def parse_fecha(value: Any) -> datetime | None:
    """'dd/mm/yyyy' -> datetime (medianoche). Vacio o invalido -> None."""
    match = _FECHA_RE.match(str(value or ""))
    if not match:
        return None
    day, month, year = (int(x) for x in match.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def normalizar_documento(documento: Any, tipo_documento: Any = "") -> str:
    """Solo digitos/letras; un DNI de 7 digitos recupera el 0 que Excel le quito."""
    doc = re.sub(r"[^0-9A-Za-z]", "", str(documento or "")).upper()
    tipo = str(tipo_documento or "").strip().upper()
    if doc.isdigit() and len(doc) < 8 and tipo in {"", "DNI"}:
        doc = doc.zfill(8)
    return doc


def normalizar_estado(estado_raw: Any, tiene_ficha: bool) -> tuple[str, str | None, str]:
    """Devuelve (estado, estado_detalle, fuente).

    - "NO_ENCONTRADO TRANSMITIDO"  -> (NO_ENCONTRADO, "TRANSMITIDO", DSSP)
    - "NO_ENCONTRADO No se encontraron resultados." -> (NO_ENCONTRADO, "No se encontraron resultados.", DSSP)
    - ""  con ficha (nombre/cursos) -> (SIN_CARNE, None, CONSULTAS)
    """
    raw = _txt(estado_raw) or ""
    upper = raw.upper()
    if upper.startswith(NO_ENCONTRADO) and len(raw) > len(NO_ENCONTRADO):
        return NO_ENCONTRADO, raw[len(NO_ENCONTRADO):].strip() or None, FUENTE_DSSP
    if not raw:
        return (SIN_CARNE if tiene_ficha else NO_ENCONTRADO), None, FUENTE_CONSULTAS
    if upper in ESTADOS_VALIDOS:
        return upper, None, FUENTE_CONSULTAS
    # Estado nuevo que SUCAMEC empiece a mostrar: se conserva tal cual, no se pierde.
    return upper, None, FUENTE_CONSULTAS


def _bloque(result: Any, campos: dict[str, str], sufijo: str = "") -> dict[str, Any] | None:
    data: dict[str, Any] = {}
    for destino, origen in campos.items():
        valor = getattr(result, f"{origen}{sufijo}", "")
        data[destino] = parse_fecha(valor) if destino.startswith("fecha") else _txt(valor)
    return data if any(v is not None for v in data.values()) else None


_CARNE = {
    "nro": "nro_carne", "modalidad": "modalidad", "ruc": "ruc", "empresa": "empresa",
    "expediente": "expediente", "nro_expediente": "nro_expediente", "anho_expediente": "anho_expediente",
    "fecha_emision": "fecha_emision", "fecha_vencimiento": "fecha_vencimiento",
}
_CURSO = {
    "ruc": "curso_ruc_", "razon_social": "curso_razon_social_", "evaluacion": "curso_evaluacion_",
    "tipo": "curso_tipo_", "fecha_inicio": "curso_fecha_inicio_", "fecha_vencimiento": "curso_fecha_venc_",
    "estado": "curso_estado_",
}
_LICENCIA = {
    "numero": "licencia_numero", "fecha_emision": "licencia_fecha_emision",
    "fecha_vencimiento": "licencia_fecha_venc", "modalidad": "licencia_modalidad",
    "restricciones": "licencia_restricciones",
}
_HISTORIAL = {
    "ruc": "historial_ruc_", "razon_social": "historial_razon_social_", "modalidad": "historial_modalidad_",
    "procedimiento": "historial_procedimiento_", "fecha_emision": "historial_fecha_emision_",
    "fecha_vencimiento": "historial_fecha_venc_", "fecha_baja": "historial_fecha_baja_",
}


# SUCAMEC deja "Fec vencimiento" vacio en la ficha del carne (verificado 10/11/2026).
# En el historial de SUCAMEC, los carnes emitidos desde 2021 vencen a los 3 anios
# (98.6% de 1263 casos 2022+). Para emisiones anteriores el regimen era otro: no se calcula.
VIGENCIA_ANIOS = 3
VIGENCIA_DESDE = datetime(2021, 1, 1)


def _sumar_anios(fecha: datetime, anios: int) -> datetime:
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:  # 29/02 -> 28/02
        return fecha.replace(year=fecha.year + anios, day=28)


def completar_vencimiento(carne: dict[str, Any] | None) -> dict[str, Any] | None:
    """Agrega `fecha_vencimiento_origen`: SUCAMEC | CALCULADA | None."""
    if not carne:
        return carne
    if carne.get("fecha_vencimiento"):
        carne["fecha_vencimiento_origen"] = "SUCAMEC"
    elif carne.get("fecha_emision") and carne["fecha_emision"] >= VIGENCIA_DESDE:
        carne["fecha_vencimiento"] = _sumar_anios(carne["fecha_emision"], VIGENCIA_ANIOS)
        carne["fecha_vencimiento_origen"] = "CALCULADA"
    else:
        carne["fecha_vencimiento_origen"] = None
    return carne


def build_snapshot(result: Any, negocio: str) -> dict[str, Any]:
    """Campos de datos del vigilante (lo que el bot es duenio de sobrescribir)."""
    negocio = negocio.strip().upper()
    dni = normalizar_documento(result.documento, result.tipo_documento)
    cursos = [c for c in (_bloque(result, _CURSO, "1"), _bloque(result, _CURSO, "2")) if c]
    historial = [h for h in (_bloque(result, _HISTORIAL, "1"), _bloque(result, _HISTORIAL, "2")) if h]
    nombre = _txt(result.nombre)
    estado, detalle, fuente = normalizar_estado(result.estado, tiene_ficha=bool(nombre or cursos or historial))
    return {
        "_id": f"{negocio}:{dni}",
        "negocio": negocio,
        "dni": dni,
        "tipo_documento": _txt(result.tipo_documento) or "DNI",
        "nombre": nombre,
        "estado": estado,
        "estado_detalle": detalle,
        "estado_raw": _txt(result.estado),
        "fuente": fuente,
        "carne": completar_vencimiento(_bloque(result, _CARNE)),
        "cursos": cursos,
        "licencia": _bloque(result, _LICENCIA),
        "historial_laboral": historial,
    }
