# engines/john_engine.py
# BRUTEZIPER – John Engine v11 (Advanced, UI Refactor)
# ------------------------------------------------------------------
# Fitur Utama:
# - Integrasi langsung dengan John the Ripper (wordlist, incremental).
# - zip2john → file hash → jalankan john → john --show.
# - Resume session otomatis (--restore) jika ada.
# - Logging ke file.
# - UI baru: ui.panels + ui.dashboard + utils.proc.run_with_dashboard.
# - Modularisasi via utils.john_ops & utils.proc.
# ------------------------------------------------------------------

import os
import sys
import time
from datetime import datetime
from typing import Optional

# === UI (baru) ===
from ui.panels import (
    panel_info,
    panel_success,
    panel_warning,
    panel_error,
    panel_stage,
)
from ui.dashboard import Dashboard

# === Utils (baru) ===
from utils.john_ops import zip2john, john_show, john_cmd
from utils.proc import run_with_dashboard
from utils.file_ops import expand


# --------------------------- Logger ---------------------------------

def _mk_log_file(zip_file: str) -> str:
    base = os.path.splitext(os.path.basename(zip_file))[0]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(os.getcwd(), "logs", f"john_{base}_{ts}.log")

class Logger:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8", errors="ignore")
        self.path = path

    def write(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._fh.write(f"[{ts}] {msg}\n")
        self._fh.flush()

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass


# --------------------------- Engine ---------------------------------

def brute_john(
    zip_file: str,
    wordlist: Optional[str] = None,
    john_path: str = "~/john/run",
    live: bool = True,
    resume: bool = True,
) -> dict:
    """
    Brute-force ZIP dengan John the Ripper:
        - Tahap 1: zip2john untuk konversi ZIP → hash.
        - Tahap 2: john (wordlist / incremental).
        - Tahap 3: john --show untuk ambil hasil password.
    """
    t0 = time.time()

    panel_stage(
        f"[bold magenta]BRUTEZIPER – John Engine[/]\n"
        f"[white]📦 ZIP      :[/] {os.path.basename(zip_file)}\n"
        + (f"[white]📝 Wordlist :[/] {os.path.basename(wordlist)}\n" if wordlist else "")
        + f"[white]📂 John dir :[/] {expand(john_path)}",
        color="magenta",
    )

    # logging
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)
    logger.write(f"START engine=john zip={zip_file} wordlist={wordlist} john_path={john_path}")

    # step 1: zip2john
    hash_file = zip2john(zip_file, john_path, logger=logger)
    if not hash_file:
        msg = "Gagal membuat hash dengan zip2john."
        panel_error(msg)
        logger.write(f"ERROR {msg}")
        logger.close()
        return _ret("", 0.0, False, log_path, msg)

    logger.write(f"HASH file={hash_file}")

    # step 2: jalankan john
    cmd = john_cmd(hash_file, john_path, wordlist=wordlist, resume=resume)
    ret_code = run_with_dashboard(cmd, cwd=expand(john_path), logger=logger, label="John the Ripper")

    if ret_code != 0:
        panel_warning(f"John exited dengan code {ret_code} (mungkin normal).")

    # step 3: ambil hasil dengan john --show
    password = john_show(hash_file, john_path, logger=logger)
    elapsed = time.time() - t0

    if password:
        panel_success(f"Password ditemukan oleh John: {password}")
        logger.write(f"FOUND pw='{password}' elapsed={elapsed:.2f}s")
    else:
        panel_warning("Password tidak ditemukan oleh John.")
        logger.write(f"NOTFOUND elapsed={elapsed:.2f}s")

    logger.close()
    return _ret(password or "", elapsed, True, log_path, None)


# --------------------------- Return Helper --------------------------

def _ret(
    password: str,
    elapsed: float,
    used_john: bool,
    log_path: str,
    error: Optional[str],
) -> dict:
    return {
        "password": password or None,
        "elapsed": elapsed,
        "engine": "john",
        "used_john": used_john,
        "log_file": log_path,
        "error": error,
    }


# --------------------------- CLI Quick Test -------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BRUTEZIPER – John Engine v11 (Advanced)")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("--wordlist", help="Path ke file wordlist (opsional)")
    parser.add_argument("--john", default="~/john/run", help="Path ke direktori john (default: ~/john/run)")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    args = parser.parse_args()

    res = brute_john(
        args.zip,
        wordlist=args.wordlist,
        john_path=args.john,
        live=True,
        resume=(not args.no_resume),
    )
    print(res)
