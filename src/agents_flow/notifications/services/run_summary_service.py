from __future__ import annotations

import logging
import urllib.error
from pathlib import Path

from src.agents_flow.excel_flow import SearchResult

from ..builders import build_html_body, build_subject
from ..graph_client import classify_graph_failure, send_mail
from ..mail_config import load_mail_config, mask_secret, validate_mail_config


def _build_summary(results: list[SearchResult], dssp_results: list[SearchResult]) -> dict[str, int]:
    states = [(result.estado or "").strip().upper() for result in results]
    return {
        "total_registros": len(results),
        "no_encontrado": sum(1 for state in states if state == "NO_ENCONTRADO"),
        "sin_ver": sum(1 for state in states if state == "SIN_VER"),
        "worker_error": sum(1 for state in states if state == "WORKER_ERROR"),
        "con_dssp": len(dssp_results),
    }


def send_run_summary_mail(
    grupo: str,
    run_name: str,
    results: list[SearchResult],
    dssp_results: list[SearchResult],
    attachments: list[Path],
    logger: logging.Logger,
) -> None:
    config = load_mail_config()
    config_error = validate_mail_config(config)
    if config_error:
        logger.info("Correo Graph de resumen omitido [CONFIG_INVALID]: %s", config_error)
        return

    valid_attachments = [path for path in attachments if isinstance(path, Path) and path.exists()]
    summary = _build_summary(results, dssp_results)
    subject = build_subject(config.subject_prefix, grupo, run_name, len(valid_attachments))
    body = build_html_body(grupo, run_name, summary, valid_attachments)

    try:
        logger.info(
            "Correo Graph resumen preparado | to=%s | cc=%s | attachments=%s | tenant_id=%s | client_id=%s | secret=%s",
            ",".join(config.to),
            ",".join(config.cc),
            ",".join(path.name for path in valid_attachments) or "-",
            config.tenant_id,
            config.client_id,
            mask_secret(config.client_secret),
        )
        send_mail(config, subject, body, valid_attachments)
        logger.info(
            "Correo Graph resumen enviado [SEND_OK] | attachments=%s",
            ",".join(path.name for path in valid_attachments) or "-",
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        error_tag, friendly_message = classify_graph_failure(exc.code, detail)
        logger.warning(
            "Fallo envio Graph resumen [%s] (HTTP %s) | %s | detalle=%s",
            error_tag,
            exc.code,
            friendly_message,
            detail,
        )
    except Exception as exc:
        logger.warning("Fallo envio Graph resumen [UNEXPECTED_ERROR] | %s", exc)
