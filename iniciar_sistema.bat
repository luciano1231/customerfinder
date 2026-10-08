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

:: Enlace para el celular sin límite de tiempo (Cloudflare). Si falla, el lanzador usa Pinggy.
if not exist "herramientas\cloudflared.exe" (
    echo Descargando cloudflared por unica vez...
    if not exist herramientas mkdir herramientas
    curl -sL -o herramientas\cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
)

:: Abre el lanzador (ventanita con el boton de encendido) sin consola
start "" pythonw Lanzador.pyw
