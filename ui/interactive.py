# ui/interactive.py

import sys
import readchar
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

from utils.file_ops import pick_file_with_ranger, is_zip as _is_zip, is_txt as _is_txt
from engines.python_engine import brute_python_fast_v11
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid

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
                    if opt.lower().startswith("exit"):
                        cells.append(f"[bold red][*] {opt}[/]")
                    else:
                        cells.append(f"[bold cyan][*] {opt}[/]")
                else:
                    if opt.lower().startswith("exit"):
                        cells.append(f"[dim red][ ] {opt}[/]")
                    else:
                        cells.append(f"[dim][ ] {opt}[/]")
            while len(cells) < cols:
                cells.append("")
            table.add_row(*cells)

        return Panel(table, title=title, border_style=border_style)

    with Live(render(), refresh_per_second=24, console=console) as live:
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


def interactive_flow():
    engine = radio_grid_menu("Pilih Engine Untuk Brute",
        ["Python", "John", "John Live", "Hybrid", "Exit!"], cols=2).lower()

    if engine.startswith("exit"):
        console.print("[yellow]⚠️ Program dibatalkan oleh user.[/]")
        sys.exit(0)

    # pilih ZIP
    zip_file = pick_file_with_ranger("📂 Pilih file ZIP")
    if not _is_zip(zip_file):
        console.print(Panel("[red]❌ File ZIP tidak valid/dipilih.[/]", border_style="red"))
        sys.exit(1)

    if engine == "python":
        wordlist = pick_file_with_ranger("📂 Pilih file wordlist (.txt)")
        if not _is_txt(wordlist):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
            sys.exit(1)
        brute_python_fast_v11(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)

    elif engine == "john":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("📂 Pilih file wordlist (.txt)")
            if not _is_txt(wordlist):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
                sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False)

    elif engine == "john live":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("📂 Pilih file wordlist (.txt)")
            if not _is_txt(wordlist):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
                sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=True)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True)

    elif engine == "hybrid":
        wordlist = pick_file_with_ranger("📂 Pilih file wordlist (.txt) [untuk tahap Python]")
        if not _is_txt(wordlist):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
            sys.exit(1)
        brute_hybrid(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)
