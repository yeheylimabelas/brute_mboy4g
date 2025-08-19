import time
from datetime import timedelta
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align

console = Console()

def format_eta(seconds):
    if seconds is None:
        return "—"
    if seconds > 10**8:
        return "∞"
    try:
        return str(timedelta(seconds=int(max(0, seconds))))
    except OverflowError:
        return "∞"

def render_dashboard(zip_file, wordlist, processes, start_at, remaining_total,
                    tested, in_flight, start_time, status="Running",
                    cpu=None, mem=None, temp=None):
    elapsed = time.time() - start_time
    rate = tested / elapsed if elapsed > 0 else 0.0
    eta = format_eta((remaining_total - tested) / rate) if (rate > 0 and tested < remaining_total) else "—"

    table = Table(title="BRUTEZIPER – Python Engine", show_header=False, expand=True)
    table.add_row("📦 ZIP", zip_file)
    table.add_row("📝 Wordlist", wordlist)
    table.add_row("🧠 Worker", str(processes))
    table.add_row("🔢 Total", f"{remaining_total:,} kandidat (mulai idx {start_at:,})")
    table.add_row("✅ Tested", f"{tested:,}")
    table.add_row("⚡ Rate", f"{rate:,.0f} pw/s")
    table.add_row("⏳ ETA", eta)
    if cpu is not None: table.add_row("🖥 CPU", f"{cpu:.1f}%")
    if mem is not None: table.add_row("🧩 RAM", f"{mem:.1f}%")
    if temp is not None: table.add_row("🌡 Suhu", f"{temp}")
    table.add_row("📦 In-Flight", str(in_flight))
    table.add_row("📈 Status", status)

    return Panel(Align.center(table), border_style="cyan", title="Live Dashboard", subtitle="Gunakan untuk file Anda sendiri")

# === Optional: decorator supaya output konsisten panelized ===
def panelize(color="cyan", title="INFO"):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            console.print(Panel(str(result), border_style=color, title=title))
            return result
        return wrapper
    return decorator
