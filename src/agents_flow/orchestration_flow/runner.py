from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace

from playwright.sync_api import sync_playwright

from src.agents_flow.excel_flow import (
    InputRecord,
    SearchResult,
    ensure_data_dirs,
    load_input_records,
    resolve_input_excel,
    write_search_results,
)
from src.agents_flow.login_flow.auth import login
from src.agents_flow.login_flow.browser import close_browser, open_browser
from src.agents_flow.login_flow.config import credentials_for_group, load_settings
from src.agents_flow.login_flow.logging import RunLoggers
from src.agents_flow.mis_vigilantes_flow import navigate_to_mis_vigilantes, process_records_in_mis_vigilantes


def _load_records(settings, excel_logger) -> list[InputRecord]:
    entrada_dir = ensure_data_dirs(settings.logs_dir.parent)
    input_excel = resolve_input_excel(entrada_dir, explicit_path=settings.input_excel_path)
    records = load_input_records(input_excel, excel_logger)
    if settings.max_records:
        records = records[: settings.max_records]
        excel_logger.info("Limite SUCAMEC_MAX_RECORDS aplicado: %s", len(records))
    return records


def _resolve_worker_count(settings, total_records: int) -> int:
    if total_records <= 0:
        return 1

    worker_count = 1
    if settings.scheduled_multiworker:
        worker_count = min(settings.scheduled_workers, total_records)

    if settings.worker_max_rows > 0:
        worker_count = min(
            total_records,
            max(worker_count, math.ceil(total_records / settings.worker_max_rows)),
        )

    return max(1, worker_count)


def _split_records(records: list[InputRecord], worker_count: int) -> list[list[InputRecord]]:
    if not records:
        return []

    worker_count = max(1, min(worker_count, len(records)))
    base_size, remainder = divmod(len(records), worker_count)
    batches: list[list[InputRecord]] = []
    start = 0

    for index in range(worker_count):
        batch_size = base_size + (1 if index < remainder else 0)
        end = start + batch_size
        batch = records[start:end]
        if batch:
            batches.append(batch)
        start = end

    return batches


def _configure_worker_browser_env(worker_id: int, total_workers: int) -> None:
    os.environ["BROWSER_TILE_TOTAL"] = str(max(1, total_workers))
    os.environ["BROWSER_TILE_INDEX"] = str(max(0, worker_id - 1))


def _run_single_browser_batch(
    grupo: str,
    settings,
    run_name: str,
    records: list[InputRecord],
    worker_id: int = 1,
    worker_total: int = 1,
    keep_browser_open: bool = False,
) -> list[SearchResult]:
    worker_scope = f"worker_{worker_id:02d}"
    run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name=worker_scope)
    logger = run_loggers.get("login_flow")
    mis_vigilantes_logger = run_loggers.get("mis_vigilantes_flow")
    browser = None
    context = None

    effective_settings = replace(settings, hold_browser_open=False)
    _configure_worker_browser_env(worker_id, worker_total)

    with sync_playwright() as playwright:
        try:
            browser, context, page = open_browser(playwright, effective_settings)
            login(page, effective_settings, credentials_for_group(grupo), grupo, logger)
            logger.info("[%s] URL post-login: %s", grupo, page.url)
            if not records:
                return []

            navigate_to_mis_vigilantes(page, mis_vigilantes_logger)
            mis_vigilantes_logger.info("[%s] URL post-MIS VIGILANTES: %s", grupo, page.url)
            mis_vigilantes_logger.info(
                "[worker %s/%s] Procesando lote de %s registro(s): filas %s-%s",
                worker_id,
                worker_total,
                len(records),
                records[0].row_number,
                records[-1].row_number,
            )
            results = process_records_in_mis_vigilantes(page, records, mis_vigilantes_logger)

            if keep_browser_open and settings.hold_browser_open and not settings.headless:
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

            return results
        finally:
            close_browser(browser, context, logger=logger)
            run_loggers.close()


def _run_worker_batch(
    grupo: str,
    settings,
    run_name: str,
    batch_index: int,
    worker_total: int,
    records: list[InputRecord],
) -> tuple[int, list[SearchResult]]:
    results = _run_single_browser_batch(
        grupo=grupo,
        settings=settings,
        run_name=run_name,
        records=records,
        worker_id=batch_index + 1,
        worker_total=worker_total,
    )
    return batch_index, results


def _run_solo_login(grupo: str, settings, run_name: str) -> None:
    run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name="worker_01")
    logger = run_loggers.get("login_flow")
    browser = None
    context = None

    with sync_playwright() as playwright:
        try:
            browser, context, page = open_browser(playwright, settings)
            login(page, settings, credentials_for_group(grupo), grupo, logger)
            logger.info("[%s] URL post-login: %s", grupo, page.url)

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


def _run_multiworker(grupo: str, settings, run_name: str, records: list[InputRecord]) -> list[SearchResult]:
    run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name="coordinador")
    orchestration_logger = run_loggers.get("orchestration_flow")
    try:
        worker_count = _resolve_worker_count(settings, len(records))
        batches = _split_records(records, worker_count)
        orchestration_logger.info(
            "[%s] Multiworker activado | workers=%s | registros=%s",
            grupo,
            len(batches),
            len(records),
        )
        for index, batch in enumerate(batches, start=1):
            orchestration_logger.info(
                "[%s] Worker %s asignado a %s registro(s): filas %s-%s",
                grupo,
                index,
                len(batch),
                batch[0].row_number,
                batch[-1].row_number,
            )

        results_by_batch: dict[int, list[SearchResult]] = {}
        with ProcessPoolExecutor(max_workers=len(batches)) as executor:
            futures = [
                executor.submit(
                    _run_worker_batch,
                    grupo,
                    settings,
                    run_name,
                    batch_index,
                    len(batches),
                    batch,
                )
                for batch_index, batch in enumerate(batches)
            ]
            for future in as_completed(futures):
                batch_index, batch_results = future.result()
                results_by_batch[batch_index] = batch_results
                orchestration_logger.info(
                    "[%s] Worker %s completado | resultados=%s",
                    grupo,
                    batch_index + 1,
                    len(batch_results),
                )

        ordered_results: list[SearchResult] = []
        for batch_index in range(len(batches)):
            ordered_results.extend(results_by_batch.get(batch_index, []))

        return ordered_results
    finally:
        run_loggers.close()


def run_group_flow(grupo: str, solo_login: bool = False) -> None:
    settings = load_settings()
    run_loggers = RunLoggers(settings.logs_dir, scope_name="coordinador")
    run_name = run_loggers.run_name
    excel_logger = run_loggers.get("excel_flow")

    try:
        if solo_login:
            run_loggers.close()
            _run_solo_login(grupo, settings, run_name)
            return

        records = _load_records(settings, excel_logger)
        if settings.scheduled_multiworker and len(records) > 1:
            results = _run_multiworker(grupo, settings, run_name, records)
        else:
            run_loggers.close()
            results = _run_single_browser_batch(
                grupo,
                settings,
                run_name,
                records,
                keep_browser_open=True,
            )

        run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name="coordinador")
        excel_logger = run_loggers.get("excel_flow")
        write_search_results(settings.lots_dir / run_name, results, excel_logger)
    finally:
        run_loggers.close()
