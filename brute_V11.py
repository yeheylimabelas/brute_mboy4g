#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BRUTEZIPER v11 (modular)

import sys, os
from rich.console import Console
from rich.panel import Panel

from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid
from utils.io import auto_select_engine
from ui.menu import radio_grid_menu, pick_file_with_ranger
from ui.theming import set_theme, _THEMES
from ui import messages as ui

console = Console()

# =========================
# Banner
# =========================
def banner():
    os.system("cls" if os.name == "nt" else "clear")
    ui.info(
        "[bold magenta]BRUTEZIPER v11[/]\n"
        "By [bold bright_blue]MBOY4G[/]\n"
        "As [bold bright_blue]Ryven Novyr Asmadeus[/]\n"
        "Mode Python · John · John Live · Hybrid",
        title="[cyan]SCRIPT")

# =========================
# CLI Usage
# =========================
def usage():
    ui.blue(
        "📌 Penggunaan:\n"
        "  python main.py                (mode interaktif)\n"
        "  python main.py --engine python <zip> <wordlist>\n"
        "  python main.py --engine john   <zip> [wordlist] [--live] [--john-path <dir>]\n"
        "  python main.py --engine hybrid <zip> <wordlist>\n")

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

    elif engine == "auto":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        choice = auto_select_engine(zip_file, wordlist)
        ui.info(f"🤖 Auto-select memilih engine: {choice.upper()}")
        if choice == "python":
            brute_python_fast(zip_file, wordlist)
        else:
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)

    else:
        usage(); sys.exit(1)

# =========================
# Interactive Flow
# =========================
def interactive_flow():
    while True:
        engine = radio_grid_menu("Pilih Engine Untuk Brute",
            ["Python", "John", "John Live", "Hybrid", "Auto", "Theme", "Exit!"], cols=3).lower()

        if engine.startswith("exit!"):
            ui.warning("⚠️ Program dibatalkan oleh user.")
            sys.exit(0)

        if engine == "theme":
            # tampilkan daftar theme dari THEMES dict
            themes = list(_THEMES.keys())
            chosen = radio_grid_menu("Pilih Theme", themes, cols=2).lower()
            try:
                set_theme(chosen)
                ui.success(f"🎨 Theme berhasil diganti ke: {chosen}")
            except Exception as e:
                ui.error(str(e))
            # setelah selesai, loop balik ke menu utama
            continue

        # pilih ZIP
        zip_file = pick_file_with_ranger("Pilih file ZIP")
        if not zip_file or not zip_file.lower().endswith(".zip") or not os.path.isfile(zip_file):
            ui.error("❌ File ZIP tidak valid/dipilih.")
            sys.exit(1)

        if engine == "python":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not wordlist or not wordlist.lower().endswith(".txt"):
                ui.error("❌ Wordlist harus file .txt yang valid.")
                sys.exit(1)
            brute_python_fast(zip_file, wordlist)

        elif engine == "john":
            mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
            if mode.startswith("exit!"):
                ui.warning("⚠️ Dibatalkan.")
                sys.exit(0)
            if mode == "wordlist":
                wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
                if not wordlist or not wordlist.lower().endswith(".txt"):
                    ui.error("❌ Wordlist harus file .txt yang valid.")
                    sys.exit(1)
                brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
            else:
                brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False)

        elif engine == "john live":
            mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
            if mode.startswith("exit!"):
                ui.warning("⚠️ Dibatalkan.")
                sys.exit(0)
            if mode == "wordlist":
                wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
                if not wordlist or not wordlist.lower().endswith(".txt"):
                    ui.error("❌ Wordlist harus file .txt yang valid.")
                    sys.exit(1)
                brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=True)
            else:
                brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True)

        elif engine == "hybrid":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt) [untuk tahap Python]")
            if not wordlist or not wordlist.lower().endswith(".txt"):
                ui.error("❌ Wordlist harus file .txt yang valid.")
                sys.exit(1)
            brute_hybrid(zip_file, wordlist)

        elif engine == "auto":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not wordlist or not wordlist.lower().endswith(".txt"):
                ui.error("❌ Wordlist harus file .txt yang valid.")
                sys.exit(1)
            selected = auto_select_engine(zip_file, wordlist)
            ui.info(f"🤖 Auto-select memilih engine: {selected.upper()}")
            if selected == "python":
                brute_python_fast(zip_file, wordlist)
            else:
                brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    banner()
    if len(sys.argv) == 1:
        interactive_flow()
    else:
        cli_flow()
