# ESTADOS-GADSO — Documentación del Proyecto

## Índice

1. [Visión General](#1-visión-general)
2. [Arquitectura](#2-arquitectura)
3. [Estructura de Directorios](#3-estructura-de-directorios)
4. [Módulos y Lógica de Negocio](#4-módulos-y-lógica-de-negocio)
   - 4.1 [Entry Point & CLI](#41-entry-point--cli)
   - 4.2 [Flujo de Login y Autenticación](#42-flujo-de-login-y-autenticación)
   - 4.3 [Orquestación (Multiworker)](#43-orquestación-multiworker)
   - 4.4 [Consultas Common](#44-consultas-common)
   - 4.5 [Mis Vigilantes Flow](#45-mis-vigilantes-flow)
   - 4.6 [Búsqueda de Vigilantes Flow](#46-búsqueda-de-vigilantes-flow)
   - 4.7 [Extracción de Datos](#47-extracción-de-datos)
   - 4.8 [Excel Flow (Entrada / Salida)](#48-excel-flow-entrada--salida)
   - 4.9 [DSSP Validación Flow](#49-dssp-validación-flow)
   - 4.10 [Notificaciones (Microsoft Graph)](#410-notificaciones-microsoft-graph)
   - 4.11 [Logging](#411-logging)
5. [Modelos de Datos](#5-modelos-de-datos)
6. [Flujo de Ejecución End-to-End](#6-flujo-de-ejecución-end-to-end)
7. [Configuración (.env)](#7-configuración-env)
8. [Salidas del Sistema](#8-salidas-del-sistema)
9. [Herramientas y Librerías](#9-herramientas-y-librerías)
10. [Manejo de Errores y Resiliencia](#10-manejo-de-errores-y-resiliencia)
11. [Decisiones de Negocio Importantes](#11-decisiones-de-negocio-importantes)

---

## 1. Visión General

**ESTADOS-GADSO** es un sistema de automatización de navegador web para consultar la plataforma **SUCAMEC** (Superintendencia Nacional de Control de Servicios de Seguridad, Armas, Municiones y Explosivos de Uso Civil — Perú).

El sistema carga una lista de documentos (DNI o Carné de Extranjería) desde un archivo Excel, consulta el portal SUCAMEC por cada uno, extrae datos estructurados del vigilante (estado de carnet, cursos, licencias, historial laboral), y genera reportes consolidados en Excel. Soporta dos empresas cliente: **J&V Resguardo** y **SELVA**, cada una con sus propias credenciales SUCAMEC.

**Capacidades principales:**
- Autenticación automática con resolución de CAPTCHA vía OCR
- Procesamiento paralelo con múltiples instancias de navegador (multiworker)
- Dos módulos de consulta: *Mis Vigilantes* y *Búsqueda de Vigilantes*
- Validación secundaria de registros no encontrados vía DSSP > Bandeja de Emisión
- Exportación a Excel formateado con 46 columnas de datos
- Envío automático de resumen por correo electrónico vía Microsoft Graph API

---

## 2. Arquitectura

```
┌────────────────────────────────────────────────────────────────────┐
│                          CLI / Entry Point                         │
│              run_agents_flow.bat  →  src/agents_flow/cli.py        │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                  Orquestador  (orchestration_flow)                 │
│   Carga Excel → Distribuye lotes → ProcessPoolExecutor (workers)   │
└────┬──────────────────────┬──────────────────────────┬─────────────┘
     │ Worker 1             │ Worker 2 ... N           │ Coordinador
     ▼                      ▼                          │
┌──────────────┐     ┌──────────────┐                  │
│ login_flow   │     │ login_flow   │                  │
│ (auth +      │     │ (auth +      │                  │
│  CAPTCHA)    │     │  CAPTCHA)    │                  │
└──────┬───────┘     └──────┬───────┘                  │
       │                    │                          │
       ▼                    ▼                          │
┌──────────────────────────────────┐                  │
│     consultas_common             │                  │
│  (PrimeFaces AJAX wait, Ver)     │                  │
└──────┬───────────────────────────┘                  │
       │                                              │
  ┌────┴────┐                                         │
  │  Módulo │◄─── SUCAMEC_CONSULTAS_MODULE env var    │
  └────┬────┘                                         │
       │                                              │
  ┌────▼────────────────┐  ┌────────────────────────┐ │
  │  mis_vigilantes_flow│  │busqueda_vigilantes_flow│ │
  │  (simple búsqueda)  │  │(con tipo_doc selector) │ │
  └────────────────────┬┘  └┬───────────────────────┘ │
                       │    │                          │
                       ▼    ▼                          │
               ┌────────────────────┐                 │
               │   extraction_flow  │                 │
               │  detail / courses  │                 │
               │  license / history │                 │
               └────────┬───────────┘                 │
                        │ SearchResult[]               │
                        ▼                             │
               ┌────────────────────┐                 │
               │     excel_flow     │◄────────────────┘
               │  write_results()   │
               └────────┬───────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │     dssp_emision_flow         │
        │  (valida NO_ENCONTRADO)        │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │      notifications            │
        │  (Microsoft Graph / correo)   │
        └───────────────────────────────┘
```

**Patrón arquitectónico:** Pipeline de pasos especializados donde cada `_flow` es un módulo independiente con su propio `navigation.py`, `search.py`, `selectors.py`. Los selectores CSS/texto están aislados de la lógica para facilitar mantenimiento ante cambios en SUCAMEC.

---

## 3. Estructura de Directorios

```
ESTADOS-GADSO/
│
├── run_agents_flow.bat              # Punto de entrada Windows
├── .env                             # Variables de entorno (credenciales, config)
├── requirements.txt                 # Dependencias Python
├── PROYECTO.md                      # Este documento
│
├── src/
│   └── agents_flow/
│       ├── cli.py                   # Delegador al login_flow/cli.py
│       ├── consultas_common.py      # Utilidades compartidas (AJAX wait, clic Ver)
│       │
│       ├── login_flow/              # Autenticación y ciclo de vida del browser
│       │   ├── cli.py               # Parser de argumentos y despacho
│       │   ├── config.py            # Carga de .env, dataclasses Settings/Credentials
│       │   ├── auth.py              # Login, OCR CAPTCHA, validación de sesión
│       │   ├── browser.py           # Playwright lifecycle, window tiling
│       │   ├── selectors.py         # Selectores del formulario de login
│       │   └── logging.py           # RunLoggers: logs por scope y subflow
│       │
│       ├── orchestration_flow/      # Distribución de trabajo y consolidación
│       │   └── runner.py            # Orquestador principal, ProcessPoolExecutor
│       │
│       ├── extraction_flow/         # Extractores de datos del detalle
│       │   ├── __init__.py          # Agrega extractores y OUTPUT_FIELDS (46 cols)
│       │   ├── detail.py            # Campos base del vigilante (13 campos)
│       │   ├── courses.py           # Cursos de capacitación (hasta 2, solo APROBADO)
│       │   ├── license.py           # Licencia por prioridad L4>L1>L2>L3
│       │   └── history.py           # Historial laboral (hasta 2 registros)
│       │
│       ├── excel_flow/              # Lectura de Excel de entrada, escritura de salida
│       │   └── records.py           # InputRecord, SearchResult, load/write functions
│       │
│       ├── mis_vigilantes_flow/     # Módulo CONSULTAS > MIS VIGILANTES
│       │   ├── navigation.py        # Navegación al menú, validación de vista
│       │   ├── search.py            # Búsqueda y extracción por documento
│       │   └── selectors.py         # Selectores CSS/texto del módulo
│       │
│       ├── busqueda_vigilantes_flow/ # Módulo CONSULTAS > BUSQUEDA DE VIGILANTES
│       │   ├── navigation.py        # Navegación al menú, validación de vista
│       │   ├── search.py            # Búsqueda con selección de tipo doc
│       │   └── selectors.py         # Selectores + infer_document_type()
│       │
│       ├── dssp_emision_flow/       # DSSP > BANDEJA DE EMISION (validación secundaria)
│       │   ├── navigation.py        # Navegación al menú DSSP
│       │   ├── search.py            # Validación de registros NO_ENCONTRADO
│       │   └── selectors.py         # Selectores de la bandeja
│       │
│       └── notifications/           # Integración Microsoft Graph (correo)
│           ├── graph_client.py      # OAuth token + sendMail
│           ├── mail_config.py       # MailConfig dataclass, validación
│           ├── builders/
│           │   └── run_summary.py   # Asunto y cuerpo HTML del correo
│           └── services/
│               └── run_summary_service.py  # Orquestador del envío
│
├── data/
│   └── entrada_data/                # Excel de entrada (NRO DOCUMENTO)
│       └── plantilla_mis_vigilantes.xlsx
│
├── lotes/
│   └── YYYYMMDD_HHMMSS/             # Excel de salida por cada corrida
│       ├── RB_GADSOCarnetSUCAMEC_*.xlsx
│       └── RB_GADSOValidacionNoEncontradosSUCAMEC_*.xlsx
│
├── logs/
│   └── YYYYMMDD_HHMMSS/             # Logs de cada corrida
│       ├── coordinador/             # Logs del proceso principal
│       └── worker_##/               # Logs por worker paralelo
│
└── .venv/                           # Entorno virtual Python
```

---

## 4. Módulos y Lógica de Negocio

### 4.1 Entry Point & CLI

**Archivo:** [src/agents_flow/login_flow/cli.py](src/agents_flow/login_flow/cli.py)

Punto de entrada real del sistema. Recibe argumentos de línea de comandos y despacha la ejecución.

**Argumentos soportados:**
| Argumento | Valores | Descripción |
|---|---|---|
| `--grupo` | `JV`, `SELVA`, `TODOS` | Selecciona las credenciales a usar |
| `--solo-login` | flag | Solo prueba login, no navega ni extrae datos |

**Comportamiento con `TODOS`:** Ejecuta primero el grupo JV, luego SELVA secuencialmente. Cada grupo tiene su propio ciclo completo (carga Excel, procesamiento, escritura, email).

**Archivo batch:** `run_agents_flow.bat` activa el `.venv` y llama al módulo Python con los argumentos pasados.

---

### 4.2 Flujo de Login y Autenticación

**Archivos:** [src/agents_flow/login_flow/auth.py](src/agents_flow/login_flow/auth.py), [browser.py](src/agents_flow/login_flow/browser.py), [config.py](src/agents_flow/login_flow/config.py)

#### Ciclo de vida del browser

`open_browser()` retorna la tupla `(browser, context, page)` de Playwright con Chromium. Flags de lanzamiento configurados en `build_launch_args()`:
- Deshabilita infobars y ocultamiento por inactividad (`--disable-backgrounding-occluded-windows`)
- Soporte para modo tile 2×2 para multiworker (calcula posición X/Y por worker index)
- Modo headless o visible según `.env`

#### Proceso de login

```
navigate(login_url)
    → activate_traditional_tab()   # Clic en pestaña "Autenticación Tradicional"
    → fill_credentials()           # Selecciona tipo_doc, llena documento/usuario/clave
    → solve_captcha()              # Loop OCR hasta resolver o timeout
    → submit form
    → validate_login_result()      # Espera selectores de éxito o mensajes de error
```

#### Resolución de CAPTCHA (OCR)

El CAPTCHA de SUCAMEC es una imagen con texto alfanumérico. El sistema lo resuelve:

1. Toma screenshot del elemento `<img>` del CAPTCHA
2. Aplica 3 variantes de preprocesamiento con Pillow:
   - Contraste aumentado + escala de grises
   - Escala aumentada (interpolación LANCZOS)
   - Filtros combinados
3. EasyOCR con `allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"` y `detail=0`
4. Toma el resultado más largo entre las 3 variantes (heurística de confianza)
5. Si el resultado es inválido (vacío, muy corto), refresca el CAPTCHA y reintenta
6. Límite configurable: `CARNET_OCR_MAX_INTENTOS` intentos, `SUCAMEC_CAPTCHA_SOLVE_TIMEOUT_MS` timeout total

**Fallback de escritura de campos:** Si el campo se limpia solo (comportamiento PrimeFaces), usa `Control+A` + `Backspace` antes de tipear para garantizar que el valor quede escrito.

---

### 4.3 Orquestación (Multiworker)

**Archivo:** [src/agents_flow/orchestration_flow/runner.py](src/agents_flow/orchestration_flow/runner.py)

El orquestador es el núcleo del sistema. Gestiona todo el pipeline:

#### Carga y distribución

```python
records = load_input_records(excel_path)         # Lee Excel de entrada
n_workers = _resolve_worker_count(records)       # Calcula workers según config
batches = _split_records(records, n_workers)     # Divide registros en lotes contiguos
```

**Cálculo de workers** (`_resolve_worker_count`):
- Si `SCHEDULED_MULTIWORKER=0` → 1 worker (single)
- Si `CARNET_WORKER_MAX_ROWS > 0` → `ceil(total_records / max_rows)` workers (auto-scaling)
- Si no → usa `SCHEDULED_WORKERS` directamente
- Siempre capped al máximo configurado

#### Ejecución paralela

Con `ProcessPoolExecutor` de Python se spawnan N procesos independientes. Cada proceso:
1. Abre su propia instancia de Chromium
2. Hace login con las mismas credenciales
3. Navega al módulo de consultas
4. Procesa su lote de registros secuencialmente
5. Retorna `list[SearchResult]`

Los resultados se consolidan respetando el orden original del Excel de entrada.

#### Flujo single (1 worker)

Cuando hay un solo worker, el browser se mantiene abierto al final si `HOLD_BROWSER_OPEN=1` (útil para debug).

#### Post-procesamiento

Después de consolidar resultados:
1. Escribe Excel principal (`RB_GADSOCarnetSUCAMEC_*.xlsx`)
2. Ejecuta pase de validación DSSP para registros `NO_ENCONTRADO`
3. Escribe Excel de validación (`RB_GADSOValidacionNoEncontradosSUCAMEC_*.xlsx`)
4. Envía email de resumen vía Microsoft Graph

---

### 4.4 Consultas Common

**Archivo:** [src/agents_flow/consultas_common.py](src/agents_flow/consultas_common.py)

Funciones compartidas por `mis_vigilantes_flow` y `busqueda_vigilantes_flow`:

**`wait_primefaces_ajax(page, timeout_ms)`**
Espera a que la cola de AJAX de PrimeFaces esté vacía:
```javascript
// Evalúa en browser:
PrimeFaces.ajax.Queue.isEmpty()
// o si no existe: queue.requests.length === 0
```
Esencial después de cada interacción con la UI PrimeFaces del SUCAMEC.

**`click_ver_and_wait_detail(page, ver_locator)`**
Clic en el enlace "Ver" del resultado de búsqueda con 3 modos de fallback:
1. Click normal
2. Click con `force=True` (ignora visibility checks de Playwright)
3. Click vía JavaScript `element.click()`

Después del clic, espera la vista de detalle del vigilante.

---

### 4.5 Mis Vigilantes Flow

**Archivos:** [src/agents_flow/mis_vigilantes_flow/](src/agents_flow/mis_vigilantes_flow/)

Módulo para el menú **CONSULTAS > MIS VIGILANTES** de SUCAMEC. Es la ruta de búsqueda más simple: solo requiere escribir el número de documento y hacer clic en "Buscar".

#### Navegación

`navigate_to_mis_vigilantes(page)`:
- Intenta fast-path vía atributo `onclick` del anchor JSF (más rápido)
- Fallback: expande menú CONSULTAS → clic en enlace MIS VIGILANTES
- Valida que la vista de búsqueda sea visible (campo criterio_busqueda o botón "Buscar")

#### Búsqueda por registro

`search_record_and_open_detail(page, record)`:
1. Escribe `nro_documento` en campo `criterio_busqueda`
2. Clic en `boton_buscar`
3. Espera respuesta AJAX
4. Detecta fila vacía → retorna `SearchResult(estado="NO_ENCONTRADO")`
5. Detecta enlace "Ver" → hace clic y espera detalle
6. Llama a todos los extractores (`detail`, `courses`, `license`, `history`)
7. Clic en botón de retorno para resetear búsqueda
8. Retorna `SearchResult` consolidado

---

### 4.6 Búsqueda de Vigilantes Flow

**Archivos:** [src/agents_flow/busqueda_vigilantes_flow/](src/agents_flow/busqueda_vigilantes_flow/)

Módulo para el menú **CONSULTAS > BUSQUEDA DE VIGILANTES**. Agrega la capacidad de seleccionar el tipo de documento (DNI o C.E.) antes de buscar, lo que lo hace más preciso para documentos de extranjería.

#### Inferencia de tipo de documento

`infer_document_type(document_number)` en `selectors.py`:
- Si la parte numérica tiene exactamente **9 dígitos** → `"CE"` (Carné de Extranjería)
- En cualquier otro caso → `"DNI"`

#### Selección de tipo en UI

`_select_document_type(page, doc_type)`:
1. Abre el dropdown `tipo_documento_widget`
2. Hace clic en la opción correspondiente (`opcion_nro_dni` o `opcion_nro_ce`)
3. Espera que la etiqueta de confirmación se actualice

El resto del flujo de búsqueda es idéntico al de Mis Vigilantes.

#### Cuándo usar cada módulo

Controlado por variable de entorno `SUCAMEC_CONSULTAS_MODULE`:
- `mis_vigilantes` → módulo simple sin selección de tipo
- `busqueda_vigilantes` → módulo con selección de tipo (default en producción)

---

### 4.7 Extracción de Datos

**Archivos:** [src/agents_flow/extraction_flow/](src/agents_flow/extraction_flow/)

Todos los extractores operan sobre la vista de detalle del vigilante, leyendo el DOM vía JavaScript.

#### detail.py — Campos base (13 campos)

Lee el `panelGrid` de datos generales evaluando JS:
```javascript
// Obtiene pares label → valor del panel
document.querySelectorAll('.detalle-panel tr')
```
Normaliza labels con NFKD unicode (elimina tildes/acentos para matching robusto). Mapeo a campos:

| Campo SUCAMEC | Campo sistema |
|---|---|
| Documento | `documento` |
| Tipo Documento | `tipo_documento` |
| Nombre Completo | `nombre` |
| Estado | `estado` |
| Nro. Carné | `nro_carne` |
| Modalidad | `modalidad` |
| RUC Empresa | `ruc` |
| Expediente | `expediente` |
| Nro. Expediente | `nro_expediente` |
| Año Expediente | `anho_expediente` |
| Fecha Emisión | `fecha_emision` |
| Fecha Vencimiento | `fecha_vencimiento` |
| Empresa | `empresa` |

#### courses.py — Cursos de capacitación (hasta 14 campos)

Lee `tbody#verForm:buscarCurDatatable_data`. **Regla de negocio crítica:**
- Solo toma cursos con `Evaluacion = "APROBADO"`
- Ignora filas vacías
- Máximo 2 cursos (sufijos `_1`, `_2`)

Campos por curso: `ruc`, `razon_social`, `evaluacion`, `tipo`, `fecha_inicio`, `fecha_venc`, `estado`

#### license.py — Licencia de armas (5 campos)

Lee `tbody#verForm:licDatatable_data`. **Regla de negocio crítica — Prioridad:**

```
L4 > L1 > L2 > L3
```

Si el vigilante tiene múltiples licencias, se selecciona la de mayor prioridad (no la primera visible). El código de licencia se extrae con regex del patrón `"(Lx)"` en el campo modalidad.

Campos: `licencia_numero`, `licencia_fecha_emision`, `licencia_fecha_venc`, `licencia_modalidad`, `licencia_restricciones`

#### history.py — Historial laboral (hasta 14 campos)

Lee `tbody#verForm:buscarHistDatatable_data`.
- Filtra filas vacías y filas que contengan `"NO SE ENCONTR"`
- Máximo 2 registros (sufijos `_1`, `_2`)

Campos por registro: `ruc`, `razon_social`, `modalidad`, `procedimiento`, `fecha_emision`, `fecha_venc`, `fecha_baja`

---

### 4.8 Excel Flow (Entrada / Salida)

**Archivo:** [src/agents_flow/excel_flow/records.py](src/agents_flow/excel_flow/records.py)

#### Lectura de entrada

`load_input_records(path)`:
- Lee columna `NRO DOCUMENTO` (acepta `DNI` como alias legacy)
- Preserva ceros a la izquierda inspeccionando el `number_format` de la celda
- Valida que el campo no esté vacío
- Retorna `list[InputRecord]` con `row_number`, `nro_documento`, `apellidos_nombres`

`resolve_input_excel()` toma el `.xlsx` más reciente de `data/entrada_data/`, o el path explícito de `SUCAMEC_INPUT_EXCEL`.

#### Escritura de salida

`write_search_results(results, run_timestamp, output_dir)`:
- Crea workbook con openpyxl
- Fila de encabezado: `OUTPUT_FIELDS` (46 columnas)
- Por cada `SearchResult`: fila con `getattr(result, field)`
- Auto-sizing de columnas (min 12px, max 35px)
- Formato de celda: texto (`@`) para todos los valores
- Nombre de archivo: `RB_GADSO{tipo}_{DD.MM.YY}_{HH.MM.SS}.xlsx`
- Destino: `lotes/<YYYYMMDD_HHMMSS>/`

---

### 4.9 DSSP Validación Flow

**Archivos:** [src/agents_flow/dssp_emision_flow/](src/agents_flow/dssp_emision_flow/)

Flujo secundario que valida los registros marcados como `NO_ENCONTRADO` en el módulo de consultas. Navega a **DSSP > BANDEJA DE EMISION** para buscar si el registro existe en otra bandeja del sistema.

#### Proceso

1. Filtra `results` donde `estado == "NO_ENCONTRADO"`
2. Navega a DSSP > Bandeja de Emisión (con fast-path y fallbacks)
3. Para cada registro NO_ENCONTRADO:
   - Asegura que el modo de búsqueda sea `"DNI PROSPECTO / PERSONAL DE SEGURIDAD"`
   - Escribe el número de documento y busca
   - Si hay resultado: extrae `Estado registro` de la primera fila
   - Actualiza el `SearchResult` con estado enriquecido: `"NO_ENCONTRADO {estado_registro}"`
4. Merge de resultados: reemplaza los NO_ENCONTRADO originales con los validados

El pase DSSP corre **después** de que todos los workers han terminado, en el proceso coordinador, con un solo browser.

---

### 4.10 Notificaciones (Microsoft Graph)

**Archivos:** [src/agents_flow/notifications/](src/agents_flow/notifications/)

Integración con **Microsoft 365** para enviar correo de resumen al finalizar cada corrida.

#### Autenticación OAuth

`acquire_access_token()` en `graph_client.py`:
- Flow: `client_credentials` (app-only, sin usuario)
- Endpoint: `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
- Scope: `https://graph.microsoft.com/.default`
- Retorna Bearer token o string vacío si falla

#### Envío de correo

`send_mail()` construye el objeto `message` de la Graph API:
- Para: `MS_GRAPH_TO` (lista separada por `;` o `,`)
- CC: `MS_GRAPH_CC`
- Adjuntos: archivos Excel del lote, codificados en base64
- Guarda en elementos enviados (`saveToSentItems: true`)
- Endpoint: `POST /v1.0/users/{sender}/sendMail`

#### Contenido del correo

`build_html_body()` en `builders/run_summary.py` genera HTML con:
- Saludo con emoji de robot
- Tabla resumen con conteos:
  | Métrica | Descripción |
  |---|---|
  | Total procesados | Total de filas en el Excel de entrada |
  | No encontrado | Registros con estado `NO_ENCONTRADO` |
  | Sin Ver | Registros donde no se pudo abrir el detalle |
  | Worker error | Registros que fallaron por error de proceso |
  | Validados por DSSP | NO_ENCONTRADO confirmados/enriquecidos con DSSP |
- Lista de archivos adjuntos
- Pie de página indicando que es generado automáticamente

#### Clasificación de errores Graph

`classify_graph_failure()` mapea códigos HTTP y mensajes a etiquetas legibles:
- `AUTH_ERROR` (401), `SENDER_NOT_FOUND` (404), `RATE_LIMIT` (429), etc.

Un fallo de email **no cancela ni invalida** el resultado de la corrida.

---

### 4.11 Logging

**Archivo:** [src/agents_flow/login_flow/logging.py](src/agents_flow/login_flow/logging.py)

Sistema de logs con organización por scope y subflow.

#### Estructura de directorios de logs

```
logs/
└── YYYYMMDD_HHMMSS/          ← run_id (timestamp de inicio)
    ├── coordinador/
    │   ├── login_flow.log
    │   ├── orchestration_flow.log
    │   ├── excel_flow.log
    │   └── notifications.log
    └── worker_01/
        ├── login_flow.log
        ├── mis_vigilantes_flow.log
        └── extraction_flow.log
```

**`RunLoggers`** crea la estructura de directorios y retorna loggers por subflow. Cada scope (coordinador o worker_##) tiene su propio subdirectorio. Todos los loggers comparten un console handler adicional.

**Retención automática:** Si el número de directorios de corridas supera `SUCAMEC_LOG_MAX_RUNS`, se eliminan los más antiguos.

---

## 5. Modelos de Datos

### InputRecord

```python
@dataclass(frozen=True)
class InputRecord:
    row_number: int          # Fila en el Excel de entrada (para trazabilidad)
    nro_documento: str       # DNI o Carné de Extranjería
    apellidos_nombres: str   # Nombre del vigilante (si existe en el Excel)
```

### SearchResult

```python
@dataclass(frozen=True)
class SearchResult:
    # Identificación
    documento: str

    # Detalle base (extraction_flow/detail.py)
    tipo_documento: str
    nombre: str
    estado: str              # VIGENTE | VENCIDO | NO_ENCONTRADO | SIN_VER | WORKER_ERROR
    nro_carne: str
    modalidad: str
    ruc: str
    expediente: str
    nro_expediente: str
    anho_expediente: str
    fecha_emision: str
    fecha_vencimiento: str
    empresa: str

    # Cursos (extraction_flow/courses.py) — hasta 2, solo APROBADO
    curso_ruc_1: str;           curso_ruc_2: str
    curso_razon_social_1: str;  curso_razon_social_2: str
    curso_evaluacion_1: str;    curso_evaluacion_2: str
    curso_tipo_1: str;          curso_tipo_2: str
    curso_fecha_inicio_1: str;  curso_fecha_inicio_2: str
    curso_fecha_venc_1: str;    curso_fecha_venc_2: str
    curso_estado_1: str;        curso_estado_2: str

    # Licencia (extraction_flow/license.py) — prioridad L4>L1>L2>L3
    licencia_numero: str
    licencia_fecha_emision: str
    licencia_fecha_venc: str
    licencia_modalidad: str
    licencia_restricciones: str

    # Historial laboral (extraction_flow/history.py) — hasta 2 registros
    historial_ruc_1: str;           historial_ruc_2: str
    historial_razon_social_1: str;  historial_razon_social_2: str
    historial_modalidad_1: str;     historial_modalidad_2: str
    historial_procedimiento_1: str; historial_procedimiento_2: str
    historial_fecha_emision_1: str; historial_fecha_emision_2: str
    historial_fecha_venc_1: str;    historial_fecha_venc_2: str
    historial_fecha_baja_1: str;    historial_fecha_baja_2: str
```

**Total: 46 campos** (columnas en el Excel de salida)

### Credentials

```python
@dataclass(frozen=True)
class Credentials:
    tipo_documento_valor: str   # Valor del selector de tipo doc en SUCAMEC
    numero_documento: str       # Número de documento del operador
    usuario: str                # Usuario SUCAMEC
    contrasena: str             # Contraseña SUCAMEC
```

### Settings

```python
@dataclass(frozen=True)
class Settings:
    login_url: str
    consultas_module: str           # "mis_vigilantes" | "busqueda_vigilantes"
    headless: bool
    hold_browser_open: bool
    ocr_max_intentos: int
    captcha_solve_timeout_ms: int
    login_captcha_retries: int
    force_first_captcha: str        # Solo para testing
    login_validation_timeout_ms: int
    logs_dir: Path
    lots_dir: Path
    screenshots_dir: Path
    input_excel_path: str
    max_records: int                # 0 = todos
    scheduled_multiworker: bool
    scheduled_workers: int
    worker_max_rows: int            # 0 = sin auto-scaling
```

---

## 6. Flujo de Ejecución End-to-End

```
1. run_agents_flow.bat JV
       │
2. login_flow/cli.py → parse args → grupo="JV"
       │
3. orchestration_flow/runner.py: run_group_flow("JV")
       │
4. load_settings() → lee .env
       │
5. resolve_input_excel() → encuentra .xlsx más reciente en data/entrada_data/
       │
6. load_input_records(excel) → lista[InputRecord]
       │
7. _resolve_worker_count(records) → N workers
       │
8. _split_records(records, N) → N lotes contiguos
       │
9. ProcessPoolExecutor(max_workers=N):
       ├── Worker 1: open_browser → login → navigate → process_batch_1 → lista[SearchResult]
       ├── Worker 2: open_browser → login → navigate → process_batch_2 → lista[SearchResult]
       └── Worker N: open_browser → login → navigate → process_batch_N → lista[SearchResult]
       │
       Por cada registro en el batch:
       ├── (busqueda_vigilantes) _select_document_type()
       ├── write documento en campo de búsqueda
       ├── clic boton_buscar → wait AJAX
       ├── ¿fila vacía? → SearchResult(estado="NO_ENCONTRADO")
       ├── ¿sin enlace Ver? → SearchResult(estado="SIN_VER")
       └── clic Ver → wait detalle →
           ├── extract_detail_fields()
           ├── extract_course_fields()
           ├── extract_license_fields()
           ├── extract_history_fields()
           └── SearchResult(**merged_fields)
       │
10. Consolidar resultados en orden original
       │
11. write_search_results(results) → lotes/YYYYMMDD_HHMMSS/RB_GADSOCarnetSUCAMEC_*.xlsx
       │
12. Filtrar NO_ENCONTRADO → _run_dssp_validation_pass()
       ├── navigate_to_bandeja_emision()
       └── Por cada NO_ENCONTRADO:
           └── buscar en bandeja → enriquecer estado → SearchResult actualizado
       │
13. Merge resultados DSSP → write_search_results() → RB_GADSOValidacionNoEncontradosSUCAMEC_*.xlsx
       │
14. send_run_summary_mail()
       ├── acquire_access_token() → Bearer token
       ├── build_subject() + build_html_body()
       └── send_mail(token, subject, body, attachments=[ambos xlsx])
       │
15. Log cleanup: eliminar runs antiguas si count > SUCAMEC_LOG_MAX_RUNS
```

---

## 7. Configuración (.env)

### Credenciales

| Variable | Grupo | Descripción |
|---|---|---|
| `TIPO_DOC` | JV | Valor del selector tipo documento operador |
| `NUMERO_DOCUMENTO` | JV | Número de documento operador |
| `USUARIO_SEL` | JV | Usuario SUCAMEC J&V Resguardo |
| `CLAVE_SEL` | JV | Contraseña SUCAMEC J&V Resguardo |
| `SELVA_TIPO_DOC` | SELVA | Tipo documento operador SELVA |
| `SELVA_NUMERO_DOCUMENTO` | SELVA | Número documento operador SELVA |
| `SELVA_USUARIO_SEL` | SELVA | Usuario SUCAMEC SELVA |
| `SELVA_CLAVE_SEL` | SELVA | Contraseña SUCAMEC SELVA |

### Modo de ejecución

| Variable | Default | Descripción |
|---|---|---|
| `RUN_MODE` | `scheduled` | `scheduled` / `manual` / `test` |
| `SCHEDULED_MULTIWORKER` | `1` | `1` = procesar en paralelo |
| `SCHEDULED_WORKERS` | `5` | Número de workers paralelos |
| `CARNET_WORKER_SCAN_ROWS` | `200` | Filas aproximadas por worker |
| `CARNET_WORKER_MAX_ROWS` | `0` | Max filas por worker para auto-scaling (0 = desactivado) |
| `SUCAMEC_MAX_RECORDS` | `0` | Límite de registros (0 = todos) |
| `SUCAMEC_CONSULTAS_MODULE` | `busqueda_vigilantes` | Módulo a usar |
| `SUCAMEC_INPUT_EXCEL` | _(vacío)_ | Path explícito al Excel (vacío = auto) |

### Browser

| Variable | Default | Descripción |
|---|---|---|
| `CARNET_HEADLESS` | `1` | `1` = headless, `0` = visible |
| `HOLD_BROWSER_OPEN` | `0` | `1` = mantener ventana al terminar |
| `BROWSER_KEEP_VISIBLE` | `0` | `1` = evitar ocultamiento por inactividad |
| `BROWSER_TILE_ENABLE` | `0` | `1` = organizar ventanas en grilla 2×2 |
| `BROWSER_TILE_GAP` | `6` | Píxeles entre ventanas en modo tile |
| `BROWSER_TILE_TOP_OFFSET` | `0` | Offset vertical (para taskbar) |

### OCR / CAPTCHA

| Variable | Default | Descripción |
|---|---|---|
| `EASYOCR_LANGS` | `en` | Idioma del OCR |
| `EASYOCR_ALLOWLIST` | `A-Z0-9` | Caracteres válidos para reconocimiento |
| `EASYOCR_USE_GPU` | `0` | `1` = usar GPU (requiere CUDA) |
| `CARNET_OCR_MAX_INTENTOS` | `6` | Reintentos de OCR por CAPTCHA |
| `SUCAMEC_LOGIN_CAPTCHA_RETRIES` | `3` | Reintentos de login completo |
| `SUCAMEC_CAPTCHA_SOLVE_TIMEOUT_MS` | `120000` | Timeout total OCR (ms) |
| `SUCAMEC_LOGIN_VALIDATION_TIMEOUT_MS` | `12000` | Timeout validación post-login (ms) |

### Microsoft Graph (Email)

| Variable | Descripción |
|---|---|
| `MS_GRAPH_MAIL_ENABLED` | `1` = habilitar email |
| `MS_GRAPH_MAIL_SUMMARY_ENABLED` | `1` = enviar resumen al finalizar |
| `MS_GRAPH_TENANT_ID` | GUID del tenant Azure |
| `MS_GRAPH_CLIENT_ID` | Client ID del app registration Azure |
| `MS_GRAPH_CLIENT_SECRET` | Secret del app registration |
| `MS_GRAPH_SENDER` | Dirección del remitente |
| `MS_GRAPH_TO` | Destinatarios (separados por `;` o `,`) |
| `MS_GRAPH_CC` | CC (separados por `;` o `,`) |
| `MS_GRAPH_SUBJECT_PREFIX` | Prefijo del asunto del correo |

### Logs

| Variable | Default | Descripción |
|---|---|---|
| `LOG_DIR` | `logs` | Directorio base de logs |
| `SUCAMEC_LOG_MAX_RUNS` | `10` | Máximo de corridas a retener |

---

## 8. Salidas del Sistema

### Archivos Excel generados

Cada corrida genera hasta 2 archivos en `lotes/YYYYMMDD_HHMMSS/`:

**1. Reporte principal:**
```
RB_GADSOCarnetSUCAMEC_DD.MM.YY_HH.MM.SS.xlsx
```
Contiene todos los registros procesados con sus 46 columnas.

**2. Reporte de validación DSSP:**
```
RB_GADSOValidacionNoEncontradosSUCAMEC_DD.MM.YY_HH.MM.SS.xlsx
```
Solo contiene los registros que fueron `NO_ENCONTRADO` en el módulo de consultas, con el estado enriquecido desde DSSP > Bandeja de Emisión.

### Columnas del Excel de salida (46 total)

| # | Columna | Fuente |
|---|---|---|
| 1 | `documento` | detail |
| 2 | `tipo_documento` | detail |
| 3 | `nombre` | detail |
| 4 | `estado` | detail |
| 5 | `nro_carne` | detail |
| 6 | `modalidad` | detail |
| 7 | `ruc` | detail |
| 8 | `expediente` | detail |
| 9 | `nro_expediente` | detail |
| 10 | `anho_expediente` | detail |
| 11 | `fecha_emision` | detail |
| 12 | `fecha_vencimiento` | detail |
| 13 | `empresa` | detail |
| 14-20 | `curso_*_1` (7 campos) | courses |
| 21-27 | `curso_*_2` (7 campos) | courses |
| 28 | `licencia_numero` | license |
| 29 | `licencia_fecha_emision` | license |
| 30 | `licencia_fecha_venc` | license |
| 31 | `licencia_modalidad` | license |
| 32 | `licencia_restricciones` | license |
| 33-39 | `historial_*_1` (7 campos) | history |
| 40-46 | `historial_*_2` (7 campos) | history |

### Estados posibles del campo `estado`

| Estado | Descripción |
|---|---|
| `VIGENTE` | Carnet vigente en SUCAMEC |
| `VENCIDO` | Carnet vencido |
| `NO_ENCONTRADO` | No existe en módulo de consultas |
| `NO_ENCONTRADO {estado_dssp}` | No encontrado, pero validado en DSSP con su estado |
| `SIN_VER` | Resultado encontrado pero no se pudo abrir el detalle |
| `WORKER_ERROR` | Error de proceso durante el procesamiento del registro |

---

## 9. Herramientas y Librerías

### Runtime principal

| Librería | Versión | Uso |
|---|---|---|
| `playwright` | 1.51.0 | Automatización de Chromium (navegación, clics, JS eval) |
| `python-dotenv` | 1.0.1 | Carga de variables de entorno desde `.env` |
| `openpyxl` | 3.1.5 | Lectura y escritura de archivos Excel (.xlsx) |
| `easyocr` | 1.7.2 | OCR para resolución de CAPTCHA (modelo en inglés) |
| `Pillow` | 12.2.0 | Preprocesamiento de imágenes CAPTCHA para OCR |
| `numpy` | 2.4.4 | Arrays numéricos requeridos por EasyOCR |
| `pandas` | 3.0.1 | Manipulación de datos (uso auxiliar) |

### Servicios externos

| Servicio | Protocolo | Uso |
|---|---|---|
| SUCAMEC Portal | HTTPS + PrimeFaces/JSF | Consulta de estados de vigilantes |
| Microsoft Graph API | REST / OAuth2 | Envío de correo electrónico |
| Azure AD | OAuth2 client_credentials | Autenticación para Graph API |

### Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| Python 3.11+ | Runtime principal |
| Chromium (vía Playwright) | Navegador automatizado |
| Git | Control de versiones |
| Windows Task Scheduler | Ejecución programada (vía `.bat`) |

---

## 10. Manejo de Errores y Resiliencia

### CAPTCHA

| Situación | Comportamiento |
|---|---|
| OCR retorna string vacío | Refresca CAPTCHA, reintenta |
| OCR retorna texto muy corto | Refresca CAPTCHA, reintenta |
| Límite de intentos alcanzado | Lanza excepción, login falla |
| SUCAMEC devuelve error de captcha | Detectado por `ERROR_SELECTORS`, reintenta login completo |
| Timeout total de OCR | Lanza excepción con mensaje de timeout |

### Búsqueda de registros

| Situación | Estado resultante |
|---|---|
| Fila vacía en resultados | `NO_ENCONTRADO` |
| Sin enlace "Ver" visible | `SIN_VER` |
| Error de playwright durante extracción | `WORKER_ERROR` (capturado por orquestador) |
| Excepción en worker completo | Todos los registros del batch → `WORKER_ERROR` |

### Workers paralelos

Los workers corren en procesos independientes vía `ProcessPoolExecutor`. Si un worker falla completamente (crash del proceso), el orquestador captura la excepción y marca todos los registros de ese batch como `WORKER_ERROR`. El resto de workers continúan sin interrupción.

### Email

- Fallo en adquisición de token → loggeado, corrida continúa
- Fallo en envío → clasificado con `classify_graph_failure()`, loggeado, corrida continúa
- Email nunca bloquea ni invalida los resultados de la corrida

### DSSP

- Excepción durante validación DSSP → loggeada, registro mantiene estado `NO_ENCONTRADO` original
- La validación DSSP no bloquea la generación del Excel principal

---

## 11. Decisiones de Negocio Importantes

### 1. Prioridad de licencias: L4 > L1 > L2 > L3

Un vigilante puede tener múltiples licencias de armas en SUCAMEC. El sistema no toma la primera visible en la tabla; aplica una regla de prioridad donde **L4** (categoría más alta) es siempre preferida sobre L1, L2 o L3. Implementado en `extraction_flow/license.py`.

### 2. Solo cursos APROBADOS

De todos los cursos de capacitación que puede tener un vigilante, el sistema filtra y exporta únicamente los que tienen evaluación = `"APROBADO"`. Cursos reprobados o en proceso son ignorados. Máximo 2 cursos aprobados por vigilante.

### 3. Inferencia de tipo de documento por longitud

El campo `tipo_documento` (DNI vs C.E.) se infiere automáticamente por la longitud de la parte numérica del documento: exactamente 9 dígitos → C.E., cualquier otra longitud → DNI. Esto permite procesar listas mixtas sin que el operador tenga que clasificar manualmente.

### 4. Módulo de consulta configurable por empresa

Cada empresa cliente (JV, SELVA) puede usar un módulo diferente de SUCAMEC. `SUCAMEC_CONSULTAS_MODULE` en `.env` controla esto. En producción se usa `busqueda_vigilantes` porque permite seleccionar tipo de documento, siendo más preciso para vigilantes extranjeros.

### 5. Validación DSSP como segundo pase

Los registros `NO_ENCONTRADO` en el módulo de consultas no se descartan. Se validan en un segundo pase en **DSSP > Bandeja de Emisión**, que puede revelar el estado real de un vigilante cuyo expediente no aparece en el módulo principal. Esto reduce falsos negativos.

### 6. Dos empresas, una sola instancia del sistema

El sistema soporta dos empresas (JV Resguardo y SELVA) con credenciales separadas pero la misma lógica. El argumento `--grupo TODOS` permite procesar ambas secuencialmente en una sola ejecución. Cada grupo genera sus propios archivos de salida independientes.

### 7. Orden preservado en multiworker

A pesar de que los workers paralelos pueden terminar en orden diferente, el orquestador consolida los resultados en el orden original del Excel de entrada (usando `row_number` de `InputRecord`). El Excel de salida tiene el mismo orden que el de entrada.
