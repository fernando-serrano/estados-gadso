MENU_SELECTORS = {
    "menu_root": "#j_idt11\\:menuPrincipal, #j_idt11\\:menuprincipal",
    "header_consultas": (
        '.ui-panelmenu-header:has(a:text-is("CONSULTAS")), '
        '.ui-panelmenu-header:has(a:has-text("CONSULTAS")), '
        '.ui-panelmenu-header:has(a:text-is("Consultas")), '
        '.ui-panelmenu-header:has(a:has-text("Consultas"))'
    ),
    "item_mis_vigilantes": (
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("MIS VIGILANTES")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("MIS VIGILANTES")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:text-is("Mis vigilantes")), '
        '.ui-menuitem-link:has(span.ui-menuitem-text:has-text("Mis vigilantes"))'
    ),
    "item_mis_vigilantes_onclick": (
        'a[onclick*="addSubmitParam"][onclick*="j_idt11:menuprincipal"]:has(span.ui-menuitem-text:text-is("MIS VIGILANTES")), '
        'a[onclick*="addSubmitParam"][onclick*="j_idt11:menuPrincipal"]:has(span.ui-menuitem-text:text-is("MIS VIGILANTES")), '
        'a[onclick*="addSubmitParam"][onclick*="j_idt11:menuprincipal"]:has(span.ui-menuitem-text:has-text("MIS VIGILANTES")), '
        'a[onclick*="addSubmitParam"][onclick*="j_idt11:menuPrincipal"]:has(span.ui-menuitem-text:has-text("MIS VIGILANTES"))'
    ),
}

VIEW_SELECTORS = {
    "dni_inputs": (
        'input[id*="dni"], input[id*="Dni"], input[id*="DNI"], '
        'input[name*="dni"], input[name*="Dni"], input[name*="DNI"]'
    ),
    "buscar_buttons": (
        'button:has-text("Buscar"), input[type="submit"][value*="Buscar"], '
        'button[id*="buscar"], button[id*="Buscar"], button[id*="btnBuscar"]'
    ),
}
