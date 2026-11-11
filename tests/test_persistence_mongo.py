"""Pruebas de integracion contra el Mongo real.

Usa colecciones temporales con prefijo `test_<random>_` que se BORRAN al terminar;
no toca colecciones de produccion. Se omite si no hay DATABASE_URL.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.agents_flow.excel_flow.records import SearchResult
from src.agents_flow.persistence_flow import persist_run_results
from src.agents_flow.persistence_flow.repository import EstadosRepository

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="DATABASE_URL no configurada")


@pytest.fixture()
def repo():
    from pymongo import MongoClient

    client = MongoClient(URL, serverSelectionTimeoutMS=10000)
    db = client[os.getenv("MONGO_DATABASE", "").strip()] if os.getenv("MONGO_DATABASE", "").strip() else client.get_default_database()
    prefix = f"test_{uuid.uuid4().hex[:8]}_"
    r = EstadosRepository(db, prefix)
    r.ensure_indexes()
    yield r
    r.agentes.drop()
    r.corridas.drop()
    assert not [n for n in db.list_collection_names() if n.startswith(prefix)]
    client.close()


def _r(doc="41234567", estado="VIGENTE", **kw):
    base = dict(documento=doc, tipo_documento="DNI", nombre="PEREZ JUAN", estado=estado,
                nro_carne="123", fecha_emision="14/10/2024", curso_ruc_1="201", curso_estado_1="VIGENTE")
    base.update(kw)
    return SearchResult(**base)


T1, T2, T3, T4 = (datetime(2026, 11, d, 10) for d in (1, 2, 3, 4))


def test_alta_y_reproceso_sin_cambio(repo):
    assert repo.guardar_resultados([_r()], "JV", "20261101_100000", T1) == {"nuevos": 1, "total": 1}
    assert repo.guardar_resultados([_r()], "JV", "20261102_100000", T2) == {"sin_cambio": 1, "total": 1}
    d = repo.agentes.find_one({"_id": "JV:41234567"})
    assert d["creado_en"] == T1 and d["ultima_consulta"] == T2 and d["corrida"] == "20261102_100000"
    assert len(d["historial"]) == 1 and d["estado_anterior"] is None
    assert isinstance(d["carne"]["fecha_emision"], datetime)


def test_cambio_de_estado_queda_en_historial(repo):
    repo.guardar_resultados([_r()], "JV", "c1", T1)
    st = repo.guardar_resultados([_r(estado="VENCIDO")], "JV", "c2", T2)
    assert st["cambios_estado"] == 1
    d = repo.agentes.find_one({"_id": "JV:41234567"})
    assert d["estado"] == "VENCIDO" and d["estado_anterior"] == "VIGENTE" and d["cambio_estado_en"] == T2
    assert [h["estado"] for h in d["historial"]] == ["VIGENTE", "VENCIDO"]


def test_fallo_del_bot_no_pisa_estado_bueno(repo):
    repo.guardar_resultados([_r()], "JV", "c1", T1)
    fallo = SearchResult(documento="41234567", tipo_documento="DNI", estado="WORKER_ERROR")
    st = repo.guardar_resultados([fallo], "JV", "c2", T2)
    assert st["fallos_conservados"] == 1
    d = repo.agentes.find_one({"_id": "JV:41234567"})
    assert d["estado"] == "VIGENTE" and d["carne"]["nro"] == "123" and d["corrida"] == "c1"
    assert d["ultimo_intento_fallido"]["estado"] == "WORKER_ERROR"
    # La siguiente corrida exitosa limpia la marca
    repo.guardar_resultados([_r()], "JV", "c3", T3)
    assert repo.agentes.find_one({"_id": "JV:41234567"})["ultimo_intento_fallido"] is None


def test_fallo_sin_estado_previo_si_se_guarda(repo):
    repo.guardar_resultados([SearchResult(documento="70000001", estado="SIN_VER")], "JV", "c1", T1)
    assert repo.agentes.find_one({"_id": "JV:70000001"})["estado"] == "SIN_VER"


def test_mismo_dni_en_jv_y_selva_son_documentos_distintos(repo):
    repo.guardar_resultados([_r()], "JV", "c1", T1)
    repo.guardar_resultados([_r(estado="CESADO")], "SELVA", "c1", T1)
    assert repo.agentes.count_documents({"dni": "41234567"}) == 2
    assert repo.agentes.find_one({"_id": "SELVA:41234567"})["estado"] == "CESADO"


def test_dssp_detalle_cuenta_como_cambio(repo):
    repo.guardar_resultados([SearchResult(documento="70000002", estado="NO_ENCONTRADO")], "JV", "c1", T1)
    repo.guardar_resultados([SearchResult(documento="70000002", estado="NO_ENCONTRADO TRANSMITIDO")], "JV", "c2", T2)
    d = repo.agentes.find_one({"_id": "JV:70000002"})
    assert d["estado_detalle"] == "TRANSMITIDO" and d["fuente"] == "SUCAMEC_DSSP" and len(d["historial"]) == 2


def test_historial_se_limita(repo):
    for i in range(55):
        repo.guardar_resultados([_r(estado="VIGENTE" if i % 2 else "VENCIDO")], "JV", f"c{i}", T1)
    assert len(repo.agentes.find_one({"_id": "JV:41234567"})["historial"]) == 50


def test_registrar_corrida(repo):
    res = [_r(), _r("70000003", "NO_ENCONTRADO TRANSMITIDO"), _r("70000004", "")]
    st = repo.guardar_resultados(res, "SELVA", "20261104_090000", T4)
    repo.registrar_corrida(res, "SELVA", "20261104_090000", T4, st, ["a.xlsx"])
    c = repo.corridas.find_one({"_id": "SELVA:20261104_090000"})
    assert c["total"] == 3 and c["conteo_estados"] == {"VIGENTE": 1, "NO_ENCONTRADO": 1, "SIN_CARNE": 1}
    assert c["origen_bot"] == "estados-gadso" and c["archivos"] == ["a.xlsx"]


def test_persist_deshabilitado_y_url_mala_no_lanzan(monkeypatch):
    log = logging.getLogger("test")
    monkeypatch.setenv("MONGO_ENABLED", "0")
    assert persist_run_results("JV", "c", [_r()], [], log) is None
    monkeypatch.setenv("MONGO_ENABLED", "1")
    monkeypatch.setenv("DATABASE_URL", "mongodb://127.0.0.1:1/x?serverSelectionTimeoutMS=500")
    assert persist_run_results("JV", "c", [_r()], [], log) is None  # registra el error, no rompe la corrida


def test_volumen_lote_real(repo):
    """Carga el ultimo lote real (~1200 filas) en colecciones temporales y mide."""
    import glob
    import time
    from dataclasses import fields

    import pandas as pd

    files = sorted(glob.glob(str(ROOT / "lotes" / "*" / "RB_GADSOValidacion*.xlsx")))
    if not files:
        pytest.skip("sin lotes")
    df = pd.read_excel(files[-1], dtype=str).fillna("")
    nombres = {f.name for f in fields(SearchResult)}
    res = [SearchResult(**{k: v for k, v in row.items() if k in nombres}) for row in df.to_dict("records")]
    t = time.perf_counter()
    st = repo.guardar_resultados(res, "JV", "20260707_123038", T1)
    t1 = time.perf_counter() - t
    st2 = repo.guardar_resultados(res, "JV", "20260708_123038", T2)
    t2 = time.perf_counter() - t - t1
    print(f"\n[volumen] filas={len(res)} primera={t1:.1f}s {st} | reproceso={t2:.1f}s {st2}")
    assert st["nuevos"] == len(res) == repo.agentes.count_documents({})
    assert st2 == {"sin_cambio": len(res), "total": len(res)}
    assert t1 < 60 and t2 < 60
