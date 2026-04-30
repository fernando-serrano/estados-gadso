from __future__ import annotations

import logging
import re
from dataclasses import replace

from playwright.sync_api import Page

from src.agents_flow.excel_flow import SearchResult
from src.agents_flow.login_flow.auth import write_input
from src.agents_flow.consultas_common import wait_primefaces_ajax

from .navigation import navigate_to_bandeja_emision
from .selectors import VIEW_SELECTORS


def _wait_for_search_response(page: Page, timeout_ms: int = 9000) -> None:
    wait_primefaces_ajax(page, timeout_ms=timeout_ms)
    try:
        page.locator(VIEW_SELECTORS["tabla_resultados"]).first.wait_for(state="visible", timeout=timeout_ms)
    except Exception:
        pass


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _results_table_has_empty_message(page: Page) -> bool:
    locator = page.locator(VIEW_SELECTORS["fila_sin_resultados"]).first
    try:
        if not locator.is_visible(timeout=250):
            return False
        text = locator.inner_text(timeout=250).upper()
    except Exception:
        return False
    return "NO SE ENCONTR" in text


def _ensure_search_mode_dni(page: Page, logger: logging.Logger) -> None:
    label = page.locator(VIEW_SELECTORS["buscar_por_label"]).first
    try:
        current_value = _normalize_spaces(label.inner_text(timeout=300)).upper()
    except Exception:
        current_value = ""

    if "DNI PROSPECTO / PERSONAL DE SEGURIDAD" in current_value:
        return

    widget = page.locator(VIEW_SELECTORS["buscar_por_widget"]).first
    widget.wait_for(state="visible", timeout=8000)
    widget.click(timeout=8000)
    page.locator(VIEW_SELECTORS["buscar_por_items"]).first.wait_for(state="visible", timeout=6000)
    page.locator(VIEW_SELECTORS["buscar_por_opcion_dni"]).first.click(timeout=8000)
    wait_primefaces_ajax(page, timeout_ms=5000)
    logger.info("Filtro 'Buscar por' configurado en DNI PROSPECTO / PERSONAL DE SEGURIDAD")


def _extract_first_row_estado_registro(page: Page) -> str:
    try:
        row_data = page.evaluate(
            """() => {
                const row = document.querySelector('#listForm\\\\:dtResultados_data > tr.ui-widget-content');
                if (!row) return [];
                return Array.from(row.querySelectorAll('td')).map((cell) =>
                    String(cell.innerText || '').replace(/\\s+/g, ' ').trim()
                );
            }"""
        )
    except Exception:
        return ""

    if not isinstance(row_data, list) or len(row_data) < 3:
        return ""

    return _normalize_spaces(row_data[-3]).upper()


def validate_no_encontrado_in_bandeja_emision(
    page: Page,
    result: SearchResult,
    logger: logging.Logger,
) -> SearchResult:
    logger.info("Validando DNI=%s en BANDEJA DE EMISION", result.documento)

    _ensure_search_mode_dni(page, logger)
    write_input(page, VIEW_SELECTORS["filtro_busqueda"], result.documento)
    page.locator(VIEW_SELECTORS["boton_buscar"]).first.click(timeout=10000)
    _wait_for_search_response(page)

    if _results_table_has_empty_message(page):
        logger.info("DNI=%s sin tramites pendientes en BANDEJA DE EMISION", result.documento)
        return replace(result, estado="NO_ENCONTRADO No se encontraron resultados.")

    estado_registro = _extract_first_row_estado_registro(page)
    if estado_registro:
        logger.info(
            "DNI=%s encontrado en BANDEJA DE EMISION | estado_registro=%s",
            result.documento,
            estado_registro,
        )
        return replace(result, estado=f"NO_ENCONTRADO {estado_registro}")

    logger.warning(
        "DNI=%s tuvo resultados en BANDEJA DE EMISION pero no se pudo extraer 'Estado registro'",
        result.documento,
    )
    return replace(result, estado="NO_ENCONTRADO")


def process_no_encontrados_in_bandeja_emision(
    page: Page,
    results: list[SearchResult],
    logger: logging.Logger,
) -> list[SearchResult]:
    targets = [result for result in results if (result.estado or "").strip().upper() == "NO_ENCONTRADO"]
    if not targets:
        logger.info("No hay registros NO_ENCONTRADO para validar en BANDEJA DE EMISION")
        return []

    navigate_to_bandeja_emision(page, logger)
    validated: list[SearchResult] = []

    for index, result in enumerate(targets, start=1):
        logger.info("Validacion DSSP %s/%s", index, len(targets))
        validated.append(validate_no_encontrado_in_bandeja_emision(page, result, logger))

    return validated
