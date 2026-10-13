@echo off
setlocal
cd /d "%~dp0"
set "LENA_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%LENA_PYTHON%" (
    echo Create .venv and install requirements.txt first. See README.md.
    pause
    exit /b 1
)
"%LENA_PYTHON%" "%~dp0prepare_models.py" --verify-only
if errorlevel 1 (
    pause
    exit /b 1
)
"%LENA_PYTHON%" "%~dp0lena_app.py"
if errorlevel 1 pause
