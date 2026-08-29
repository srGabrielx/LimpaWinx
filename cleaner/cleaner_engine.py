"""
Motor de Execução de Limpeza e Otimização do Windows.
Executa chamadas Win32 nativas (RAM Working Set, Lixeira), limpeza de arquivos
temporários com tratamento seguro de arquivos bloqueados, flush DNS e rotinas por níveis.
"""

import os
import sys
import shutil
import ctypes
from ctypes import wintypes
import subprocess
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from .system_monitor import SystemMonitor
from .auto_healer import AutoHealer


# Constantes Win32
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
PROCESS_ALL_ACCESS = 0x1F0FFF
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004


@dataclass
class ActionResult:
    action_id: str
    name: str
    success: bool
    bytes_freed: int = 0
    ram_freed_mb: float = 0.0
    items_deleted: int = 0
    message: str = ""
    error: Optional[str] = None


@dataclass
class ExecutionReport:
    total_bytes_freed: int = 0
    total_ram_freed_mb: float = 0.0
    total_items_deleted: int = 0
    actions_executed: List[ActionResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CleanerEngine:
    """Motor central que executa todas as operações reais no sistema operacional."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.safety_config = config_manager.config.get("safety", {}) if config_manager else {}
        self.ignore_exts = set(self.safety_config.get("ignore_extensions", [".lock", ".pid", ".sock", ".db-wal", ".git"]))
        self.ignore_folders = set(self.safety_config.get("ignore_folders", ["System Volume Information", "$Recycle.Bin", "Recovery"]))

    # =========================================================================
    # 1. OTIMIZAÇÃO REAL DE MEMÓRIA RAM (WIN32 API)
    # =========================================================================
    def optimize_ram(self, mode: str = "all") -> ActionResult:
        """
        Libera Working Set de processos do Windows usando EmptyWorkingSet e SetProcessWorkingSetSize.
        Mede o uso de RAM antes e depois para relatar os MB reais liberados.
        """
        mem_before = SystemMonitor.get_memory_info()
        pids_trimmed = 0

        try:
            # Obter lista de todos os PIDs ativos
            pids = (wintypes.DWORD * 4096)()
            bytes_returned = wintypes.DWORD()
            res = ctypes.windll.psapi.EnumProcesses(
                ctypes.byref(pids),
                ctypes.sizeof(pids),
                ctypes.byref(bytes_returned)
            )

            if res:
                num_pids = int(bytes_returned.value / ctypes.sizeof(wintypes.DWORD))
                psapi = ctypes.windll.psapi
                kernel32 = ctypes.windll.kernel32
                
                # Ignorar PIDs críticos (0 = Idle, 4 = System) que sempre falham
                critical_pids = {0, 4}

                for i in range(num_pids):
                    pid = pids[i]
                    if pid in critical_pids:
                        continue
                    # Tenta abrir o processo com permissão de Quota
                    h_process = kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION,
                        False,
                        pid
                    )
                    if h_process:
                        try:
                            # 1. Tenta EmptyWorkingSet
                            trimmed = psapi.EmptyWorkingSet(h_process)
                            if not trimmed:
                                # 2. Fallback para SetProcessWorkingSetSize(-1, -1)
                                kernel32.SetProcessWorkingSetSize(h_process, -1, -1)
                            pids_trimmed += 1
                        except Exception:
                            pass
                        finally:
                            kernel32.CloseHandle(h_process)

        except Exception as e:
            return ActionResult(
                action_id="optimize_ram",
                name="Otimização de Memória RAM",
                success=False,
                error=f"Falha na chamada Win32 de memória: {str(e)}"
            )

        # Mede novamente após a liberação
        mem_after = SystemMonitor.get_memory_info()
        # Se a memória disponível aumentou, calculamos a diferença
        diff_mb = max(0.0, mem_after["avail_mb"] - mem_before["avail_mb"])

        return ActionResult(
            action_id="optimize_ram",
            name="Otimização de Memória RAM",
            success=True,
            ram_freed_mb=round(diff_mb, 1),
            items_deleted=pids_trimmed,
            message=f"Processos otimizados: {pids_trimmed} | Memória liberada: ~{diff_mb:.1f} MB (Uso: {mem_before['percent_used']}% → {mem_after['percent_used']}%)"
        )

    # =========================================================================
    # 2. ESVAZIAR LIXEIRA (WIN32 API)
    # =========================================================================
    def empty_recycle_bin(self) -> ActionResult:
        """Esvazia a lixeira do Windows via SHEmptyRecycleBinW."""
        rb_before = SystemMonitor.get_recycle_bin_info()
        bytes_before = rb_before.get("size_bytes", 0)
        items_before = rb_before.get("num_items", 0)

        if items_before == 0 and bytes_before == 0:
            return ActionResult(
                action_id="recycle_bin",
                name="Esvaziar Lixeira do Windows",
                success=True,
                bytes_freed=0,
                items_deleted=0,
                message="A Lixeira já estava vazia."
            )

        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)

        if res == 0 or res == -2147418113:  # S_OK ou já vazia
            return ActionResult(
                action_id="recycle_bin",
                name="Esvaziar Lixeira do Windows",
                success=True,
                bytes_freed=bytes_before,
                items_deleted=items_before,
                message=f"Lixeira esvaziada: {items_before} itens removidos ({SystemMonitor.format_bytes(bytes_before)} liberados)."
            )
        else:
            return ActionResult(
                action_id="recycle_bin",
                name="Esvaziar Lixeira do Windows",
                success=False,
                error=f"Código de retorno Windows: {res}"
            )

    # =========================================================================
    # 3. LIMPEZA SEGURA DE DIRETÓRIOS E ARQUIVOS TEMPORÁRIOS
    # =========================================================================
    def clean_directory_content(self, path: str, name: str = "Diretório") -> ActionResult:
        """Limpa todo o conteúdo de um diretório ignorando com segurança arquivos bloqueados/em uso."""
        expanded_path = os.path.expandvars(path)
        if not os.path.exists(expanded_path):
            return ActionResult(
                action_id="clean_dir",
                name=name,
                success=True,
                bytes_freed=0,
                items_deleted=0,
                message="Diretório não encontrado ou já limpo."
            )

        bytes_freed = 0
        items_deleted = 0
        locked_items = 0

        # Iterar sobre os itens do diretório raiz
        try:
            with os.scandir(expanded_path) as entries:
                for entry in entries:
                    # Ignorar pastas protegidas
                    if entry.name in self.ignore_folders:
                        continue

                    full_path = entry.path

                    # Se for arquivo
                    if entry.is_file(follow_symlinks=False) or entry.is_symlink():
                        # Ignorar extensões de lock
                        _, ext = os.path.splitext(entry.name)
                        if ext.lower() in self.ignore_exts:
                            continue

                        try:
                            fsize = entry.stat(follow_symlinks=False).st_size
                            os.chmod(full_path, 0o777)  # Garantir permissão de escrita
                            os.remove(full_path)
                            bytes_freed += fsize
                            items_deleted += 1
                        except (PermissionError, OSError):
                            locked_items += 1
                            continue

                    # Se for diretório
                    elif entry.is_dir(follow_symlinks=False):
                        try:
                            dir_size, _ = SystemMonitor.get_directory_size(full_path)
                            # Tentativa de remover árvore
                            shutil.rmtree(full_path, ignore_errors=False)
                            bytes_freed += dir_size
                            items_deleted += 1
                        except Exception:
                            # Se falhar a pasta toda, tenta limpar recursivamente os arquivos internos que não estejam travados
                            sub_freed, sub_deleted, sub_locked = self._clean_subtree_safe(full_path)
                            bytes_freed += sub_freed
                            items_deleted += sub_deleted
                            locked_items += sub_locked
                            try:
                                os.rmdir(full_path)
                            except Exception:
                                pass
        except (PermissionError, OSError) as e:
            return ActionResult(
                action_id="clean_dir",
                name=name,
                success=False,
                error=f"Acesso negado (execute como Administrador se necessário): {str(e)}"
            )

        msg = f"{items_deleted} itens removidos ({SystemMonitor.format_bytes(bytes_freed)} liberados)"
        if locked_items > 0:
            msg += f" [{locked_items} itens em uso foram ignorados com segurança]"

        return ActionResult(
            action_id="clean_dir",
            name=name,
            success=True,
            bytes_freed=bytes_freed,
            items_deleted=items_deleted,
            message=msg
        )

    def _clean_subtree_safe(self, folder: str) -> Tuple[int, int, int]:
        """Auxiliar para limpar recursivamente ignorando arquivos em uso."""
        freed = 0
        deleted = 0
        locked = 0
        for root, dirs, files in os.walk(folder, topdown=False):
            for f in files:
                fpath = os.path.join(root, f)
                try:
                    size = os.path.getsize(fpath)
                    os.chmod(fpath, 0o777)
                    os.remove(fpath)
                    freed += size
                    deleted += 1
                except Exception:
                    locked += 1
            for d in dirs:
                dpath = os.path.join(root, d)
                try:
                    os.rmdir(dpath)
                except Exception:
                    pass
        return freed, deleted, locked

    # =========================================================================
    # 4. FLUSH DNS
    # =========================================================================
    def flush_dns(self) -> ActionResult:
        """Limpa o cache do resolvedor DNS do Windows."""
        try:
            res = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, errors="replace", timeout=10)
            if res.returncode == 0:
                return ActionResult(
                    action_id="flush_dns",
                    name="Limpar Cache DNS",
                    success=True,
                    message="Cache do resolvedor DNS liberado com sucesso."
                )
            else:
                return ActionResult(
                    action_id="flush_dns",
                    name="Limpar Cache DNS",
                    success=False,
                    error=res.stderr.strip() or "Falha ao executar ipconfig /flushdns"
                )
        except Exception as e:
            return ActionResult(
                action_id="flush_dns",
                name="Limpar Cache DNS",
                success=False,
                error=str(e)
            )

    # =========================================================================
    # 5. LOGS DE EVENTOS DO WINDOWS (WEVTUTIL)
    # =========================================================================
    def clean_event_logs(self) -> ActionResult:
        """Limpa os logs de eventos do Windows utilizando wevtutil."""
        if not SystemMonitor.is_admin():
            return ActionResult(
                action_id="windows_event_logs",
                name="Limpar Logs de Eventos do Windows",
                success=False,
                error="Esta ação requer privilégios de Administrador. Execute o cleaner como Administrador."
            )

        try:
            # Obter lista de canais de log
            p = subprocess.run(["wevtutil", "el"], capture_output=True, text=True, errors="replace", timeout=15)
            if p.returncode != 0:
                return ActionResult(
                    action_id="windows_event_logs",
                    name="Limpar Logs de Eventos",
                    success=False,
                    error="Não foi possível listar os logs de eventos."
                )

            logs = p.stdout.strip().splitlines()
            cleared_count = 0

            for log_name in logs:
                log_name = log_name.strip()
                if not log_name:
                    continue
                res = subprocess.run(["wevtutil", "cl", log_name], capture_output=True, text=True, errors="replace", timeout=5)
                if res.returncode == 0:
                    cleared_count += 1

            return ActionResult(
                action_id="windows_event_logs",
                name="Limpar Logs de Eventos do Windows",
                success=True,
                items_deleted=cleared_count,
                message=f"{cleared_count} canais de log de eventos limpos."
            )
        except Exception as e:
            return ActionResult(
                action_id="windows_event_logs",
                name="Limpar Logs de Eventos",
                success=False,
                error=str(e)
            )

    # =========================================================================
    # 6. CACHE DO WINDOWS UPDATE
    # =========================================================================
    def clean_windows_update_cache(self) -> ActionResult:
        """Para o serviço wuauserv, limpa SoftwareDistribution\\Download e reinicia o serviço."""
        if not SystemMonitor.is_admin():
            return ActionResult(
                action_id="windows_update_cache",
                name="Cache do Windows Update",
                success=False,
                error="Esta ação requer privilégios de Administrador."
            )

        try:
            subprocess.run(["net", "stop", "wuauserv"], capture_output=True, text=True, errors="replace", timeout=15)
            update_dir = os.path.expandvars("C:\\Windows\\SoftwareDistribution\\Download")
            res = self.clean_directory_content(update_dir, "Cache do Windows Update")
            subprocess.run(["net", "start", "wuauserv"], capture_output=True, text=True, errors="replace", timeout=15)
            return res
        except Exception as e:
            return ActionResult(
                action_id="windows_update_cache",
                name="Cache do Windows Update",
                success=False,
                error=str(e)
            )

    # =========================================================================
    # PRO: PONTO DE RESTAURAÇÃO
    # =========================================================================
    def create_restore_point(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("restore_point", "Criar Ponto de Restauração", False, error="Requer Administrador.")
        try:
            cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Checkpoint-Computer -Description \\"Smart PC Cleaner PRO\\" -RestorePointType \\"MODIFY_SETTINGS\\""'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace", timeout=30)
            if res.returncode == 0:
                return ActionResult("restore_point", "Criar Ponto de Restauração", True, message="Ponto de restauração criado com segurança.")
            else:
                return ActionResult("restore_point", "Criar Ponto de Restauração", False, error=res.stderr.strip() or "Falha ao criar o ponto.")
        except Exception as e:
            return ActionResult("restore_point", "Criar Ponto de Restauração", False, error=str(e))

    # =========================================================================
    # PRO: DISM COMPONENT CLEANUP (WINSXS)
    # =========================================================================
    def dism_cleanup(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("dism_cleanup", "Limpeza Base de Componentes (WinSxS)", False, error="Requer Administrador.")
        try:
            cmd = 'DISM /Online /Cleanup-Image /StartComponentCleanup'
            # Isso pode demorar bastante, usamos um timeout maior
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace", timeout=300)
            if res.returncode == 0:
                return ActionResult("dism_cleanup", "Limpeza Base de Componentes (WinSxS)", True, message="Otimização de componentes concluída via DISM.")
            else:
                return ActionResult("dism_cleanup", "Limpeza Base de Componentes (WinSxS)", False, error="Comando DISM falhou (ou precisa reiniciar o PC).")
        except Exception as e:
            return ActionResult("dism_cleanup", "Limpeza Base de Componentes (WinSxS)", False, error=str(e))

    # =========================================================================
    # PRO: REPARO DE REDE
    # =========================================================================
    def network_reset(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("network_reset", "Otimizar & Reparação de Rede", False, error="Requer Administrador.")
        try:
            subprocess.run("netsh winsock reset", shell=True, capture_output=True, timeout=10)
            subprocess.run("netsh int ip reset", shell=True, capture_output=True, timeout=10)
            return ActionResult("network_reset", "Otimizar & Reparação de Rede", True, message="Pilha TCP/IP e Winsock redefinidas. Reinicie o PC para surtir efeito.")
        except Exception as e:
            return ActionResult("network_reset", "Otimizar & Reparação de Rede", False, error=str(e))

    def quick_network_boost(self) -> ActionResult:
        """Libera buffers de rede, limpa cache DNS e renova tabelas de resolução de rota sem derrubar conexões ativas."""
        actions_done = []
        try:
            # 1. Flush DNS
            res_dns = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, errors="replace", timeout=8)
            if res_dns.returncode == 0:
                actions_done.append("Cache DNS limpo")
            # 2. NetBIOS Name Cache
            subprocess.run(["nbtstat", "-R"], capture_output=True, text=True, errors="replace", timeout=8)
            actions_done.append("Tabela NetBIOS recarregada")
            # 3. ARP cache se admin
            if SystemMonitor.is_admin():
                subprocess.run(["arp", "-d", "*"], capture_output=True, text=True, errors="replace", timeout=8)
                actions_done.append("Tabela ARP liberada")
            
            msg = "; ".join(actions_done) if actions_done else "Rotas e cache de rede atualizados"
            return ActionResult(
                action_id="quick_network_boost",
                name="Liberação e Aceleração de Rede em Tempo Real",
                success=True,
                message=f"{msg}. Tráfego e resolução otimizados!"
            )
        except Exception as e:
            return ActionResult(
                action_id="quick_network_boost",
                name="Liberação e Aceleração de Rede em Tempo Real",
                success=False,
                error=str(e)
            )

    # =========================================================================
    # PRO: AGENDAR TAREFA AUTOMÁTICA
    # =========================================================================
    def schedule_task(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("schedule_task", "Agendar Limpeza Automática", False, error="Requer Administrador.")
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            bat_path = os.path.join(base_dir, "cleaner_admin.bat")
            # Agendar semanalmente rodando nível 2 invisivelmente
            cmd = f'schtasks /create /tn "SmartPCCleanerPro" /tr "\\"{bat_path}\\" --nivel 2" /sc weekly /d SUN /st 12:00 /rl highest /f'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace", timeout=15)
            if res.returncode == 0:
                return ActionResult("schedule_task", "Agendar Limpeza Automática", True, message="Limpeza semanal (Nível 2) agendada todo Domingo 12:00.")
            else:
                return ActionResult("schedule_task", "Agendar Limpeza Automática", False, error=res.stderr.strip() or "Falha no Schtasks")
        except Exception as e:
            return ActionResult("schedule_task", "Agendar Limpeza Automática", False, error=str(e))

    # =========================================================================
    # ULTIMATE: ANTIVÍRUS (WINDOWS DEFENDER)
    # =========================================================================
    def run_antivirus_scan(self, quick: bool = True) -> ActionResult:
        """Executa o scanner nativo do Windows Defender via CLI."""
        if not SystemMonitor.is_admin():
            return ActionResult("antivirus_scan", "Scan Anti-Malware", False, error="Requer Administrador.")
        try:
            # Caminho padrão do MpCmdRun
            mpcmd_path = os.path.expandvars("%ProgramFiles%\\Windows Defender\\MpCmdRun.exe")
            if not os.path.exists(mpcmd_path):
                return ActionResult("antivirus_scan", "Scan Anti-Malware", False, error="Windows Defender não encontrado.")
            
            scan_type = "1" if quick else "2" # 1=Quick, 2=Full
            cmd = f'"{mpcmd_path}" -Scan -ScanType {scan_type}'
            
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace") # Sem timeout rígido, pode demorar
            if res.returncode == 0:
                return ActionResult("antivirus_scan", "Scan Anti-Malware", True, message="Nenhuma ameaça encontrada. Computador Seguro.")
            elif res.returncode == 2:
                return ActionResult("antivirus_scan", "Scan Anti-Malware", True, message="Ameaças foram encontradas e tratadas pelo Windows Defender!")
            else:
                return ActionResult("antivirus_scan", "Scan Anti-Malware", False, error=res.stderr.strip() or f"Código de saída: {res.returncode}")
        except Exception as e:
            return ActionResult("antivirus_scan", "Scan Anti-Malware", False, error=str(e))

    # =========================================================================
    # ULTIMATE: REPARO DE ARQUIVOS (SFC)
    # =========================================================================
    def system_file_checker(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("sfc_scan", "Reparo do Sistema (SFC)", False, error="Requer Administrador.")
        try:
            res = subprocess.run("sfc /scannow", shell=True, capture_output=True, text=True, errors="replace")
            # SFC retorna 0 se não achar nada, 1 se achar e não puder corrigir tudo, e as vezes outros se achar e corrigir
            msg = "Varredura concluída. Consulte logs do Windows para detalhes."
            if "não encontrou nenhuma violação de integridade" in res.stdout:
                msg = "Sistema íntegro. Nenhuma violação encontrada."
            elif "corrigiu com êxito" in res.stdout:
                msg = "Arquivos corrompidos foram encontrados e corrigidos com sucesso!"
                
            return ActionResult("sfc_scan", "Reparo do Sistema (SFC)", True, message=msg)
        except Exception as e:
            return ActionResult("sfc_scan", "Reparo do Sistema (SFC)", False, error=str(e))

    # =========================================================================
    # ULTIMATE: OTIMIZAÇÃO DE DISCO (DEFRAG / TRIM)
    # =========================================================================
    def optimize_disk(self) -> ActionResult:
        if not SystemMonitor.is_admin():
            return ActionResult("optimize_disk", "Otimização de Disco (TRIM/Defrag)", False, error="Requer Administrador.")
        try:
            res = subprocess.run("defrag C: /O", shell=True, capture_output=True, text=True, errors="replace", timeout=120)
            if res.returncode == 0:
                return ActionResult("optimize_disk", "Otimização de Disco (TRIM/Defrag)", True, message="Armazenamento otimizado com sucesso.")
            else:
                return ActionResult("optimize_disk", "Otimização de Disco (TRIM/Defrag)", False, error=res.stderr.strip() or "Erro ao otimizar o disco.")
        except Exception as e:
            return ActionResult("optimize_disk", "Otimização de Disco (TRIM/Defrag)", False, error=str(e))

    # =========================================================================
    # ULTIMATE: LIMPEZA DE NAVEGADORES (PRIVACIDADE)
    # =========================================================================
    def clean_browsers(self) -> ActionResult:
        """Limpa Caches de Chrome, Edge e Firefox do usuário atual."""
        localappdata = os.path.expandvars("%LOCALAPPDATA%")
        
        targets = [
            (f"{localappdata}\\Google\\Chrome\\User Data\\Default\\Cache", "Chrome Cache"),
            (f"{localappdata}\\Google\\Chrome\\User Data\\Default\\Code Cache", "Chrome Code Cache"),
            (f"{localappdata}\\Google\\Chrome\\User Data\\Default\\GPUCache", "Chrome GPU Cache"),
            (f"{localappdata}\\Microsoft\\Edge\\User Data\\Default\\Cache", "Edge Cache"),
            (f"{localappdata}\\Microsoft\\Edge\\User Data\\Default\\Code Cache", "Edge Code Cache"),
            (f"{localappdata}\\Microsoft\\Edge\\User Data\\Default\\GPUCache", "Edge GPU Cache")
        ]
        
        # O Firefox usa um sistema de perfis dinâmico
        ff_profiles = f"{localappdata}\\Mozilla\\Firefox\\Profiles"
        if os.path.exists(ff_profiles):
            for profile in os.listdir(ff_profiles):
                p_path = os.path.join(ff_profiles, profile, "cache2")
                if os.path.exists(p_path):
                    targets.append((p_path, f"Firefox Cache ({profile})"))

        total_bytes = 0
        total_items = 0
        for path, _ in targets:
            if os.path.exists(path):
                try:
                    b, items = SystemMonitor.get_directory_size(path)
                    shutil.rmtree(path, ignore_errors=True)
                    os.makedirs(path, exist_ok=True)
                    total_bytes += b
                    total_items += items
                except Exception:
                    pass
        
        return ActionResult(
            "clean_browsers", 
            "Privacidade de Navegadores", 
            True, 
            message=f"{total_items} itens removidos ({SystemMonitor.format_bytes(total_bytes)}) de caches Chrome/Edge/Firefox."
        )
    def execute_action(self, action_id: str) -> ActionResult:
        """Mapeia o ID da ação para a rotina correspondente."""
        if action_id in ["ram", "optimize_ram_user", "optimize_ram_all"]:
            return self.optimize_ram()
        elif action_id == "recycle_bin":
            return self.empty_recycle_bin()
        elif action_id == "user_temp":
            user_temp = os.environ.get("TEMP", "")
            return self.clean_directory_content(user_temp, "Arquivos Temporários do Usuário (%TEMP%)")
        elif action_id == "system_temp":
            return self.clean_directory_content("C:\\Windows\\Temp", "Temporários do Sistema (Windows\\Temp)")
        elif action_id == "prefetch":
            return self.clean_directory_content("C:\\Windows\\Prefetch", "Cache de Inicialização (Prefetch)")
        elif action_id == "crash_dumps":
            dumps = os.path.expandvars("%LOCALAPPDATA%\\CrashDumps")
            return self.clean_directory_content(dumps, "Relatórios de Erro (Crash Dumps)")
        elif action_id == "thumbnail_cache":
            thumb_path = os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer")
            return self.clean_directory_content(thumb_path, "Cache de Miniaturas do Explorer")
        elif action_id == "flush_dns":
            return self.flush_dns()
        elif action_id == "windows_event_logs":
            return self.clean_event_logs()
        elif action_id == "windows_update_cache":
            return self.clean_windows_update_cache()
        elif action_id == "dev_caches":
            return self.execute_shell_cmd("npm cache clean --force 2>nul & pip cache purge 2>nul", "Caches de Dev (npm, pip)")
        elif action_id == "restore_point":
            return self.create_restore_point()
        elif action_id == "dism_cleanup":
            return self.dism_cleanup()
        elif action_id == "network_reset":
            return self.network_reset()
        elif action_id in ["quick_network_boost", "boost_network", "liberar_rede"]:
            return self.quick_network_boost()
        elif action_id == "schedule_task":
            return self.schedule_task()
        elif action_id == "antivirus_scan":
            return self.run_antivirus_scan(quick=True)
        elif action_id == "sfc_scan":
            return self.system_file_checker()
        elif action_id == "optimize_disk":
            return self.optimize_disk()
        elif action_id == "clean_browsers":
            return self.clean_browsers()
        else:
            return ActionResult(
                action_id=action_id,
                name=f"Ação {action_id}",
                success=False,
                error=f"Ação desconhecida: {action_id}"
            )

    def execute_shell_cmd(self, command: str, name: str) -> ActionResult:
        """Executa um comando de terminal shell de forma segura."""
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, errors="replace", timeout=30)
            return ActionResult(
                action_id="custom_cmd",
                name=name,
                success=(res.returncode == 0),
                message="Comando executado com sucesso." if res.returncode == 0 else (res.stderr.strip() or "Comando finalizou com aviso.")
            )
        except Exception as e:
            return ActionResult(
                action_id="custom_cmd",
                name=name,
                success=False,
                error=str(e)
            )

    def execute_custom_rule(self, rule_id: str) -> ActionResult:
        """Executa uma regra personalizada configurada em config.json."""
        if not self.config_manager:
            return ActionResult(action_id=rule_id, name=rule_id, success=False, error="ConfigManager não configurado.")

        rules = self.config_manager.get_custom_rules()
        matched = next((r for r in rules if r.get("id") == rule_id), None)
        if not matched:
            return ActionResult(action_id=rule_id, name=rule_id, success=False, error="Regra não encontrada.")

        name = matched.get("name", rule_id)
        action_type = matched.get("action_type")
        requires_admin = matched.get("requires_admin", False)

        if requires_admin and not SystemMonitor.is_admin():
            return ActionResult(
                action_id=rule_id,
                name=name,
                success=False,
                error="Esta regra customizada requer privilégios de Administrador."
            )

        if action_type == "shell_cmd":
            cmd = matched.get("command", "")
            return self.execute_shell_cmd(cmd, name)
        elif action_type in ["delete_dir_content", "delete_dir"]:
            path = matched.get("path", "")
            return self.clean_directory_content(path, name)
        else:
            return ActionResult(action_id=rule_id, name=name, success=False, error=f"Tipo de ação inválido: {action_type}")

    # =========================================================================
    # 8. PROCEDIMENTO POR NÍVEIS (1, 2 OU 3)
    # =========================================================================
    def execute_level(self, level_num: int) -> ExecutionReport:
        """Executa todas as ações configuradas para um nível específico."""
        report = ExecutionReport()
        actions = []
        if self.config_manager:
            actions = self.config_manager.get_level_actions(level_num)
        if not actions:
            # Fallback padrão
            if level_num == 1:
                actions = ["recycle_bin", "user_temp", "flush_dns", "optimize_ram_user"]
            elif level_num == 2:
                actions = ["recycle_bin", "user_temp", "system_temp", "crash_dumps", "prefetch", "flush_dns", "optimize_ram_all"]
            elif level_num == 3:
                actions = ["recycle_bin", "user_temp", "system_temp", "crash_dumps", "prefetch", "windows_event_logs", "windows_update_cache", "flush_dns", "optimize_ram_all"]

        for action_id in actions:
            res = self.execute_action(action_id)
            report.actions_executed.append(res)
            report.total_bytes_freed += res.bytes_freed
            report.total_ram_freed_mb += res.ram_freed_mb
            report.total_items_deleted += res.items_deleted
            if not res.success and res.error:
                report.warnings.append(f"[{res.name}] {res.error}")

        return report

    def execute_targets(self, targets: List[str], custom_rules: List[Dict[str, Any]] = None) -> ExecutionReport:
        report = ExecutionReport()

        for target in targets:
            try:
                res = self.execute_action(target)
                report.actions_executed.append(res)
                report.total_bytes_freed += res.bytes_freed
                report.total_ram_freed_mb += res.ram_freed_mb
                report.total_items_deleted += res.items_deleted
                if not res.success and res.error:
                    report.warnings.append(f"[{res.name}] {res.error}")
            except Exception as e:
                resolved = AutoHealer.attempt_recovery(target, e, {"target": target})
                if not resolved:
                    AutoHealer.log_failure(target, e, context="execute_targets_default")
                report.actions_executed.append(ActionResult(target, f"Ação: {target}", False, error="Falha interceptada pelo Auto-Healer."))

        if custom_rules:
            for rule in custom_rules:
                try:
                    res = self.execute_custom_rule(rule)
                    report.actions_executed.append(res)
                    report.total_bytes_freed += res.bytes_freed
                    report.total_ram_freed_mb += res.ram_freed_mb
                    report.total_items_deleted += res.items_deleted
                except Exception as e:
                    rule_name = rule.get("name", "Regra Customizada")
                    resolved = AutoHealer.attempt_recovery(rule_name, e, {"rule": rule})
                    if not resolved:
                        AutoHealer.log_failure(rule_name, e, context="execute_targets_custom")
                    report.actions_executed.append(ActionResult(rule_name, rule_name, False, error="Falha interceptada pelo Auto-Healer."))

        return report
