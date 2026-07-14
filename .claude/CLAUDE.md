# ESTADOS-GADSO — Contexto para Claude

Automatización de navegador (Playwright + Chromium) que consulta el portal
**SUCAMEC** por lotes de documentos (DNI / Carné de Extranjería), extrae el estado
de cada vigilante y genera reportes en Excel, con envío de resumen por correo
(Microsoft Graph). Soporta dos empresas: **J&V Resguardo (JV)** y **SELVA**.

> Documentación funcional completa y exhaustiva: [PROYECTO.md](../PROYECTO.md).
> Este archivo es el resumen operativo para trabajar el código.

## Cómo ejecutar

```powershell
# Activar entorno e instalar (una sola vez)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

# Ejecutar el flujo (JV por defecto; SELVA o TODOS también válidos)
.\run_agents_flow.bat JV
.\run_agents_flow.bat JV --solo-login   # solo prueba de login
```

El intérprete del proyecto es `.\.venv\Scripts\python.exe`. La configuración vive en
`.env` (credenciales, modo, OCR, correo). No se versiona.

## Mapa del código (`src/agents_flow/`)

| Módulo | Responsabilidad |
|---|---|
| `login_flow/cli.py` | Entry point real: parsea `--grupo`, despacha. |
| `login_flow/auth.py` | Login + resolución de CAPTCHA por OCR (easyocr). |
| `login_flow/config.py` | `Settings` y `Credentials` desde `.env`. |
| `login_flow/browser.py` | Ciclo de vida Playwright, tiling de ventanas. |
| `orchestration_flow/runner.py` | Núcleo: carga Excel, reparte lotes, multiworker (`ProcessPoolExecutor`), consolida, DSSP, correo. |
| `consultas_common.py` | Utilidades compartidas (espera AJAX PrimeFaces, clic "Ver"). |
| `recovery.py` | **Recuperación de sesión ante el "Error del servidor" de SUCAMEC** (ver abajo). |
| `mis_vigilantes_flow/` | Módulo CONSULTAS > MIS VIGILANTES (búsqueda simple). |
| `busqueda_vigilantes_flow/` | Módulo CONSULTAS > BÚSQUEDA DE VIGILANTES (con tipo de doc). |
| `dssp_emision_flow/` | Segundo pase: valida `NO_ENCONTRADO` en DSSP > Bandeja de Emisión. |
| `extraction_flow/` | Extractores: `detail`, `courses`, `license`, `history` (46 campos). |
| `excel_flow/records.py` | `InputRecord`, `SearchResult`, lectura/escritura de Excel. |
| `notifications/` | Envío de resumen vía Microsoft Graph. |

Cada `_flow` aísla sus selectores en `selectors.py`; la lógica está separada de los
selectores para soportar cambios frecuentes en la UI de SUCAMEC.

## Resiliencia ante "Error del servidor" (recovery.py)

SUCAMEC devuelve de forma intermitente la pantalla *"Error del servidor — Ha
ocurrido un error interno en el sistema. Por favor vuelva a ingresar al sistema"*,
cuyo enlace rebota al login. Además, bajo carga, el navegador Chromium llega a
**morir** (`TargetClosedError`). La recuperación es de **dos niveles**, modelando a
un operador que reanuda su cola desde el registro pendiente hasta terminarla:

**Nivel 1 — sesión (misma página), en `recovery.py`:**
- `page_shows_server_error(page)` detecta la pantalla (texto del panel o rebote a
  `login.xhtml` a mitad del flujo).
- `SessionRecovery.restore_session()` re-loguea y re-navega sobre la **misma página**.
- `run_record_with_recovery(...)` reintenta el **mismo registro** re-logueando en la
  página (hasta `SUCAMEC_SERVER_ERROR_RETRIES` veces). Si la página/navegador murió
  o se agotan los reintentos, **propaga** la excepción al nivel 2.

**Nivel 2 — navegador (reabrir + reanudar), en `runner.py::_run_single_browser_batch`:**
- Bucle `while remaining:` que **reabre el navegador completo** y **reanuda desde el
  registro pendiente**, preservando lo ya hecho vía el parámetro `sink` (lista de
  resultados acumulados). Nunca reprocesa lo completado ni descarta lo pendiente.
- `login()` también tolera la pantalla de error al inicio (`wait_until_login_form_ready`
  re-ingresa al `href` del login si SUCAMEC sirve el panel de error).
- Por defecto reintenta **indefinidamente hasta agotar la cola**. Válvula de
  seguridad: `SUCAMEC_SERVER_ERROR_MAX_FAILED_SESSIONS` aborta si hay N sesiones
  consecutivas **sin avanzar ni un registro** (auth rota, no SUCAMEC caído).

Ambos flujos (`mis_vigilantes_flow`, `busqueda_vigilantes_flow`) aceptan `recovery` y
`sink`.

Variables de entorno (`.env`):

| Variable | Default | Descripción |
|---|---|---|
| `SUCAMEC_SERVER_ERROR_RETRIES` | `3` | Re-logins en la misma página antes de reabrir el navegador. |
| `SUCAMEC_SERVER_ERROR_WAIT_MS` | `4000` | Espera antes de re-login y antes de reabrir navegador. |
| `SUCAMEC_SERVER_ERROR_MAX_FAILED_SESSIONS` | `0` | Sesiones consecutivas sin avanzar antes de abortar. **0 = ilimitado**. |

> ⚠️ **Workers vs. estabilidad:** con SUCAMEC inestable, muchos workers paralelos
> (`SCHEDULED_WORKERS`) lo saturan y disparan las caídas/`TargetClosedError`. Para
> máxima fiabilidad usar **1–2 workers** (un operador, una cola).

## Convenciones

- Comentarios y logs en español, sin tildes en strings críticos para matching.
- Selectores PrimeFaces/JSF con escapes (`buscarForm\\:...`).
- Tras cada interacción con la UI, esperar `wait_primefaces_ajax`.
- Salidas en `lotes/YYYYMMDD_HHMMSS/`; logs en `logs/YYYYMMDD_HHMMSS/`.
