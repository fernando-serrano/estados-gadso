from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from src.agents_flow.extraction_flow import (
    extract_course_fields,
    extract_detail_fields,
    extract_history_fields,
    extract_license_fields,
)
from src.agents_flow.excel_flow import InputRecord, SearchResult

from .navigation import navigate_to_mis_vigilantes, wait_primefaces_ajax
from .selectors import VIEW_SELECTORS


def _write_input(page: Page, selector: str, value: str) -> None:
    field = page.locator(selector).first
    field.wait_for(state="visible", timeout=12000)
    field.click()
    field.fill(value)
    field.evaluate(
        'el => { el.dispatchEvent(new Event("input", {bubbles:true})); '
        'el.dispatchEvent(new Event("change", {bubbles:true})); }'
    )
    field.blur()


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
    logger.info("[FILA %s] Buscando DNI=%s", record.row_number, record.dni)

    _write_input(page, VIEW_SELECTORS["criterio_busqueda"], record.dni)
    page.locator(VIEW_SELECTORS["boton_buscar"]).first.click(timeout=10000)
    _wait_for_search_response(page)

    if _results_table_has_empty_message(page):
        logger.info("[FILA %s] Sin resultados para DNI=%s (empty-message)", record.row_number, record.dni)
        return SearchResult(
            documento=record.dni,
            tipo_documento="DNI",
            nombre=record.apellidos_nombres,
            estado="NO_ENCONTRADO",
        )

    if not _first_ver_link_is_available(page):
        if _page_has_no_results(page):
            logger.info("[FILA %s] Sin resultados para DNI=%s", record.row_number, record.dni)
            return SearchResult(
                documento=record.dni,
                tipo_documento="DNI",
                nombre=record.apellidos_nombres,
                estado="NO_ENCONTRADO",
            )
        logger.warning("[FILA %s] No se encontro enlace Ver para DNI=%s", record.row_number, record.dni)
        return SearchResult(
            documento=record.dni,
            tipo_documento="DNI",
            nombre=record.apellidos_nombres,
            estado="SIN_VER",
        )

    page.locator(VIEW_SELECTORS["ver_primero"]).first.click(timeout=10000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    wait_primefaces_ajax(page, timeout_ms=9000)

    logger.info("[FILA %s] Registro abierto con Ver para DNI=%s", record.row_number, record.dni)
    detail = extract_detail_fields(page, logger)
    courses = extract_course_fields(page, logger)
    license_data = extract_license_fields(page, logger)
    history = extract_history_fields(page, logger)
    if not detail.get("documento"):
        detail["documento"] = record.dni
    if not detail.get("nombre"):
        detail["nombre"] = record.apellidos_nombres
    result = SearchResult(**detail, **courses, **license_data, **history)
    return_to_search_view(page, logger)
    return result


def process_records_in_mis_vigilantes(
    page: Page,
    records: list[InputRecord],
    logger: logging.Logger,
) -> list[SearchResult]:
    results: list[SearchResult] = []

    for index, record in enumerate(records, start=1):
        logger.info("Procesando registro %s/%s", index, len(records))
        navigate_to_mis_vigilantes(page, logger)
        results.append(search_record_and_open_detail(page, record, logger))

    return results
