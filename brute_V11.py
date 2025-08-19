#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BRUTEZIPER v11 (modular)

import sys, os
from rich.console import Console
from rich.panel import Panel

from bruteziper.engines.python_engine import brute_python_fast
from bruteziper.engines.john_engine import brute_john
from bruteziper.engines.hybrid import brute_hybrid
from bruteziper.ui.menu import radio_grid_menu, pick_file_with_ranger

console = Console()

# =========================
# Banner
# =========================
def banner():
    os.system("cls" if os.name == "nt" else "clear")
    console.print(Panel(
        "[bold magenta]BRUTEZIPER v11[/]\n"
        "By [bold bright_blue]MBOY4G[/]\n"
        "As [bold bright_blue]Ryven Novyr Asmadeus[/]\n"
        "Mode Python · John · John Live · Hybrid",
        title="[cyan]SCRIPT[/]", border_style="magenta"
    ))

# =========================
# CLI Usage
# =========================
def usage():
    console.print(Panel(
        "📌 Penggunaan:\n"
        "  python main.py                (mode interaktif)\n"
        "  python main.py --engine python <zip> <wordlist>\n"
        "  python main.py --engine john   <zip> [wordlist] [--live] [--john-path <dir>]\n"
        "  python main.py --engine hybrid <zip> <wordlist>\n",
        border_style="blue"))

# =========================
# CLI Flow
# =========================
def cli_flow():
    if len(sys.argv) < 3 or sys.argv[1] != "--engine":
        usage(); sys.exit(1)

    engine = sys.argv[2].lower()
    if engine == "python":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        brute_python_fast(zip_file, wordlist)

    elif engine == "john":
        if len(sys.argv) < 4:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]
        wordlist = None
        if len(sys.argv) >= 5 and not sys.argv[4].startswith("--"):
            wordlist = sys.argv[4]
        live = "--live" in sys.argv
        john_path = "~/john/run"
        if "--john-path" in sys.argv:
            try: john_path = sys.argv[sys.argv.index("--john-path")+1]
            except Exception: pass
        brute_john(zip_file, wordlist=wordlist, john_path=john_path, live=live)

    elif engine == "hybrid":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        brute_hybrid(zip_file, wordlist)
    else:
        usage(); sys.exit(1)

# =========================
# Interactive Flow
# =========================
def interactive_flow():
    engine = radio_grid_menu("Pilih Engine Untuk Brute",
        ["Python", "John", "John Live", "Hybrid", "Exit!"], cols=2).lower()

    if engine.startswith("exit!"):
        console.print("[yellow]⚠️ Program dibatalkan oleh user.[/]")
        sys.exit(0)

    # pilih ZIP
    zip_file = pick_file_with_ranger("Pilih file ZIP")
    if not zip_file or not zip_file.lower().endswith(".zip") or not os.path.isfile(zip_file):
        console.print(Panel("[red]❌ File ZIP tidak valid/dipilih.[/]", border_style="red")); sys.exit(1)

    if engine == "python":
        wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
        if not wordlist or not wordlist.lower().endswith(".txt"):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
        brute_python_fast(zip_file, wordlist)

    elif engine == "john":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit!"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not wordlist or not wordlist.lower().endswith(".txt"):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False)

    elif engine == "john live":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit!"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not wordlist or not wordlist.lower().endswith(".txt"):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=True)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True)

    elif engine == "hybrid":
        wordlist = pick_file_with_ranger("Pilih file wordlist (.txt) [untuk tahap Python]")
        if not wordlist or not wordlist.lower().endswith(".txt"):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
            sys.exit(1)
        brute_hybrid(zip_file, wordlist)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    banner()
    if len(sys.argv) == 1:
        interactive_flow()
    else:
        cli_flow()
