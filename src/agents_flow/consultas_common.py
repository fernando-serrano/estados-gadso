from __future__ import annotations

import logging

from playwright.sync_api import Page


def wait_primefaces_ajax(page: Page, timeout_ms: int = 7000) -> None:
    try:
        page.wait_for_function(
            """() => {
                try {
                    if (!window.PrimeFaces || !PrimeFaces.ajax || !PrimeFaces.ajax.Queue) return true;
                    const queue = PrimeFaces.ajax.Queue;
                    if (typeof queue.isEmpty === 'function') return queue.isEmpty();
                    const requests = queue.requests || queue.queue || [];
                    return !requests || requests.length === 0;
                } catch (e) {
                    return true;
                }
            }""",
            timeout=max(1000, int(timeout_ms)),
        )
    except Exception:
        pass


def click_ver_and_wait_detail(
    page: Page,
    logger: logging.Logger,
    ver_selector: str,
    detail_timeout_ms: int = 18000,
) -> None:
    from src.agents_flow.extraction_flow.detail import wait_detail_view

    last_exception: Exception | None = None
    attempts = (
        ("click", False),
        ("click", True),
        ("js", False),
    )

    for index, (mode, use_force) in enumerate(attempts, start=1):
        try:
            link = page.locator(ver_selector).first
            link.wait_for(state="visible", timeout=6000)

            if mode == "js":
                clicked = page.evaluate(
                    """(selector) => {
                        const el = document.querySelector(selector);
                        if (!el) return false;
                        el.click();
                        return true;
                    }""",
                    ver_selector,
                )
                if not clicked:
                    raise RuntimeError("No se pudo ejecutar click JS sobre el enlace Ver")
            else:
                link.click(timeout=10000, force=use_force)

            try:
                page.wait_for_load_state("domcontentloaded", timeout=4000)
            except Exception:
                pass
            wait_primefaces_ajax(page, timeout_ms=9000)
            wait_detail_view(page, timeout_ms=detail_timeout_ms)
            if index > 1:
                logger.info("Apertura de detalle con Ver recuperada en intento %s (%s)", index, mode)
            return
        except Exception as exc:
            last_exception = exc
            logger.warning(
                "Intento %s de apertura con Ver no confirmo detalle (%s%s): %s",
                index,
                mode,
                ", force" if use_force else "",
                exc,
            )
            page.wait_for_timeout(350)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("No se pudo abrir el detalle con el enlace Ver")
