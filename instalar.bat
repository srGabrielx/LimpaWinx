@echo off
chcp 65001 >nul
title Instalando Smart PC Cleaner PRO

echo ========================================================
echo   🚀 INSTALADOR OFICIAL DO SMART PC CLEANER PRO
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"

echo.
pause
