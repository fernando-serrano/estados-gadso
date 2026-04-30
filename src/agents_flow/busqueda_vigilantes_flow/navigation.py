from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from src.agents_flow.consultas_common import wait_primefaces_ajax

from .selectors import MENU_SELECTORS, VIEW_SELECTORS


def validate_busqueda_vigilantes_view(page: Page, timeout_ms: int = 6000) -> bool:
    deadline = time.time() + (max(600, int(timeout_ms)) / 1000.0)

    while time.time() < deadline:
        for selector in (
            VIEW_SELECTORS["tipo_documento_widget"],
            VIEW_SELECTORS["criterio_busqueda"],
            VIEW_SELECTORS["boton_buscar"],
        ):
            try:
                if page.locator(selector).first.is_visible(timeout=150):
                    return True
            except Exception:
                pass

        try:
            ok = page.evaluate(
                """() => {
                    const text = String(document.body?.innerText || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toUpperCase();
                    return text.includes('BUSCAR') && (text.includes('NRO DNI') || text.includes('NRO C.E.'));
                }"""
            )
            if bool(ok):
                return True
        except Exception:
            pass

        page.wait_for_timeout(180)

    return False


def _click_busqueda_vigilantes_fast_path(page: Page, logger: logging.Logger) -> bool:
    try:
        page.locator(MENU_SELECTORS["menu_root"]).first.wait_for(state="visible", timeout=6000)
        clicked = page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a[onclick]'));
                const target = anchors.find((anchor) => {
                    const text = String(anchor.textContent || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toUpperCase();
                    return text === 'BUSQUEDA DE VIGILANTES'
                        || text === 'BÚSQUEDA DE VIGILANTES'
                        || text.includes('BUSQUEDA DE VIGILANTES')
                        || text.includes('BÚSQUEDA DE VIGILANTES');
                });
                if (!target) return false;
                target.click();
                return true;
            }"""
        )
        if not clicked:
            return False

        logger.info("Fast-path: click directo en BUSQUEDA DE VIGILANTES")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        wait_primefaces_ajax(page, timeout_ms=4500)
        return validate_busqueda_vigilantes_view(page, timeout_ms=3000)
    except Exception:
        return False


def navigate_to_busqueda_vigilantes(page: Page, logger: logging.Logger) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass

    if _click_busqueda_vigilantes_fast_path(page, logger):
        logger.info("Vista BUSQUEDA DE VIGILANTES confirmada")
        return

    logger.info("Navegando por menu: CONSULTAS > BUSQUEDA DE VIGILANTES")
    root = page.locator(MENU_SELECTORS["menu_root"]).first
    root.wait_for(state="visible", timeout=12000)

    header_consultas = root.locator(MENU_SELECTORS["header_consultas"]).first
    header_consultas.wait_for(state="visible", timeout=8000)

    aria_expanded = (header_consultas.get_attribute("aria-expanded") or "").strip().lower()
    if aria_expanded != "true":
        header_consultas.click(timeout=8000)
        page.wait_for_timeout(300)
        aria_expanded = (header_consultas.get_attribute("aria-expanded") or "").strip().lower()
        if aria_expanded != "true":
            raise RuntimeError("No se pudo expandir el menu CONSULTAS")

    item = root.locator(MENU_SELECTORS["item_busqueda_vigilantes_onclick"]).first
    try:
        item.wait_for(state="visible", timeout=4500)
    except Exception:
        item = root.locator(MENU_SELECTORS["item_busqueda_vigilantes"]).first
        item.wait_for(state="visible", timeout=6000)

    item.click(timeout=10000)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    wait_primefaces_ajax(page, timeout_ms=6000)

    if not validate_busqueda_vigilantes_view(page, timeout_ms=6500):
        raise RuntimeError("No se confirmo la vista BUSQUEDA DE VIGILANTES")

    logger.info("Vista BUSQUEDA DE VIGILANTES confirmada")
