@echo off
chcp 65001 >nul
title Desinstalando Smart PC Cleaner PRO

echo ========================================================
echo   🗑️ DESINSTALADOR DO SMART PC CLEANER PRO
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall

echo.
pause
