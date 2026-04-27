MENU_SELECTORS = {
    "menu_root": "#j_idt11\\:menuPrincipal, #j_idt11\\:menuprincipal",
    "header_dssp": (
        '.ui-panelmenu-header:has(a:text-is("DSSP")), '
        '.ui-panelmenu-header:has(a:has-text("DSSP"))'
    ),
    "item_bandeja_emision": (
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("BANDEJA DE EMISIÓN")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("BANDEJA DE EMISION")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("BANDEJA DE EMISIÓN")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("BANDEJA DE EMISION"))'
    ),
    "item_bandeja_emision_onclick": (
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:text-is("BANDEJA DE EMISIÓN")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:text-is("BANDEJA DE EMISION")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:has-text("BANDEJA DE EMISIÓN")), '
        'a[onclick*="PrimeFaces.ab"][onclick*="j_idt11"]:has(span.ui-menuitem-text:has-text("BANDEJA DE EMISION"))'
    ),
}

VIEW_SELECTORS = {
    "buscar_por_widget": "#listForm\\:buscarPor",
    "buscar_por_label": "#listForm\\:buscarPor_label",
    "buscar_por_items": "#listForm\\:buscarPor_items",
    "buscar_por_opcion_dni": "#listForm\\:buscarPor_4",
    "filtro_busqueda": "#listForm\\:filtroBusqueda",
    "boton_buscar": "#listForm\\:j_idt56, button:has-text('Buscar')",
    "tabla_resultados": "#listForm\\:dtResultados, table[role='grid']",
    "fila_sin_resultados": (
        "#listForm\\:dtResultados_data tr.ui-datatable-empty-message, "
        "tr.ui-datatable-empty-message"
    ),
    "filas_resultado": "#listForm\\:dtResultados_data > tr.ui-widget-content",
}
