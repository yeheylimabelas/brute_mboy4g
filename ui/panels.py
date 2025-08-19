# ui/panels.py
# BRUTEZIPER v11 – UI Panels
# -------------------------------------------------------------
# Helper untuk membuat panel Rich dengan gaya konsisten
# supaya semua engine (python, john, hybrid) pakai tampilan sama.
# -------------------------------------------------------------

from rich.console import Console
from rich.panel import Panel

console = Console()

def panel_info(msg: str):
    console.print(Panel(msg, border_style="cyan"))

def panel_success(msg: str):
    console.print(Panel(f"[green]✅ {msg}[/]", border_style="green"))

def panel_warning(msg: str):
    console.print(Panel(f"[yellow]⚠️ {msg}[/]", border_style="yellow"))

def panel_error(msg: str):
    console.print(Panel(f"[red]❌ {msg}[/]", border_style="red"))

def panel_stage(title: str, color: str = "blue"):
    console.print(Panel(f"[{color}]{title}[/]", border_style=color))
