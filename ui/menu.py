import os, sys, tempfile, subprocess
import readchar
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from ui import messages as ui
from ui.theming import get_style

console = Console()

def radio_grid_menu(title, options, default=0, cols=2, border_style="magenta"):
    idx = default
    def render():
        table = Table.grid(expand=True)
        for _ in range(cols):
            table.add_column(justify="left", ratio=1, no_wrap=True)
        rows = [options[i:i+cols] for i in range(0, len(options), cols)]
        for r in rows:
            cells = []
            for opt in r:
                pos = options.index(opt)
                if pos == idx:
                    mark = "[*]"
                    if opt.lower() == "exit!":
                        style = get_style("error")
                    elif opt.lower() == "theme":
                        style = get_style("warning")
                    else:
                        style = get_style("info")
                    cells.append(f"[bold {style}]{mark} {opt}[/]")
                else:
                    if opt.lower() == "exit!":
                        style = f"dim {get_style('error')}"
                    elif opt.lower() == "theme":
                        style = f"dim {get_style('warning')}"
                    else:
                        style = "dim"
                    cells.append(f"[{style}][ ] {opt}[/]")
            while len(cells) < cols:
                cells.append("")
            table.add_row(*cells)
        return Panel(table, title=title, border_style=border_style)

    with Live(render(), refresh_per_second=24, console=console, transient=True) as live:
        while True:
            key = readchar.readkey()
            if key == readchar.key.RIGHT:
                idx = (idx + 1) % len(options); live.update(render())
            elif key == readchar.key.LEFT:
                idx = (idx - 1) % len(options); live.update(render())
            elif key == readchar.key.UP:
                idx = (idx - cols) % len(options); live.update(render())
            elif key == readchar.key.DOWN:
                idx = (idx + cols) % len(options); live.update(render())
            elif key == readchar.key.ENTER:
                return options[idx]

def _ensure_ranger():
    try:
        subprocess.check_call(["ranger", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        ui.error("❌ Ranger tidak ditemukan. Install dulu: pkg install ranger")
        return False

def pick_file_with_ranger(prompt_title="Pilih file"):
    if not _ensure_ranger():
        return None
    fd, tmpfile = tempfile.mkstemp(prefix="ranger_select_", suffix=".txt")
    os.close(fd)
    ui.attention(f"📂 {prompt_title}")
    try:
        subprocess.call(["ranger", "--choosefiles", tmpfile])
    except FileNotFoundError:
        ui.error("❌ Ranger tidak ditemukan.")
        return None

    if os.path.exists(tmpfile):
        with open(tmpfile, "r") as f:
            path = f.readline().strip()
        try: os.remove(tmpfile)
        except Exception: pass
        if path:
            return path
        else:
            console.print(f"[{get_style('error')}]⚠ Tidak ada yang dipilih.[/]")
            return None
    else:
        console.print(f"[{get_style('error')}]❌ File hasil pilihan tidak ditemukan.[/]")
        return None