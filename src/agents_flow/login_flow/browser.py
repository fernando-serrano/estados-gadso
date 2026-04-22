from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from .config import Settings, bool_env, int_env


def build_launch_args() -> list[str]:
    args = ["--disable-infobars"]

    if bool_env("BROWSER_KEEP_VISIBLE", default=True):
        args.extend(
            [
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=CalculateNativeWinOcclusion",
            ]
        )

    if bool_env("BROWSER_START_MAXIMIZED", default=False):
        args.append("--start-maximized")

    if bool_env("BROWSER_TILE_ENABLE", default=False):
        total = max(1, int_env("BROWSER_TILE_TOTAL", 1))
        index = min(max(0, int_env("BROWSER_TILE_INDEX", 0)), total - 1)
        screen_w = int_env("BROWSER_TILE_SCREEN_W", 1920)
        screen_h = int_env("BROWSER_TILE_SCREEN_H", 1080)
        gap = max(0, int_env("BROWSER_TILE_GAP", 6))
        top = max(0, int_env("BROWSER_TILE_TOP_OFFSET", 0))
        cols = 1 if total == 1 else 2
        rows = (total + cols - 1) // cols
        cell_w = max(360, screen_w // cols)
        cell_h = max(320, (screen_h - top) // rows)
        col = index % cols
        row = index // cols
        args.extend(
            [
                f"--window-size={max(320, cell_w - (gap * 2))},{max(260, cell_h - (gap * 2))}",
                f"--window-position={col * cell_w + gap},{top + row * cell_h + gap}",
            ]
        )

    return args


def open_browser(playwright: Playwright, settings: Settings) -> tuple[Browser, BrowserContext, Page]:
    browser = playwright.chromium.launch(
        headless=settings.headless,
        slow_mo=0,
        args=build_launch_args(),
    )
    context = browser.new_context(no_viewport=True, ignore_https_errors=True)
    page = context.new_page()
    return browser, context, page


def close_browser(browser: Browser | None, context: BrowserContext | None, keep_open: bool = False) -> None:
    if keep_open:
        return
    if context is not None:
        context.close()
    if browser is not None:
        browser.close()
