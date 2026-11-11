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
                # Click via JS sobre el elemento ya resuelto por Playwright. Evita reusar el
                # string del selector con document.querySelector, que no soporta :has-text().
                clicked = link.evaluate(
                    """(el) => {
                        if (!el) return false;
                        el.click();
                        return true;
                    }"""
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


# --- Eleccion de fila cuando SUCAMEC devuelve varios carnes del mismo documento ---------
#
# Un vigilante puede tener varios carnes (p.ej. uno VENCIDO de otra modalidad y uno VIGENTE
# recien emitido). La tabla no viene ordenada por relevancia, asi que abrir siempre la
# primera fila reportaba VENCIDO aunque existiera un carne VIGENTE.
# Regla: VIGENTE primero; dentro del mismo grupo, la fecha de emision mas reciente.

TBODY_RESULTADOS = "#buscarForm\:buscarDatatable_data"

_JS_FILAS_RESULTADO = r"""
(tbodySel) => {
    const tbody = document.querySelector(tbodySel);
    if (!tbody) return null;
    const table = tbody.closest('table');
    const headers = table ? Array.from(table.querySelectorAll('thead th')).map(th =>
        String(th.innerText || '').replace(/\s+/g, ' ').trim().toUpperCase()) : [];
    const filas = Array.from(tbody.children)
        .filter(tr => tr.tagName === 'TR' && !tr.classList.contains('ui-datatable-empty-message'))
        .map(tr => Array.from(tr.querySelectorAll('td')).map(td =>
            String(td.innerText || '').replace(/\s+/g, ' ').trim()));
    return {headers, filas};
}
"""


def _fecha_orden(texto: str) -> tuple[int, int, int]:
    partes = str(texto or "").strip().split("/")
    if len(partes) == 3 and all(p.isdigit() for p in partes):
        return int(partes[2]), int(partes[1]), int(partes[0])
    return (0, 0, 0)


def elegir_indice_fila(headers: list[str], filas: list[list[str]]) -> int:
    """Indice (0-based) de la fila a abrir: VIGENTE primero, luego emision mas reciente."""
    if not filas:
        return 0

    def col(*claves: str) -> int:
        for i, h in enumerate(headers):
            if any(c in h for c in claves):
                return i
        return -1

    i_estado = col("ESTADO")
    i_emision = col("EMISI")

    def valor(fila: list[str], i: int) -> str:
        return fila[i] if 0 <= i < len(fila) else ""

    def clave(item: tuple[int, list[str]]):
        idx, fila = item
        vigente = valor(fila, i_estado).strip().upper() == "VIGENTE"
        return (vigente, _fecha_orden(valor(fila, i_emision)), -idx)

    return max(enumerate(filas), key=clave)[0]


def selector_ver_mejor_fila(page: Page, logger: logging.Logger, fallback_selector: str) -> str:
    """Devuelve el selector del enlace Ver de la fila elegida (o el fallback si no se pudo leer)."""
    try:
        data = page.evaluate(_JS_FILAS_RESULTADO, TBODY_RESULTADOS) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron leer las filas de resultados (%s); se abre la primera", exc)
        return fallback_selector
    filas = data.get("filas") or []
    if len(filas) <= 1:
        return fallback_selector
    idx = elegir_indice_fila(data.get("headers") or [], filas)
    logger.info("Varios carnes (%s filas); se abre la fila %s: %s", len(filas), idx + 1, " | ".join(filas[idx]))
    fila = TBODY_RESULTADOS + " > tr:not(.ui-datatable-empty-message):nth-child(" + str(idx + 1) + ")"
    return fila + " a.ui-commandlink:has-text('Ver'), " + fila + " a.ui-commandlink"
