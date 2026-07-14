from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from src.agents_flow.consultas_common import click_ver_and_wait_detail, wait_primefaces_ajax
from src.agents_flow.extraction_flow import (
    extract_course_fields,
    extract_detail_fields,
    extract_history_fields,
    extract_license_fields,
)
from src.agents_flow.excel_flow import InputRecord, SearchResult
from src.agents_flow.login_flow.auth import write_input
from src.agents_flow.recovery import SessionRecovery, run_record_with_recovery

from .navigation import navigate_to_mis_vigilantes
from .selectors import VIEW_SELECTORS


def _wait_for_search_response(page: Page, timeout_ms: int = 9000) -> None:
    wait_primefaces_ajax(page, timeout_ms=timeout_ms)
    try:
        page.locator(VIEW_SELECTORS["tabla_resultados"]).first.wait_for(state="visible", timeout=timeout_ms)
    except Exception:
        pass


def _first_ver_link_is_available(page: Page, timeout_ms: int = 3500) -> bool:
    deadline = time.time() + (max(500, timeout_ms) / 1000.0)
    while time.time() < deadline:
        try:
            if page.locator(VIEW_SELECTORS["ver_primero"]).first.is_visible(timeout=150):
                return True
        except Exception:
            pass
        page.wait_for_timeout(150)
    return False


def _results_table_has_empty_message(page: Page) -> bool:
    locator = page.locator(VIEW_SELECTORS["fila_sin_resultados"]).first
    try:
        if not locator.is_visible(timeout=250):
            return False
        text = locator.inner_text(timeout=250).upper()
    except Exception:
        return False
    return "NO SE ENCONTR" in text


def _page_has_no_results(page: Page) -> bool:
    if _results_table_has_empty_message(page):
        return True
    try:
        text = page.locator("body").inner_text(timeout=800).upper()
    except Exception:
        return False
    no_result_markers = [
        "NO SE ENCONTRARON",
        "NO SE ENCONTRO",
        "SIN RESULTADOS",
        "NO HAY REGISTROS",
        "NO RECORDS",
    ]
    return any(marker in text for marker in no_result_markers)


def _extract_first_result_row_summary(page: Page, expected_document: str) -> dict[str, str]:
    try:
        row = page.evaluate(
            """() => {
                const tbody = document.querySelector('#buscarForm\\\\:buscarDatatable_data');
                if (!tbody) return null;
                const tr = Array.from(tbody.querySelectorAll('tr'))
                    .find((candidate) => !candidate.classList.contains('ui-datatable-empty-message'));
                if (!tr) return null;
                const cells = Array.from(tr.querySelectorAll('td')).map((td) =>
                    String(td.innerText || '').replace(/\\s+/g, ' ').trim()
                );
                return {cells};
            }"""
        )
    except Exception:
        return {}

    cells = [str(value or "").strip() for value in (row or {}).get("cells", [])]
    if not cells:
        return {}

    expected = str(expected_document or "").strip()
    summary: dict[str, str] = {}

    for value in cells:
        compact = value.replace(" ", "")
        if compact == expected:
            summary["documento"] = value
            break

    name_candidates = []
    for value in cells:
        normalized = value.strip()
        if not normalized or normalized.upper() == "VER":
            continue
        if normalized.replace(" ", "") == expected:
            continue
        if any(char.isalpha() for char in normalized) and len(normalized) >= 6:
            name_candidates.append(normalized)
    if name_candidates:
        summary["nombre"] = max(name_candidates, key=len)

    return summary


def return_to_search_view(page: Page, logger: logging.Logger) -> None:
    button = page.locator(VIEW_SELECTORS["boton_buscar_vigilantes"]).first
    button.wait_for(state="visible", timeout=10000)
    button.click(timeout=10000)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    wait_primefaces_ajax(page, timeout_ms=9000)
    page.locator(VIEW_SELECTORS["criterio_busqueda"]).first.wait_for(state="visible", timeout=10000)
    logger.info("Retorno a vista de busqueda MIS VIGILANTES confirmado")


def search_record_and_open_detail(page: Page, record: InputRecord, logger: logging.Logger) -> SearchResult:
    logger.info("[FILA %s] Buscando NRO DOCUMENTO=%s", record.row_number, record.nro_documento)

    write_input(page, VIEW_SELECTORS["criterio_busqueda"], record.nro_documento)
    page.locator(VIEW_SELECTORS["boton_buscar"]).first.click(timeout=10000)
    _wait_for_search_response(page)

    if _results_table_has_empty_message(page):
        logger.info("[FILA %s] Sin resultados para NRO DOCUMENTO=%s (empty-message)", record.row_number, record.nro_documento)
        return SearchResult(
            documento=record.nro_documento,
            tipo_documento="DNI",
            nombre=record.apellidos_nombres,
            estado="NO_ENCONTRADO",
        )

    if not _first_ver_link_is_available(page):
        if _page_has_no_results(page):
            logger.info("[FILA %s] Sin resultados para NRO DOCUMENTO=%s", record.row_number, record.nro_documento)
            return SearchResult(
                documento=record.nro_documento,
                tipo_documento="DNI",
                nombre=record.apellidos_nombres,
                estado="NO_ENCONTRADO",
            )
        logger.warning("[FILA %s] No se encontro enlace Ver para NRO DOCUMENTO=%s", record.row_number, record.nro_documento)
        return SearchResult(
            documento=record.nro_documento,
            tipo_documento="DNI",
            nombre=record.apellidos_nombres,
            estado="SIN_VER",
        )

    row_summary = _extract_first_result_row_summary(page, record.nro_documento)
    click_ver_and_wait_detail(page, logger, VIEW_SELECTORS["ver_primero"], detail_timeout_ms=18000)

    logger.info("[FILA %s] Registro abierto con Ver para NRO DOCUMENTO=%s", record.row_number, record.nro_documento)
    detail = extract_detail_fields(page, logger)
    courses = extract_course_fields(page, logger)
    license_data = extract_license_fields(page, logger)
    history = extract_history_fields(page, logger)
    if not detail.get("documento"):
        detail["documento"] = record.nro_documento
    if not detail.get("nombre") and row_summary.get("nombre"):
        detail["nombre"] = row_summary["nombre"]
    if not detail.get("nombre"):
        detail["nombre"] = record.apellidos_nombres
    result = SearchResult(**detail, **courses, **license_data, **history)
    return_to_search_view(page, logger)
    return result


def process_records_in_mis_vigilantes(
    page: Page,
    records: list[InputRecord],
    logger: logging.Logger,
    recovery: SessionRecovery | None = None,
    sink: list[SearchResult] | None = None,
) -> list[SearchResult]:
    # `sink` permite preservar los resultados ya obtenidos si la sesion cae a mitad:
    # el runner sabe cuantos se completaron y reanuda desde el registro pendiente.
    results = sink if sink is not None else []
    if records:
        navigate_to_mis_vigilantes(page, logger)

    for index, record in enumerate(records, start=1):
        logger.info("Procesando registro %s/%s", index, len(records))
        results.append(
            run_record_with_recovery(
                page,
                record,
                logger,
                search_record_and_open_detail,
                recovery,
            )
        )

    return results
