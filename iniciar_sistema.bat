@echo off
chcp 65001 > nul
title Prospector Pro
cd /d "%~dp0"

where python > nul 2>&1
if errorlevel 1 (
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/ ^(marca "Add to PATH"^).
    pause
    exit /b
)

:: Primera vez: instalar dependencias y el navegador de Playwright
python -c "import flask, playwright, openpyxl" > nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias por unica vez...
    python -m pip install -r requirements.txt
    python -m playwright install chromium
)

:: Abre el lanzador (ventanita con el boton de encendido) sin consola
start "" pythonw Lanzador.pyw
