from __future__ import annotations

import logging
import re
import time
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


def _detail_view_is_ready(page: Page) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                    const isVisible = (element) => {
                        if (!element) return false;
                        const style = window.getComputedStyle(element);
                        if (!style) return false;
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            return false;
                        }
                        const rect = element.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };

                    const body = document.body;
                    if (!body || body.children.length === 0) return false;

                    const panel = document.querySelector('#verForm\\\\:panelGrid');
                    if (isVisible(panel)) return true;

                    const fallbackSelectors = [
                        '#verForm\\\\:licDatatable_data',
                        '#verForm\\\\:buscarCurDatatable_data',
                        '#verForm\\\\:buscarHistDatatable_data',
                        '#verForm'
                    ];
                    return fallbackSelectors.some((selector) => isVisible(document.querySelector(selector)));
                }"""
            )
        )
    except Exception:
        return False


def wait_detail_view(page: Page, timeout_ms: int = 18000) -> None:
    deadline = time.time() + (max(1000, timeout_ms) / 1000.0)

    while time.time() < deadline:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=1000)
        except Exception:
            pass

        if _detail_view_is_ready(page):
            return

        page.wait_for_timeout(250)

    page.locator("#verForm\\:panelGrid").first.wait_for(state="visible", timeout=1000)


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
