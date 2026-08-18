@echo off
chcp 65001 >nul
echo ════════════════════════════════════════════════════════
echo   MOVER FOTOS - La Liga 26/27
echo   Mueve las fotos descargadas a las carpetas del catálogo
echo ════════════════════════════════════════════════════════
echo.

:: Detectar Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=py
    ) else (
        echo ERROR: Python no encontrado.
        pause
        exit /b 1
    )
)

echo Moviendo fotos desde Descargas a CATALOGO...
echo.
%PYTHON% "%~dp0mover_fotos.py"
pause
