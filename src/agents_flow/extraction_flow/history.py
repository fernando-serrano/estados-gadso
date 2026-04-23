from __future__ import annotations

import logging
import re

from playwright.sync_api import Page


HISTORY_OUTPUT_FIELDS = [
    "historial_ruc_1",
    "historial_razon_social_1",
    "historial_modalidad_1",
    "historial_procedimiento_1",
    "historial_fecha_emision_1",
    "historial_fecha_venc_1",
    "historial_fecha_baja_1",
    "historial_ruc_2",
    "historial_razon_social_2",
    "historial_modalidad_2",
    "historial_procedimiento_2",
    "historial_fecha_emision_2",
    "historial_fecha_venc_2",
    "historial_fecha_baja_2",
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_history_fields(page: Page, logger: logging.Logger) -> dict[str, str]:
    raw_rows = page.evaluate(
        """() => {
            const tbody = document.querySelector('#verForm\\\\:buscarHistDatatable_data');
            if (!tbody) return [];

            return Array.from(tbody.querySelectorAll('tr')).map((tr) =>
                Array.from(tr.querySelectorAll('td')).map((td) =>
                    String(td.innerText || '').replace(/\\s+/g, ' ').trim()
                )
            );
        }"""
    )

    output = {field: "" for field in HISTORY_OUTPUT_FIELDS}
    rows = [row for row in (raw_rows or []) if any(_clean_text(value) for value in row)]
    field_names = [
        "ruc",
        "razon_social",
        "modalidad",
        "procedimiento",
        "fecha_emision",
        "fecha_venc",
        "fecha_baja",
    ]

    for index, row in enumerate(rows[:2], start=1):
        for position, field_name in enumerate(field_names):
            value = row[position] if position < len(row) else ""
            output[f"historial_{field_name}_{index}"] = _clean_text(value)

    logger.info(
        "Historial extraido: historial_1=%s/%s | historial_2=%s/%s",
        output.get("historial_ruc_1", ""),
        output.get("historial_fecha_baja_1", ""),
        output.get("historial_ruc_2", ""),
        output.get("historial_fecha_baja_2", ""),
    )
    return output
