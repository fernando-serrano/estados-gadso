# ESTADOS GADSO - Flujo SUCAMEC

Automatizacion modular para acceder a la plataforma SUCAMEC, autenticar empresas J&V Resguardo/Selva y navegar al modulo `CONSULTAS > MIS VIGILANTES`.

## Instalacion Desde Cero

Requisitos del equipo:

- Windows 10/11.
- Python instalado y disponible en consola con `python --version`.
- Acceso a internet para instalar dependencias y navegador Playwright.
- Archivo `.env` en la raiz del proyecto con credenciales vigentes.

Instalacion recomendada:

```powershell
cd C:\Users\fserrano\Desktop\ESTADOS-GADSO
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Si PowerShell bloquea la activacion del entorno virtual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Luego vuelve a ejecutar:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Configuracion

El archivo `.env` debe estar en la raiz del proyecto. No se debe versionar ni compartir porque contiene credenciales.

Credenciales requeridas:

```env
# J&V Resguardo
TIPO_DOC=RUC
NUMERO_DOCUMENTO=
USUARIO_SEL=
CLAVE_SEL=

# Selva
SELVA_TIPO_DOC=RUC
SELVA_NUMERO_DOCUMENTO=
SELVA_USUARIO_SEL=
SELVA_CLAVE_SEL=
```

Configuracion operativa recomendada para pruebas visibles:

```env
RUN_MODE=manual
SCHEDULED_MULTIWORKER=0
SCHEDULED_WORKERS=1
CARNET_WORKER_MAX_ROWS=0
CARNET_HEADLESS=1
HOLD_BROWSER_OPEN=0
BROWSER_KEEP_VISIBLE=1
BROWSER_TILE_ENABLE=0
```

Variables SUCAMEC usadas por el flujo actual:

```env
SUCAMEC_LOGIN_CAPTCHA_RETRIES=3
SUCAMEC_CAPTCHA_SOLVE_TIMEOUT_MS=120000
SUCAMEC_FORCE_FIRST_CAPTCHA=
SUCAMEC_LOGIN_VALIDATION_TIMEOUT_MS=12000
SUCAMEC_LOG_MAX_RUNS=10
SUCAMEC_INPUT_EXCEL=
SUCAMEC_MAX_RECORDS=0
```

Variables Microsoft Graph para envio de correo:

```env
MS_GRAPH_MAIL_ENABLED=1
MS_GRAPH_MAIL_SUMMARY_ENABLED=1
MS_GRAPH_TENANT_ID=
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_SENDER=
MS_GRAPH_TO=
MS_GRAPH_CC=
MS_GRAPH_SUBJECT_PREFIX=BOT ARMAS-GADSO
```

Variables heredadas que tambien se respetan:

```env
CARNET_HEADLESS=1
HOLD_BROWSER_OPEN=0
CARNET_OCR_MAX_INTENTOS=6
CARNET_WORKER_MAX_ROWS=0
LOGIN_VALIDATION_TIMEOUT_MS=12000
LOG_DIR=logs
SCREENSHOT_DIR=screenshots
```

## Ejecucion

Forma recomendada en Windows:

```bat
run_agents_flow.bat
run_agents_flow.bat JV
run_agents_flow.bat SELVA
run_agents_flow.bat TODOS
```

Por defecto, `run_agents_flow.bat` usa `JV`.

Para probar solo login, sin navegar a `MIS VIGILANTES`:

```bat
run_agents_flow.bat JV --solo-login
```

Ejecucion directa por Python:

```powershell
python -m src.agents_flow.cli --grupo JV
python -m src.agents_flow.cli --grupo SELVA
python -m src.agents_flow.cli --grupo TODOS
python -m src.agents_flow.cli --grupo JV --solo-login
```

## Flujo Actual

El flujo implementado hace:

1. Abre Chromium con Playwright.
2. Ingresa al login de SUCAMEC.
3. Activa `Autenticacion Tradicional`.
4. Carga credenciales desde `.env`.
5. Resuelve captcha con OCR.
6. Si SUCAMEC responde `Error el captcha es incorrecto`, refresca captcha y reintenta.
7. Valida sesion autenticada.
8. Navega a `CONSULTAS > MIS VIGILANTES`.
9. Lee el Excel local desde `data/entrada_data`.
10. El orquestador central carga los registros una sola vez y aplica `SUCAMEC_MAX_RECORDS` si corresponde.
11. Si `SCHEDULED_MULTIWORKER=1`, divide los registros en lotes para workers; si no, ejecuta un solo worker.
12. Cada worker inicia una sola sesion, procesa su lote completo y evita recargar el Excel desde cero.
13. Cada worker navega a `MIS VIGILANTES` una vez por lote y luego procesa los registros de forma secuencial dentro de esa vista.
14. Extrae los datos base del vigilante desde la vista de detalle.
15. Extrae hasta 2 cursos validos de la tabla de cursos, filtrando solo filas con `Evaluacion = APROBADO` y respetando el orden visual actual de la tabla.
16. Extrae una sola licencia vigente de la tabla de licencias, aplicando prioridad de modalidad segun reglas de negocio.
17. Extrae los 2 primeros registros reales de la tabla de historial.
18. Consolida toda la informacion en un unico registro por DNI, preservando el orden original de entrada.
19. Guarda el Excel principal y el Excel complementario de validacion en la raiz del proyecto, dentro de `lotes/<aaaammdd_hhmmss>/`.
20. Si Microsoft Graph esta habilitado, envia ambos Excel por correo con un resumen operativo consolidado de la corrida.
21. Si el navegador corre en modo oculto (`headless`), la retencion visual se desactiva automaticamente sin afectar login, navegacion ni scraping.

## Entrada Excel

La entrada local se coloca en:

```text
data/
  entrada_data/
    archivo_entrada.xlsx
```

Formato obligatorio del Excel:

```text
DNI | APELLIDOS Y NOMBRES
```

Restricciones de lectura:

- El encabezado debe llamarse exactamente `DNI` y `APELLIDOS Y NOMBRES`.
- Los DNIs se tratan como texto, no como numeros.
- No se convierten a `int`.
- No se eliminan ceros al inicio ni al final.
- Si Excel guardo el DNI como numero con formato de celda tipo `00000000`, se recupera el relleno de ceros.
- Si Excel ya perdio los ceros por estar guardado como numero sin formato, el bot no puede reconstruirlos con certeza.
- Recomendacion: en Excel, formatear la columna `DNI` como `Texto` antes de pegar datos.

Si `SUCAMEC_INPUT_EXCEL=` esta vacio, el flujo toma el `.xlsx` mas reciente dentro de `data/entrada_data`.

Para probar un numero limitado de filas:

```env
SUCAMEC_MAX_RECORDS=5
```

Con `SUCAMEC_MAX_RECORDS=0` procesa todas las filas.

Configuracion de workers:

- `SCHEDULED_MULTIWORKER=0` ejecuta un solo navegador y un solo lote.
- `SCHEDULED_MULTIWORKER=1` activa procesamiento paralelo por workers.
- `SCHEDULED_WORKERS` define el numero base de workers concurrentes.
- `CARNET_WORKER_MAX_ROWS`, cuando es mayor que `0`, incrementa el numero efectivo de workers si hace falta para no exceder ese tamano aproximado por lote.
- El Excel de entrada se carga una sola vez en el proceso orquestador; los workers reciben solo sus segmentos ya particionados.
- `SUCAMEC_CAPTCHA_SOLVE_TIMEOUT_MS` define el timeout total para resolver captcha por OCR dentro de un intento de login.
- `CARNET_HEADLESS=1` ejecuta los navegadores ocultos.
- Si `CARNET_HEADLESS=1`, el flujo desactiva internamente `HOLD_BROWSER_OPEN` para evitar retenciones incompatibles con ejecucion sin UI.

## Estructura Modular

```text
src/agents_flow/
  cli.py
  orchestration_flow/
    runner.py     # Orquestador: carga Excel, particiona lotes y consolida resultados
    __init__.py
  login_flow/
    auth.py       # Login, captcha, reintentos y validacion de sesion
    browser.py    # Apertura/cierre de Chromium y reglas de ejecucion headless/visible
    config.py     # Carga .env y settings
    logging.py    # Logs por corrida, scope y fase
    selectors.py  # Selectores del login
    cli.py        # Orquestacion actual
  mis_vigilantes_flow/
    navigation.py # CONSULTAS > MIS VIGILANTES
    search.py     # Busqueda por DNI y click en Ver
    selectors.py  # Selectores del menu/vista
  notifications/
    graph_client.py    # OAuth client credentials y envio de correo por Microsoft Graph
    mail_config.py     # Carga/validacion de variables de correo
    builders/
      run_summary.py   # Construccion de asunto y cuerpo HTML del resumen final
    services/
      run_summary_service.py # Envio final de ambos Excel al cierre de la corrida
  extraction_flow/
    detail.py     # Extraccion de datos base del vigilante
    courses.py    # Extraccion de cursos con filtro por Evaluacion = APROBADO
    license.py    # Extraccion de licencia con prioridad por modalidad
    history.py    # Extraccion de historial (2 primeros registros reales)
    __init__.py   # Agregacion de campos de salida e interfaz publica
  excel_flow/
    records.py    # Lectura entrada y escritura resumen
```

`example/carnet_emision.py` queda como referencia historica, no como punto principal de ejecucion.

## Logs Y Lotes

Los logs se crean por ejecucion y se agrupan por scope operativo:

```text
logs/
  20260422_113000/
    coordinador/
      orchestration_flow.log
      excel_flow.log
    worker_01/
      login_flow.log
      mis_vigilantes_flow.log
    worker_02/
      login_flow.log
      mis_vigilantes_flow.log
```

La salida de lotes se guarda aparte, en la raiz del proyecto:

```text
lotes/
  20260422_113000/
    RB_GADSOCarnetSUCAMEC_22.04.26_12.30.10.xlsx
```

Buenas practicas aplicadas:

- La consola muestra todos los subflujos unificados.
- Los logs del proceso padre quedan en `coordinador/`.
- Cada worker escribe sus fases en su propia carpeta comun `worker_##`.
- La carpeta `lotes/<timestamp>/` contiene solo el archivo Excel final de la corrida.
- `SUCAMEC_LOG_MAX_RUNS=10` conserva maximo 10 corridas.
- Al crear la corrida 11, se elimina la carpeta de corrida mas antigua.
- La carpeta `lotes/` tambien conserva un maximo de 10 corridas; al crear la corrida 11, se elimina la carpeta mas antigua.
- Los handlers de archivo se cierran al finalizar para evitar bloqueos en Windows.

## Validaciones Aplicadas

Login:

- Valida que existan `numero_documento`, `usuario` y `contrasena`.
- Espera visibilidad de campos antes de escribir.
- Dispara eventos `input` y `change` despues de escribir valores.
- Si PrimeFaces limpia la contrasena al refrescar captcha, el flujo vuelve a escribir todas las credenciales antes de cada intento.
- Valida sesion por URL `/faces/aplicacion/inicio.xhtml` o selectores de menu autenticado.
- Captura mensajes de error visibles, incluyendo growls de PrimeFaces.

Captcha:

- OCR con `easyocr`, `Pillow` y `numpy`.
- Preprocesamiento de imagen en variantes.
- Reintentos internos de OCR por imagen.
- Timeout total configurable por intento de resolucion mediante `SUCAMEC_CAPTCHA_SOLVE_TIMEOUT_MS`.
- Reintentos de login si SUCAMEC rechaza el captcha.
- `SUCAMEC_FORCE_FIRST_CAPTCHA=ABCDE` puede usarse para probar el camino de recuperacion; debe dejarse vacio en uso normal.

Navegador:

- Cierre tolerante: si el usuario cierra la ventana, el flujo termina sin exigir `Ctrl+C`.
- Registra `Navegador cerrado`.
- Ejecuta oculto con `CARNET_HEADLESS=1` o visible con `CARNET_HEADLESS=0`.
- La decision visual queda encapsulada en `login_flow/browser.py`, separada de login y orquestacion.
- Si `headless` esta activo, el flujo desactiva automaticamente `hold_browser_open` en runtime.

Navegacion a Mis Vigilantes:

- Usa fast-path por anchor JSF `MIS VIGILANTES` cuando esta disponible.
- Fallback jerarquico: expande `CONSULTAS` y hace click en `MIS VIGILANTES`.
- Espera cola AJAX de PrimeFaces.
- Valida la vista por presencia de `DNI` y `Buscar`.

Busqueda por DNI:

- Escribe el DNI en `buscarForm:j_idt32`.
- Acciona `buscarForm:botonBuscar`.
- Espera la tabla `table[role='grid']`.
- La navegacion a `MIS VIGILANTES` se realiza una sola vez por lote, no antes de cada registro.
- Si la tabla devuelve la fila PrimeFaces `tr.ui-datatable-empty-message` con el texto `No se encontraron resultados.`, marca el registro como `NO_ENCONTRADO` de forma temprana.
- Si existe enlace `Ver`, hace click sobre el primer resultado.
- Si no existe enlace `Ver` y tampoco se pudo confirmar el empty-state de la tabla, usa una validacion de respaldo sobre el texto visible de la pagina.
- Si ninguna validacion confirma resultado ni empty-state, marca `SIN_VER` para diferenciar un caso ambiguo de un `NO_ENCONTRADO` confirmado.
- Antes de cada registro vuelve a asegurar la vista `MIS VIGILANTES`.

Orquestacion y workers:

- La carga del Excel se realiza una sola vez al inicio de la corrida.
- El orquestador calcula el numero efectivo de workers a partir de `SCHEDULED_MULTIWORKER`, `SCHEDULED_WORKERS` y `CARNET_WORKER_MAX_ROWS`.
- Los registros se reparten en lotes contiguos para preservar el orden del archivo de entrada.
- Cada worker abre su propio navegador, realiza login una sola vez y procesa su lote completo.
- Los resultados parciales se consolidan al final en el proceso padre antes de escribir el Excel.
- En multiworker no se deja el navegador abierto al finalizar.
- El coordinador centraliza la escritura del Excel final en `lotes/<timestamp>/`.
- La segmentacion de logs se hace por scope: `coordinador/` y `worker_##/`.
- El correo de salida se dispara una sola vez al final de la corrida, desde el coordinador, para evitar duplicados por worker.
- La segunda etapa DSSP reutiliza la logica base de login y, si un worker falla por sesion o captcha, reintenta el worker completo antes de dar el caso por no validado.

Notificaciones por correo:

- El envio de correo usa Microsoft Graph con flujo OAuth `client_credentials`.
- La autenticacion se realiza con `tenant_id`, `client_id` y `client_secret` cargados desde `.env`.
- El endpoint de envio usa la cuenta configurada en `MS_GRAPH_SENDER`.
- Los destinatarios principales se leen desde `MS_GRAPH_TO`.
- Los destinatarios en copia se leen desde `MS_GRAPH_CC`.
- El asunto usa el prefijo definido en `MS_GRAPH_SUBJECT_PREFIX`.
- El correo se construye al final de la corrida, cuando ya existen los Excel definitivos.
- Se adjuntan siempre 2 archivos:
- `RB_GADSOCarnetSUCAMEC_*.xlsx`
- `RB_GADSOValidacionNoEncontradosSUCAMEC_*.xlsx`
- Si la segunda etapa DSSP no genera cambios, el Excel complementario igual se emite con la consolidacion disponible para mantener consistencia operativa del envio.
- El cuerpo del correo incluye identificacion de corrida, fecha/hora de generacion resaltadas y una tabla ejecutiva de resumen operativo.
- El saludo del correo es `Saludos` con icono de robot.
- El bloque `Generado` resalta fecha y hora en amarillo y muestra la hora con sufijo `hras`.
- `Resumen operativo` se presenta en columnas: `Total procesados`, `No encontrado`, `Sin Ver`, `Worker error`, `Validados por DSSP`.
- El bloque `Archivos adjuntos` se muestra como lista simple de los Excel emitidos.
- El correo no incluye una seccion narrativa de sintesis del flujo.
- Si el envio falla, la corrida no se invalida; el error se registra en logs y los Excel permanecen en `lotes/`.

Extraccion estructurada:

- La extraccion de la vista `Ver` esta segmentada por responsabilidad para mantener alta cohesion.
- `detail.py` extrae solo los campos base del vigilante.
- `courses.py` extrae un maximo de 2 cursos con `Evaluacion = APROBADO` y genera columnas con sufijos `_1` y `_2`.
- `license.py` selecciona una sola licencia segun prioridad de modalidad: `L4` sobre `L1`, `L1` sobre `L2`, y `L3` solo cuando no existe otra modalidad candidata; luego genera un unico bloque de columnas `licencia_*`.
- `history.py` extrae un maximo de 2 registros de historial y genera columnas con sufijos `_1` y `_2`.
- Los extractores de tablas ignoran filas vacias del `tbody`, por lo que toman los primeros registros reales y no los primeros `tr` vacios.
- La combinacion final del resultado se realiza en `mis_vigilantes_flow/search.py`, no dentro de los extractores, para mantener separadas la navegacion y la logica de parsing.
- El esquema consolidado de salida ya esta implementado en `extraction_flow/__init__.py` mediante `OUTPUT_FIELDS` y en `excel_flow/records.py` mediante el dataclass `SearchResult`.

## Logica De Cursos Y Licencias

Arquitectura aplicada:

- La navegacion y el click en `Ver` viven en `mis_vigilantes_flow/search.py`.
- La extraccion de cursos vive de forma aislada en `src/agents_flow/extraction_flow/courses.py`.
- La extraccion de licencias vive de forma aislada en `src/agents_flow/extraction_flow/license.py`.
- La consolidacion final de ambos bloques se hace al construir `SearchResult`, sin mezclar reglas de negocio con el flujo de navegacion.
- Esta separacion permite cambiar criterios de seleccion de cursos o licencias sin tocar login, menu, busqueda ni escritura de Excel.

Logica de cursos:

- Fuente: tabla `#verForm:buscarCurDatatable_data`.
- El extractor lee todas las filas reales del `tbody` y elimina filas vacias.
- No se toma automaticamente la primera fila visible.
- Solo se consideran candidatas las filas cuya columna `Evaluacion` sea exactamente `APROBADO`.
- El orden de prioridad no se recalcula por fecha dentro del codigo; se respeta el orden visual que ya devuelve SUCAMEC en la tabla.
- `curso_*_1` toma la primera fila aprobada encontrada.
- `curso_*_2` toma la segunda fila aprobada encontrada.
- Si solo existe una fila aprobada, solo se llena el bloque `_1` y el bloque `_2` queda vacio.
- Si no existe ninguna fila aprobada, todas las columnas `curso_*_1` y `curso_*_2` quedan vacias.
- Los campos exportados por cada curso son: `ruc`, `razon_social`, `evaluacion`, `tipo`, `fecha_inicio`, `fecha_venc`, `estado`.

Casos de negocio cubiertos en cursos:

- Si la primera fila visible no esta aprobada, se omite y se busca la siguiente aprobada.
- Si la tabla tiene filas aprobadas y no aprobadas mezcladas, solo se exportan las aprobadas.
- Si la tabla ya viene ordenada por fecha, el sistema conserva ese orden y por eso el primer aprobado corresponde al aprobado mas relevante segun la vista actual.

Logica de licencias:

- Fuente: tabla `#verForm:licDatatable_data`.
- El extractor lee todas las filas reales del `tbody` y elimina filas vacias.
- No se toma automaticamente la primera fila visible.
- La modalidad se interpreta desde el texto de la columna `Modalidad`, detectando el codigo entre parentesis, por ejemplo `SEGURIDAD PRIVADA (L4)`.
- Se reconocen los tipos `L1`, `L2`, `L3` y `L4`.
- La seleccion responde a prioridad de negocio, no al orden visual de la tabla.

Prioridad de seleccion de licencias:

- Si existe al menos una licencia `L4`, se selecciona una `L4`.
- Si no existe `L4` pero existe `L1`, se selecciona una `L1`.
- Si no existe `L4` ni `L1` pero existe `L2`, se selecciona una `L2`.
- `L3` solo se selecciona cuando esta sola o, equivalentemente, cuando no existe ninguna `L4`, `L1` ni `L2` candidata.
- Si existen varias filas del mismo tipo priorizado, se conserva la primera que aparece en la tabla.

Casos de negocio cubiertos en licencias:

- `L1 + L2 + L4` -> se exporta `L4`.
- `L1 + L4` -> se exporta `L4`.
- `L2 + L4` -> se exporta `L4`.
- `L1 + L2` -> se exporta `L1`.
- `L3` sola -> se exporta `L3`.
- `L3 + L1` -> se exporta `L1`.
- `L3 + L2` -> se exporta `L2`.
- `L3 + L4` -> se exporta `L4`.

Columnas afectadas en la salida:

- Cursos: `curso_ruc_1`, `curso_razon_social_1`, `curso_evaluacion_1`, `curso_tipo_1`, `curso_fecha_inicio_1`, `curso_fecha_venc_1`, `curso_estado_1`, `curso_ruc_2`, `curso_razon_social_2`, `curso_evaluacion_2`, `curso_tipo_2`, `curso_fecha_inicio_2`, `curso_fecha_venc_2`, `curso_estado_2`.
- Licencia: `licencia_numero`, `licencia_fecha_emision`, `licencia_fecha_venc`, `licencia_modalidad`, `licencia_restricciones`.

Impacto funcional:

- El flujo gana consistencia frente a tablas donde el primer registro visible no es el correcto para negocio.
- La logica de seleccion queda centralizada y auditable dentro de cada extractor.
- El Excel final representa la prioridad operativa real solicitada por negocio y no solo el primer registro que SUCAMEC muestra en pantalla.

Excel local:

- Crea `data/entrada_data` si no existe.
- Lee solo archivos `.xlsx` y omite temporales `~$`.
- Toma el archivo mas reciente si no se configura ruta explicita.
- Cierra explicitamente los workbooks al terminar lectura y escritura para reducir riesgo de bloqueos de archivo.
- Escribe el resultado final en `lotes/<aaaammdd_hhmmss>/RB_GADSOCarnetSUCAMEC_dd.mm.aa_hh.mm.ss.xlsx`.
- El Excel final ya incluye todas las columnas implementadas hasta la fecha y esta ordenado por bloques funcionales:
- Por corrida ahora se generan dos archivos de salida para facilitar control operativo y envio por correo:
- Excel principal: `RB_GADSOCarnetSUCAMEC_dd.mm.aa_hh.mm.ss.xlsx`.
- Excel complementario: `RB_GADSOValidacionNoEncontradosSUCAMEC_dd.mm.aa_hh.mm.ss.xlsx`.
- Datos base: `documento`, `tipo_documento`, `nombre`, `estado`, `nro_carne`, `modalidad`, `ruc`, `expediente`, `nro_expediente`, `anho_expediente`, `fecha_emision`, `fecha_vencimiento`, `empresa`.
- Cursos: `curso_ruc_1`, `curso_razon_social_1`, `curso_evaluacion_1`, `curso_tipo_1`, `curso_fecha_inicio_1`, `curso_fecha_venc_1`, `curso_estado_1`, `curso_ruc_2`, `curso_razon_social_2`, `curso_evaluacion_2`, `curso_tipo_2`, `curso_fecha_inicio_2`, `curso_fecha_venc_2`, `curso_estado_2`.
- Licencia: `licencia_numero`, `licencia_fecha_emision`, `licencia_fecha_venc`, `licencia_modalidad`, `licencia_restricciones`.
- Historial: `historial_ruc_1`, `historial_razon_social_1`, `historial_modalidad_1`, `historial_procedimiento_1`, `historial_fecha_emision_1`, `historial_fecha_venc_1`, `historial_fecha_baja_1`, `historial_ruc_2`, `historial_razon_social_2`, `historial_modalidad_2`, `historial_procedimiento_2`, `historial_fecha_emision_2`, `historial_fecha_venc_2`, `historial_fecha_baja_2`.
- El orden de columnas actual es: detalle base -> cursos -> licencia -> historial.

## Buenas Practicas Del Proyecto

- Mantener cada etapa en su carpeta de subflujo.
- No mezclar login, navegacion, extraccion y Excel en un archivo monolitico.
- Centralizar selectores por subflujo.
- Mantener la extraccion segmentada por tabla o bloque funcional cuando la vista `Ver` crezca.
- Agregar nuevos campos al Excel mediante `OUTPUT_FIELDS` y el dataclass `SearchResult` para conservar consistencia entre scraping y salida.
- No imprimir credenciales ni valores sensibles en logs.
- No versionar `.env`, logs, outputs ni caches.
- Usar `.bat` para ejecucion operativa en Windows.
- Usar `--solo-login` para aislar errores de autenticacion.
- Mantener `SUCAMEC_FORCE_FIRST_CAPTCHA=` vacio salvo pruebas controladas.
- Mantener los DNIs como texto en Excel.
- No abrir ni editar el archivo de entrada mientras el bot lo procesa.
- Revisar logs por scope y fase antes de modificar selectores.
- Para nuevas etapas, crear modulo dedicado antes de tocar el orquestador.
- Mantener la lectura del Excel y el particionado de lotes en el orquestador, no dentro de los workers.
- Cada worker debe procesar un lote completo para evitar re-logins por registro.

## Siguientes Etapas

Pendiente por implementar:

1. Ejecutar validaciones end-to-end con multiples DNIs reales para confirmar el orden visual de cursos, licencia e historial en produccion.
2. Medir la mejora de tiempo obtenida por la deteccion temprana de `NO_ENCONTRADO` via `ui-datatable-empty-message` y ajustar timeouts si aplica.
3. Medir rendimiento real del modo multiworker y ajustar cantidad de workers segun CPU, red y estabilidad de SUCAMEC.
4. Actualizar la exportacion remota si el destino final migra de Excel local a Google Sheets por lotes.
5. Clasificar formalmente vigencia/en tramite por empresa.
6. Definir si la fuente definitiva de entrada sera local, Google Drive u otra herramienta.
