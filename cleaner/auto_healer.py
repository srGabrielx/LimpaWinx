import os
import json
import traceback
import subprocess
from datetime import datetime
from functools import wraps
from typing import Any, Callable

# Configura o diretório de logs
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
CRASH_LOG_FILE = os.path.join(LOG_DIR, "crash_reports.log")

class AutoHealer:
    """Módulo de identificação, registro e auto-solução de falhas e críticas."""

    @staticmethod
    def log_failure(action_name: str, error: Exception, context: str = "") -> None:
        """Registra a falha no arquivo de log de forma não obstrutiva."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trace = traceback.format_exc()
        
        log_entry = (
            f"\n{'='*50}\n"
            f"[{timestamp}] CRITICAL FAILURE in action: '{action_name}'\n"
            f"Context: {context}\n"
            f"Error Type: {type(error).__name__}\n"
            f"Message: {str(error)}\n"
            f"Traceback:\n{trace}\n"
            f"{'='*50}\n"
        )
        
        try:
            with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass # Se até o logger falhar, ignoramos silenciosamente para não travar o app

    @staticmethod
    def attempt_recovery(action_name: str, error: Exception, kwargs: dict) -> bool:
        """
        Tenta corrigir o erro automaticamente.
        Retorna True se resolvido, False se não foi possível resolver.
        """
        if isinstance(error, PermissionError):
            # Exemplo de auto-correção: Tentar remover a flag Read-Only se for arquivo
            path = kwargs.get("path", "")
            if path and os.path.isfile(path):
                try:
                    # Tenta remover o atributo Read-Only no Windows via attrib
                    subprocess.run(f'attrib -R "{path}"', shell=True, capture_output=True, timeout=2)
                    os.remove(path)
                    return True # Sucesso ao forçar
                except Exception:
                    pass
            return False

        if isinstance(error, OSError):
            # Erro 32 (Arquivo em uso por outro processo)
            if error.winerror == 32:
                # Não tentaremos matar o processo dono do arquivo pois pode desestabilizar o SO.
                # A resolução segura é apenas ignorar o arquivo e logar.
                return False
                
        return False

def with_auto_healing(action_name: str):
    """
    Decorador para envolver métodos críticos. 
    Se falhar, tenta auto-correção, senão loga silenciosamente e continua.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Tenta auto-correção
                resolved = AutoHealer.attempt_recovery(action_name, e, kwargs)
                if not resolved:
                    # Deixa material de log para avanços futuros
                    AutoHealer.log_failure(action_name, e, context=str(kwargs))
                
                # Se a função precisa retornar ActionResult, retornamos um genérico de falha.
                # O ideal é que o motor trate isso. Retornamos None e o motor resolve, 
                # ou retornamos a exceção.
                raise e # O decorador apenas loga e tenta curar, mas se falhar, repassa o erro 
                        # para o cleaner_engine envelopar no ActionResult
        return wrapper
    return decorator
