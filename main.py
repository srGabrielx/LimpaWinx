"""
Smart PC Cleaner — Ponto de Entrada Principal (CLI e Modo Interativo).
Suporta comandos por argumentos de linha de comando ou console interativo contínuo.
"""

import os
import sys
import argparse

# Configurar encoding UTF-8 no Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Adicionar pasta raiz ao path do Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cleaner.semantic_parser import SemanticParser
from cleaner.config_manager import ConfigManager
from cleaner.system_monitor import SystemMonitor
from cleaner.cleaner_engine import CleanerEngine
from cleaner.ui_terminal import TerminalUI


try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style as PStyle
    from rich.console import Console
    console = Console()
except ImportError:
    pass

def run_interactive_loop(parser: SemanticParser, engine: CleanerEngine, config_mgr: ConfigManager):
    """Executa o loop interativo REPL com suporte a Auto-completar inteligente."""
    TerminalUI.print_banner()
    
    with console.status("[bold green]Coletando métricas de hardware...[/]"):
        diag = SystemMonitor.get_full_diagnostics()
    TerminalUI.print_diagnostics(diag)

    console.print("[dim]Digite comandos como 'limpar ram', 'nivel 2', 'status', 'ajuda' ou 'sair'.[/]\n")

    # Configurar auto-completar
    commands = [
        "limpar ram", "limpar lixeira", "limpar pc e ram", "limpar navegadores",
        "nivel 1", "nivel 2", "nivel 3", "limpeza profunda",
        "status", "diagnostico", "regras", "config", "ajuda", "sair",
        "agendar limpeza", "reparar rede", "liberar rede", "limpar winsxs", "restaurar",
        "verificar virus", "scan", "reparar sistema", "sfc", "otimizar disco", "defrag", "intermediador"
    ]
    completer = WordCompleter(commands, ignore_case=True, match_middle=True)
    style = PStyle.from_dict({'prompt': 'ansicyan bold'})
    session = PromptSession(completer=completer, style=style)

    while True:
        try:
            # Prompt customizado
            user_input = session.prompt('PC-Cleaner ❯ ').strip()

            if not user_input:
                continue

            result = parser.parse(user_input)

            # 1. Encerramento
            if result.intent == "exit":
                console.print("\n[bold green]Encerrando o Smart PC Cleaner PRO. Até logo![/]\n")
                break

            # 2. Ajuda
            elif result.intent == "help":
                TerminalUI.print_help()

            # 3. Diagnóstico / Status
            elif result.intent == "status":
                with console.status("[bold cyan]Coletando telemetria em tempo real...[/]"):
                    current_diag = SystemMonitor.get_full_diagnostics()
                TerminalUI.print_diagnostics(current_diag)

            # 4. Configurações / Regras
            elif result.intent == "config":
                rules = config_mgr.get_custom_rules()
                TerminalUI.print_rules(rules)

            # 5. Execução por Nível (1/3, 2/3, 3/3)
            elif result.intent == "level":
                level = result.level or 1
                level_info = config_mgr.config.get("levels", {}).get(str(level), {})
                level_name = level_info.get("name", f"Nível {level}")

                console.print(f"\n[bold yellow]► {result.explanation}[/]")

                if level == 3 and config_mgr.config.get("safety", {}).get("ask_confirmation_for_level_3", True):
                    confirm = session.prompt('Atenção: O Nível 3 executa manutenção profunda (Logs/WinSxS). Deseja continuar? [S/N]: ').strip().lower()
                    if confirm not in ["s", "sim", "y", "yes"]:
                        console.print("[dim]Operação cancelada pelo usuário.[/]\n")
                        continue

                with console.status(f"[bold cyan]Executando {level_name}... Isso pode levar alguns minutos.[/]", spinner="dots"):
                    report = engine.execute_level(level)
                TerminalUI.print_execution_report(report, f"RESULTADO — {level_name.upper()}")

            # 6. Limpeza por Alvos Específicos
            elif result.intent == "clean":
                console.print(f"\n[bold yellow]► {result.explanation}[/]")
                targets = result.targets
                custom_rules = result.custom_rules

                if not targets and not custom_rules:
                    console.print("[bold red]Nenhum alvo específico foi identificado.[/]\n")
                    continue

                with console.status("[bold cyan]Otimizando os alvos solicitados...[/]", spinner="arc"):
                    report = engine.execute_targets(targets, custom_rules)
                TerminalUI.print_execution_report(report, "RESULTADO DA LIMPEZA PERSONALIZADA")

            # 7. Comando Desconhecido
            else:
                console.print(f"\n[bold red]✗ {result.explanation}[/]\n")

        except KeyboardInterrupt:
            console.print("\n\n[bold green]Saindo...[/]\n")
            break
        except Exception as e:
            console.print(f"\n[bold red on white] ERRO INTERNO [/] {str(e)}\n")


def main():
    config_mgr = ConfigManager()
    custom_rules = config_mgr.get_custom_rules()
    parser = SemanticParser(custom_rules=custom_rules)
    engine = CleanerEngine(config_manager=config_mgr)

    # Suporte a argumentos CLI diretos
    arg_parser = argparse.ArgumentParser(description="Smart PC Cleaner — Ferramenta Inteligente de Limpeza Sem IA")
    arg_parser.add_argument("query", nargs="*", help="Comando em linguagem natural (ex: 'limpar ram e lixeira', 'nivel 2')")
    arg_parser.add_argument("--nivel", "-n", type=int, choices=[1, 2, 3], help="Executa diretamente o Nível 1, 2 ou 3")
    arg_parser.add_argument("--status", "-s", action="store_true", help="Exibe o status do sistema e sai")
    arg_parser.add_argument("--regras", "-r", action="store_true", help="Exibe as regras customizadas e sai")
    arg_parser.add_argument("--daemon", action="store_true", help="Inicia o Escudo Residente em segundo plano")

    args = arg_parser.parse_args()

    # Se chamado com --daemon
    if args.daemon:
        try:
            from cleaner.resident_shield import ResidentShield
            shield = ResidentShield()
            shield.start()
        except ImportError:
            print("Bibliotecas do Escudo não instaladas.")
        return

    # Se passou --status
    if args.status:
        TerminalUI.print_banner()
        diag = SystemMonitor.get_full_diagnostics()
        TerminalUI.print_diagnostics(diag)
        return

    # Se passou --regras
    if args.regras:
        TerminalUI.print_banner()
        rules = config_mgr.get_custom_rules()
        TerminalUI.print_rules(rules)
        return

    # Se passou --nivel X
    if args.nivel:
        TerminalUI.print_banner()
        level_name = config_mgr.config.get("levels", {}).get(str(args.nivel), {}).get("name", f"Nível {args.nivel}")
        print(f"{Colors.CYAN}Executando {level_name}...{Colors.RESET}")
        report = engine.execute_level(args.nivel)
        TerminalUI.print_execution_report(report, f"RESULTADO — {level_name.upper()}")
        return

    # Se passou uma query como argumento: ex: python main.py "limpar lixeira e ram"
    if args.query:
        raw_cmd = " ".join(args.query)
        TerminalUI.print_banner()
        result = parser.parse(raw_cmd)
        console.print(f"[yellow]► Comando recebido: '{raw_cmd}'[/]")
        console.print(f"[dim]► Interpretação semântica: {result.explanation}[/]\n")

        if result.intent == "level":
            report = engine.execute_level(result.level or 1)
            TerminalUI.print_execution_report(report, f"RESULTADO — NÍVEL {result.level}")
        elif result.intent == "clean":
            report = engine.execute_targets(result.targets, result.custom_rules)
            TerminalUI.print_execution_report(report, "RESULTADO DA LIMPEZA")
        elif result.intent == "status":
            diag = SystemMonitor.get_full_diagnostics()
            TerminalUI.print_diagnostics(diag)
        elif result.intent == "help":
            TerminalUI.print_help()
        else:
            print(f"{Colors.RED}✗ {result.explanation}{Colors.RESET}")
        return

    # Caso contrário, entra no modo interativo contínuo
    run_interactive_loop(parser, engine, config_mgr)


if __name__ == "__main__":
    main()
