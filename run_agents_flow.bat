@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [INFO] No se encontro .venv. Se usara el Python disponible en PATH.
)

set "GRUPO=%~1"
if "%GRUPO%"=="" set "GRUPO=JV"

if /I "%GRUPO%"=="--help" goto :help
if /I "%GRUPO%"=="-h" goto :help
if /I "%GRUPO%"=="/?" goto :help

if /I "%GRUPO%"=="JV" goto :run
if /I "%GRUPO%"=="SELVA" goto :run
if /I "%GRUPO%"=="TODOS" goto :run

echo [ERROR] Grupo invalido: %GRUPO%
echo Use: run_agents_flow.bat [JV^|SELVA^|TODOS]
pause
exit /b 2

:run
echo [INFO] Ejecutando flujo SUCAMEC con grupo: %GRUPO%
python -m src.agents_flow.cli --grupo %GRUPO%

set "EXIT_CODE=%ERRORLEVEL%"
echo [INFO] Flujo finalizado con codigo: %EXIT_CODE%

pause
exit /b %EXIT_CODE%

:help
echo Uso:
echo   run_agents_flow.bat [JV^|SELVA^|TODOS]
echo.
echo Ejemplos:
echo   run_agents_flow.bat
echo   run_agents_flow.bat SELVA
echo   run_agents_flow.bat TODOS
pause
exit /b 0
