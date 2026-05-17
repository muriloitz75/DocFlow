@echo off
REM MarkItDown Web Interface - Inicializador
REM Este script inicia a interface gráfica do MarkItDown

title MarkItDown Web Interface
echo.
echo ╔════════════════════════════════════════╗
echo ║   MarkItDown Web Interface v1.0       ║
echo ║   Iniciando servidor...                ║
echo ╚════════════════════════════════════════╝
echo.

REM Ativar ambiente virtual
call .venv\Scripts\activate.bat

REM Iniciar o servidor
python app.py

pause
