from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from typing import TypeVar

from playwright.sync_api import sync_playwright

from src.agents_flow.dssp_emision_flow import process_no_encontrados_in_bandeja_emision
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
from src.agents_flow.login_flow.logging import RunLoggers, max_run_dirs, prune_old_run_dirs
from src.agents_flow.mis_vigilantes_flow import navigate_to_mis_vigilantes, process_records_in_mis_vigilantes
from src.agents_flow.notifications import send_run_summary_mail

T = TypeVar("T")


def _merge_dssp_validation_results(
    results: list[SearchResult],
    validated_results: list[SearchResult],
) -> list[SearchResult]:
    validated_by_document = {result.documento: result for result in validated_results if result.documento}
    if not validated_by_document:
        return list(results)

    merged: list[SearchResult] = []
    for result in results:
        replacement = validated_by_document.get(result.documento)
        if replacement is not None and (result.estado or "").strip().upper() == "NO_ENCONTRADO":
            merged.append(replacement)
        else:
            merged.append(result)
    return merged


def _build_failed_batch_results(records: list[InputRecord], error_message: str) -> list[SearchResult]:
    return [
        SearchResult(
            documento=record.dni,
            tipo_documento="DNI",
            nombre=record.apellidos_nombres,
            estado="WORKER_ERROR",
            empresa=error_message,
        )
        for record in records
    ]


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


def _split_records(records: list[T], worker_count: int) -> list[list[T]]:
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


def _wait_for_browser_close_if_needed(page, browser, settings, grupo: str, logger) -> None:
    if not settings.hold_browser_open or settings.headless:
        return

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

            if keep_browser_open:
                _wait_for_browser_close_if_needed(page, browser, settings, grupo, logger)

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
            _wait_for_browser_close_if_needed(page, browser, settings, grupo, logger)
        finally:
            close_browser(browser, context, logger=logger)
            run_loggers.close()


def _run_dssp_validation_pass(
    grupo: str,
    settings,
    run_name: str,
    results: list[SearchResult],
) -> list[SearchResult]:
    targets = [result for result in results if (result.estado or "").strip().upper() == "NO_ENCONTRADO"]
    if not targets:
        return []

    if settings.scheduled_multiworker and len(targets) > 1:
        return _run_dssp_validation_multiworker(grupo, settings, run_name, targets)

    return _run_dssp_validation_single_worker(grupo, settings, run_name, targets, worker_id=1, worker_total=1)


def _run_dssp_validation_single_worker(
    grupo: str,
    settings,
    run_name: str,
    targets: list[SearchResult],
    worker_id: int,
    worker_total: int,
) -> list[SearchResult]:
    scope_name = f"postproceso_{worker_id:02d}"
    run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name=scope_name)
    logger = run_loggers.get("login_flow")
    dssp_logger = run_loggers.get("dssp_emision_flow")
    orchestration_logger = run_loggers.get("orchestration_flow")

    effective_settings = replace(settings, hold_browser_open=False)
    _configure_worker_browser_env(worker_id, worker_total)
    max_worker_attempts = max(1, settings.login_captcha_retries)
    last_exception: Exception | None = None

    try:
        with sync_playwright() as playwright:
            for worker_attempt in range(1, max_worker_attempts + 1):
                browser = None
                context = None
                orchestration_logger.info(
                    "[%s] Iniciando segunda etapa DSSP | worker=%s/%s | intento=%s/%s | registros_no_encontrado=%s",
                    grupo,
                    worker_id,
                    worker_total,
                    worker_attempt,
                    max_worker_attempts,
                    len(targets),
                )
                try:
                    browser, context, page = open_browser(playwright, effective_settings)
                    login(page, effective_settings, credentials_for_group(grupo), grupo, logger)
                    logger.info("[%s] URL post-login etapa DSSP: %s", grupo, page.url)
                    validated = process_no_encontrados_in_bandeja_emision(page, targets, dssp_logger)
                    orchestration_logger.info(
                        "[%s] Segunda etapa DSSP completada | worker=%s/%s | intento=%s/%s | registros_validados=%s",
                        grupo,
                        worker_id,
                        worker_total,
                        worker_attempt,
                        max_worker_attempts,
                        len(validated),
                    )
                    return validated
                except Exception as exc:
                    last_exception = exc
                    if worker_attempt < max_worker_attempts:
                        orchestration_logger.warning(
                            "[%s] Reintentando worker DSSP %s/%s tras fallo en intento %s/%s | error=%s: %s",
                            grupo,
                            worker_id,
                            worker_total,
                            worker_attempt,
                            max_worker_attempts,
                            type(exc).__name__,
                            exc,
                        )
                    else:
                        orchestration_logger.error(
                            "[%s] Worker DSSP %s/%s agoto reintentos | error=%s: %s",
                            grupo,
                            worker_id,
                            worker_total,
                            type(exc).__name__,
                            exc,
                        )
                finally:
                    close_browser(browser, context, logger=logger)
    finally:
        run_loggers.close()

    if last_exception is not None:
        raise last_exception
    raise RuntimeError(f"[{grupo}] Segunda etapa DSSP finalizo sin resultado para worker {worker_id}")


def _run_dssp_validation_worker_batch(
    grupo: str,
    settings,
    run_name: str,
    batch_index: int,
    worker_total: int,
    targets: list[SearchResult],
) -> tuple[int, list[SearchResult]]:
    results = _run_dssp_validation_single_worker(
        grupo=grupo,
        settings=settings,
        run_name=run_name,
        targets=targets,
        worker_id=batch_index + 1,
        worker_total=worker_total,
    )
    return batch_index, results


def _run_dssp_validation_multiworker(
    grupo: str,
    settings,
    run_name: str,
    targets: list[SearchResult],
) -> list[SearchResult]:
    run_loggers = RunLoggers(settings.logs_dir, run_name=run_name, scope_name="postproceso_coordinador")
    orchestration_logger = run_loggers.get("orchestration_flow")
    try:
        worker_count = _resolve_worker_count(settings, len(targets))
        batches = _split_records(targets, worker_count)
        orchestration_logger.info(
            "[%s] Segunda etapa DSSP multiworker | workers=%s | registros_no_encontrado=%s",
            grupo,
            len(batches),
            len(targets),
        )

        results_by_batch: dict[int, list[SearchResult]] = {}
        with ProcessPoolExecutor(max_workers=len(batches)) as executor:
            futures = {
                executor.submit(
                    _run_dssp_validation_worker_batch,
                    grupo,
                    settings,
                    run_name,
                    batch_index,
                    len(batches),
                    batch,
                ): (batch_index, batch)
                for batch_index, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_index, batch = futures[future]
                try:
                    completed_batch_index, batch_results = future.result()
                    results_by_batch[completed_batch_index] = batch_results
                    orchestration_logger.info(
                        "[%s] DSSP worker %s completado | resultados=%s",
                        grupo,
                        completed_batch_index + 1,
                        len(batch_results),
                    )
                except Exception as exc:
                    orchestration_logger.exception(
                        "[%s] DSSP worker %s fallo | registros=%s | error=%s: %s",
                        grupo,
                        batch_index + 1,
                        len(batch),
                        type(exc).__name__,
                        exc,
                    )
                    results_by_batch[batch_index] = batch

        ordered_results: list[SearchResult] = []
        for batch_index in range(len(batches)):
            ordered_results.extend(results_by_batch.get(batch_index, []))

        return ordered_results
    finally:
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
            futures = {
                executor.submit(
                    _run_worker_batch,
                    grupo,
                    settings,
                    run_name,
                    batch_index,
                    len(batches),
                    batch,
                ): (batch_index, batch)
                for batch_index, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_index, batch = futures[future]
                try:
                    completed_batch_index, batch_results = future.result()
                    results_by_batch[completed_batch_index] = batch_results
                    orchestration_logger.info(
                        "[%s] Worker %s completado | resultados=%s",
                        grupo,
                        completed_batch_index + 1,
                        len(batch_results),
                    )
                except Exception as exc:
                    error_message = f"{type(exc).__name__}: {exc}"
                    orchestration_logger.exception(
                        "[%s] Worker %s fallo | filas %s-%s | error=%s",
                        grupo,
                        batch_index + 1,
                        batch[0].row_number,
                        batch[-1].row_number,
                        error_message,
                    )
                    results_by_batch[batch_index] = _build_failed_batch_results(batch, error_message)
                    orchestration_logger.info(
                        "[%s] Worker %s marcado como fallido | resultados_sustituidos=%s",
                        grupo,
                        batch_index + 1,
                        len(results_by_batch[batch_index]),
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
        orchestration_logger = run_loggers.get("orchestration_flow")
        output_dir = settings.lots_dir / run_name
        output_dir.mkdir(parents=True, exist_ok=True)
        deleted_lot_dirs = prune_old_run_dirs(
            settings.lots_dir,
            keep_dirs=max_run_dirs(),
            protected_dir=output_dir,
        )
        if deleted_lot_dirs:
            orchestration_logger.info(
                "Control de lotes aplicado: %s corrida(s) antigua(s) eliminada(s)",
                deleted_lot_dirs,
            )
        primary_output_path = write_search_results(output_dir, results, excel_logger)

        try:
            dssp_results = _run_dssp_validation_pass(grupo, settings, run_name, results)
        except Exception as exc:
            orchestration_logger.exception(
                "[%s] Segunda etapa DSSP fallo sin afectar la salida principal | error=%s: %s",
                grupo,
                type(exc).__name__,
                exc,
            )
            dssp_results = []

        merged_dssp_results = _merge_dssp_validation_results(results, dssp_results) if dssp_results else list(results)
        validation_output_path = write_search_results(
            output_dir,
            merged_dssp_results,
            excel_logger,
            filename_prefix="RB_GADSOValidacionNoEncontradosSUCAMEC",
        )
        notification_attachments = [primary_output_path, validation_output_path]

        send_run_summary_mail(
            grupo=grupo,
            run_name=run_name,
            results=results,
            dssp_results=dssp_results,
            attachments=notification_attachments,
            logger=orchestration_logger,
        )
    finally:
        run_loggers.close()
