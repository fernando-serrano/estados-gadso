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
CARNET_HEADLESS=0
HOLD_BROWSER_OPEN=1
BROWSER_KEEP_VISIBLE=1
BROWSER_TILE_ENABLE=0
```

Variables SUCAMEC usadas por el flujo actual:

```env
SUCAMEC_LOGIN_CAPTCHA_RETRIES=3
SUCAMEC_FORCE_FIRST_CAPTCHA=
SUCAMEC_LOGIN_VALIDATION_TIMEOUT_MS=12000
SUCAMEC_LOG_MAX_RUNS=10
SUCAMEC_INPUT_EXCEL=
SUCAMEC_MAX_RECORDS=0
```

Variables heredadas que tambien se respetan:

```env
CARNET_HEADLESS=0
HOLD_BROWSER_OPEN=1
CARNET_OCR_MAX_INTENTOS=6
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
10. Itera los registros y busca cada DNI.
11. Si encuentra resultado, abre el enlace `Ver`.
12. Extrae los datos base del vigilante desde la vista de detalle.
13. Extrae los 2 primeros registros reales de la tabla de cursos.
14. Extrae el primer registro real de la tabla de licencia.
15. Extrae los 2 primeros registros reales de la tabla de historial.
16. Consolida toda la informacion en un unico registro por DNI.
17. Guarda el Excel final dentro de la carpeta de la corrida en `logs/<fecha_hora>/excel_flow`.
18. Deja el navegador visible si `HOLD_BROWSER_OPEN=1`.

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

## Estructura Modular

```text
src/agents_flow/
  cli.py
  login_flow/
    auth.py       # Login, captcha, reintentos y validacion de sesion
    browser.py    # Apertura/cierre de Chromium
    config.py     # Carga .env y settings
    logging.py    # Logs por corrida y subflujo
    selectors.py  # Selectores del login
    cli.py        # Orquestacion actual
  mis_vigilantes_flow/
    navigation.py # CONSULTAS > MIS VIGILANTES
    search.py     # Busqueda por DNI y click en Ver
    selectors.py  # Selectores del menu/vista
  extraction_flow/
    detail.py     # Extraccion de datos base del vigilante
    courses.py    # Extraccion de cursos (2 primeros registros reales)
    license.py    # Extraccion de licencia (primer registro real)
    history.py    # Extraccion de historial (2 primeros registros reales)
    __init__.py   # Agregacion de campos de salida e interfaz publica
  excel_flow/
    records.py    # Lectura entrada y escritura resumen
```

`example/carnet_emision.py` queda como referencia historica, no como punto principal de ejecucion.

## Logs

Los logs se crean por ejecucion y por subflujo:

```text
logs/
  20260422_113000/
    login_flow/
      login_flow.log
    mis_vigilantes_flow/
      mis_vigilantes_flow.log
    excel_flow/
      excel_flow.log
      RB_GADSOCarnetSUCAMEC_22.04.26_12.30.10.xlsx
```

Buenas practicas aplicadas:

- La consola muestra todos los subflujos unificados.
- Cada subflujo escribe su propio archivo.
- `SUCAMEC_LOG_MAX_RUNS=10` conserva maximo 10 corridas.
- Al crear la corrida 11, se elimina la carpeta de corrida mas antigua.
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
- Reintentos de login si SUCAMEC rechaza el captcha.
- `SUCAMEC_FORCE_FIRST_CAPTCHA=ABCDE` puede usarse para probar el camino de recuperacion; debe dejarse vacio en uso normal.

Navegador:

- Cierre tolerante: si el usuario cierra la ventana, el flujo termina sin exigir `Ctrl+C`.
- Registra `Navegador cerrado`.
- Ejecuta visible con `CARNET_HEADLESS=0`.
- Mantiene ventana para inspeccion con `HOLD_BROWSER_OPEN=1`.

Navegacion a Mis Vigilantes:

- Usa fast-path por anchor JSF `MIS VIGILANTES` cuando esta disponible.
- Fallback jerarquico: expande `CONSULTAS` y hace click en `MIS VIGILANTES`.
- Espera cola AJAX de PrimeFaces.
- Valida la vista por presencia de `DNI` y `Buscar`.

Busqueda por DNI:

- Escribe el DNI en `buscarForm:j_idt32`.
- Acciona `buscarForm:botonBuscar`.
- Espera la tabla `table[role='grid']`.
- Si existe enlace `Ver`, hace click sobre el primer resultado.
- Si no existe resultado, marca `NO_ENCONTRADO` en el resumen.
- Antes de cada registro vuelve a asegurar la vista `MIS VIGILANTES`.

Extraccion estructurada:

- La extraccion de la vista `Ver` esta segmentada por responsabilidad para mantener alta cohesion.
- `detail.py` extrae solo los campos base del vigilante.
- `courses.py` extrae un maximo de 2 cursos y genera columnas con sufijos `_1` y `_2`.
- `license.py` extrae la licencia visible y genera un unico bloque de columnas `licencia_*`.
- `history.py` extrae un maximo de 2 registros de historial y genera columnas con sufijos `_1` y `_2`.
- Los extractores de tablas ignoran filas vacias del `tbody`, por lo que toman los primeros registros reales y no los primeros `tr` vacios.
- La combinacion final del resultado se realiza en `mis_vigilantes_flow/search.py`, no dentro de los extractores, para mantener separadas la navegacion y la logica de parsing.

Excel local:

- Crea `data/entrada_data` si no existe.
- Lee solo archivos `.xlsx` y omite temporales `~$`.
- Toma el archivo mas reciente si no se configura ruta explicita.
- Escribe el resultado dentro de la carpeta de corrida: `logs/<fecha_hora>/excel_flow/RB_GADSOCarnetSUCAMEC_dd.mm.aa_hh.mm.ss.xlsx`.
- El Excel final contiene un esquema consolidado y ordenado por bloques funcionales:
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
- Revisar logs por subflujo antes de modificar selectores.
- Para nuevas etapas, crear modulo dedicado antes de tocar el orquestador.

## Siguientes Etapas

Pendiente por implementar:

1. Ejecutar validaciones end-to-end con multiples DNIs reales para confirmar el orden visual de cursos, licencia e historial en produccion.
2. Clasificar formalmente vigencia/en tramite por empresa.
3. Definir si la fuente definitiva de entrada sera local, Google Drive u otra herramienta.
4. Definir paralelismo/workers para procesamiento masivo.
