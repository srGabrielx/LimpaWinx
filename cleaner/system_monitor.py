"""
Módulo de Diagnóstico e Monitoramento de Recursos do Windows.
Lê métricas reais de Memória RAM (via Win32 API), Espaço em Disco e Diretórios Temporários.
"""

import os
import sys
import ctypes
from ctypes import wintypes
from typing import Dict, Any, List, Optional
import shutil


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


class SystemMonitor:
    """Coleta informações de telemetria e estado do sistema operacional Windows."""

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo atual está executando com privilégios de Administrador."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def get_memory_info() -> Dict[str, Any]:
        """Obtém dados detalhados de consumo de memória física (RAM) via Windows API."""
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        success = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

        if not success:
            return {
                "total_mb": 0,
                "avail_mb": 0,
                "used_mb": 0,
                "percent_used": 0
            }

        total_bytes = stat.ullTotalPhys
        avail_bytes = stat.ullAvailPhys
        used_bytes = total_bytes - avail_bytes

        return {
            "total_bytes": total_bytes,
            "avail_bytes": avail_bytes,
            "used_bytes": used_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 1),
            "avail_mb": round(avail_bytes / (1024 * 1024), 1),
            "used_mb": round(used_bytes / (1024 * 1024), 1),
            "total_gb": round(total_bytes / (1024 * 1024 * 1024), 2),
            "avail_gb": round(avail_bytes / (1024 * 1024 * 1024), 2),
            "used_gb": round(used_bytes / (1024 * 1024 * 1024), 2),
            "percent_used": stat.dwMemoryLoad
        }

    @staticmethod
    def get_disk_info(drive_letter: str = "C:") -> Dict[str, Any]:
        """Obtém dados de espaço livre e total da partição informada."""
        drive_path = f"{drive_letter}\\" if not drive_letter.endswith("\\") else drive_letter
        try:
            usage = shutil.disk_usage(drive_path)
            return {
                "drive": drive_letter,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent_used": round((usage.used / usage.total) * 100, 1)
            }
        except Exception:
            return {
                "drive": drive_letter,
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "percent_used": 0
            }

    @staticmethod
    def get_recycle_bin_info() -> Dict[str, Any]:
        """Obtém quantidade de itens e tamanho total ocupado na Lixeira do Windows."""
        try:
            rb_info = SHQUERYRBINFO()
            rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
            res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(rb_info))
            if res == 0:  # S_OK
                size_bytes = rb_info.i64Size
                return {
                    "num_items": rb_info.i64NumItems,
                    "size_bytes": size_bytes,
                    "size_mb": round(size_bytes / (1024 * 1024), 2),
                    "size_str": SystemMonitor.format_bytes(size_bytes)
                }
        except Exception:
            pass

        return {
            "num_items": 0,
            "size_bytes": 0,
            "size_mb": 0.0,
            "size_str": "0 MB"
        }

    @staticmethod
    def get_directory_size(path: str, max_depth: int = 4) -> Tuple[int, int]:
        """Calcula o tamanho total em bytes e a quantidade de arquivos de um diretório de forma ultrarrápida usando os.scandir."""
        expanded_path = os.path.expandvars(path)
        if not os.path.exists(expanded_path):
            return 0, 0

        total_size = 0
        total_files = 0

        def _scan(current_path: str, depth: int):
            nonlocal total_size, total_files
            if depth > max_depth:
                return
            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        try:
                            if entry.is_file(follow_symlinks=False):
                                total_size += entry.stat(follow_symlinks=False).st_size
                                total_files += 1
                            elif entry.is_dir(follow_symlinks=False):
                                _scan(entry.path, depth + 1)
                        except (OSError, PermissionError):
                            continue
            except (OSError, PermissionError):
                pass

        _scan(expanded_path, 0)
        return total_size, total_files

    @staticmethod
    def format_bytes(size_in_bytes: int) -> str:
        """Formata bytes para representação legível (B, KB, MB, GB)."""
        if size_in_bytes < 1024:
            return f"{size_in_bytes} B"
        elif size_in_bytes < 1024 ** 2:
            return f"{size_in_bytes / 1024:.1f} KB"
        elif size_in_bytes < 1024 ** 3:
            return f"{size_in_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_in_bytes / (1024 ** 3):.2f} GB"

    @classmethod
    def get_full_diagnostics(cls) -> Dict[str, Any]:
        """Gera um relatório completo de diagnóstico do sistema."""
        user_temp = os.environ.get("TEMP", "")
        system_temp = "C:\\Windows\\Temp"
        prefetch = "C:\\Windows\\Prefetch"
        crash_dumps = os.path.expandvars("%LOCALAPPDATA%\\CrashDumps")

        size_user_temp, files_user_temp = cls.get_directory_size(user_temp) if user_temp else (0, 0)
        size_sys_temp, files_sys_temp = cls.get_directory_size(system_temp)
        size_prefetch, files_prefetch = cls.get_directory_size(prefetch)
        size_dumps, files_dumps = cls.get_directory_size(crash_dumps)
        rb_info = cls.get_recycle_bin_info()

        return {
            "is_admin": cls.is_admin(),
            "memory": cls.get_memory_info(),
            "disk": cls.get_disk_info("C:"),
            "recycle_bin": rb_info,
            "temp_stats": {
                "user_temp": {
                    "path": user_temp,
                    "size_bytes": size_user_temp,
                    "size_str": cls.format_bytes(size_user_temp),
                    "files": files_user_temp
                },
                "system_temp": {
                    "path": system_temp,
                    "size_bytes": size_sys_temp,
                    "size_str": cls.format_bytes(size_sys_temp),
                    "files": files_sys_temp
                },
                "prefetch": {
                    "path": prefetch,
                    "size_bytes": size_prefetch,
                    "size_str": cls.format_bytes(size_prefetch),
                    "files": files_prefetch
                },
                "crash_dumps": {
                    "path": crash_dumps,
                    "size_bytes": size_dumps,
                    "size_str": cls.format_bytes(size_dumps),
                    "files": files_dumps
                }
            }
        }
