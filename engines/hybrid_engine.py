# engines/hybrid_engine.py
# BRUTEZIPER – Hybrid Engine v11 (Advanced, UI Refactor)
# ------------------------------------------------------------------
# Fitur:
# - Tahap 1: Python wordlist
# - Tahap 2: fallback John incremental
# - Auto-select engine (opsional)
# - Resume canggih (Python ckpt + John --restore)
# - Logging ke file
# - UI konsisten pakai panels + dashboard
# - Return dict konsisten + subresults untuk debug
# ------------------------------------------------------------------

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Engine lain
from engines.python_engine import brute_python_fast_v11, recommend_engine_for
from engines.john_engine import brute_john

# UI
from ui.panels import (
    panel_info,
    panel_success,
    panel_warning,
    panel_error,
    panel_stage,
)

# ------------------------------------------------------------------
# Logging util
# ------------------------------------------------------------------

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
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
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


# ------------------------------------------------------------------
# Engine Utama
# ------------------------------------------------------------------

def brute_hybrid(
    zip_file: str,
    wordlist: str,
    processes: Optional[int] = None,
    start_chunk: int = 1000,
    resume: bool = True,
    john_path: str = "~/john/run",
    live: bool = True,
) -> Dict[str, Any]:
    """
    Hybrid brute-force:
      - Tahap 1: Python (wordlist)
      - Tahap 2: Jika gagal → John incremental
    """
    t0 = time.time()
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)

    panel_stage(
        f"[bold cyan]BRUTEZIPER – Hybrid Engine[/]\n"
        f"[white]📦 ZIP       :[/] {os.path.basename(zip_file)}\n"
        f"[white]📝 Wordlist  :[/] {os.path.basename(wordlist)}",
        color="cyan",
    )
    logger.write(f"START engine={ENGINE_NAME} zip={zip_file} wordlist={wordlist}")

    # ================ Tahap 1: Python (wordlist) ================
    panel_stage("🧪 Tahap 1: Python (wordlist) — jika gagal lanjut John incremental", color="cyan")
    res_python = brute_python_fast_v11(
        zip_file,
        wordlist,
        processes=processes,
        start_chunk=start_chunk,
        resume=resume,
    )

    # Jika Python menemukan password, selesai
    if res_python.get("password"):
        elapsed = time.time() - t0
        pw = res_python["password"]
        panel_success(f"Password ditemukan oleh Python: {pw}")
        logger.write(f"FOUND via Python pw='{pw}' elapsed={elapsed:.2f}s")
        logger.close()
        return {
            "password": pw,
            "tested": res_python.get("tested", 0),
            "elapsed": elapsed,
            "rate": res_python.get("rate", 0.0),
            "engine": ENGINE_NAME,
            "stage": "python",
            "used_resume": res_python.get("used_resume", False),
            "checkpoint_file": res_python.get("checkpoint_file"),
            "log_file": log_path,
            "error": None,
            "subresults": {
                "python": res_python,
                "john": None,
            },
        }

    # ================ Tahap 2: John (incremental) ================
    panel_warning("❌ Wordlist gagal. Lanjut ke John incremental…")
    logger.write("Python failed → switching to John incremental")

    res_john = brute_john(
        zip_file,
        wordlist=None,            # incremental
        john_path=john_path,
        live=live,
        resume=resume,            # akan memakai --restore bila ada
    )

    elapsed = time.time() - t0
    final_pw = res_john.get("password")

    if final_pw:
        panel_success(f"Password ditemukan oleh John: {final_pw}")
        logger.write(f"FOUND via John pw='{final_pw}' elapsed_total={elapsed:.2f}s")
    else:
        panel_warning("Hybrid selesai. Password tidak ditemukan.")
        logger.write("NOTFOUND by hybrid")

    logger.close()

    # Catatan: John engine kita tidak mengembalikan 'tested' total.
    tested_py = int(res_python.get("tested", 0))
    rate_overall = (tested_py / elapsed) if elapsed > 0 else 0.0

    return {
        "password": final_pw,
        "tested": tested_py,                  # yang terukur hanya dari tahap Python
        "elapsed": elapsed,
        "rate": rate_overall,
        "engine": ENGINE_NAME,
        "stage": "john" if final_pw else "done",
        "used_resume": res_python.get("used_resume", False) or bool(res_john.get("used_john")),
        "checkpoint_file": res_python.get("checkpoint_file"),
        "log_file": log_path,
        "error": res_john.get("error"),
        "subresults": {
            "python": res_python,
            "john": res_john,
        },
    }


# ------------------------------------------------------------------
# Auto Engine (opsional)
# ------------------------------------------------------------------

def brute_auto(
    zip_file: str,
    wordlist: str,
    processes: Optional[int] = None,
    start_chunk: int = 1000,
    resume: bool = True,
    john_path: str = "~/john/run",
    live: bool = True,
) -> Dict[str, Any]:
    """
    Auto-select engine (python / john / hybrid) berdasarkan heuristik wordlist & memori.
    """
    choice = recommend_engine_for(wordlist)
    panel_info(f"🤖 Auto memilih engine: {choice}")

    if choice == "python":
        return brute_python_fast_v11(zip_file, wordlist, processes, start_chunk, resume)
    elif choice == "john":
        return brute_john(zip_file, wordlist=wordlist, john_path=john_path, live=live, resume=resume)
    else:
        return brute_hybrid(zip_file, wordlist, processes, start_chunk, resume, john_path, live)


# ------------------------------------------------------------------
# CLI Quick Test
# ------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BRUTEZIPER – Hybrid Engine v11 (Advanced)")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("wordlist", help="Path ke file wordlist (.txt)")
    parser.add_argument("--workers", type=int, default=None, help="Jumlah proses worker (default: cores-1)")
    parser.add_argument("--chunk", type=int, default=1000, help="Ukuran batch awal untuk Python")
    parser.add_argument("--john-path", help="Path ke folder run/ John", default="~/john/run")
    parser.add_argument("--auto", action="store_true", help="Gunakan auto engine selection")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    parser.add_argument("--no-live", action="store_true", help="Nonaktifkan live dashboard untuk John")
    args = parser.parse_args()

    if args.auto:
        res = brute_auto(
            args.zip,
            args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=(not args.no_resume),
            john_path=args.john_path,
            live=(not args.no_live),
        )
    else:
        res = brute_hybrid(
            args.zip,
            args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=(not args.no_resume),
            john_path=args.john_path,
            live=(not args.no_live),
        )

    print(res)
