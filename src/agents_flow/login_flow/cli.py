from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright

from .auth import login
from .browser import close_browser, open_browser
from .config import credentials_for_group, load_settings
from .logging import RunLoggers
from ..mis_vigilantes_flow import navigate_to_mis_vigilantes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flujo segmentado SUCAMEC")
    parser.add_argument(
        "--grupo",
        choices=["JV", "SELVA", "TODOS"],
        default="JV",
        help="Credenciales a usar para probar login.",
    )
    parser.add_argument(
        "--solo-login",
        action="store_true",
        help="Ejecuta solo el login y no navega a CONSULTAS > MIS VIGILANTES.",
    )
    return parser.parse_args()


def run_login_for_group(grupo: str, solo_login: bool = False) -> None:
    settings = load_settings()
    run_loggers = RunLoggers(settings.logs_dir)
    logger = run_loggers.get("login_flow")
    mis_vigilantes_logger = run_loggers.get("mis_vigilantes_flow")
    browser = None
    context = None

    with sync_playwright() as playwright:
        try:
            browser, context, page = open_browser(playwright, settings)
            login(page, settings, credentials_for_group(grupo), grupo, logger)
            logger.info("[%s] URL post-login: %s", grupo, page.url)
            if not solo_login:
                navigate_to_mis_vigilantes(page, mis_vigilantes_logger)
                mis_vigilantes_logger.info("[%s] URL post-MIS VIGILANTES: %s", grupo, page.url)

            if settings.hold_browser_open and not settings.headless:
                logger.info("[%s] Navegador abierto para inspeccion. Cierra la ventana o usa Ctrl+C.", grupo)
                try:
                    while True:
                        try:
                            browser_closed = page.is_closed() or not browser.is_connected()
                        except Exception:
                            browser_closed = True
                        if browser_closed:
                            logger.info("[%s] Ventana del navegador cerrada por el usuario", grupo)
                            break
                        try:
                            page.wait_for_timeout(1000)
                        except Exception:
                            logger.info("[%s] Ventana del navegador cerrada por el usuario", grupo)
                            break
                except KeyboardInterrupt:
                    logger.info("[%s] Interrupcion manual recibida", grupo)
        finally:
            close_browser(browser, context, logger=logger)
            run_loggers.close()


def main() -> int:
    args = parse_args()
    groups = ["JV", "SELVA"] if args.grupo == "TODOS" else [args.grupo]
    for group in groups:
        run_login_for_group(group, solo_login=args.solo_login)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
