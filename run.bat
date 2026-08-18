@echo off
echo Arrancando Bot de Camisetas...
cd /d "%~dp0"

:: Intentar con "python" primero, luego con "py"
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python bot.py
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        py bot.py
    ) else (
        echo ERROR: Python no encontrado. Ejecuta primero instalar.bat
    )
)
pause
