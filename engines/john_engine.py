# engines/john_engine.py
# BRUTEZIPER – John Engine v11
# -------------------------------------------------------------
# Fitur:
# - Panggil John the Ripper (JtR) via subprocess.
# - Mode wordlist (--wordlist=...) atau incremental (--incremental).
# - Resume canggih dengan opsi --restore (lanjut dari sesi John sebelumnya).
# - Konsisten return dict: {password, tested, elapsed, rate, log_file, engine, error}
# - Logging ke file.
# - Integrasi dengan zip2john otomatis (buat hash dari ZIP).
# -------------------------------------------------------------

import os
import subprocess
import time
from datetime import datetime
from typing import Optional, Dict

from rich.console import Console
from rich.panel import Panel

console = Console()

ENGINE_NAME = "john"
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

def _mk_log_file(zip_file: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(zip_file))[0]
    return os.path.join(DEFAULT_LOG_DIR, f"john_{base}_{stamp}.log")

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

# ------------------------------ Helper --------------------------------------

def _run_cmd(cmd: str, cwd: Optional[str] = None, live: bool = True, logger: Optional[Logger] = None) -> int:
    """
    Jalankan perintah shell. Jika live=True, stream output ke console.
    """
    console.print(Panel(f"[cyan]$ {cmd}[/]", border_style="cyan"))
    if logger:
        logger.write(f"RUN {cmd}")
    proc = subprocess.Popen(
        cmd, shell=True, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    if live:
        for line in proc.stdout:
            console.print(line.rstrip())
            if logger:
                logger.write(line.rstrip())
    else:
        out, _ = proc.communicate()
        if out and logger:
            for ln in out.splitlines():
                logger.write(ln)
    return proc.wait()

def _zip2john(zip_file: str, john_path: str, logger: Logger) -> Optional[str]:
    """
    Konversi ZIP ke hash file untuk John.
    """
    john_bin = os.path.join(john_path, "john")
    zip2john_bin = os.path.join(john_path, "zip2john")
    hash_file = os.path.splitext(os.path.basename(zip_file))[0] + ".hash"

    cmd = f"{zip2john_bin} '{zip_file}' > '{hash_file}'"
    ret = _run_cmd(cmd, cwd=john_path, live=False, logger=logger)
    if ret != 0 or not os.path.exists(os.path.join(john_path, hash_file)):
        return None
    return os.path.join(john_path, hash_file)

def _john_show(hash_file: str, john_path: str, logger: Logger) -> Optional[str]:
    """
    Ambil password hasil crack dari John (john --show).
    """
    john_bin = os.path.join(john_path, "john")
    cmd = f"{john_bin} --show '{hash_file}'"
    try:
        out = subprocess.check_output(cmd, shell=True, cwd=john_path, text=True)
        if logger:
            logger.write(out.strip())
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1]:
                return parts[1]
    except Exception as e:
        if logger:
            logger.write(f"ERROR john_show: {e}")
    return None

# ------------------------------ Engine Utama --------------------------------

def brute_john(zip_file: str,
            wordlist: Optional[str] = None,
            john_path: str = "~/john/run",
            live: bool = True,
            resume: bool = True) -> Dict:
    """
    Jalankan John the Ripper untuk crack ZIP.
    - Jika wordlist != None → mode wordlist.
    - Jika wordlist == None → mode incremental.
    - Resume: gunakan --restore kalau ada sesi sebelumnya.
    """

    start_time = time.time()
    john_path = os.path.expanduser(john_path)
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)

    console.print(Panel.fit(
        f"[bold magenta]BRUTEZIPER v11 – John Engine[/]\n"
        f"[white]📦 ZIP :[/] {os.path.basename(zip_file)}\n"
        f"[white]📂 Mode:[/] {'Wordlist' if wordlist else 'Incremental'}",
        border_style="magenta"
    ))

    # Buat hash file
    hash_file = _zip2john(zip_file, john_path, logger)
    if not hash_file:
        msg = "Gagal membuat hash file dengan zip2john."
        console.print(Panel(msg, border_style="red"))
        logger.write(f"ERROR {msg}")
        logger.close()
        return {
            "password": None,
            "tested": 0,
            "elapsed": 0.0,
            "rate": 0.0,
            "log_file": log_path,
            "engine": ENGINE_NAME,
            "error": msg,
        }

    # Tentukan command
    john_bin = os.path.join(john_path, "john")
    if resume and os.path.exists(os.path.join(john_path, "restore")):
        cmd = f"{john_bin} --restore"
    else:
        if wordlist:
            cmd = f"{john_bin} --format=zip --wordlist='{wordlist}' '{hash_file}'"
        else:
            cmd = f"{john_bin} --format=zip --incremental '{hash_file}'"

    # Jalankan John
    ret = _run_cmd(cmd, cwd=john_path, live=live, logger=logger)

    # Ambil hasil
    password = _john_show(hash_file, john_path, logger)

    elapsed = time.time() - start_time
    logger.write(f"FINISHED elapsed={elapsed:.2f}s ret={ret} found={bool(password)}")
    logger.close()

    if password:
        console.print(Panel(f"[green]✅ Password ditemukan oleh John: [bold]{password}[/][/]", border_style="green"))
    else:
        console.print(Panel("[yellow]❌ Password tidak ditemukan oleh John.[/]", border_style="yellow"))

    return {
        "password": password,
        "tested": 0,  # sulit hitung tested dari John CLI
        "elapsed": elapsed,
        "rate": 0.0,
        "log_file": log_path,
        "engine": ENGINE_NAME,
        "error": None if ret == 0 else f"John exited {ret}"
    }

# ------------------------------ CLI Quick Test ------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BRUTEZIPER v11 - John Engine")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("--wordlist", help="Path ke file wordlist (opsional)", default=None)
    parser.add_argument("--john-path", help="Path ke folder run/ John", default="~/john/run")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume John (--restore)")
    args = parser.parse_args()

    res = brute_john(
        args.zip,
        wordlist=args.wordlist,
        john_path=args.john_path,
        live=True,
        resume=(not args.no_resume)
    )
    console.print(res)
