@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0GESTIONAR.ps1" -Accion restaurar -SinNavegador
if errorlevel 1 (
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0GESTIONAR.ps1" -Accion iniciar
if errorlevel 1 pause
