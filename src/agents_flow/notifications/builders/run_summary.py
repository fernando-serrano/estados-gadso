from __future__ import annotations

from datetime import datetime
from pathlib import Path


def build_subject(subject_prefix: str, grupo: str, run_name: str, attachment_count: int) -> str:
    pieces = [subject_prefix, "Resumen flujo SUCAMEC", grupo]
    if attachment_count:
        pieces.append(f"{attachment_count} excel")
    pieces.append(run_name)
    return " | ".join(piece for piece in pieces if piece)


def _summary_header() -> str:
    labels = [
        "Total procesados",
        "No encontrado",
        "Sin Ver",
        "Worker error",
        "Validados por DSSP",
    ]
    return "".join(
        f"<th style='border:1px solid #d0d7de;padding:8px;background:#f6f8fa;text-align:center;'>{label}</th>"
        for label in labels
    )


def _summary_values(summary: dict[str, int]) -> str:
    values = [
        summary.get("total_registros", 0),
        summary.get("no_encontrado", 0),
        summary.get("sin_ver", 0),
        summary.get("worker_error", 0),
        summary.get("con_dssp", 0),
    ]
    return "".join(
        f"<td style='border:1px solid #d0d7de;padding:8px;text-align:center;'>{value}</td>"
        for value in values
    )


def _attachment_list(attachments: list[Path]) -> str:
    if not attachments:
        return "<li>Sin adjuntos disponibles</li>"
    return "".join(f"<li>{path.name}</li>" for path in attachments)


def build_html_body(
    grupo: str,
    run_name: str,
    summary: dict[str, int],
    attachments: list[Path],
) -> str:
    now = datetime.now()
    generated_date = now.strftime("%d/%m/%Y")
    generated_time = now.strftime("%H:%M:%S")
    highlight_style = "background:#fff3b0;padding:2px 6px;border-radius:4px;"
    return (
        "<p>Saludos &#129302;</p>"
        "<p>Se completó la corrida del flujo <strong>SUCAMEC - MIS VIGILANTES</strong> y se adjuntan los Excel generados.</p>"
        "<p>"
        f"<strong>Grupo:</strong> {grupo}<br>"
        f"<strong>Corrida:</strong> {run_name}<br>"
        f"<strong>Generado:</strong> "
        f"<span style='{highlight_style}'>{generated_date}</span> "
        f"<span style='{highlight_style}'>{generated_time} hras</span>"
        "</p>"
        "<p><strong>Resumen operativo:</strong></p>"
        "<table style='border-collapse:collapse;border:1px solid #d0d7de;'>"
        f"<thead><tr>{_summary_header()}</tr></thead>"
        f"<tbody><tr>{_summary_values(summary)}</tr></tbody></table>"
        "<p><strong>Archivos adjuntos:</strong></p>"
        f"<ul>{_attachment_list(attachments)}</ul>"
        "<p>Correo emitido automáticamente por el bot.</p>"
    )
