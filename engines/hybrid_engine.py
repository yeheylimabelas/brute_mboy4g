# engines/hybrid_engine.py
# BRUTEZIPER – Hybrid Engine v11 (UI Refactor)
# -------------------------------------------------------------
# Fitur:
# - Tahap 1: Python wordlist
# - Tahap 2: fallback ke John incremental
# - Auto-select engine (opsional)
# - Konsisten return dict
# - Resume canggih (Python ckpt + John --restore)
# - Logging ke file
# - UI konsisten pakai panels + dashboard
# -------------------------------------------------------------

import os
import time
from datetime import datetime
from typing import Optional, Dict

# Import engine lain
from engines.python_engine import brute_python_fast_v11, recommend_engine_for
from engines.john_engine import brute_john

from ui.panels import panel_info, panel_success, panel_warning, panel_error, panel_stage
from ui.dashboard import Dashboard

ENGINE_NAME = "hybrid"
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

def _mk_log_file(zip_file: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(zip_file))[0]
    return os.path.join(DEFAULT_LOG_DIR, f"hybrid_{base}_{stamp}.log")

class Logger:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._fh = open(self.log_path, "a", encoding="utf-8", errors="ignore")

    def write(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._fh.write(f"[{ts}] {msg}\n")
        self._fh.flush()

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass

# ------------------------------ Engine Utama --------------------------------

def brute_hybrid(zip_file: str,
                wordlist: str,
                processes: Optional[int] = None,
                start_chunk: int = 1000,
                resume: bool = True,
                john_path: str = "~/john/run") -> Dict:
    """
    Hybrid brute-force:
    - Tahap 1: Python wordlist
    - Tahap 2: kalau gagal, fallback John incremental
    """
    start_time = time.time()
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)

    panel_stage(
        f"[bold cyan]BRUTEZIPER v11 – Hybrid Engine[/]\n"
        f"[white]📦 ZIP :[/] {os.path.basename(zip_file)}\n"
        f"[white]📝 Wordlist:[/] {os.path.basename(wordlist)}",
        color="cyan"
    )
    logger.write(f"Hybrid start zip={zip_file} wordlist={wordlist}")

    # === Tahap 1: Python wordlist ===
    panel_stage("🧪 Tahap 1: Python (wordlist) — jika gagal lanjut John incremental", color="cyan")
    res_python = brute_python_fast_v11(
        zip_file,
        wordlist,
        processes=processes,
        start_chunk=start_chunk,
        resume=resume
    )

    if res_python["password"]:
        elapsed = time.time() - start_time
        logger.write(f"Hybrid success via Python pw={res_python['password']}")
        logger.close()
        return {
            "password": res_python["password"],
            "tested": res_python["tested"],
            "elapsed": elapsed,
            "rate": res_python["rate"],
            "log_file": log_path,
            "engine": ENGINE_NAME,
            "error": None
        }

    # === Tahap 2: John incremental ===
    panel_warning("❌ Wordlist gagal. Lanjut ke John incremental...")
    logger.write("Python failed, switching to John incremental")

    res_john = brute_john(
        zip_file,
        wordlist=None,
        john_path=john_path,
        live=True,
        resume=resume
    )

    elapsed = time.time() - start_time
    final_pw = res_john["password"]
    if final_pw:
        logger.write(f"Hybrid success via John pw={final_pw}")
    else:
        logger.write("Hybrid failed, no password found")

    logger.close()
    return {
        "password": final_pw,
        "tested": res_python["tested"],  # tested dari Python saja
        "elapsed": elapsed,
        "rate": res_python["rate"],
        "log_file": log_path,
        "engine": ENGINE_NAME,
        "error": res_john["error"]
    }

# ------------------------------ Auto Engine ---------------------------------

def brute_auto(zip_file: str,
            wordlist: str,
            processes: Optional[int] = None,
            start_chunk: int = 1000,
            resume: bool = True,
            john_path: str = "~/john/run") -> Dict:
    """
    Auto-select engine (python / john / hybrid) berdasarkan heuristik wordlist & CPU.
    """
    choice = recommend_engine_for(wordlist)
    panel_info(f"🤖 Auto memilih engine: {choice}")

    if choice == "python":
        return brute_python_fast_v11(zip_file, wordlist, processes, start_chunk, resume)
    elif choice == "john":
        return brute_john(zip_file, wordlist=wordlist, john_path=john_path, live=True, resume=resume)
    else:
        return brute_hybrid(zip_file, wordlist, processes, start_chunk, resume, john_path)

# ------------------------------ CLI Quick Test ------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BRUTEZIPER v11 - Hybrid Engine")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("wordlist", help="Path ke file wordlist (.txt)")
    parser.add_argument("--workers", type=int, default=None, help="Jumlah proses worker (default: cores-1)")
    parser.add_argument("--chunk", type=int, default=1000, help="Ukuran batch awal untuk Python")
    parser.add_argument("--john-path", help="Path ke folder run/ John", default="~/john/run")
    parser.add_argument("--auto", action="store_true", help="Gunakan auto engine selection")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    args = parser.parse_args()

    if args.auto:
        res = brute_auto(
            args.zip, args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=(not args.no_resume),
            john_path=args.john_path
        )
    else:
        res = brute_hybrid(
            args.zip, args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=(not args.no_resume),
            john_path=args.john_path
        )
    print(res)
