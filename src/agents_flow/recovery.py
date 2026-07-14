"""Recuperacion de sesion ante el corte intermitente de SUCAMEC.

SUCAMEC esta devolviendo de forma intermitente la pantalla "Error del servidor"
("Ha ocurrido un error interno en el sistema. Por favor vuelva a ingresar al
sistema.") cuyo enlace rebota al login. Cuando eso ocurre a mitad del flujo, el
registro en curso lanza excepcion.

Modelo de recuperacion (como lo haria una persona con su cola de registros):

1. Nivel registro (este modulo): si la sesion se corta pero la pagina sigue viva,
   se re-loguea sobre la MISMA pagina y se reintenta el registro pendiente. Es lo
   barato y rapido.
2. Nivel navegador (orchestration_flow.runner): si la pagina/navegador murio o el
   re-login persistente falla, se propaga la excepcion; el runner REABRE el
   navegador completo y REANUDA desde el registro pendiente, hasta acabar la cola.

Asi ningun registro se descarta: se reintenta hasta procesarlo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from playwright.sync_api import Page

from .excel_flow import InputRecord, SearchResult
from .login_flow.auth import login
from .login_flow.config import Credentials, Settings


# Texto del panel "Error del servidor" (mayusculas, sin tildes para matching robusto).
SERVER_ERROR_TEXT_MARKERS = (
    "ERROR DEL SERVIDOR",
    "ERROR INTERNO EN EL SISTEMA",
    "VUELVA A INGRESAR AL SISTEMA",
)


def page_shows_server_error(page: Page) -> bool:
    """Detecta la pantalla 'Error del servidor' de SUCAMEC o el rebote al login.

    Solo se invoca durante el procesamiento de registros (ya autenticados y dentro
    del modulo de consultas); por eso encontrarse de vuelta en login.xhtml significa
    que la sesion fue cortada por SUCAMEC.
    """
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "login.xhtml" in url:
        return True
    try:
        body = (page.locator("body").inner_text(timeout=500) or "").upper()
    except Exception:
        return False
    return any(marker in body for marker in SERVER_ERROR_TEXT_MARKERS)


def _confirm_server_error(page: Page) -> bool:
    """Confirma el corte tras una excepcion, dando margen a un redirect en curso."""
    if page_shows_server_error(page):
        return True
    try:
        page.wait_for_timeout(600)
    except Exception:
        pass
    return page_shows_server_error(page)


NavigateFn = Callable[[Page, logging.Logger], None]
SearchFn = Callable[[Page, InputRecord, logging.Logger], SearchResult]


@dataclass
class SessionRecovery:
    """Contexto para reabrir la sesion SUCAMEC sobre la misma pagina (re-login)."""

    page: Page
    settings: Settings
    credentials: Credentials
    grupo: str
    navigate_consultas: NavigateFn
    login_logger: logging.Logger
    flow_logger: logging.Logger

    @property
    def max_attempts(self) -> int:
        """Reintentos de re-login en la misma pagina antes de reabrir el navegador."""
        return max(1, self.settings.server_error_retries)

    @property
    def wait_ms(self) -> int:
        return max(0, self.settings.server_error_wait_ms)

    def restore_session(self) -> None:
        """Re-login y re-navegacion al modulo de consultas sobre la MISMA pagina.

        Si la pagina/navegador esta muerto, `login()` (page.goto) lanzara excepcion;
        se deja propagar para que el runner reabra el navegador completo.
        """
        if self.wait_ms:
            try:
                self.page.wait_for_timeout(self.wait_ms)
            except Exception:
                pass
        self.login_logger.warning(
            "[%s] Error del servidor SUCAMEC detectado; reabriendo sesion", self.grupo
        )
        login(self.page, self.settings, self.credentials, self.grupo, self.login_logger)
        self.navigate_consultas(self.page, self.flow_logger)
        self.flow_logger.info(
            "[%s] Sesion reabierta; se reanuda el registro pendiente", self.grupo
        )


def run_record_with_recovery(
    page: Page,
    record: InputRecord,
    logger: logging.Logger,
    search_fn: SearchFn,
    recovery: Optional[SessionRecovery],
) -> SearchResult:
    """Procesa un registro reanudando ante el corte de SUCAMEC.

    - Sesion cortada con pagina viva -> re-login en la misma pagina y reintenta.
    - Pagina/navegador muerto, o re-login agotado -> propaga la excepcion para que
      el runner reabra el navegador y reanude desde este mismo registro.
    - Errores ajenos al corte se propagan igual que antes (no se enmascaran bugs).
    """
    if recovery is None:
        return search_fn(page, record, logger)

    max_attempts = recovery.max_attempts
    attempt = 0

    while True:
        attempt += 1

        # Sesion cortada antes de empezar (este u otro registro previo): reabrir.
        if page_shows_server_error(page):
            logger.warning(
                "[FILA %s] Error del servidor antes de procesar; re-login en misma pagina (intento %s/%s)",
                record.row_number,
                attempt,
                max_attempts,
            )
            recovery.restore_session()  # si la pagina murio, propaga -> reabrir navegador

        try:
            return search_fn(page, record, logger)
        except Exception as exc:
            if not _confirm_server_error(page):
                # Pagina muerta o error ajeno al corte: lo maneja el runner (reabrir).
                raise
            logger.warning(
                "[FILA %s] Error del servidor durante el procesamiento (intento %s/%s): %s",
                record.row_number,
                attempt,
                max_attempts,
                exc,
            )
            if attempt >= max_attempts:
                logger.warning(
                    "[FILA %s] Agotado el re-login en misma pagina; se reabrira el navegador",
                    record.row_number,
                )
                raise
            recovery.restore_session()  # si falla, propaga -> reabrir navegador
