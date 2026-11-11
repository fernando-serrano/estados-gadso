"""Pruebas unitarias del mapeo SearchResult -> documento Mongo (sin BD)."""
from __future__ import annotations

import glob
from dataclasses import fields
from datetime import datetime
from pathlib import Path

import pytest

from src.agents_flow.excel_flow.records import SearchResult
from src.agents_flow.persistence_flow.mapper import (
    build_snapshot, normalizar_documento, normalizar_estado, parse_fecha,
)

ROOT = Path(__file__).resolve().parents[1]


def _vigente(**kw) -> SearchResult:
    base = dict(
        documento="41234567", tipo_documento="DNI", nombre="PEREZ GOMEZ JUAN", estado="VIGENTE",
        nro_carne="123456", modalidad="VIGILANCIA PRIVADA", ruc="20100901481",
        empresa="J & V RESGUARDO S.A.C.", expediente="202400357166", fecha_emision="14/10/2024",
        curso_ruc_1="20100901481", curso_razon_social_1="CENTRO X", curso_evaluacion_1="APROBADO",
        curso_tipo_1="BÁSICA", curso_fecha_inicio_1="04/09/2024", curso_fecha_venc_1="04/09/2026",
        curso_estado_1="VIGENTE",
        licencia_numero="L-999", licencia_fecha_venc="23/09/2028", licencia_modalidad="SEGURIDAD PRIVADA (L4)",
        historial_ruc_1="20100901481", historial_razon_social_1="J & V", historial_procedimiento_1="RENOVACION",
        historial_fecha_emision_1="13/10/2021", historial_fecha_venc_1="13/10/2024", historial_fecha_baja_1="18/09/2024",
    )
    base.update(kw)
    return SearchResult(**base)


@pytest.mark.parametrize("raw,esperado", [
    ("14/10/2024", datetime(2024, 10, 14)),
    (" 1/2/2025 ", datetime(2025, 2, 1)),
    ("", None), (None, None), ("31/02/2024", None), ("2024-10-14", None),
])
def test_parse_fecha(raw, esperado):
    assert parse_fecha(raw) == esperado


@pytest.mark.parametrize("doc,tipo,esperado", [
    ("3069273", "DNI", "03069273"),      # caso real: Excel perdio el 0
    ("41234567", "DNI", "41234567"),
    (" 41.234.567 ", "DNI", "41234567"),
    ("001234567", "CE", "001234567"),
    ("12345", "CE", "12345"),            # CE no se rellena
])
def test_normalizar_documento(doc, tipo, esperado):
    assert normalizar_documento(doc, tipo) == esperado


@pytest.mark.parametrize("raw,ficha,esperado", [
    ("VIGENTE", True, ("VIGENTE", None, "SUCAMEC_CONSULTAS")),
    ("vencido", True, ("VENCIDO", None, "SUCAMEC_CONSULTAS")),
    ("CESADO", True, ("CESADO", None, "SUCAMEC_CONSULTAS")),
    ("NO_ENCONTRADO", False, ("NO_ENCONTRADO", None, "SUCAMEC_CONSULTAS")),
    ("NO_ENCONTRADO TRANSMITIDO", False, ("NO_ENCONTRADO", "TRANSMITIDO", "SUCAMEC_DSSP")),
    ("NO_ENCONTRADO No se encontraron resultados.", False,
     ("NO_ENCONTRADO", "No se encontraron resultados.", "SUCAMEC_DSSP")),
    ("", True, ("SIN_CARNE", None, "SUCAMEC_CONSULTAS")),
    ("", False, ("NO_ENCONTRADO", None, "SUCAMEC_CONSULTAS")),
    ("WORKER_ERROR", False, ("WORKER_ERROR", None, "SUCAMEC_CONSULTAS")),
    ("SUSPENDIDO", True, ("SUSPENDIDO", None, "SUCAMEC_CONSULTAS")),  # estado nuevo no se pierde
])
def test_normalizar_estado(raw, ficha, esperado):
    assert normalizar_estado(raw, ficha) == esperado


def test_snapshot_completo():
    s = build_snapshot(_vigente(), "jv")
    assert s["_id"] == "JV:41234567" and s["negocio"] == "JV" and s["dni"] == "41234567"
    assert s["estado"] == "VIGENTE" and s["fuente"] == "SUCAMEC_CONSULTAS"
    assert s["carne"]["nro"] == "123456"
    assert s["carne"]["fecha_emision"] == datetime(2024, 10, 14)
    assert s["carne"]["fecha_vencimiento"] == datetime(2027, 10, 14)
    assert s["carne"]["fecha_vencimiento_origen"] == "CALCULADA"
    assert len(s["cursos"]) == 1 and s["cursos"][0]["tipo"] == "BÁSICA"
    assert s["cursos"][0]["fecha_vencimiento"] == datetime(2026, 9, 4)
    assert s["licencia"]["fecha_vencimiento"] == datetime(2028, 9, 23)
    assert s["historial_laboral"][0]["fecha_baja"] == datetime(2024, 9, 18)


def test_snapshot_no_encontrado_sin_bloques_vacios():
    s = build_snapshot(SearchResult(documento="70000001", tipo_documento="DNI", estado="NO_ENCONTRADO"), "SELVA")
    assert s["_id"] == "SELVA:70000001"
    assert s["carne"] is None and s["licencia"] is None
    assert s["cursos"] == [] and s["historial_laboral"] == []


# ---------- Validacion contra TODOS los Excel historicos reales de lotes/ ----------
LOTES = sorted(glob.glob(str(ROOT / "lotes" / "*" / "*.xlsx")))
ESTADOS_ESPERADOS = {"VIGENTE", "VENCIDO", "CESADO", "SIN_CARNE", "NO_ENCONTRADO", "SIN_VER", "WORKER_ERROR"}


@pytest.mark.skipif(not LOTES, reason="no hay lotes historicos")
@pytest.mark.parametrize("path", LOTES, ids=lambda p: Path(p).parent.name + "/" + Path(p).name[:25])
def test_mapea_lote_real_sin_perder_datos(path):
    import pandas as pd

    df = pd.read_excel(path, dtype=str).fillna("")
    nombres = {f.name for f in fields(SearchResult)}
    ids = set()
    for row in df.to_dict("records"):
        r = SearchResult(**{k: v for k, v in row.items() if k in nombres})
        s = build_snapshot(r, "JV")
        assert s["estado"] in ESTADOS_ESPERADOS, s["estado_raw"]
        assert s["_id"] not in ids
        ids.add(s["_id"])
        # Ninguna fecha con texto se pierde al convertir
        for campo, valor in row.items():
            if "fecha" in campo and valor:
                assert parse_fecha(valor) is not None, (campo, valor)
        # Cursos/historial: el numero de bloques coincide con columnas llenas
        assert len(s["cursos"]) == sum(1 for i in "12" if any(row[c] for c in row if c.startswith("curso_") and c.endswith(i)))


@pytest.mark.parametrize("emision,venc_sucamec,esperado,origen", [
    ("14/10/2024", "", datetime(2027, 10, 14), "CALCULADA"),
    ("29/02/2024", "", datetime(2027, 2, 28), "CALCULADA"),      # bisiesto
    ("14/10/2024", "01/01/2030", datetime(2030, 1, 1), "SUCAMEC"),  # si SUCAMEC lo publica, manda
    ("10/05/2019", "", None, None),                                # regimen anterior: no se calcula
])
def test_vencimiento_carne(emision, venc_sucamec, esperado, origen):
    s = build_snapshot(_vigente(fecha_emision=emision, fecha_vencimiento=venc_sucamec), "JV")
    assert s["carne"]["fecha_vencimiento"] == esperado
    assert s["carne"]["fecha_vencimiento_origen"] == origen
