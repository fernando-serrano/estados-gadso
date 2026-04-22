from __future__ import annotations

import argparse
import time

from playwright.sync_api import sync_playwright

from .auth import login
from .browser import close_browser, open_browser
from .config import credentials_for_group, load_settings
from .logging import build_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flujo segmentado SUCAMEC")
    parser.add_argument(
        "--grupo",
        choices=["JV", "SELVA", "TODOS"],
        default="JV",
        help="Credenciales a usar para probar login.",
    )
    return parser.parse_args()


def run_login_for_group(grupo: str) -> None:
    settings = load_settings()
    logger = build_logger(settings.logs_dir, name=f"sucamec_login_{grupo.lower()}")
    browser = None
    context = None

    with sync_playwright() as playwright:
        try:
            browser, context, page = open_browser(playwright, settings)
            login(page, settings, credentials_for_group(grupo), grupo, logger)
            logger.info("[%s] URL post-login: %s", grupo, page.url)

            if settings.hold_browser_open and not settings.headless:
                logger.info("[%s] Navegador abierto para inspeccion. Cierra con Ctrl+C.", grupo)
                while True:
                    time.sleep(60)
        finally:
            close_browser(browser, context, keep_open=settings.hold_browser_open and not settings.headless)


def main() -> int:
    args = parse_args()
    groups = ["JV", "SELVA"] if args.grupo == "TODOS" else [args.grupo]
    for group in groups:
        run_login_for_group(group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
