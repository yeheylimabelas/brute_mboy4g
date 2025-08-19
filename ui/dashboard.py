# ui/dashboard.py
# -------------------------------------------------------------------
# Dashboard ala V10: tabel manual (bukan progress bar)
# -------------------------------------------------------------------

import os, time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.live import Live
from utils.sysinfo import get_cpu_percent, get_ram_usage, get_temp

console = Console()


class Dashboard:
    def __init__(self, zip_file, wordlist, processes, total, start_at=0, label="Python Engine"):
        self.zip_file = os.path.basename(zip_file)
        self.wordlist = os.path.basename(wordlist) if wordlist else "-"
        self.processes = processes
        self.total = total
        self.start_at = start_at
        self.label = label

        self.tested = 0
        self.in_flight = 0
        self.status = "Running"
        self.start_time = time.time()

    def render(self):
        elapsed = time.time() - self.start_time
        rate = self.tested / elapsed if elapsed > 0 else 0.0
        remaining = self.total - self.tested if self.total else 0
        eta = self._format_eta(remaining / rate) if (rate > 0 and remaining > 0) else "—"

        cpu = get_cpu_percent() or 0
        ram = get_ram_usage() or 0
        temp = get_temp() or 0

        table = Table(title=f"BRUTEZIPER – {self.label}", show_header=False, expand=True)
        table.add_row("📦 ZIP", self.zip_file)
        table.add_row("📝 Wordlist", self.wordlist)
        table.add_row("🧠 Worker", str(self.processes))
        table.add_row("🔢 Total", f"{self.total:,} kandidat (mulai idx {self.start_at:,})")
        table.add_row("✅ Tested", f"{self.tested:,}")
        table.add_row("⚡ Rate", f"{rate:,.0f} pw/s")
        table.add_row("⏳ ETA", eta)
        table.add_row("🖥 CPU", f"{cpu:.1f}%")
        table.add_row("🧩 RAM", f"{ram:.1f}%")
        table.add_row("🌡 Suhu", f"{temp}")
        table.add_row("📦 In-Flight", str(self.in_flight))
        table.add_row("📈 Status", self.status)

        return Panel(Align.center(table), border_style="cyan", title="Live Dashboard", subtitle="Gunakan untuk file Anda sendiri")

    def __enter__(self):
        self._live = Live(self.render(), refresh_per_second=4, console=console)
        self._live.__enter__()
        return self

    def update(self, tested=None, in_flight=None, status=None):
        if tested is not None:
            self.tested = tested
        if in_flight is not None:
            self.in_flight = in_flight
        if status is not None:
            self.status = status
        self._live.update(self.render())

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._live.__exit__(exc_type, exc_val, exc_tb)

    @staticmethod
    def _format_eta(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}"
