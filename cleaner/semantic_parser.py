"""
Motor Semântico Local para Processamento de Linguagem Natural e Palavras-chave.
Não utiliza IA externa, operando inteiramente com normalização semântica,
lematização de sinônimos, n-grams e distância de Levenshtein (Fuzzy Matching).
"""

import re
import unicodedata
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field


def normalize_text(text: str) -> str:
    """Remove acentuação, caracteres especiais e converte para minúsculas."""
    if not text:
        return ""
    # Decomposição Unicode para remover diacríticos (á -> a, ç -> c, etc.)
    nfkd = unicodedata.normalize('NFKD', text)
    without_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Limpar pontuação e caracteres não alfanuméricos exceto barras e hífens
    cleaned = re.sub(r'[^a-zA-Z0-9/\s\-_]', ' ', without_accents)
    # Reduzir múltiplos espaços
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calcula a distância de edição entre duas strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """Calcula a taxa de similaridade (0.0 a 1.0) entre duas strings."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    distance = levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)


@dataclass
class ParseResult:
    original_query: str
    normalized_query: str
    intent: str  # 'clean', 'level', 'status', 'config', 'help', 'exit', 'unknown'
    level: Optional[int] = None  # 1, 2, 3
    targets: List[str] = field(default_factory=list)
    custom_rules: List[str] = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""


class SemanticParser:
    """Analisador semântico de comandos locais baseado em regras e palavras-chave."""

    # Dicionário de sinônimos e palavras-chave para intenções
    INTENT_KEYWORDS = {
        "status": ["status", "diagnostico", "info", "informacao", "espaco", "saude", "como esta", "memoria livre", "disco", "analisar", "ver"],
        "help": ["ajuda", "help", "socorro", "comandos", "manual", "como usar", "duvidas", "?"],
        "config": ["config", "configuracao", "configurar", "regras", "customizar", "personalizar"],
        "exit": ["sair", "exit", "quit", "q", "fechar", "encerrar", "tchau", "fim"],
        "clean": ["limpar", "limpeza", "esvaziar", "apagar", "otimizar", "otimizacao", "liberar", "liberacao", "remover", "faxina", "executar", "rodar", "clean", "purge"]
    }

    # Reconhecimento de níveis de procedimento
    LEVEL_PATTERNS = [
        (1, ["nivel 1", "procedimento 1", "fase 1", "etapa 1", "1/3", "1 3", "basico", "basica", "leve", "rapida", "seguro", "segura"]),
        (2, ["nivel 2", "procedimento 2", "fase 2", "etapa 2", "2/3", "2 3", "moderado", "moderada", "medio", "media", "intermediario", "intermediaria", "performance"]),
        (3, ["nivel 3", "procedimento 3", "fase 3", "etapa 3", "3/3", "3 3", "profundo", "profunda", "pesado", "pesada", "completo", "completa", "avancado", "avancada", "full", "total"])
    ]

    # Mapeamento de alvos específicos
    TARGET_SYNONYMS = {
        "ram": ["ram", "memoria", "working set", "processos", "gargalo", "travamento", "consumo"],
        "recycle_bin": ["lixeira", "lixo", "recycle", "trash", "cesto"],
        "user_temp": ["temp", "temporario", "temporarios", "cache", "arquivos temporarios", "appdata temp"],
        "system_temp": ["system temp", "temp sistema", "windows temp", "temporarios sistema"],
        "prefetch": ["prefetch", "boot", "inicializacao", "cache prefetch"],
        "crash_dumps": ["crash dump", "crash dumps", "dumps", "relatorios de erro", "erros"],
        "thumbnail_cache": ["miniaturas", "thumbnails", "cache de imagens", "thumbcache"],
        "flush_dns": ["dns", "cache dns", "ipconfig", "rede", "conexao"],
        "windows_event_logs": ["logs", "eventos", "log de eventos", "wevtutil", "historico do windows"],
        "windows_update_cache": ["windows update", "update cache", "softwaredistribution", "atualizacoes"],
        "all_pc": ["pc", "computador", "notebook", "maquina", "sistema", "geral", "tudo", "disco", "hd", "ssd"],
        # Novos recursos PRO
        "restore_point": ["restaurar", "ponto de restauracao", "restore point", "backup"],
        "dism_cleanup": ["winsxs", "dism", "componentes", "component store", "limpeza profunda de disco"],
        "network_reset": ["reparar rede", "winsock", "resetar rede", "tcp ip"],
        "quick_network_boost": ["liberar rede", "acelerar rede", "otimizar conexao", "boost rede", "limpar conexao", "intermediador rede"],
        "schedule_task": ["agendar", "cron", "automatizar", "tarefa agendada", "toda semana"],
        # Novos recursos ULTIMATE
        "antivirus_scan": ["antivirus", "scan", "virus", "malware", "defender", "verificar virus"],
        "sfc_scan": ["sfc", "reparar sistema", "arquivos corrompidos", "integridade", "scannow"],
        "optimize_disk": ["defrag", "desfragmentar", "trim", "ssd", "otimizar disco"],
        "clean_browsers": ["navegadores", "browser", "chrome", "edge", "firefox", "privacidade"]
    }

    def __init__(self, custom_rules: Optional[List[Dict[str, Any]]] = None):
        self.custom_rules = custom_rules or []

    def update_custom_rules(self, rules: List[Dict[str, Any]]) -> None:
        """Atualiza a lista de regras customizadas para o parser."""
        self.custom_rules = rules

    def _fuzzy_match(self, word: str, candidates: List[str], threshold: float = 0.80) -> Optional[str]:
        """Procura o candidato mais próximo usando distância de Levenshtein."""
        best_match = None
        best_score = 0.0
        for candidate in candidates:
            # Se for match exato
            if word == candidate:
                return candidate
            # Similaridade
            score = similarity_ratio(word, candidate)
            if score >= threshold and score > best_score:
                best_score = score
                best_match = candidate
        return best_match

    def parse(self, raw_input: str) -> ParseResult:
        """Processa a entrada do usuário e extrai a intenção, nível e alvos."""
        normalized = normalize_text(raw_input)
        if not normalized:
            return ParseResult(
                original_query=raw_input,
                normalized_query="",
                intent="empty",
                confidence=1.0,
                explanation="Nenhum comando digitado."
            )

        words = normalized.split()

        # 1. Checar intenções diretas simples
        if normalized in ["sair", "exit", "quit", "q"]:
            return ParseResult(raw_input, normalized, "exit", confidence=1.0, explanation="Encerrar o aplicativo.")
        if normalized in ["ajuda", "help", "comandos", "?"]:
            return ParseResult(raw_input, normalized, "help", confidence=1.0, explanation="Exibir menu de ajuda.")
        if normalized in ["config", "configuracao", "regras"]:
            return ParseResult(raw_input, normalized, "config", confidence=1.0, explanation="Exibir ou editar configurações.")
        if normalized in ["status", "diagnostico", "info", "espaco"]:
            return ParseResult(raw_input, normalized, "status", confidence=1.0, explanation="Exibir status do sistema e uso de recursos.")

        # 2. Verificar Nível de Procedimento (1, 2 ou 3)
        detected_level = None
        for lvl_num, phrases in self.LEVEL_PATTERNS:
            for phrase in phrases:
                if phrase in normalized:
                    detected_level = lvl_num
                    break
                # Suporte a "nivel 1", "nivel 2", "nivel 3" com regex
                if re.search(rf'\b(nivel|procedimento|fase)\s*{lvl_num}\b', normalized):
                    detected_level = lvl_num
                    break
                if f"{lvl_num}/3" in normalized or f"{lvl_num} de 3" in normalized:
                    detected_level = lvl_num
                    break
            if detected_level:
                break

        # 3. Detectar Alvos Específicos
        matched_targets = set()
        matched_custom_rules = set()

        for target_key, synonyms in self.TARGET_SYNONYMS.items():
            for syn in synonyms:
                # Se a frase do sinônimo estiver contida na query normalizada
                if syn in normalized:
                    matched_targets.add(target_key)
                    break
                # Se alguma palavra tiver match fuzzy (para palavras únicas como lixeira, ram, prefetch)
                if len(syn.split()) == 1:
                    for w in words:
                        if self._fuzzy_match(w, [syn], threshold=0.82):
                            matched_targets.add(target_key)
                            break

        # 4. Detectar Regras Customizadas
        for rule in self.custom_rules:
            if not rule.get("enabled", True):
                continue
            rule_id = rule.get("id")
            keywords = rule.get("keywords", [])
            for kw in keywords:
                norm_kw = normalize_text(kw)
                if norm_kw in normalized:
                    matched_custom_rules.add(rule_id)
                    break
                for w in words:
                    if self._fuzzy_match(w, [norm_kw], threshold=0.85):
                        matched_custom_rules.add(rule_id)
                        break

        # 5. Determinar a Intenção Principal
        # Se detectou nível explícito
        if detected_level is not None:
            explanation = f"Executar procedimento de limpeza Nível {detected_level}/3"
            if matched_targets:
                clean_targets = [t for t in matched_targets if t != "all_pc"]
                if clean_targets:
                    explanation += f" com foco adicional em: {', '.join(clean_targets)}"
            return ParseResult(
                original_query=raw_input,
                normalized_query=normalized,
                intent="level",
                level=detected_level,
                targets=list(matched_targets),
                custom_rules=list(matched_custom_rules),
                confidence=0.95,
                explanation=explanation
            )

        # Se detectou alvos de limpeza ou termos de limpeza
        is_clean_intent = False
        for clean_word in self.INTENT_KEYWORDS["clean"]:
            if clean_word in normalized:
                is_clean_intent = True
                break
            for w in words:
                if self._fuzzy_match(w, [clean_word], threshold=0.82):
                    is_clean_intent = True
                    break

        if is_clean_intent or matched_targets or matched_custom_rules:
            # Se disse apenas "limpar pc" ou "limpar computador" sem especificar nível, assume nível 1 ou geral
            if "all_pc" in matched_targets and len(matched_targets) == 1:
                return ParseResult(
                    original_query=raw_input,
                    normalized_query=normalized,
                    intent="level",
                    level=3,
                    targets=["user_temp", "recycle_bin", "flush_dns", "ram", "system_temp", "prefetch", "crash_dumps", "windows_update_cache", "clean_browsers", "optimize_disk"],
                    custom_rules=list(matched_custom_rules),
                    confidence=0.98,
                    explanation="Auto-Pilot (Limpeza Profunda Nível 3 + Otimizações) ativado por comando genérico."
                )

            # Targets específicos selecionados
            targets_list = list(matched_targets)
            if "all_pc" in targets_list:
                targets_list.remove("all_pc")

            exp_parts = []
            if targets_list:
                exp_parts.append(f"Alvos selecionados: {', '.join(targets_list)}")
            if matched_custom_rules:
                exp_parts.append(f"Regras customizadas: {', '.join(matched_custom_rules)}")

            return ParseResult(
                original_query=raw_input,
                normalized_query=normalized,
                intent="clean",
                level=None,
                targets=targets_list,
                custom_rules=list(matched_custom_rules),
                confidence=0.88,
                explanation="; ".join(exp_parts) if exp_parts else "Limpeza de alvos selecionados."
            )

        # Se detectou status / diagnóstico
        for st_word in self.INTENT_KEYWORDS["status"]:
            if st_word in normalized:
                return ParseResult(raw_input, normalized, "status", confidence=0.9, explanation="Exibir diagnóstico de recursos do sistema.")

        # Fallback / Desconhecido com sugestão
        return ParseResult(
            original_query=raw_input,
            normalized_query=normalized,
            intent="unknown",
            confidence=0.2,
            explanation=f"Comando não reconhecido: '{raw_input}'. Digite 'ajuda' para ver exemplos de comandos suportados."
        )
