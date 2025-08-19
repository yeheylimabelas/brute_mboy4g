from rich.console import Console
from rich.panel import Panel
from bruteziper.ui.theming import get_style

console = Console()

def info(msg, title="INFO"):
    console.print(Panel(msg, border_style=get_style("info"), title=title))

def bold_info(msg, title="BOLD_INFO"):
    console.print(Panel(msg, border_style=get_style("bold_info"), title=title))

def attention(msg, title="ATTENTION"):
    console.print(Panel(msg, border_style=get_style("attention"), title=title))

def white(msg, title="WHITE"):
    console.print(Panel(msg, border_style=get_style("white"), title=title))

def blue(msg, title="BLUE"):
    console.print(Panel(msg, border_style=get_style("blue"), title=title))

def success(msg, title="SUCCESS"):
    console.print(Panel(msg, border_style=get_style("success"), title=title))

def warning(msg, title="WARNING"):
    console.print(Panel(msg, border_style=get_style("warning"), title=title))

def error(msg, title="ERROR"):
    console.print(Panel(msg, border_style=get_style("error"), title=title))

# === Shortcut khusus untuk bruteziper ===
def password_found(password, elapsed=None, rate=None, source=""):
    msg = f"[{get_style('success')}]✅ Password ditemukan: {password}[/]"
    if elapsed is not None or rate is not None:
        extra = []
        if elapsed is not None:
            extra.append(f"⏳ {elapsed:.2f}s")
        if rate is not None:
            extra.append(f"⚡ {rate:,.0f} pw/s")
        msg += f"\n[{get_style('info')}]" + " · ".join(extra) + "[/]"
    title = f"FOUND ({source})" if source else "FOUND"
    success(msg, title=title)

def password_not_found(elapsed=None, rate=None, source=""):
    msg = f"[{get_style('error')}]❌ Password tidak ditemukan[/]"
    if elapsed is not None or rate is not None:
        extra = []
        if elapsed is not None:
            extra.append(f"⏳ {elapsed:.2f}s")
        if rate is not None:
            extra.append(f"⚡ {rate:,.0f} pw/s")
        msg += f"\n[{get_style('info')}]" + " · ".join(extra) + "[/]"
    title = f"FAILED ({source})" if source else "FAILED"
    error(msg, title=title)
