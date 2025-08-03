@echo off
setlocal

REM Ruta del entorno virtual (modifica si usás otra)
set VENV_DIR=venv

REM Activar el entorno virtual si existe
if exist %VENV_DIR%\Scripts\activate (
    call %VENV_DIR%\Scripts\activate
) else (
    echo ❌ No se encontró el entorno virtual. Creando uno...
    python -m venv %VENV_DIR%
    call %VENV_DIR%\Scripts\activate
)

REM Verificar si hay que instalar dependencias
echo 🔍 Verificando dependencias...
pip show fastapi >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ⏳ Instalando dependencias desde requirements.txt...
    pip install -r requirements.txt
) else (
    echo ✅ Dependencias ya instaladas.
)

REM Ejecutar el servidor FastAPI
echo 🚀 Iniciando FastAPI...
python main.py

endlocal
pause