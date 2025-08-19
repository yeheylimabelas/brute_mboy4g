# ui/dashboard.py
# -------------------------------------------------------------------
# Dashboard untuk progress worker & monitoring CPU/RAM
# Kompatibel dengan semua versi rich (fallback RateColumn).
# -------------------------------------------------------------------

import time
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    SpinnerColumn,
)

# coba import RateColumn
try:
    from rich.progress import RateColumn
    _has_rate = True
except ImportError:
    class RateColumn:  # dummy → tampil kosong
        def __init__(self, *a, **kw): pass
        def __rich_console__(self, *a, **kw): return []
    _has_rate = False

from utils.sysinfo import get_cpu_percent, get_ram_usage, get_temp


class Dashboard:
    def __init__(self, total: int | None, label: str = "Progress"):
        self.total = total
        self.label = label
        self._progress = None
        self._task = None

    def __enter__(self):
        cols = [
            SpinnerColumn(),
            TextColumn(f"[cyan]{self.label}[/]"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}" if self.total else "{task.completed}"),
        ]
        if _has_rate:
            cols.append(RateColumn())
        cols.extend([
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TextColumn("CPU {task.fields[cpu]}%"),
            TextColumn("RAM {task.fields[ram]}%"),
            TextColumn("🌡 {task.fields[temp]}°C"),
            TextColumn("{task.fields[status]}"),
        ])

        self._progress = Progress(*cols)
        self._progress.start()
        self._task = self._progress.add_task(
            f"[cyan]{self.label}[/]",
            total=self.total,
            cpu=0,
            ram=0,
            temp=0,
            status="Running",
        )
        return self

    def update(self, advance: int = 0, completed=None, total=None, rate=None, status=None):
        if not self._progress:
            return
        cpu = int(get_cpu_percent())
        ram = int(get_ram_usage())
        temp = int(get_temp() or 0)

        fields = dict(cpu=cpu, ram=ram, temp=temp)
        if status is not None:
            fields["status"] = status

        kwargs = {}
        if completed is not None:
            kwargs["completed"] = completed
        if total is not None:
            kwargs["total"] = total

        self._progress.update(
            self._task,
            advance=advance,
            **kwargs,
            **fields,
        )
        time.sleep(0.05)  # biar animasi smooth

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._progress:
            self._progress.stop()
