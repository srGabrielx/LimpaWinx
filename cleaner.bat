@echo off
chcp 65001 >nul
title Smart PC Cleaner PRO
cd /d "%~dp0"

echo [Verificando dependências...]
python -c "import rich; import prompt_toolkit" 2>nul
if %errorlevel% neq 0 (
    echo [Instalando bibliotecas Pro (rich, prompt_toolkit)...]
    pip install -r requirements.txt -q
)

python main.py %*
if errorlevel 1 (
    echo.
    echo Pressione qualquer tecla para fechar...
    pause >nul
)
