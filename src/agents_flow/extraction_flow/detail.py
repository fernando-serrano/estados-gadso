from __future__ import annotations

import logging
import re
import unicodedata

from playwright.sync_api import Page


DETAIL_OUTPUT_FIELDS = [
    "documento",
    "tipo_documento",
    "nombre",
    "estado",
    "nro_carne",
    "modalidad",
    "ruc",
    "expediente",
    "nro_expediente",
    "anho_expediente",
    "fecha_emision",
    "fecha_vencimiento",
    "empresa",
]

# Compatibilidad interna si algun modulo ya importa OUTPUT_FIELDS desde este archivo.
OUTPUT_FIELDS = DETAIL_OUTPUT_FIELDS


FIELD_LABELS = {
    "documento": ["NRO DOCUMENTO", "NRO. DOCUMENTO", "NUMERO DOCUMENTO"],
    "tipo_documento": ["DESC USR", "DESC. USR", "TIPO DOCUMENTO", "TIPO DE DOCUMENTO"],
    "nombre": ["NOMBRE"],
    "estado": ["ESTADO"],
    "nro_carne": ["NRO CARNE", "NRO CARNÉ", "NRO. CARNE", "NRO. CARNÉ"],
    "modalidad": ["MODALIDAD"],
    "ruc": ["RUC"],
    "expediente": ["EXPEDIENTE"],
    "nro_expediente": ["NRO EXPEDIENTE", "NRO. EXPEDIENTE"],
    "anho_expediente": ["ANO EXPEDIENTE", "AÑO EXPEDIENTE"],
    "fecha_emision": ["FEC EMISION", "FEC EMISIÓN", "FECHA EMISION", "FECHA EMISIÓN"],
    "fecha_vencimiento": ["FEC VENCIMIENTO", "FECHA VENCIMIENTO"],
    "empresa": ["EMPRESA"],
}


def _normalize_label(value: str) -> str:
    text = str(value or "").strip().upper().replace(":", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


NORMALIZED_FIELD_LABELS = {
    field: {_normalize_label(label) for label in labels}
    for field, labels in FIELD_LABELS.items()
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def wait_detail_view(page: Page, timeout_ms: int = 9000) -> None:
    page.locator("#verForm\\:panelGrid").first.wait_for(state="visible", timeout=timeout_ms)


def extract_detail_fields(page: Page, logger: logging.Logger) -> dict[str, str]:
    wait_detail_view(page)
    raw_rows = page.evaluate(
        """() => {
            const tables = Array.from(document.querySelectorAll('#verForm\\\\:panelGrid'));
            const rows = [];
            for (const table of tables) {
                for (const tr of Array.from(table.querySelectorAll('tr'))) {
                    const cells = Array.from(tr.querySelectorAll('td'));
                    if (cells.length < 2) continue;
                    const key = String(cells[0].innerText || '').replace(/\\s+/g, ' ').trim();
                    const value = String(cells[1].innerText || '').replace(/\\s+/g, ' ').trim();
                    if (key || value) rows.push({key, value});
                }
            }
            return rows;
        }"""
    )

    by_label: dict[str, str] = {}
    for row in raw_rows or []:
        key = _normalize_label(str(row.get("key", "")))
        value = _clean_text(str(row.get("value", "")))
        if key:
            by_label[key] = value

    output = {field: "" for field in DETAIL_OUTPUT_FIELDS}
    for field, labels in NORMALIZED_FIELD_LABELS.items():
        for label in labels:
            if label in by_label:
                output[field] = by_label[label]
                break

    logger.info(
        "Detalle extraido: documento=%s | estado=%s | nro_carne=%s",
        output.get("documento", ""),
        output.get("estado", ""),
        output.get("nro_carne", ""),
    )
    return output
