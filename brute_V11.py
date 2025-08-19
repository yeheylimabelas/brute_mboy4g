#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BRUTEZIPER v11 (modular)

import sys, os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid
from utils.io import auto_select_engine
from utils.analyzer import get_zip_metadata
from utils import benchmark
from ui.menu import radio_grid_menu, pick_file_with_ranger
from ui.theming import set_theme, THEMES
from ui import messages as ui
from ui.theming import get_style

console = Console()

# =========================
# Banner
# =========================
def banner():
    os.system("cls" if os.name == "nt" else "clear")
    ui.info(
        f"[{get_style('title')}]BRUTEZIPER v11[/]\n"
        f"By [{get_style('info')}]MBOY4G[/]\n"
        f"As [{get_style('info')}]Ryven Novyr Asmadeus[/]\n"
        f"Mode Python · John · John Live · Hybrid",
        title=f"[{get_style('panel')}]SCRIPT"
    )

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
            ["Python", "John", "John Live", "Hybrid", "Auto", "Benchmark", "Theme", "Exit!"], cols=3).lower()

        if engine.startswith("exit!"):
            ui.warning("⚠️ Program dibatalkan oleh user.")
            sys.exit(0)

        elif engine == "benchmark":
            run_benchmark()
            return

        if engine == "theme":
            # tampilkan daftar theme
            themes = list(THEMES.keys())
            chosen = radio_grid_menu("Pilih Theme", themes, cols=2).lower()
            try:
                set_theme(chosen)
                ui.success(f"🎨 Theme berhasil diganti ke: {chosen}")
            except Exception as e:
                ui.error(str(e))
            # khusus theme → ulang lagi ke menu utama
            continue

        # kalau sampai sini, berarti engine (bukan Theme/Exit)
        # → jalankan engine sekali, lalu keluar
        break

    # pilih ZIP
    zip_file = pick_file_with_ranger("Pilih file ZIP")
    if not zip_file or not zip_file.lower().endswith(".zip") or not os.path.isfile(zip_file):
        ui.error("❌ File ZIP tidak valid/dipilih.")
        sys.exit(1)

    # 🔍 panggil analyzer
    meta = get_zip_metadata(zip_file)
    if "error" in meta:
        ui.error(f"Gagal membaca ZIP: {meta['error']}")
    else:
        ui.info(
            f"📦 File: {meta['file']}\n"
            f"📏 Size: {meta['size']:,} bytes\n"
            f"📂 Entries: {meta['entries']}\n"
            f"🔐 Encrypted: {'Ya' if meta['encrypted'] else 'Tidak'}",
            title="ZIP Metadata"
        )

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

def run_benchmark():
    # pilih ZIP & wordlist
    zip_file = pick_file_with_ranger("Pilih file ZIP (untuk benchmark)")
    wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")

    dry = benchmark.dry_run(zip_file, wordlist)
    if not dry["ok"]:
        ui.error("❌ Input tidak valid:\n" + "\n".join(dry["issues"]))
        return

    ui.info("🚀 Menjalankan benchmark kecil...")

    results = []

    # PythonEngine mini
    from engines.python_engine import PythonEngine
    py_eng = PythonEngine(zip_file, wordlist, processes=2, start_chunk=500, resume=False)
    results.append(benchmark.benchmark_engine("PythonEngine", lambda: py_eng.run_sample(limit=5000), repeat=2))

    # JohnEngine mini
    from engines.john_engine import JohnEngine
    john_eng = JohnEngine(zip_file, wordlist, live=False)
    results.append(benchmark.benchmark_engine("JohnEngine", lambda: john_eng.run_sample(limit=5000), repeat=2))

    # tampilkan hasil
    table = Table(title="📊 Benchmark Results")
    table.add_column("Engine", style="cyan")
    table.add_column("Rata-rata (s)", style="magenta")
    table.add_column("Status", style="green")

    for r in results:
        status = r["sample_result"].get("status", "?")
        table.add_row(r["label"], f"{r['avg_seconds']:.2f}", status)

    console.print(Panel(table, title="Benchmark Summary", border_style="blue"))


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    banner()
    if len(sys.argv) == 1:
        interactive_flow()
    else:
        cli_flow()
