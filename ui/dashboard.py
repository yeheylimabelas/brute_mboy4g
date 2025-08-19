# ui/dashboard.py
# BRUTEZIPER v11 – Dashboard
# -------------------------------------------------------------
# Komponen Rich Progress untuk memantau brute force secara live.
# - Progress bar
# - Rate
# - ETA
# - CPU/RAM usage
# -------------------------------------------------------------

import time
from typing import Optional

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    RateColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

try:
    import psutil
except ImportError:
    psutil = None

console = Console()

class Dashboard:
    def __init__(self, total: Optional[int] = None, label: str = "Bruteforce"):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.fields[label]}[/]"),
            BarColumn(),
            MofNCompleteColumn() if total is not None else TextColumn(""),
            RateColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn() if total is not None else TextColumn(""),
            TextColumn(" | CPU {task.fields[cpu]}% RAM {task.fields[ram]}%"),
            transient=False,
            console=console,
        )
        self.task_id = self.progress.add_task(
            "brute",
            total=total or 0,
            label=label,
            cpu="--",
            ram="--"
        )
        self.start = time.time()

    def __enter__(self):
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, completed: Optional[int] = None):
        # Ambil CPU/RAM
        cpu_p, ram_p = "--", "--"
        if psutil:
            try:
                cpu_p = f"{psutil.cpu_percent(interval=0):.0f}"
                ram_p = f"{psutil.virtual_memory().percent:.0f}"
            except Exception:
                pass
        self.progress.update(
            self.task_id,
            completed=completed if completed is not None else None,
            cpu=cpu_p,
            ram=ram_p
        )

    def advance(self, n: int = 1):
        self.update(completed=self.progress.tasks[self.task_id].completed + n)

    def stop(self):
        elapsed = time.time() - self.start
        self.progress.stop()
        return elapsed
