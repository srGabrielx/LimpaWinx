"""
Módulo de Proteção e Intermediação de Recursos em Tempo Real (Resident Shield & Resource Watchdog).
Atua em segundo plano como um intermediador inteligente:
1. Monitora o consumo de RAM, Disco e Rede em tempo real.
2. Quando detecta saturação ou esgotamento de recursos, executa mitigação instantânea (Working Set trim, Flush DNS, liberação de buffers de rede).
3. Notifica o usuário nativamente via Windows Toast Notification.
4. Mantém ícone interativo na Bandeja do Windows (System Tray) para comandos manuais rápidos.
5. Monitora pastas de download contra arquivos suspeitos.
"""

import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    pass

from .system_monitor import SystemMonitor
from .cleaner_engine import CleanerEngine
from .config_manager import ConfigManager
from .auto_healer import AutoHealer


def send_windows_toast(title: str, message: str) -> None:
    """Envia uma notificação Toast nativa e assíncrona no Windows 10/11."""
    # Escapar aspas simples e duplas para PowerShell
    safe_title = title.replace('"', '`"').replace("'", "''")
    safe_message = message.replace('"', '`"').replace("'", "''")

    ps_script = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
    $textNodes = $xml.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($xml.CreateTextNode("{safe_title}")) | Out-Null
    $textNodes.Item(1).AppendChild($xml.CreateTextNode("{safe_message}")) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Smart PC Cleaner")
    $notifier.Show($toast)
    '''
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


class ThreatHandler(FileSystemEventHandler):
    """Monitora a chegada de arquivos executáveis/scripts baixados da internet."""
    
    def __init__(self):
        super().__init__()
        self.suspicious_extensions = {".exe", ".bat", ".cmd", ".vbs", ".ps1", ".msi", ".dll", ".scr"}

    def on_created(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.src_path)[1].lower()
        if ext in self.suspicious_extensions:
            threading.Thread(target=self.scan_file, args=(event.src_path,), daemon=True).start()

    def on_moved(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.dest_path)[1].lower()
        if ext in self.suspicious_extensions:
            threading.Thread(target=self.scan_file, args=(event.dest_path,), daemon=True).start()

    def scan_file(self, filepath: str):
        time.sleep(1.5)
        if not os.path.exists(filepath):
            return

        filename = os.path.basename(filepath)
        mpcmdrun_path = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
        if not os.path.exists(mpcmdrun_path):
            return

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                [mpcmdrun_path, "-Scan", "-ScanType", "3", "-File", filepath],
                startupinfo=startupinfo,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 2:
                send_windows_toast(
                    "🛡️ Smart PC Cleaner: Ameaça Bloqueada!",
                    f"O arquivo {filename} foi identificado como malicioso e neutralizado pelo Windows Defender."
                )
        except Exception as e:
            AutoHealer.log_failure("shield_scan_file", e, filepath)


class RealtimeResourceWatchdog(threading.Thread):
    """
    Thread de Intermediação de Recursos em Tempo Real.
    Monitora uso de RAM, latência/cache de rede e capacidade de disco.
    Quando detecta esgotamento, executa otimizações automáticas de alta prioridade.
    """

    def __init__(self, engine: CleanerEngine, config: Dict[str, Any]):
        super().__init__(daemon=True, name="ResourceWatchdogThread")
        self.engine = engine
        self.config = config.get("realtime_watchdog", {})
        self.interval = self.config.get("check_interval_seconds", 15)
        self.ram_threshold = self.config.get("ram_threshold_percent", 80)
        self.ram_cooldown = self.config.get("ram_cooldown_seconds", 120)
        self.min_disk_free_gb = self.config.get("min_disk_free_gb", 5.0)
        self.auto_flush_dns = self.config.get("auto_flush_dns", True)
        self.enable_toast = self.config.get("enable_toast_notifications", True)

        self.running = True
        self.paused = False
        self.last_ram_boost_time = 0.0
        self.last_disk_check_time = 0.0

    def run(self):
        while self.running:
            try:
                if not self.paused:
                    self._check_resources()
            except Exception as e:
                AutoHealer.log_failure("realtime_resource_watchdog", e)
            
            time.sleep(self.interval)

    def _check_resources(self):
        now = time.time()
        mem_info = SystemMonitor.get_memory_info()
        current_ram_pct = mem_info.get("percent_used", 0)

        # 1. Verificação de Esgotamento de Memória RAM
        if current_ram_pct >= self.ram_threshold:
            if (now - self.last_ram_boost_time) > self.ram_cooldown:
                self.last_ram_boost_time = now
                
                # Executa otimização imediata de Working Set de processos
                ram_result = self.engine.optimize_ram(mode="all")
                
                # Se configurado, otimiza também buffers de rede/DNS para desafogar a pilha
                net_msg = ""
                if self.auto_flush_dns:
                    net_result = self.engine.quick_network_boost()
                    if net_result.success:
                        net_msg = " + Buffers de Rede Otimizados"

                freed_mb = ram_result.ram_freed_mb
                if self.enable_toast:
                    send_windows_toast(
                        "⚡ Intermediador: Recursos Liberados!",
                        f"Consumo de RAM atingiu {current_ram_pct}%. Liberamos {freed_mb:.1f} MB de RAM instantaneamente{net_msg}."
                    )

        # 2. Verificação periódica de Espaço em Disco Crítico (a cada 5 minutos)
        if (now - self.last_disk_check_time) > 300:
            self.last_disk_check_time = now
            disk_info = SystemMonitor.get_disk_info("C:")
            free_gb = disk_info.get("free_gb", 999.0)

            if free_gb < self.min_disk_free_gb:
                # Esgotamento de disco: limpa temporários de emergência
                user_temp = os.environ.get("TEMP", "")
                temp_res = self.engine.clean_directory_content(user_temp, "Temporários Emergenciais")
                
                if self.enable_toast:
                    send_windows_toast(
                        "⚠️ Intermediador: Espaço em Disco Baixo",
                        f"Disco C: com apenas {free_gb:.1f} GB livres. Limpeza emergencial liberou {SystemMonitor.format_bytes(temp_res.bytes_freed)}."
                    )

    def stop(self):
        self.running = False


class ResidentShield:
    """Daemon Principal: Integra o Intermediador de Recursos, Escudo de Arquivos e Menu na Bandeja."""
    
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.engine = CleanerEngine(config_manager=self.config_mgr)
        self.user_profile = os.environ.get("USERPROFILE", "C:\\")
        self.watch_dirs = [
            os.path.join(self.user_profile, "Downloads"),
            os.path.join(self.user_profile, "Desktop")
        ]
        self.observer = Observer()
        self.watchdog_thread = RealtimeResourceWatchdog(self.engine, self.config_mgr.config)
        self.icon = None

    def create_icon_image(self, active: bool = True):
        """Cria um ícone moderno de escudo na bandeja do sistema."""
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        
        main_color = (0, 200, 83, 255) if active else (255, 171, 0, 255) # Verde ativo, Amarelo pausado
        sec_color = (0, 120, 50, 255) if active else (180, 100, 0, 255)
        
        # Desenha escudo
        d.polygon([(32, 4), (58, 16), (58, 42), (32, 60), (6, 42), (6, 16)], fill=main_color)
        d.polygon([(32, 4), (58, 16), (58, 42), (32, 60)], fill=sec_color)
        
        # Símbolo central de raio / proteção
        d.polygon([(34, 14), (20, 32), (30, 32), (28, 48), (44, 28), (34, 28)], fill=(255, 255, 255, 255))
        return image

    def start_watchdogs(self):
        """Inicia observador de arquivos e thread de recursos."""
        # 1. Threat Watchdog
        handler = ThreatHandler()
        for directory in self.watch_dirs:
            if os.path.exists(directory):
                self.observer.schedule(handler, directory, recursive=False)
        self.observer.start()

        # 2. Resource Intermediator Thread
        self.watchdog_thread.start()

    def action_optimize_now(self, icon=None, item=None):
        """Disparo manual de otimização instantânea de RAM."""
        ram_res = self.engine.optimize_ram(mode="all")
        send_windows_toast(
            "⚡ Otimização Instantânea Concluída",
            f"{ram_res.ram_freed_mb:.1f} MB de memória RAM foram liberados para o sistema!"
        )

    def action_boost_network(self, icon=None, item=None):
        """Disparo manual de liberação e aceleração de rede."""
        net_res = self.engine.quick_network_boost()
        send_windows_toast(
            "🌐 Rede & DNS Otimizados",
            net_res.message
        )

    def action_show_status(self, icon=None, item=None):
        """Exibe status atual do hardware em toast."""
        mem = SystemMonitor.get_memory_info()
        disk = SystemMonitor.get_disk_info("C:")
        msg = f"RAM: {mem.get('percent_used', 0)}% em uso ({mem.get('avail_mb', 0)} MB livres) | Disco C: {disk.get('free_gb', 0)} GB livres"
        send_windows_toast("📊 Status dos Recursos do Sistema", msg)

    def action_toggle_pause(self, icon=None, item=None):
        """Pausa ou retoma a intermediação automática."""
        self.watchdog_thread.paused = not self.watchdog_thread.paused
        state = "Pausado" if self.watchdog_thread.paused else "Ativo"
        if self.icon:
            self.icon.icon = self.create_icon_image(active=not self.watchdog_thread.paused)
            self.icon.title = f"Smart PC Cleaner — Intermediador ({state})"
        send_windows_toast("Smart PC Cleaner", f"Intermediador automático em tempo real agora está: {state}")

    def on_quit(self, icon, item):
        """Encerra com segurança todas as threads e fecha a bandeja."""
        self.watchdog_thread.stop()
        self.observer.stop()
        icon.stop()

    def start(self):
        """Inicia o daemon no background com bandeja do sistema."""
        print("[INTERMEDIADOR] Ativado com sucesso! Monitorando RAM, Rede e Arquivos em tempo real.")
        
        self.start_watchdogs()
        
        # Notificação de inicialização
        send_windows_toast(
            "🛡️ Smart PC Cleaner PRO — Intermediador Ativo",
            "O Guardião em Tempo Real está monitorando e otimizando automaticamente o uso de RAM e rede do seu PC."
        )

        menu = pystray.Menu(
            item('🛡️ Intermediador: Ativo', lambda: None, enabled=False),
            item('⚡ Otimizar Recursos Agora (RAM)', self.action_optimize_now),
            item('🌐 Liberar Recursos de Rede & DNS', self.action_boost_network),
            item('📊 Ver Status do Sistema', self.action_show_status),
            pystray.Menu.SEPARATOR,
            item('⏸️ Pausar / Retomar Intermediador', self.action_toggle_pause),
            item('❌ Fechar Intermediador', self.on_quit)
        )
        
        self.icon = pystray.Icon(
            "SmartPCCleaner",
            self.create_icon_image(active=True),
            "Smart PC Cleaner — Intermediador Ativo",
            menu
        )
        
        self.icon.run()
        self.observer.join()
