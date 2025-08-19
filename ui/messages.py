from rich.console import Console
from rich.panel import Panel

console = Console()

def info(msg, title="INFO"):
    console.print(Panel(msg, border_style="magenta", title=title))

def attention(msg, title="ATTENTION"):
    console.print(Panel(msg, border_style="cyan", title=title))

def white(msg, title="WHITE"):
    console.print(Panel(msg, border_style="white", title=title))

def success(msg, title="SUCCESS"):
    console.print(Panel(msg, border_style="green", title=title))

def warning(msg, title="WARNING"):
    console.print(Panel(msg, border_style="yellow", title=title))

def error(msg, title="ERROR"):
    console.print(Panel(msg, border_style="red", title=title))

# === Shortcut khusus untuk bruteziper ===
def password_found(password, elapsed=None, rate=None, source=""):
    msg = f"[green]✅ Password ditemukan: {password}[/]"
    if elapsed is not None or rate is not None:
        extra = []
        if elapsed is not None:
            extra.append(f"⏳ {elapsed:.2f}s")
        if rate is not None:
            extra.append(f"⚡ {rate:,.0f} pw/s")
        msg += "\n[cyan]" + " · ".join(extra) + "[/]"
    if source:
        title = f"FOUND ({source})"
    else:
        title = "FOUND"
    success(msg, title=title)

def password_not_found(elapsed=None, rate=None, source=""):
    msg = "[red]❌ Password tidak ditemukan[/]"
    if elapsed is not None or rate is not None:
        extra = []
        if elapsed is not None:
            extra.append(f"⏳ {elapsed:.2f}s")
        if rate is not None:
            extra.append(f"⚡ {rate:,.0f} pw/s")
        msg += "\n[cyan]" + " · ".join(extra) + "[/]"
    title = f"FAILED ({source})" if source else "FAILED"
    error(msg, title=title)
