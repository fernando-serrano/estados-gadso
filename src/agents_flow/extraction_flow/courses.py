from __future__ import annotations

import logging
import re

from playwright.sync_api import Page


COURSE_OUTPUT_FIELDS = [
    "curso_ruc_1",
    "curso_razon_social_1",
    "curso_evaluacion_1",
    "curso_tipo_1",
    "curso_fecha_inicio_1",
    "curso_fecha_venc_1",
    "curso_estado_1",
    "curso_ruc_2",
    "curso_razon_social_2",
    "curso_evaluacion_2",
    "curso_tipo_2",
    "curso_fecha_inicio_2",
    "curso_fecha_venc_2",
    "curso_estado_2",
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_course_fields(page: Page, logger: logging.Logger) -> dict[str, str]:
    raw_rows = page.evaluate(
        """() => {
            const tbody = document.querySelector('#verForm\\\\:buscarCurDatatable_data');
            if (!tbody) return [];

            return Array.from(tbody.querySelectorAll('tr')).map((tr) =>
                Array.from(tr.querySelectorAll('td')).map((td) =>
                    String(td.innerText || '').replace(/\\s+/g, ' ').trim()
                )
            );
        }"""
    )

    output = {field: "" for field in COURSE_OUTPUT_FIELDS}
    rows = [row for row in (raw_rows or []) if any(_clean_text(value) for value in row)]
    field_names = [
        "ruc",
        "razon_social",
        "evaluacion",
        "tipo",
        "fecha_inicio",
        "fecha_venc",
        "estado",
    ]

    for index, row in enumerate((rows or [])[:2], start=1):
        for position, field_name in enumerate(field_names):
            value = row[position] if position < len(row) else ""
            output[f"curso_{field_name}_{index}"] = _clean_text(value)

    logger.info(
        "Cursos extraidos: curso_1=%s/%s | curso_2=%s/%s",
        output.get("curso_ruc_1", ""),
        output.get("curso_estado_1", ""),
        output.get("curso_ruc_2", ""),
        output.get("curso_estado_2", ""),
    )
    return output
