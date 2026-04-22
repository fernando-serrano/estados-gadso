# ESTADOS GADSO - Flujo SUCAMEC

Base modular para consultar estados de carnets SUCAMEC por empresa, empezando por el login de J&V Resguardo y Selva.

## Estructura

```text
src/agents_flow/
  cli.py
  login_flow/
    auth.py       # Login tradicional, captcha y validacion de sesion
    browser.py    # Apertura/cierre de Chromium
    config.py     # Variables .env y credenciales por grupo
    logging.py    # Logger del subflujo
    selectors.py  # Selectores Playwright del login
    cli.py        # Ejecucion aislada del login
  mis_vigilantes_flow/
    __init__.py   # Siguiente etapa: Consultas > Mis vigilantes
  extraction_flow/
    __init__.py   # Siguiente etapa: extraccion estructurada
  excel_flow/
    __init__.py   # Siguiente etapa: exportacion Excel
```

`agents_flow` representa el proceso completo. Cada carpeta interna representa una etapa del flujo para mantener bajo acoplamiento. El archivo `example/carnet_emision.py` queda como referencia historica.

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## Variables requeridas

El flujo reutiliza las credenciales actuales del `.env`:

```env
TIPO_DOC=RUC
NUMERO_DOCUMENTO=
USUARIO_SEL=
CLAVE_SEL=

SELVA_TIPO_DOC=RUC
SELVA_NUMERO_DOCUMENTO=
SELVA_USUARIO_SEL=
SELVA_CLAVE_SEL=
```

Variables utiles:

```env
SUCAMEC_HEADLESS=0
SUCAMEC_HOLD_BROWSER_OPEN=1
SUCAMEC_OCR_MAX_INTENTOS=4
SUCAMEC_LOGIN_CAPTCHA_RETRIES=3
SUCAMEC_FORCE_FIRST_CAPTCHA=
SUCAMEC_LOGIN_VALIDATION_TIMEOUT_MS=12000
SUCAMEC_LOG_MAX_FILES=10
```

Tambien se respetan variables heredadas del flujo anterior cuando existen, por ejemplo `CARNET_HEADLESS`, `HOLD_BROWSER_OPEN`, `CARNET_OCR_MAX_INTENTOS` y `LOGIN_VALIDATION_TIMEOUT_MS`.

## Probar login

```powershell
python -m src.agents_flow.cli --grupo JV
python -m src.agents_flow.cli --grupo SELVA
python -m src.agents_flow.cli --grupo TODOS
```

En Windows tambien puedes usar el `.bat`:

```bat
run_agents_flow.bat
run_agents_flow.bat SELVA
run_agents_flow.bat TODOS
run_agents_flow.bat JV --solo-login
```

Tambien se puede ejecutar solo el subflujo de login:

```powershell
python -m src.agents_flow.login_flow.cli --grupo JV
```

El comando abre SUCAMEC, completa autenticacion tradicional, resuelve el captcha por OCR y valida que la sesion haya cargado. Si `SUCAMEC_HOLD_BROWSER_OPEN=1` y el navegador no esta en headless, deja la ventana abierta para inspeccion.

Despues del login, el flujo navega a `CONSULTAS > MIS VIGILANTES`. Para probar solo login:

```powershell
python -m src.agents_flow.cli --grupo JV --solo-login
```

## Siguiente etapa

Sobre esta base se agregaran modulos separados para:

1. Navegar a `Consultas > Mis vigilantes`.
2. Buscar por DNI.
3. Validar si existe registro vigente/en tramite.
4. Abrir `Ver`.
5. Extraer los campos y exportarlos a Excel con el esquema acordado.
