#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BRUTEZIPER v12 (persistent PythonEngine)

import sys, os
from rich.console import Console

from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid
from utils.io import auto_select_engine
from utils.retry import john_retry
from ui.menu import radio_grid_menu, pick_file_with_ranger
from ui.theming import set_theme, THEMES
from ui import messages as ui
from ui.theming import get_style
from ui import dashboard

console = Console()

# =========================
# Banner
# =========================
def banner():
    os.system("cls" if os.name == "nt" else "clear")
    ui.info(
        f"[{get_style('title')}]BRUTEZIPER v12[/]\n"
        f"By [{get_style('info')}]MBOY4G[/]\n"
        f"As [{get_style('info')}]Ryven Novyr Asmadeus[/]\n"
        f"Mode Python (persistent) · John · Hybrid · Auto",
        title=f"[{get_style('panel')}]SCRIPT"
    )

# =========================
# CLI Usage
# =========================
def usage():
    ui.blue(
        "📌 Penggunaan BRUTEZIPER v12:\n"
        "  python brute_V12.py                               (mode interaktif)\n"
        "  python brute_V12.py --engine python <zip> <wordlist>\n"
        "  python brute_V12.py --engine john   <zip> [wordlist] [--live] [--john-path <dir>]\n"
        "  python brute_V12.py --engine hybrid <zip> <wordlist>\n"
        "  python brute_V12.py --engine auto   <zip> <wordlist>\n\n"
        "ℹ️  Engine:\n"
        "   - python : brute force pakai PythonEngine (persistent worker)\n"
        "   - john   : pakai John the Ripper (wordlist/incremental)\n"
        "   - hybrid : kombinasi Python → John fallback\n"
        "   - auto   : pilih engine otomatis berdasar ukuran wordlist/RAM\n"
    )

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
        brute_python_fast(zip_file, wordlist)  # v12 persistent otomatis

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
        result = brute_john(zip_file, wordlist=wordlist, john_path=john_path, live=live)
        if result and not result.get("password"):
            retry_result = john_retry(zip_file, john_path=john_path, live=live)
            if retry_result:
                result = retry_result

    elif engine == "hybrid":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        result = brute_hybrid(zip_file, wordlist)
        if result:
            dashboard.show_summary(result)

    elif engine == "auto":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        choice = auto_select_engine(zip_file, wordlist)
        ui.info(f"🤖 Auto-select memilih engine: {choice.upper()}")
        if choice == "python":
            brute_python_fast(zip_file, wordlist)
        else:
            result = brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
            if result and not result.get("password"):
                retry_result = john_retry(zip_file, john_path="~/john/run", live=False)
                if retry_result:
                    result = retry_result

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

        if engine == "theme":
            # tampilkan daftar theme
            themes = list(THEMES.keys())
            chosen = radio_grid_menu("Pilih Theme", themes, cols=2).lower()
            try:
                set_theme(chosen)
                ui.success(f"🎨 Theme berhasil diganti ke: {chosen}")
            except Exception as e:
                ui.error(str(e))
            continue  # kembali ke menu utama

        # kalau sampai sini, berarti engine valid
        break

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
        # pilih Resume atau Baru
        resume_mode = radio_grid_menu("Mulai baru atau Resume sesi lama?", ["Mulai Baru", "Resume", "Exit!"], cols=2).lower()
        if resume_mode.startswith("exit!"):
            ui.warning("⚠️ Dibatalkan.")
            sys.exit(0)

        if resume_mode == "resume":
            result = brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False, resume=True)
        else:
            mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
            if mode.startswith("exit!"):
                ui.warning("⚠️ Dibatalkan.")
                sys.exit(0)
            if mode == "wordlist":
                wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
                if not wordlist or not wordlist.lower().endswith(".txt"):
                    ui.error("❌ Wordlist harus file .txt yang valid.")
                    sys.exit(1)
                result = brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False, resume=False)
            else:
                result = brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False, resume=False)

        # 👉 tambahkan retry kalau belum ketemu
        if result and not result.get("password"):
            retry_result = john_retry(zip_file, john_path="~/john/run", live=False)
            if retry_result:
                result = retry_result

        if result:
            dashboard.show_summary(result)

    elif engine == "john live":
        resume_mode = radio_grid_menu("Mulai baru atau Resume sesi lama?", ["Mulai Baru", "Resume", "Exit!"], cols=2).lower()
        if resume_mode.startswith("exit!"):
            ui.warning("⚠️ Dibatalkan.")
            sys.exit(0)

        if resume_mode == "resume":
            result = brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True, resume=True)
        else:
            mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
            if mode.startswith("exit!"):
                ui.warning("⚠️ Dibatalkan.")
                sys.exit(0)
            if mode == "wordlist":
                wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
                if not wordlist or not wordlist.lower().endswith(".txt"):
                    ui.error("❌ Wordlist harus file .txt yang valid.")
                    sys.exit(1)
                result = brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=True, resume=False)
            else:
                result = brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True, resume=False)

        # 👉 retry juga untuk mode live
        if result and not result.get("password"):
            retry_result = john_retry(zip_file, john_path="~/john/run", live=True)
            if retry_result:
                result = retry_result

        if result:
            dashboard.show_summary(result)


    elif engine == "hybrid":
        wordlist = pick_file_with_ranger("Pilih file wordlist (.txt) [untuk tahap Python]")
        if not wordlist or not wordlist.lower().endswith(".txt"):
            ui.error("❌ Wordlist harus file .txt yang valid.")
            sys.exit(1)
        result = brute_hybrid(zip_file, wordlist)
        if result:
            dashboard.show_summary(result)

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
            result = brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
            if result and not result.get("password"):
                retry_result = john_retry(zip_file, john_path="~/john/run", live=False)
                if retry_result:
                    result = retry_result

    elif engine == "benchmark":
        from tools.benchmark import run_benchmark
        run_benchmark()
        sys.exit(0)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    banner()
    if len(sys.argv) == 1:
        interactive_flow()
    else:
        cli_flow()
