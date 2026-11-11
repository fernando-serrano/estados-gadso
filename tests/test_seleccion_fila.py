"""Eleccion de fila cuando SUCAMEC devuelve varios carnes del mismo documento."""
import logging

import pytest

from src.agents_flow.consultas_common import elegir_indice_fila, selector_ver_mejor_fila

H = ["NRO CARNÉ", "NOMBRE", "FEC EMISIÓN", "FEC VEN.", "NRO DOCUMENTO", "ESTADO", "MODALIDAD", "VER"]


def fila(carne, emision, estado):
    return [carne, "ROJAS ATIZ LUIS ANTONIO", emision, "", "76632619", estado, "X", "Ver"]


def test_caso_real_vigente_en_segunda_fila():
    filas = [fila("7926008", "31/01/2024", "VENCIDO"), fila("7877172", "20/10/2026", "VIGENTE")]
    assert elegir_indice_fila(H, filas) == 1


def test_vigente_gana_aunque_sea_mas_antiguo():
    filas = [fila("1", "01/01/2026", "CESADO"), fila("2", "01/01/2023", "VIGENTE")]
    assert elegir_indice_fila(H, filas) == 1


def test_sin_vigente_toma_emision_mas_reciente():
    filas = [fila("1", "05/03/2022", "VENCIDO"), fila("2", "12/11/2024", "CESADO"), fila("3", "01/01/2020", "VENCIDO")]
    assert elegir_indice_fila(H, filas) == 1


def test_dos_vigentes_toma_el_mas_reciente():
    filas = [fila("1", "01/01/2025", "VIGENTE"), fila("2", "01/06/2025", "VIGENTE")]
    assert elegir_indice_fila(H, filas) == 1


def test_empate_o_sin_cabeceras_conserva_la_primera():
    assert elegir_indice_fila([], [["a"], ["b"]]) == 0
    assert elegir_indice_fila(H, [fila("1", "", ""), fila("2", "", "")]) == 0


HTML = """<table id="buscarForm:buscarDatatable"><thead><tr>
<th>Nro carné</th><th>Nombre</th><th>Fec emisión</th><th>Fec ven.</th><th>Nro Documento</th><th>Estado</th><th>Modalidad</th><th>Ver</th></tr></thead>
<tbody id="buscarForm:buscarDatatable_data">
<tr><td>7926008</td><td>ROJAS</td><td>31/01/2024</td><td></td><td>76632619</td><td>VENCIDO</td><td>SISP</td>
<td><a class="ui-commandlink" href="#" onclick="document.title='7926008';return false">Ver</a></td></tr>
<tr><td>7877172</td><td>ROJAS</td><td>20/10/2026</td><td></td><td>76632619</td><td>VIGENTE</td><td>VP</td>
<td><a class="ui-commandlink" href="#" onclick="document.title='7877172';return false">Ver</a></td></tr>
</tbody></table>"""


def test_navegador_abre_la_fila_vigente():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(HTML)
        sel = selector_ver_mejor_fila(page, logging.getLogger("t"), "a.ui-commandlink")
        page.locator(sel).first.click()
        assert page.title() == "7877172"
        browser.close()
