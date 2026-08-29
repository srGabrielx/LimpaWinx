"""
Interface de Terminal PRO usando a biblioteca `rich`.
Painéis, tabelas dinâmicas, progress bars, e formatação premium corporativa.
"""

import sys
import time
from typing import Dict, Any, List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.live import Live
    from rich.align import Align
    from rich.style import Style
    from rich.layout import Layout
    from rich.tree import Tree
except ImportError:
    print("ERRO: Biblioteca 'rich' não encontrada. Execute: pip install rich")
    sys.exit(1)

from .system_monitor import SystemMonitor
from .cleaner_engine import ExecutionReport, ActionResult

console = Console()

class TerminalUI:
    """Renderizador de UI Premium com Rich."""

    @staticmethod
    def print_banner():
        banner_text = Text()
        banner_text.append(" S M A R T   P C   C L E A N E R   P R O \n", style="bold cyan")
        banner_text.append("Motor Semântico Local • Otimização Profunda • Limpeza em Níveis", style="dim white")
        
        panel = Panel(
            Align.center(banner_text), 
            border_style="cyan",
            padding=(1, 2)
        )
        console.print(panel)
        console.print()

    @staticmethod
    def print_diagnostics(diag: Dict[str, Any]):
        mem = diag.get("memory", {})
        disk = diag.get("disk", {})
        rb = diag.get("recycle_bin", {})
        temp = diag.get("temp_stats", {})
        is_admin = diag.get("is_admin", False)

        admin_badge = "[bold green]ADMINISTRADOR[/]" if is_admin else "[bold yellow]USUÁRIO NORMAL[/]"

        # Tabela Principal
        table = Table(show_header=False, border_style="dim", box=None)
        table.add_column("Key", style="bold cyan", width=25)
        table.add_column("Value")

        # RAM
        ram_pct = mem.get("percent_used", 0)
        ram_color = "green" if ram_pct < 70 else ("yellow" if ram_pct < 85 else "red")
        
        # Disco
        disk_pct = disk.get("percent_used", 0)
        disk_color = "green" if disk_pct < 75 else ("yellow" if disk_pct < 90 else "red")

        table.add_row("Privilégios de Execução", admin_badge)
        table.add_row("Memória RAM (Uso)", f"[{ram_color}]{mem.get('used_gb', 0)} GB / {mem.get('total_gb', 0)} GB ({ram_pct}%)[/]")
        table.add_row("Disco C: (Livre)", f"[{disk_color}]{disk.get('free_gb', 0)} GB livres de {disk.get('total_gb', 0)} GB[/]")
        table.add_row("Lixeira do Windows", f"{rb.get('num_items', 0)} itens detectados ({rb.get('size_str', '0 B')})")

        # Árvore de Pastas
        tree = Tree("[bold magenta]Diretórios Temporários Detectados[/]")
        
        t_user = temp.get('user_temp', {})
        tree.add(f"Temp do Usuário (%TEMP%) : [yellow]{t_user.get('size_str')}[/] ([dim]{t_user.get('files')} arquivos[/])")
        
        t_sys = temp.get('system_temp', {})
        tree.add(f"Temp do Windows (System) : [yellow]{t_sys.get('size_str')}[/] ([dim]{t_sys.get('files')} arquivos[/])")
        
        t_pref = temp.get('prefetch', {})
        tree.add(f"Cache Prefetch           : [yellow]{t_pref.get('size_str')}[/] ([dim]{t_pref.get('files')} arquivos[/])")
        
        t_dump = temp.get('crash_dumps', {})
        tree.add(f"Relatórios (Crash Dumps) : [yellow]{t_dump.get('size_str')}[/]")

        # Agrupar no Painel
        layout = Table.grid(padding=1)
        layout.add_row(table)
        layout.add_row("")
        layout.add_row(tree)

        console.print(Panel(layout, title="[bold cyan]Diagnóstico do Sistema[/]", border_style="cyan", padding=(1, 2)))
        console.print()

    @staticmethod
    def print_execution_report(report: ExecutionReport, title: str = "RELATÓRIO DE EXECUÇÃO"):
        table = Table(title=title, title_style="bold cyan", border_style="cyan", padding=(0, 1), show_lines=True)
        table.add_column("Status", justify="center", style="bold")
        table.add_column("Ação Realizada")
        table.add_column("Detalhes / Otimização")

        for act in report.actions_executed:
            if act.success:
                status = "[green]✔ OK[/]"
                msg = act.message or "Executado com sucesso."
                table.add_row(status, f"[bold]{act.name}[/]", f"[dim]{msg}[/]")
            else:
                status = "[red]✖ FALHA[/]"
                table.add_row(status, f"[bold]{act.name}[/]", f"[red]Erro: {act.error}[/]")

        # Rodapé de totais
        console.print(table)
        
        summary = Table.grid(padding=(0, 2))
        summary.add_row("[bold]Total Liberado em Disco:[/]", f"[bold green]{SystemMonitor.format_bytes(report.total_bytes_freed)}[/]")
        if report.total_ram_freed_mb > 0:
            summary.add_row("[bold]Memória RAM Liberada:[/]", f"[bold green]~{report.total_ram_freed_mb:.1f} MB[/]")
        summary.add_row("[bold]Total de Itens Limpos:[/]", f"[cyan]{report.total_items_deleted}[/]")
        
        console.print(Panel(summary, border_style="green", title="[bold green]Resumo de Otimização[/]"))
        console.print()

    @staticmethod
    def print_help():
        help_text = """
[bold cyan]Motor Semântico de NLP (Natural Language Processing)[/]
Você pode digitar comandos em linguagem natural. O sistema entende palavras-chave,
sinônimos e corrige erros de digitação automaticamente.

[bold green]1. Limpeza por Níveis de Procedimento:[/bold green]
  • [yellow]"limpeza nivel 1"[/] ou [yellow]"1/3"[/]  → Básico (Lixeira, Temp Usuário, DNS, RAM)
  • [yellow]"nivel 2"[/] ou [yellow]"2/3"[/]          → Nível 1 + Temp Sistema, Privacidade Navegadores, RAM Profunda
  • [yellow]"nivel 3"[/] ou [yellow]"3/3"[/]          → Nível 2 + WinSxS (DISM), Logs de Eventos, Ponto de Restauração

[bold green]2. ULTIMATE / Segurança & Manutenção:[/bold green]
  • [yellow]"verificar virus"[/]            → Executa Scan Anti-Malware via Windows Defender
  • [yellow]"reparar sistema"[/]            → Executa SFC Scannow para corrigir arquivos do Windows
  • [yellow]"otimizar disco"[/]             → Desfragmenta HDDs e aplica TRIM em SSDs
  • [yellow]"limpar navegadores"[/]         → Limpeza de Caches de Privacidade (Chrome, Edge, Firefox)

[bold green]3. Comandos Pro:[/bold green]
  • [yellow]"restaurar"[/]                → Cria um Ponto de Restauração de Sistema (Requer Admin)
  • [yellow]"limpar winsxs"[/]            → Limpa a Base de Componentes (DISM StartComponentCleanup)
  • [yellow]"reparar rede"[/]             → Executa TCP/IP e Winsock Reset
  • [yellow]"agendar limpeza"[/]          → Instala no Agendador de Tarefas do Windows

[bold green]4. Controles:[/bold green]
  • [yellow]"status"[/] ou [yellow]"diagnostico"[/]
  • [yellow]"regras"[/] ou [yellow]"config"[/]
  • [yellow]"ajuda"[/]
  • [yellow]"sair"[/]
"""
        console.print(Panel(help_text, title="[bold]Guia de Comandos ULTIMATE[/]", border_style="blue"))

    @staticmethod
    def print_rules(rules: List[Dict[str, Any]]):
        table = Table(title="Regras Customizadas (config.json)", border_style="magenta", show_lines=True)
        table.add_column("Status", justify="center")
        table.add_column("Nome da Regra", style="bold")
        table.add_column("Gatilhos / Palavras-chave", style="yellow")
        table.add_column("Caminho / Comando", style="dim")

        for r in rules:
            status = "[green]ATIVA[/]" if r.get("enabled", True) else "[dim]DESATIVADA[/]"
            if r.get("requires_admin"):
                status += "\n[red]ADMIN[/]"
            
            kws = ", ".join(r.get("keywords", []))
            target = r.get("command") or r.get("path") or ""
            table.add_row(status, r.get("name", "Sem Nome"), kws, target)
        
        console.print(table)
        console.print()

