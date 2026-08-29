# Script de Instalacao do Smart PC Cleaner PRO no Windows
param (
    [switch]$Uninstall
)

$AppDir = $PSScriptRoot
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$StartMenuPath = [System.Environment]::GetFolderPath('Programs')
$StartupPath = [System.Environment]::GetFolderPath('Startup')

$ShortcutDesktop = Join-Path $DesktopPath "Smart PC Cleaner PRO.lnk"
$ShortcutStartMenu = Join-Path $StartMenuPath "Smart PC Cleaner PRO.lnk"
$StartupVbs = Join-Path $StartupPath "SmartPCCleanerGuard.vbs"

if ($Uninstall) {
    Write-Host "`n[DESINSTALACAO] Removendo Smart PC Cleaner PRO..." -ForegroundColor Yellow
    
    # 1. Encerrar processos em background
    Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*main.py --daemon*" } | Stop-Process -Force -ErrorAction SilentlyContinue

    # 2. Remover atalhos
    if (Test-Path $ShortcutDesktop) { Remove-Item $ShortcutDesktop -Force; Write-Host "OK: Atalho da Area de Trabalho removido." -ForegroundColor Green }
    if (Test-Path $ShortcutStartMenu) { Remove-Item $ShortcutStartMenu -Force; Write-Host "OK: Atalho do Menu Iniciar removido." -ForegroundColor Green }
    if (Test-Path $StartupVbs) { Remove-Item $StartupVbs -Force; Write-Host "OK: Inicializacao automatica removida." -ForegroundColor Green }

    Write-Host "`n[SUCESSO] O Smart PC Cleaner PRO foi desinstalado com sucesso!`n" -ForegroundColor Green
    exit 0
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Instalando Smart PC Cleaner PRO na Maquina Local        " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Instalar dependencias Python
Write-Host "`n[1/4] Verificando e instalando pacotes Python..." -ForegroundColor Cyan
$reqFile = Join-Path $AppDir "requirements.txt"
if (Test-Path $reqFile) {
    pip install -r $reqFile --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: Todas as dependencias foram instaladas!" -ForegroundColor Green
    } else {
        Write-Host "Aviso: pip retornou codigo de aviso, continuando..." -ForegroundColor Yellow
    }
}

# 2. Criar Atalho na Area de Trabalho e Menu Iniciar
Write-Host "`n[2/4] Criando atalhos no Windows..." -ForegroundColor Cyan
$WScriptShell = New-Object -ComObject WScript.Shell
$TargetBat = Join-Path $AppDir "cleaner_admin.bat"

# Atalho Area de Trabalho
$Shortcut = $WScriptShell.CreateShortcut($ShortcutDesktop)
$Shortcut.TargetPath = $TargetBat
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.Description = "Smart PC Cleaner PRO - Otimizador Inteligente do Windows"
$Shortcut.Save()
Write-Host "OK: Atalho criado na Area de Trabalho: $ShortcutDesktop" -ForegroundColor Green

# Atalho Menu Iniciar
$Shortcut2 = $WScriptShell.CreateShortcut($ShortcutStartMenu)
$Shortcut2.TargetPath = $TargetBat
$Shortcut2.WorkingDirectory = $AppDir
$Shortcut2.Description = "Smart PC Cleaner PRO - Otimizador Inteligente do Windows"
$Shortcut2.Save()
Write-Host "OK: Atalho criado no Menu Iniciar: $ShortcutStartMenu" -ForegroundColor Green

# 3. Configurar Inicializacao com o Windows
Write-Host "`n[3/4] Configurando Intermediador em Segundo Plano no Startup..." -ForegroundColor Cyan
$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$AppDir"
WshShell.Run "pythonw.exe main.py --daemon", 0, False
"@
Set-Content -Path $StartupVbs -Value $VbsContent -Encoding ASCII
Write-Host "OK: Intermediador registrado para iniciar automaticamente com o Windows!" -ForegroundColor Green

# 4. Iniciar Intermediador Agora
Write-Host "`n[4/4] Iniciando Intermediador de Recursos e Escudo em Tempo Real..." -ForegroundColor Cyan
wscript.exe $StartupVbs
Write-Host "OK: Intermediador em Tempo Real iniciado com sucesso na Bandeja do Sistema (System Tray)!" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  INSTALACAO CONCLUIDA COM SUCESSO!                       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "O Smart PC Cleaner PRO ja esta instalado e ativo no seu PC." -ForegroundColor White
Write-Host "- O Intermediador esta vigiando RAM, Rede e Disco na bandeja." -ForegroundColor Cyan
Write-Host "- Voce pode abrir o aplicativo pelo icone na Area de Trabalho." -ForegroundColor Cyan
Write-Host ""
