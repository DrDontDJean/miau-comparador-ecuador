@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0GESTIONAR.ps1" -Accion sincronizar
pause
