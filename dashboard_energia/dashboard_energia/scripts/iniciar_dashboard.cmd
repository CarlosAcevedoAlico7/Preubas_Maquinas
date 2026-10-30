@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro .venv. Instale primero las dependencias.
    exit /b 1
)
if not exist "demo\EX14_VAREX_II.sqlite" (
    echo No se encontro la base SQLite demo en la carpeta demo.
    exit /b 1
)
if not exist "logs" mkdir "logs"

set "FUENTE_DATOS=sqlite"
set "SQLITE_DIR=%CD%\demo"
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true >> "logs\streamlit.log" 2>&1
exit /b %ERRORLEVEL%
