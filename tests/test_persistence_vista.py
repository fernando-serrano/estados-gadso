"""Vista consolidada estados + carnet. Colecciones temporales `test_<rand>_` (se borran)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.agents_flow.excel_flow.records import SearchResult
from src.agents_flow.persistence_flow.repository import EstadosRepository
from src.agents_flow.persistence_flow.vista import CARNET, VISTA, ensure_vista, pipeline

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="DATABASE_URL no configurada")


def _carnet(dni, negocio="JV", fechas_texto=True):
    f = (lambda s: s) if fechas_texto else datetime.fromisoformat
    return {
        "_id": f"{negocio}:{dni}", "dni": dni, "negocio": negocio, "corrida": "20261027_120743",
        "estado_carnet": "ENCONTRADO", "fecha_emision": f("2026-10-27"), "fuente": "SUCAMEC",
        "minio_bucket": "mga-gadso", "minio_key": f"X/{dni}.pdf", "sha256": "abc",
        "ultima_consulta": f("2026-10-27T12:11:36"),
        "historial": [{"corrida": "20261027_120743", "consultado_en": f("2026-10-27T12:11:36"),
                       "estado": "ENCONTRADO", "fecha_emision": f("2026-10-27"), "minio_key": f"X/{dni}.pdf"}],
    }


@pytest.fixture()
def env():
    from pymongo import MongoClient

    client = MongoClient(URL, serverSelectionTimeoutMS=10000)
    db = client[os.getenv("MONGO_DATABASE", "").strip()] if os.getenv("MONGO_DATABASE", "").strip() else client.get_default_database()
    prefix = f"test_{uuid.uuid4().hex[:8]}_"
    repo = EstadosRepository(db, prefix)
    yield db, prefix, repo
    for n in db.list_collection_names():
        if n.startswith(prefix):
            db.drop_collection(n)
    assert not [n for n in db.list_collection_names() if n.startswith(prefix)]
    client.close()


def test_vista_une_ambas_fuentes(env):
    db, prefix, repo = env
    # 41234567: en ambas | 70000001: solo estados | 80000001: solo carnet (fechas ya Date)
    repo.guardar_resultados([
        SearchResult(documento="41234567", tipo_documento="DNI", nombre="PEREZ JUAN", estado="VIGENTE",
                     nro_carne="123", fecha_emision="14/10/2024"),
        SearchResult(documento="70000001", estado="NO_ENCONTRADO TRANSMITIDO"),
    ], "JV", "20261109_100000", datetime(2026, 11, 9, 10))
    db[f"{prefix}{CARNET}"].insert_many([_carnet("41234567"), _carnet("80000001", fechas_texto=False)])
    ensure_vista(db, prefix)
    ensure_vista(db, prefix)  # idempotente

    v = db[f"{prefix}{VISTA}"]
    assert v.count_documents({}) == 3

    ambos = v.find_one({"dni": "41234567"})
    assert ambos["_id"] == "JV:41234567" and ambos["nombre"] == "PEREZ JUAN" and ambos["estado"] == "VIGENTE"
    assert ambos["estado_sucamec"]["carne"]["nro"] == "123"
    assert ambos["tiene_carnet_pdf"] is True
    cp = ambos["carnet_pdf"]
    assert cp["fecha_emision"] == datetime(2026, 10, 27)                  # texto -> Date
    assert cp["ultima_consulta"] == datetime(2026, 10, 27, 12, 11, 36)
    assert cp["historial"][0]["consultado_en"] == datetime(2026, 10, 27, 12, 11, 36)
    assert ambos["ultima_actualizacion"] == datetime(2026, 11, 9, 10)

    solo_e = v.find_one({"dni": "70000001"})
    assert solo_e["carnet_pdf"] is None and solo_e["tiene_carnet_pdf"] is False
    assert solo_e["estado_detalle"] == "TRANSMITIDO"

    solo_c = v.find_one({"dni": "80000001"})
    assert solo_c["estado_sucamec"] is None and solo_c["estado"] is None and solo_c["negocio"] == "JV"
    assert solo_c["carnet_pdf"]["fecha_emision"] == datetime(2026, 10, 27)  # Date sigue Date

    # Consulta tipica de la plataforma: por DNI en todos los negocios
    assert [d["_id"] for d in v.find({"dni": "41234567"})] == ["JV:41234567"]


def test_vista_sobre_carnet_real_solo_lectura(env):
    """Ejecuta el pipeline (aggregate, sin escribir) sobre los docs REALES de carnet."""
    db, _, _ = env
    if CARNET not in db.list_collection_names():
        pytest.skip("sin carnet_sucamec_agentes")
    total = db[CARNET].count_documents({})
    # Arranca desde carnet: estados de produccion aun no existe/esta vacio
    p = pipeline()
    p[1]["$unionWith"]["coll"] = CARNET
    rows = list(db[CARNET].aggregate(p))
    assert len(rows) == total
    for r in rows:
        cp = r["carnet_pdf"]
        assert r["dni"] and r["negocio"] in {"JV", "SELVA"}
        assert isinstance(cp["fecha_emision"], datetime), (r["_id"], cp["fecha_emision"])
        assert isinstance(cp["ultima_consulta"], datetime), r["_id"]
        assert all(isinstance(h["consultado_en"], datetime) for h in cp["historial"])
    print(f"\n[carnet real] {total} docs convertidos a Date sin errores")
