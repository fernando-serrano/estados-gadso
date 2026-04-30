from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from src.agents_flow.consultas_common import wait_primefaces_ajax

from .selectors import MENU_SELECTORS, VIEW_SELECTORS


def validate_bandeja_emision_view(page: Page, timeout_ms: int = 6000) -> bool:
    deadline = time.time() + (max(600, int(timeout_ms)) / 1000.0)

    while time.time() < deadline:
        for selector in (VIEW_SELECTORS["buscar_por_widget"], VIEW_SELECTORS["filtro_busqueda"]):
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
                    return text.includes('BUSCAR POR') && text.includes('FILTRO');
                }"""
            )
            if bool(ok):
                return True
        except Exception:
            pass

        page.wait_for_timeout(180)

    return False


def _click_bandeja_emision_fast_path(page: Page, logger: logging.Logger) -> bool:
    try:
        page.locator(MENU_SELECTORS["menu_root"]).first.wait_for(state="visible", timeout=6000)
        clicked = page.evaluate(
            """() => {
                const normalize = (value) => String(value || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .toUpperCase();

                const target = Array.from(document.querySelectorAll('a[onclick*="PrimeFaces.ab"]'))
                    .find((anchor) => normalize(anchor.textContent) === 'BANDEJA DE EMISION');
                if (!target) return false;
                target.click();
                return true;
            }"""
        )
        if not clicked:
            return False

        logger.info("Fast-path: click directo en BANDEJA DE EMISION")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        wait_primefaces_ajax(page, timeout_ms=4500)
        return validate_bandeja_emision_view(page, timeout_ms=3000)
    except Exception:
        return False


def _click_bandeja_emision_from_dssp_section(page: Page) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\\u0300-\\u036f]/g, '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toUpperCase();

                    const headers = Array.from(document.querySelectorAll('h3.ui-panelmenu-header'));
                    const dsspHeader = headers.find((header) => normalize(header.textContent) === 'DSSP');
                    if (!dsspHeader) return false;

                    const expanded = String(dsspHeader.getAttribute('aria-expanded') || '').toLowerCase() === 'true';
                    if (!expanded) dsspHeader.click();

                    const candidates = [];
                    if (dsspHeader.nextElementSibling) candidates.push(dsspHeader.nextElementSibling);
                    if (dsspHeader.parentElement) candidates.push(dsspHeader.parentElement);

                    for (const container of candidates) {
                        const link = Array.from(
                            container.querySelectorAll('a.ui-menuitem-link, a[onclick*="PrimeFaces.ab"]')
                        ).find((anchor) => normalize(anchor.textContent) === 'BANDEJA DE EMISION');
                        if (link) {
                            link.click();
                            return true;
                        }
                    }

                    return false;
                }"""
            )
        )
    except Exception:
        return False


def navigate_to_bandeja_emision(page: Page, logger: logging.Logger) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass

    if _click_bandeja_emision_fast_path(page, logger):
        logger.info("Vista BANDEJA DE EMISION confirmada")
        return

    logger.info("Navegando por menu: DSSP > BANDEJA DE EMISION")
    root = page.locator(MENU_SELECTORS["menu_root"]).first
    root.wait_for(state="visible", timeout=12000)

    header_dssp = root.locator(MENU_SELECTORS["header_dssp"]).first
    header_dssp.wait_for(state="visible", timeout=8000)

    aria_expanded = (header_dssp.get_attribute("aria-expanded") or "").strip().lower()
    if aria_expanded != "true":
        header_dssp.click(timeout=8000)
        wait_primefaces_ajax(page, timeout_ms=4000)
        page.wait_for_timeout(400)
        aria_expanded = (header_dssp.get_attribute("aria-expanded") or "").strip().lower()
        if aria_expanded != "true":
            raise RuntimeError("No se pudo expandir el menu DSSP")

    if _click_bandeja_emision_from_dssp_section(page):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        wait_primefaces_ajax(page, timeout_ms=6000)
        if validate_bandeja_emision_view(page, timeout_ms=6500):
            logger.info("Vista BANDEJA DE EMISION confirmada")
            return

    item = root.locator(MENU_SELECTORS["item_bandeja_emision_onclick"]).first
    try:
        item.wait_for(state="visible", timeout=4500)
    except Exception:
        item = root.locator(MENU_SELECTORS["item_bandeja_emision"]).first
        item.wait_for(state="visible", timeout=6000)

    item.click(timeout=10000)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    wait_primefaces_ajax(page, timeout_ms=6000)

    if not validate_bandeja_emision_view(page, timeout_ms=6500):
        raise RuntimeError("No se confirmo la vista BANDEJA DE EMISION")

    logger.info("Vista BANDEJA DE EMISION confirmada")
