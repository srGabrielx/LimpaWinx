"""
Gerenciador de Configurações e Perfis Customizados (config.json).
Carrega, valida, persiste e adiciona novas regras de limpeza customizadas.
"""

import os
import json
from typing import Dict, Any, List, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "app_name": "Smart PC Cleaner",
    "safety": {
        "ask_confirmation_for_level_3": True,
        "ignore_extensions": [".lock", ".pid", ".sock", ".db-wal", ".git"],
        "ignore_folders": ["System Volume Information", "$Recycle.Bin", "Recovery"]
    },
    "levels": {
        "1": {
            "name": "Nível 1 — Básico / Seguro (1/3)",
            "description": "Limpeza rápida de temporários de usuário, lixeira, cache DNS e otimização leve de RAM.",
            "requires_admin": False,
            "actions": [
                "recycle_bin",
                "user_temp",
                "flush_dns",
                "optimize_ram_user"
            ]
        },
        "2": {
            "name": "Nível 2 — Otimização de Performance (2/3)",
            "description": "Inclui Nível 1 + arquivos temporários do sistema, crash dumps, prefetch e liberação profunda de RAM.",
            "requires_admin": False,
            "actions": [
                "recycle_bin",
                "user_temp",
                "system_temp",
                "crash_dumps",
                "thumbnail_cache",
                "prefetch",
                "flush_dns",
                "optimize_ram_all"
            ]
        },
        "3": {
            "name": "Nível 3 — Limpeza Profunda & Manutenção (3/3)",
            "description": "Inclui Nível 2 + logs de eventos do Windows, cache do Windows Update e caches de desenvolvimento.",
            "requires_admin": True,
            "actions": [
                "recycle_bin",
                "user_temp",
                "system_temp",
                "crash_dumps",
                "thumbnail_cache",
                "prefetch",
                "windows_event_logs",
                "windows_update_cache",
                "dev_caches",
                "flush_dns",
                "optimize_ram_all"
            ]
        }
    },
    "custom_rules": [
        {
            "id": "dev_npm_pip",
            "name": "Limpar caches de desenvolvimento (npm, pip)",
            "keywords": ["npm", "pip", "node_modules", "devcache", "pacotes"],
            "action_type": "shell_cmd",
            "command": "npm cache clean --force 2>nul & pip cache purge 2>nul",
            "requires_admin": False,
            "enabled": True
        },
        {
            "id": "discord_cache",
            "name": "Cache do Discord",
            "keywords": ["discord", "chat cache"],
            "action_type": "delete_dir_content",
            "path": "%APPDATA%\\discord\\Cache",
            "requires_admin": False,
            "enabled": True
        },
        {
            "id": "chrome_cache",
            "name": "Cache do Google Chrome",
            "keywords": ["chrome", "navegador", "browser"],
            "action_type": "delete_dir_content",
            "path": "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache",
            "requires_admin": False,
            "enabled": True
        },
        {
            "id": "edge_cache",
            "name": "Cache do Microsoft Edge",
            "keywords": ["edge", "msedge"],
            "action_type": "delete_dir_content",
            "path": "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Cache",
            "requires_admin": False,
            "enabled": True
        }
    ]
}


class ConfigManager:
    """Gerencia o arquivo de configuração e regras customizadas."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Carrega as configurações a partir do JSON ou grava as configurações padrão."""
        if not os.path.exists(self.config_path):
            self.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save_config(self, data: Optional[Dict[str, Any]] = None) -> bool:
        """Salva os dados de configuração atuais no arquivo config.json."""
        if data is not None:
            self.config = data
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_level_actions(self, level_num: int) -> List[str]:
        """Retorna a lista de ações correspondente a um nível (1, 2 ou 3)."""
        level_str = str(level_num)
        level_data = self.config.get("levels", {}).get(level_str, {})
        return level_data.get("actions", [])

    def get_custom_rules(self) -> List[Dict[str, Any]]:
        """Retorna a lista de regras customizadas ativas."""
        return self.config.get("custom_rules", [])

    def add_custom_rule(self, rule_id: str, name: str, keywords: List[str], action_type: str, target: str, requires_admin: bool = False) -> bool:
        """Adiciona uma nova regra customizada."""
        custom_rules = self.config.get("custom_rules", [])
        # Remover se já existir com o mesmo id
        custom_rules = [r for r in custom_rules if r.get("id") != rule_id]

        new_rule = {
            "id": rule_id,
            "name": name,
            "keywords": keywords,
            "action_type": action_type,
            "requires_admin": requires_admin,
            "enabled": True
        }
        if action_type == "shell_cmd":
            new_rule["command"] = target
        else:
            new_rule["path"] = target

        custom_rules.append(new_rule)
        self.config["custom_rules"] = custom_rules
        return self.save_config()
