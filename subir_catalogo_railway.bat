@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: subir_catalogo_railway.bat
:: Sube la carpeta CATALOGO al volumen de Railway
:: REQUISITO: Railway CLI instalado (https://docs.railway.app/develop/cli)
::            y haber hecho "railway login" previamente
:: ─────────────────────────────────────────────────────────────────────────────

echo Subiendo CATALOGO a Railway Volume...
echo.

:: Ajusta el path si tu proyecto de Railway tiene otro nombre
railway volume cp "C:\Users\Usuario\Desktop\CATALOGO" /data/CATALOGO --recursive

echo.
echo Listo. El catalogo esta disponible en /data/CATALOGO en Railway.
pause
