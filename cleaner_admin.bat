@echo off
chcp 65001 >nul
title Smart PC Cleaner PRO (Elevando para Administrador...)
cd /d "%~dp0"

echo [Verificando dependências...]
python -c "import rich; import prompt_toolkit" 2>nul
if %errorlevel% neq 0 (
    echo [Instalando bibliotecas Pro (rich, prompt_toolkit)...]
    pip install -r requirements.txt -q
)

:: Verificar se já é Administrador
net session >nul 2>&1
if %errorlevel% == 0 (
    python main.py %*
) else (
    echo Solicitando privilégios de Administrador...
    if "%~1"=="" (
        powershell -Command "Start-Process cmd -ArgumentList '/k cd /d \"%~dp0\" && python main.py' -Verb RunAs"
    ) else (
        powershell -Command "Start-Process cmd -ArgumentList '/c cd /d \"%~dp0\" && python main.py %*' -Verb RunAs"
    )
)
