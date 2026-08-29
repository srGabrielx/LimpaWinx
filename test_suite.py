"""
Suíte de Testes Automatizados para o Smart PC Cleaner.
Valida o motor semântico, diagnóstico de hardware e chamadas Win32 nativas.
"""

import sys
import os

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cleaner.semantic_parser import SemanticParser, normalize_text, similarity_ratio
from cleaner.config_manager import ConfigManager
from cleaner.system_monitor import SystemMonitor
from cleaner.cleaner_engine import CleanerEngine


def test_semantic_normalization():
    print("[TEST] 1. Testando Normalização e Similaridade...")
    assert normalize_text("Limpar Memória RAM & Lixeira!") == "limpar memoria ram lixeira"
    assert normalize_text("NÍVEL 2 - Procedimento") == "nivel 2 - procedimento"
    assert normalize_text("1/3") == "1/3"
    
    sim = similarity_ratio("esvasiar", "esvaziar")
    assert sim >= 0.85, f"Taxa de similaridade baixa: {sim}"
    print("  ✓ Normalização e Levenshtein validados com sucesso.")


def test_semantic_parser():
    print("[TEST] 2. Testando Reconhecimento Semântico e Palavras-chave...")
    config_mgr = ConfigManager()
    parser = SemanticParser(custom_rules=config_mgr.get_custom_rules())

    # Caso 1: Alvos múltiplos
    res1 = parser.parse("limpar ram e lixeira")
    assert res1.intent == "clean", f"Esperado 'clean', obtido: {res1.intent}"
    assert "ram" in res1.targets, f"Faltou 'ram' em: {res1.targets}"
    assert "recycle_bin" in res1.targets, f"Faltou 'recycle_bin' em: {res1.targets}"
    print("  ✓ 'limpar ram e lixeira' -> Identificou RAM e Lixeira.")

    # Caso 2: Nível 1
    res2 = parser.parse("executar limpeza nivel 1")
    assert res2.intent == "level" and res2.level == 1
    print("  ✓ 'executar limpeza nivel 1' -> Identificou Nível 1/3.")

    # Caso 3: Procedimento 2/3
    res3 = parser.parse("procedimento 2/3")
    assert res3.intent == "level" and res3.level == 2
    print("  ✓ 'procedimento 2/3' -> Identificou Nível 2/3.")

    # Caso 4: Nível 3 profundo
    res4 = parser.parse("fazer uma faxina nivel 3 completa")
    assert res4.intent == "level" and res4.level == 3
    print("  ✓ 'fazer uma faxina nivel 3 completa' -> Identificou Nível 3/3.")

    # Caso 5: Tolerância a erro de digitação (Fuzzy Match)
    res5 = parser.parse("esvasiar lxeira e temporarios")
    assert "recycle_bin" in res5.targets, f"Erro de digitação não tolerado: {res5.targets}"
    assert "user_temp" in res5.targets
    print("  ✓ 'esvasiar lxeira e temporarios' (com erros de digitação) -> Identificou Lixeira e Temp.")

    # Caso 6: Regras customizadas
    res6 = parser.parse("limpar cache do discord e chrome")
    assert "discord_cache" in res6.custom_rules
    assert "chrome_cache" in res6.custom_rules
    print("  ✓ 'limpar cache do discord e chrome' -> Identificou regras customizadas.")


def test_system_monitor():
    print("[TEST] 3. Testando Telemetria do Sistema e Win32 API...")
    diag = SystemMonitor.get_full_diagnostics()
    mem = diag["memory"]
    disk = diag["disk"]

    assert mem["total_gb"] > 0, "Memória RAM total inválida"
    assert mem["percent_used"] > 0, "Percentual de RAM inválido"
    assert disk["total_gb"] > 0, "Espaço em disco inválido"
    print(f"  ✓ Memória detectada: {mem['used_gb']} GB usados de {mem['total_gb']} GB ({mem['percent_used']}%)")
    print(f"  ✓ Disco C: detectado: {disk['free_gb']} GB livres de {disk['total_gb']} GB")


def test_cleaner_engine_ram():
    print("[TEST] 4. Testando Otimização Real de RAM (Working Set Trim Win32)...")
    config_mgr = ConfigManager()
    engine = CleanerEngine(config_manager=config_mgr)

    act_res = engine.optimize_ram()
    assert act_res.success, f"Falha na otimização de RAM: {act_res.error}"
    assert act_res.items_deleted > 0, "Nenhum processo foi processado na otimização de RAM"
    print(f"  ✓ Otimização de RAM concluída: {act_res.message}")


def test_cleaner_engine_network():
    print("[TEST] 5. Testando Liberação de Recursos de Rede (Quick Network Boost)...")
    config_mgr = ConfigManager()
    engine = CleanerEngine(config_manager=config_mgr)

    act_res = engine.quick_network_boost()
    assert act_res.success, f"Falha na otimização de rede: {act_res.error}"
    print(f"  ✓ Otimização de rede concluída: {act_res.message}")


def run_all_tests():
    print("=" * 60)
    print("INICIANDO SUÍTE DE TESTES DO SMART PC CLEANER PRO")
    print("=" * 60)
    test_semantic_normalization()
    test_semantic_parser()
    test_system_monitor()
    test_cleaner_engine_ram()
    test_cleaner_engine_network()
    print("=" * 60)
    print("TODOS OS TESTES FORAM EXECUTADOS COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
