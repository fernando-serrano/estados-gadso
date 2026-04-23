from __future__ import annotations

import logging
import re

from playwright.sync_api import Page


LICENSE_OUTPUT_FIELDS = [
    "licencia_numero",
    "licencia_fecha_emision",
    "licencia_fecha_venc",
    "licencia_modalidad",
    "licencia_restricciones",
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_license_fields(page: Page, logger: logging.Logger) -> dict[str, str]:
    raw_rows = page.evaluate(
        """() => {
            const tbody = document.querySelector('#verForm\\\\:licDatatable_data');
            if (!tbody) return [];

            return Array.from(tbody.querySelectorAll('tr')).map((tr) =>
                Array.from(tr.querySelectorAll('td')).map((td) =>
                    String(td.innerText || '').replace(/\\s+/g, ' ').trim()
                )
            );
        }"""
    )

    output = {field: "" for field in LICENSE_OUTPUT_FIELDS}
    rows = [row for row in (raw_rows or []) if any(_clean_text(value) for value in row)]
    if rows:
        first_row = rows[0]
        field_names = [
            "numero",
            "fecha_emision",
            "fecha_venc",
            "modalidad",
            "restricciones",
        ]
        for position, field_name in enumerate(field_names):
            value = first_row[position] if position < len(first_row) else ""
            output[f"licencia_{field_name}"] = _clean_text(value)

    logger.info(
        "Licencia extraida: numero=%s | vencimiento=%s",
        output.get("licencia_numero", ""),
        output.get("licencia_fecha_venc", ""),
    )
    return output
