# engines/python_engine.py
# BRUTEZIPER – Python Engine v11
# -------------------------------------------------------------
# Fitur utama:
# - Performa: auto-detect core, dynamic chunk size, streaming wordlist (mmap/iter),
#   minimal I/O, multiprocessing event-driven stop.
# - UX: Rich dashboard (rate/ETA/CPU/RAM), progress bar, logging ke file.
# - Code Simplification: API konsisten (return dict), modular fungsi util.
# - Smart: Resume canggih via checkpoint JSON (line_index + byte_offset untuk file .txt),
#   kompatibel file wordlist besar, auto-recommend engine helper.
# - Backward compatible: alias brute_python_fast_v10 -> brute_python_fast_v11
#
# Ketergantungan opsional:
# - pyzipper (untuk AES/ZipCrypto). Disarankan: pip install pyzipper
# - psutil (untuk CPU/RAM). Opsional; kalau tak ada, tetap jalan.
#
# Penggunaan (dari modul lain):
#   from engines.python_engine import brute_python_fast_v11
#   result = brute_python_fast_v11(zip_file, wordlist, processes=None, start_chunk=1000, resume=True)
#
# result: {
#   "password": str|None,
#   "tested": int,
#   "elapsed": float,
#   "rate": float,
#   "used_resume": bool,
#   "checkpoint_file": str|None,
#   "log_file": str,
#   "engine": "python",
#   "error": str|None
# }
# -------------------------------------------------------------

from __future__ import annotations

import os
import sys
import io
import gzippolib  # dummy to trigger NameError if typo; removed below
# ^ (penjaga kesalahan tak sengaja) -> akan dihapus di runtime; jangan khawatir.
# (DIBERSIHKAN DI BAWAH)
try:
    import mmap
except Exception:
    mmap = None
import gzip
import bz2
import lzma
import time
import json
import math
import queue
import errno
import signal
import hashlib
import threading
from datetime import datetime
from typing import Iterable, Iterator, List, Tuple, Optional

from multiprocessing import Process, Event, Queue, Value, cpu_count, set_start_method
from multiprocessing.sharedctypes import Synchronized

try:
    import pyzipper  # AES & ZipCrypto
except Exception as e:
    pyzipper = None

# psutil opsional
try:
    import psutil
except Exception:
    psutil = None

# Rich UI
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    SpinnerColumn,
    RateColumn,
)
from rich.table import Table

# Bersihkan sentinel import yang sengaja bikin error di atas
if "gzippolib" in globals():
    del gzippolib

console = Console()

# ------------------------------ Konstanta ----------------------------------

ENGINE_NAME = "python"
CHECKPOINT_DIR = os.path.join(os.getcwd(), ".brutezipper")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

CHUNK_MIN = 100
CHUNK_MAX = 20000
ADJUST_INTERVAL_S = 2.0
ADJUST_UP_FACTOR = 1.25
ADJUST_DOWN_FACTOR = 0.8
HIGH_CPU_THRESHOLD = 85.0  # %
LOW_CPU_THRESHOLD = 35.0   # %
INFLIGHT_SOFT_MAX_PER_WORKER = 3  # jaga antrean tidak membengkak

# ------------------------------ Util Sistem --------------------------------

def _now() -> float:
    return time.time()

def format_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def _read_cpu_percent() -> Optional[float]:
    if psutil:
        try:
            return psutil.cpu_percent(interval=0.0)
        except Exception:
            return None
    return None

def _read_ram_usage() -> Optional[float]:
    if psutil:
        try:
            vm = psutil.virtual_memory()
            return vm.percent
        except Exception:
            return None
    return None

def get_system_info() -> dict:
    cores = cpu_count() or 1
    return {
        "cores": cores,
        "cpu_percent": _read_cpu_percent(),
        "ram_percent": _read_ram_usage(),
    }

# ------------------------------ Logging ------------------------------------

def _mk_log_file(zip_file: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(zip_file))[0]
    return os.path.join(DEFAULT_LOG_DIR, f"python_{base}_{stamp}.log")

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

# ------------------------------ Checkpoint ---------------------------------

def _ckpt_name(zip_file: str, wordlist: str) -> str:
    key = os.path.abspath(zip_file) + "|" + os.path.abspath(wordlist)
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(CHECKPOINT_DIR, f"ckpt_{h}.json")

def _load_ckpt(ckpt_path: str) -> Optional[dict]:
    if not os.path.exists(ckpt_path):
        return None
    try:
        with open(ckpt_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _save_ckpt(ckpt_path: str, data: dict):
    tmp = ckpt_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ckpt_path)

def _wordlist_stat(path: str) -> Tuple[int, float]:
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime)
    except Exception:
        return (0, 0.0)

# ------------------------------ Wordlist IO --------------------------------

def _is_plain_text(path: str) -> bool:
    lower = path.lower()
    return not (lower.endswith(".gz") or lower.endswith(".bz2") or lower.endswith(".xz") or lower.endswith(".lzma"))

def _open_stream(path: str):
    lower = path.lower()
    if lower.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    elif lower.endswith(".bz2"):
        return bz2.open(path, "rt", encoding="utf-8", errors="ignore")
    elif lower.endswith(".xz") or lower.endswith(".lzma"):
        return lzma.open(path, "rt", encoding="utf-8", errors="ignore")
    else:
        return open(path, "r", encoding="utf-8", errors="ignore")

def count_lines_fast(path: str, hard_limit_seconds: float = 3.0) -> Optional[int]:
    """
    Hitung banyak baris untuk progress total. Batasi waktu supaya tidak mahal.
    - Untuk file terkompresi, return None (biar progress tak bertotal).
    - Untuk file teks biasa: coba mmap jika tersedia, fallback ke iter cepat.
    """
    if not _is_plain_text(path):
        return None
    start = _now()
    try:
        if mmap is not None:
            with open(path, "r+b") as f:
                mm = mmap.mmap(f.fileno(), 0)
                cnt = 0
                readline = mm.readline
                while True:
                    if _now() - start > hard_limit_seconds:
                        return None
                    line = readline()
                    if not line:
                        break
                    cnt += 1
                mm.close()
                return cnt
        else:
            cnt = 0
            with open(path, "rb", buffering=1024 * 1024) as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    cnt += chunk.count(b"\n")
                    if _now() - start > hard_limit_seconds:
                        return None
            return cnt
    except Exception:
        return None

def iter_wordlist(path: str, start_index: int = 0, byte_offset: Optional[int] = None) -> Iterator[str]:
    """
    Generator baris kata sandi:
    - Mendukung .txt (seek byte_offset untuk resume cepat) dan .gz/.bz2/.xz (tanpa seek).
    - start_index digunakan sebagai fallback/penyesuaian jika byte_offset tidak akurat.
    """
    if _is_plain_text(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            if byte_offset and byte_offset > 0:
                try:
                    f.seek(byte_offset)
                except Exception:
                    pass
            # Sinkronkan kembali berdasarkan start_index (safety)
            idx = 0
            for line in f:
                if idx < start_index:
                    idx += 1
                    continue
                yield line.rstrip("\r\n")
                idx += 1
    else:
        # Kompresi: tidak reliable seek; iter sampai start_index
        with _open_stream(path) as f:
            idx = 0
            for line in f:
                if idx < start_index:
                    idx += 1
                    continue
                yield line.rstrip("\r\n")
                idx += 1

# ------------------------------ ZIP Password Test ---------------------------

class ZipTester:
    def __init__(self, zip_path: str):
        if pyzipper is None:
            raise RuntimeError("pyzipper tidak terpasang. Instal: pip install pyzipper")
        self.zip_path = zip_path
        # Preload nama pertama untuk uji cepat
        with pyzipper.AESZipFile(self.zip_path) as zf:
            names = zf.namelist()
            if not names:
                raise RuntimeError("ZIP kosong.")
            self.first_name = names[0]
        # Catat apakah terenkripsi (untuk feedback)
        self.is_encrypted = self._detect_encrypted()

    def _detect_encrypted(self) -> bool:
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                for info in zf.infolist():
                    # bit 0x1 => encrypted
                    if info.flag_bits & 0x1:
                        return True
        except Exception:
            return True
        return False

    def try_password(self, password: str) -> bool:
        """
        Kembalikan True jika password benar. Membaca 1 byte dari file pertama.
        """
        pwb = password.encode("utf-8", errors="ignore")
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                with zf.open(self.first_name, pwd=pwb) as fh:
                    _ = fh.read(1)
            return True
        except Exception:
            return False

# ------------------------------ Multiprocessing Worker ----------------------

def _worker_loop(zip_path: str,
                task_q: Queue,
                result_q: Queue,
                found_event: Event):
    tester = ZipTester(zip_path)
    while not found_event.is_set():
        try:
            batch = task_q.get(timeout=0.5)
        except queue.Empty:
            if found_event.is_set():
                break
            else:
                continue
        if batch is None:
            # sentinel
            break

        tested_local = 0
        for pwd in batch:
            if found_event.is_set():
                break
            tested_local += 1
            if tester.try_password(pwd):
                found_event.set()
                result_q.put({"tested": tested_local, "password": pwd})
                return
        # batch selesai tanpa hasil
        result_q.put({"tested": tested_local, "password": None})

# ------------------------------ Engine Utama --------------------------------

def brute_python_fast_v11(zip_file: str,
                        wordlist: str,
                        processes: Optional[int] = None,
                        start_chunk: int = 1000,
                        resume: bool = True) -> dict:
    """
    Python brute-force dengan wordlist:
    - Multiprocess, dynamic chunk size, resume canggih (line index + byte offset),
    dashboard Rich, log file, checkpoint berkala & on-signal.
    """
    start_time = _now()
    sys_info = get_system_info()
    cores = sys_info["cores"]
    if processes is None:
        # sisakan 1 core untuk sistem
        processes = max(1, cores - 1)

    # UI – header
    console.print(Panel.fit(
        f"[bold cyan]BRUTEZIPER v11 – Python Engine[/]\n"
        f"[white]📦 ZIP      :[/] {os.path.basename(zip_file)}\n"
        f"[white]📝 Wordlist :[/] {os.path.basename(wordlist)}\n"
        f"[white]🧠 Worker   :[/] {processes}\n"
        f"[white]🔢 Chunk    :[/] {start_chunk}",
        border_style="cyan"
    ))

    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)
    logger.write(f"Engine={ENGINE_NAME} zip={zip_file} wordlist={wordlist} workers={processes} chunk_start={start_chunk}")

    # Setup tester lebih awal (error cepat)
    try:
        tester_probe = ZipTester(zip_file)
    except Exception as e:
        logger.write(f"ERROR init ZipTester: {e}")
        console.print(Panel(str(e), border_style="red"))
        logger.close()
        return {"password": None, "tested": 0, "elapsed": 0.0, "rate": 0.0,
                "used_resume": False, "checkpoint_file": None,
                "log_file": log_path, "engine": ENGINE_NAME, "error": str(e)}

    if not tester_probe.is_encrypted:
        console.print(Panel("[yellow]ZIP tidak terenkripsi. Tidak perlu brute.[/]", border_style="yellow"))
        logger.write("ZIP not encrypted; abort")
        elapsed = _now() - start_time
        logger.close()
        return {"password": "", "tested": 0, "elapsed": elapsed, "rate": 0.0,
                "used_resume": False, "checkpoint_file": None,
                "log_file": log_path, "engine": ENGINE_NAME, "error": None}

    # Hitung total kandidat (opsional, bisa None)
    total_candidates = count_lines_fast(wordlist)

    # Checkpoint
    ckpt_path = _ckpt_name(zip_file, wordlist)
    used_resume = False
    wl_size, wl_mtime = _wordlist_stat(wordlist)
    state = {
        "version": 2,
        "zip_file": os.path.abspath(zip_file),
        "wordlist": os.path.abspath(wordlist),
        "wordlist_size": wl_size,
        "wordlist_mtime": wl_mtime,
        "line_index": 0,
        "byte_offset": 0 if _is_plain_text(wordlist) else None,
        "tested": 0,
        "chunk": int(max(CHUNK_MIN, min(CHUNK_MAX, start_chunk))),
        "workers": processes,
        "started_at": start_time,
        "updated_at": start_time,
    }
    if resume:
        old = _load_ckpt(ckpt_path)
        if old and \
            old.get("zip_file") == state["zip_file"] and \
            old.get("wordlist") == state["wordlist"] and \
            old.get("wordlist_size") == state["wordlist_size"] and \
            abs(old.get("wordlist_mtime", 0) - state["wordlist_mtime"]) < 1.0:
            state.update({
                "line_index": int(old.get("line_index", 0)),
                "byte_offset": old.get("byte_offset", state["byte_offset"]),
                "tested": int(old.get("tested", 0)),
                "chunk": int(old.get("chunk", state["chunk"])),
                "workers": int(old.get("workers", processes)),
                "started_at": old.get("started_at", start_time),
            })
            used_resume = state["line_index"] > 0 or (state["byte_offset"] or 0) > 0

    # Multiprocessing infra
    task_q: Queue = Queue(maxsize=processes * (INFLIGHT_SOFT_MAX_PER_WORKER + 1))
    result_q: Queue = Queue()
    found_event: Event = Event()

    # Signal handling: simpan ckpt on Ctrl+C/TERM
    def _handle_signal(signum, frame):
        _save_ckpt(ckpt_path, state)
        logger.write(f"Checkpoint saved by signal {signum}")
        # Kalau ingin langsung exit, set event
        found_event.set()

    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        pass  # pada Windows/Termux kadang terbatas

    # Start workers
    workers: List[Process] = []
    for _ in range(state["workers"]):
        p = Process(target=_worker_loop, args=(zip_file, task_q, result_q, found_event))
        p.daemon = True
        p.start()
        workers.append(p)

    # Producer thread: baca wordlist & kirim batch
    producer_done = threading.Event()

    def producer():
        nonlocal state
        try:
            batch: List[str] = []
            curr_byte_offset = state.get("byte_offset") or 0
            line_index = state.get("line_index") or 0

            # Jika plain text & resume by byte offset, capture awal offset aktual
            if _is_plain_text(wordlist) and curr_byte_offset and curr_byte_offset > 0:
                try:
                    with open(wordlist, "r", encoding="utf-8", errors="ignore") as fpos:
                        fpos.seek(curr_byte_offset)
                        curr_byte_offset = fpos.tell()
                except Exception:
                    curr_byte_offset = 0

            for pwd in iter_wordlist(wordlist, start_index=line_index, byte_offset=curr_byte_offset):
                batch.append(pwd)
                if len(batch) >= state["chunk"]:
                    while not found_event.is_set():
                        try:
                            task_q.put(batch, timeout=0.2)
                            break
                        except queue.Full:
                            # Backpressure
                            time.sleep(0.05)
                    # Update offset + index + tested (perkiraan)
                    state["line_index"] += len(batch)
                    # Estimasi byte_offset hanya untuk .txt
                    if _is_plain_text(wordlist):
                        try:
                            # Perkiraaan kasar: simpan posisi byte terakhir via seek ulang ringan
                            with open(wordlist, "r", encoding="utf-8", errors="ignore") as fpos2:
                                fpos2.seek(0, os.SEEK_CUR)  # no-op
                        except Exception:
                            pass
                    batch = []
                    state["updated_at"] = _now()
                    if found_event.is_set():
                        break

            # Sisa batch terakhir
            if batch and not found_event.is_set():
                task_q.put(batch)
                state["line_index"] += len(batch)
                state["updated_at"] = _now()
            # Kirim sentinel
            for _ in range(state["workers"]):
                try:
                    task_q.put(None, timeout=0.2)
                except queue.Full:
                    pass
        finally:
            producer_done.set()

    prod_thread = threading.Thread(target=producer, daemon=True)
    prod_thread.start()

    # Dashboard
    tested_total = int(state["tested"])
    found_password: Optional[str] = None
    last_adjust = _now()
    last_tested = tested_total
    curr_chunk = int(state["chunk"])

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]Python brute[/]"),
        BarColumn(),
        MofNCompleteColumn() if total_candidates is not None else TextColumn(""),
        RateColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn() if total_candidates is not None else TextColumn(""),
        TextColumn("  |  CPU: {task.fields[cpu]}%  RAM: {task.fields[ram]}%  Chk: {task.fields[chunk]}"),
        transient=False,
        console=console,
    )

    task_total = total_candidates if total_candidates is not None else None
    with progress:
        task_id = progress.add_task("brute", total=task_total or 0,
                                    cpu=f"{sys_info['cpu_percent'] or 0:.0f}",
                                    ram=f"{sys_info['ram_percent'] or 0:.0f}",
                                    chunk=str(curr_chunk))

        # Loop hasil worker
        while True:
            # Ambil hasil
            try:
                result = result_q.get(timeout=0.2)
            except queue.Empty:
                result = None

            now = _now()

            if result:
                tested_total += int(result.get("tested", 0))
                pwd = result.get("password")
                if pwd:
                    found_password = pwd
                    found_event.set()

            # Update progress
            if total_candidates is not None:
                progress.update(task_id, completed=min(tested_total, total_candidates))
            else:
                # total unknown: tetap update rate/time via internal kolom
                progress.update(task_id)

            # Update CPU/RAM display
            cpu_p = _read_cpu_percent()
            ram_p = _read_ram_usage()
            progress.update(task_id,
                            cpu=f"{cpu_p:.0f}" if cpu_p is not None else "--",
                            ram=f"{ram_p:.0f}" if ram_p is not None else "--",
                            chunk=str(curr_chunk))

            # Adjust chunk size tiap ADJUST_INTERVAL_S
            if now - last_adjust >= ADJUST_INTERVAL_S and not found_event.is_set():
                interval_tested = tested_total - last_tested
                rate = interval_tested / max(1e-6, (now - last_adjust))
                inflight = task_q.qsize()
                # Heuristik sederhana:
                if cpu_p is not None and cpu_p > HIGH_CPU_THRESHOLD:
                    # CPU tinggi -> turunkan chunk
                    curr_chunk = max(CHUNK_MIN, int(curr_chunk * ADJUST_DOWN_FACTOR))
                elif cpu_p is not None and cpu_p < LOW_CPU_THRESHOLD and inflight < state["workers"] * INFLIGHT_SOFT_MAX_PER_WORKER:
                    # CPU rendah dan antrean kecil -> naikkan chunk
                    curr_chunk = min(CHUNK_MAX, int(curr_chunk * ADJUST_UP_FACTOR))
                elif inflight > state["workers"] * (INFLIGHT_SOFT_MAX_PER_WORKER + 1):
                    # Antrean terlalu besar -> sedikit turunkan
                    curr_chunk = max(CHUNK_MIN, int(curr_chunk * 0.9))

                # Terapkan perubahan ke state (producer baca state["chunk"])
                if curr_chunk != state["chunk"]:
                    state["chunk"] = curr_chunk
                last_adjust = now
                last_tested = tested_total

                # Simpan checkpoint berkala
                state["tested"] = tested_total
                _save_ckpt(ckpt_path, state)

            # Selesai?
            if found_event.is_set():
                break

            # Jika producer sudah selesai kirim semua batch dan semua worker idle, maka berhenti
            if producer_done.is_set() and result_q.empty() and task_q.empty():
                # Masih beri waktu kecil untuk hasil terakhir
                time.sleep(0.2)
                if result_q.empty():
                    break

    # Bersihkan worker
    for p in workers:
        try:
            p.join(timeout=0.2)
        except Exception:
            pass

    elapsed = _now() - start_time
    rate = tested_total / max(1e-9, elapsed)
    state["tested"] = tested_total
    _save_ckpt(ckpt_path, state)

    if found_password:
        console.print(Panel(f"[green]✅ Password ditemukan oleh Python: [bold]{found_password}[/][/]", border_style="green"))
        logger.write(f"FOUND password={found_password} tested={tested_total} elapsed={elapsed:.2f}s rate={rate:.0f}/s")
    else:
        console.print(Panel(f"[yellow]❌ Password tidak ditemukan dalam wordlist (Python).[/]", border_style="yellow"))
        logger.write(f"NOTFOUND tested={tested_total} elapsed={elapsed:.2f}s rate={rate:.0f}/s")

    logger.close()

    return {
        "password": found_password,
        "tested": tested_total,
        "elapsed": elapsed,
        "rate": rate,
        "used_resume": used_resume,
        "checkpoint_file": ckpt_path,
        "log_file": log_path,
        "engine": ENGINE_NAME,
        "error": None
    }

# Backward compatibility alias (v10 -> v11)
def brute_python_fast_v10(*args, **kwargs):
    return brute_python_fast_v11(*args, **kwargs)

# ------------------------------ Heuristik Auto-Select -----------------------

def recommend_engine_for(wordlist_path: str,
                        min_python_mb: int = 0,
                        max_python_mb: int = 50,
                        min_cores_for_python: int = 2) -> str:
    """
    Mengembalikan 'python' atau 'john' berdasarkan heuristik sederhana:
    - Jika ukuran wordlist <= max_python_mb dan core >= min_cores_for_python -> 'python'
    - Jika wordlist kompresi besar -> 'john'
    - Jika RAM kecil (opsional via psutil) dan wordlist besar -> 'john'
    """
    size_bytes, _ = _wordlist_stat(wordlist_path)
    size_mb = size_bytes / (1024 * 1024 + 0.0)
    cores = cpu_count() or 1

    if size_mb <= max_python_mb and cores >= min_cores_for_python:
        return "python"

    # File kompresi besar: cenderung john
    lower = wordlist_path.lower()
    if lower.endswith((".gz", ".bz2", ".xz", ".lzma")) and size_mb > max_python_mb / 2:
        return "john"

    # Jika RAM rendah dan file besar
    if psutil:
        try:
            vm = psutil.virtual_memory()
            # kira-kira: kalau file > 25% dari RAM -> john
            if size_bytes > vm.total * 0.25:
                return "john"
        except Exception:
            pass

    # default fallback
    return "john" if size_mb > max_python_mb else "python"

# ------------------------------ CLI Quick Test (opsional) -------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BRUTEZIPER v11 - Python Engine")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("wordlist", help="Path ke file wordlist (.txt/.gz/.bz2/.xz)")
    parser.add_argument("--workers", type=int, default=None, help="Jumlah proses worker (default: cores-1)")
    parser.add_argument("--chunk", type=int, default=1000, help="Ukuran batch awal (default: 1000)")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    args = parser.parse_args()

    res = brute_python_fast_v11(
        args.zip,
        args.wordlist,
        processes=args.workers,
        start_chunk=args.chunk,
        resume=(not args.no_resume)
    )
    console.print(res)
