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

LICENSE_MODALITY_PRIORITY = {
    "L4": 0,
    "L1": 1,
    "L2": 2,
    "L3": 3,
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_license_code(modalidad: str) -> str:
    match = re.search(r"\((L\d+)\)", _clean_text(modalidad).upper())
    return match.group(1) if match else ""


def _select_license_row(rows: list[list[str]]) -> list[str]:
    prioritized_rows: list[tuple[int, int, list[str]]] = []

    for index, row in enumerate(rows):
        modalidad = row[3] if len(row) > 3 else ""
        license_code = _extract_license_code(modalidad)
        if license_code not in LICENSE_MODALITY_PRIORITY:
            continue
        prioritized_rows.append((LICENSE_MODALITY_PRIORITY[license_code], index, row))

    if not prioritized_rows:
        return []

    prioritized_rows.sort(key=lambda item: (item[0], item[1]))
    return prioritized_rows[0][2]


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
    selected_row = _select_license_row(rows)
    if selected_row:
        field_names = [
            "numero",
            "fecha_emision",
            "fecha_venc",
            "modalidad",
            "restricciones",
        ]
        for position, field_name in enumerate(field_names):
            value = selected_row[position] if position < len(selected_row) else ""
            output[f"licencia_{field_name}"] = _clean_text(value)

    logger.info(
        "Licencia extraida: candidatos=%s | modalidad=%s | numero=%s | vencimiento=%s",
        len(rows),
        output.get("licencia_modalidad", ""),
        output.get("licencia_numero", ""),
        output.get("licencia_fecha_venc", ""),
    )
    return output
