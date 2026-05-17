@echo off
REM DocFlow - Inicializador
REM Este script inicia a interface gráfica do DocFlow

title DocFlow
echo.
echo ╔════════════════════════════════════════╗
echo ║   DocFlow v1.0                        ║
echo ║   Iniciando servidor...                ║
echo ╚════════════════════════════════════════╝
echo.

REM Ativar ambiente virtual
call .venv\Scripts\activate.bat

REM Iniciar o servidor
python app.py

pause
