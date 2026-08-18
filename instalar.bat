@echo off
echo ════════════════════════════════════════
echo   INSTALADOR - Bot de Camisetas
echo ════════════════════════════════════════
echo.

:: Comprobar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python no esta instalado.
        echo.
        echo Sigue estos pasos:
        echo  1. Abre tu navegador y ve a: https://www.python.org/downloads/
        echo  2. Pulsa el boton amarillo "Download Python"
        echo  3. Ejecuta el instalador descargado
        echo  4. MUY IMPORTANTE: marca la casilla "Add Python to PATH"
        echo  5. Pulsa "Install Now"
        echo  6. Cuando termine, cierra esta ventana y vuelve a ejecutar instalar.bat
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

echo Python encontrado. Instalando dependencias...
echo.
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
echo.
echo ════════════════════════════════════════
echo   Instalacion completada correctamente
echo   Ahora ejecuta run.bat para arrancar el bot
echo ════════════════════════════════════════
pause
