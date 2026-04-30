MENU_SELECTORS = {
    "menu_root": "#j_idt11\\:menuPrincipal, #j_idt11\\:menuprincipal",
    "header_consultas": (
        '.ui-panelmenu-header:has(a:text-is("CONSULTAS")), '
        '.ui-panelmenu-header:has(a:has-text("CONSULTAS")), '
        '.ui-panelmenu-header:has(a:text-is("Consultas")), '
        '.ui-panelmenu-header:has(a:has-text("Consultas"))'
    ),
    "item_busqueda_vigilantes": (
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("BUSQUEDA DE VIGILANTES")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("BUSQUEDA DE VIGILANTES")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("BÚSQUEDA DE VIGILANTES")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("BÚSQUEDA DE VIGILANTES"))'
    ),
    "item_busqueda_vigilantes_onclick": (
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:text-is("BUSQUEDA DE VIGILANTES")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:has-text("BUSQUEDA DE VIGILANTES")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:text-is("BÚSQUEDA DE VIGILANTES")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:has-text("BÚSQUEDA DE VIGILANTES"))'
    ),
}

VIEW_SELECTORS = {
    "tipo_documento_widget": "#buscarForm\\:tipoId",
    "tipo_documento_trigger": "#buscarForm\\:tipoId .ui-selectonemenu-trigger",
    "tipo_documento_label": "#buscarForm\\:tipoId_label",
    "opcion_nro_dni": "#buscarForm\\:tipoId_1",
    "opcion_nro_ce": "#buscarForm\\:tipoId_2",
    "criterio_busqueda": "#buscarForm\\:j_idt35",
    "boton_buscar": "#buscarForm\\:botonBuscar",
    "boton_buscar_vigilantes": "#verForm\\:j_idt201, button:has-text('Buscar vigilantes')",
    "tabla_resultados": "table[role='grid'], #buscarForm\\:buscarDatatable",
    "ver_primero": "#buscarForm\\:buscarDatatable\\:0\\:j_idt67, a.ui-commandlink:has-text('Ver')",
    "fila_sin_resultados": (
        "#buscarForm\\:buscarDatatable_data tr.ui-datatable-empty-message, "
        "tr.ui-datatable-empty-message"
    ),
}


def infer_document_type(document_number: str) -> str:
    digits = "".join(char for char in str(document_number or "").strip() if char.isdigit())
    if len(digits) == 9:
        return "CE"
    return "DNI"
