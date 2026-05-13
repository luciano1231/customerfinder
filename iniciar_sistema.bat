@echo off
color 0b
title Prospector Pro - Panel Central

echo ========================================================
echo     Iniciando el Motor de Prospector Pro (Servidor)
echo ========================================================
:: Abre el servidor en una nueva ventana oculta o paralela
start "Servidor Local" cmd /c "python server.py"

timeout /t 3 /nobreak > nul

:: Abre el tablero automáticamente en el navegador de tu computadora
start http://localhost:5000

echo.
echo ========================================================
echo     Generando tu Enlace Remoto para el Celular...
echo ========================================================
echo.
echo Espera unos segundos y copia el enlace web que aparecera a continuacion
echo (El que termina en pinggy.link).
echo Cuando quieras terminar de usarlo, solo cierra esta ventana.
echo.

ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:5000 a.pinggy.io

pause
