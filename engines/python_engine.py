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
# Catatan:
# - File ini adalah versi advanced (asli ±722 baris) yang dipertahankan
#   logika & performanya, dengan UI di-refactor agar memakai:
#     * ui/panels.py  -> panel_info/panel_success/panel_warning/panel_error/panel_stage
#     * ui/dashboard.py -> Dashboard (Progress + CPU/RAM + ETA)
# - Tidak mengubah algoritma; hanya mengganti panggilan UI.
# -------------------------------------------------------------

from __future__ import annotations

import os
import io
import sys
import time
import math
import json
import gzip
import bz2
import lzma
import mmap
import queue
import signal
import typing as t
import threading
import multiprocessing
from dataclasses import dataclass, asdict
from datetime import datetime

# Optional dependencies
try:
    import pyzipper  # AES/ZipCrypto
except Exception as _:
    pyzipper = None

# psutil opsional
try:
    import psutil
except Exception:
    psutil = None

# === UI (Refactor) ===
from ui.panels import (
    panel_info,
    panel_success,
    panel_warning,
    panel_error,
    panel_stage,
)
from ui.dashboard import Dashboard

# ------------------------------ Konstanta ----------------------------------

ENGINE_NAME = "python"
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

CKPT_SUFFIX = ".py_ckpt.json"

READ_CHUNK_BYTES = 1024 * 1024  # 1MB
CHUNK_MIN = 200
CHUNK_MAX = 20_000

# Adaptive tuning
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

def get_system_info() -> dict:
    info = {
        "cpu_percent": None,
        "ram_percent": None,
        "cores": multiprocessing.cpu_count(),
    }
    if psutil:
        try:
            info["cpu_percent"] = psutil.cpu_percent(interval=0.0)
            info["ram_percent"] = psutil.virtual_memory().percent
        except Exception:
            pass
    return info

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

# ------------------------------ Wordlist Reader ----------------------------

def _open_text_maybe_compressed(path: str) -> t.IO[str]:
    """
    Buka file teks (bisa gzip/bz2/xz) sebagai text-mode stream utf-8.
    """
    lower = path.lower()
    if lower.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="ignore")
    if lower.endswith(".bz2"):
        return io.TextIOWrapper(bz2.open(path, "rb"), encoding="utf-8", errors="ignore")
    if lower.endswith(".xz") or lower.endswith(".lzma"):
        return io.TextIOWrapper(lzma.open(path, "rb"), encoding="utf-8", errors="ignore")
    return open(path, "r", encoding="utf-8", errors="ignore")

def count_lines_fast(path: str) -> t.Optional[int]:
    """
    Hitung jumlah baris wordlist. Untuk file terkompresi mungkin lambat -> kembalikan None.
    """
    lower = path.lower()
    if lower.endswith((".gz", ".bz2", ".xz", ".lzma")):
        return None
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return None

# ------------------------------ ZIP Tester ---------------------------------

@dataclass
class ZipTestResult:
    ok: bool
    error: t.Optional[str] = None
    is_encrypted: bool = True

class ZipTester:
    """
    Abstraksi untuk mengetes password pada ZIP (AES/ZipCrypto).
    """
    def __init__(self, zip_path: str):
        self.zip_path = zip_path
        self.is_encrypted = True
        self.probed = False

    def probe_encryption(self) -> ZipTestResult:
        if self.probed:
            return ZipTestResult(ok=True, is_encrypted=self.is_encrypted)
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                for zinfo in zf.infolist():
                    # jika tidak terenkripsi?
                    if not zinfo.flag_bits & 0x1:
                        self.is_encrypted = False
                        break
            self.probed = True
            return ZipTestResult(ok=True, is_encrypted=self.is_encrypted)
        except Exception as e:
            # sebagian ZIP bisa error dibuka tanpa password; anggap terenkripsi
            self.probed = True
            return ZipTestResult(ok=True, is_encrypted=True, error=str(e))

    def test_password(self, password: str) -> bool:
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                zf.pwd = password.encode("utf-8", "ignore")
                # testzip akan raise jika salah
                zf.testzip()
            return True
        except Exception:
            return False

# ------------------------------ Checkpoint ---------------------------------

@dataclass
class CheckpointState:
    line_index: int = 0          # baris terakhir (0-based)
    byte_offset: int = 0         # untuk resume cepat pada file besar
    chunk: int = 1000
    tested: int = 0
    workers: int = 1

def _ckpt_name(zip_file: str, wordlist: str) -> str:
    base = os.path.basename(zip_file)
    wbase = os.path.basename(wordlist)
    return f"{base}.{wbase}{CKPT_SUFFIX}"

def _load_ckpt(path: str) -> t.Optional[CheckpointState]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        return CheckpointState(**data)
    except Exception:
        return None

def _save_ckpt(path: str, st: CheckpointState | dict):
    try:
        if isinstance(st, CheckpointState):
            data = asdict(st)
        else:
            data = dict(st)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# ------------------------------ Producer/Worker ----------------------------

@dataclass
class Task:
    passwords: list[str]
    batch_id: int

@dataclass
class Result:
    tested: int
    password: t.Optional[str] = None

def _worker_main(zip_path: str,
                task_q: multiprocessing.Queue,
                result_q: multiprocessing.Queue,
                found_event: multiprocessing.Event):
    """
    Worker proses: terima batch passwords, uji satu per satu, laporkan jika ketemu/selesai.
    """
    tester = ZipTester(zip_path)
    while not found_event.is_set():
        try:
            task: Task | None = task_q.get(timeout=0.2)
        except queue.Empty:
            continue
        if task is None:  # sentinel
            break

        found = None
        for pw in task.passwords:
            if found_event.is_set():
                break
            if tester.test_password(pw):
                found = pw
                found_event.set()
                break

        result_q.put(Result(tested=len(task.passwords), password=found))

# ------------------------------ Engine Utama --------------------------------

def brute_python_fast_v11(zip_file: str,
                        wordlist: str,
                        processes: t.Optional[int] = None,
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

    # UI – header (refactor ke panel_stage)
    panel_stage(
        f"[bold cyan]BRUTEZIPER v11 – Python Engine[/]\n"
        f"[white]📦 ZIP      :[/] {os.path.basename(zip_file)}\n"
        f"[white]📝 Wordlist :[/] {os.path.basename(wordlist)}\n",
        color="cyan"
    )

    # Inisialisasi log
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)
    logger.write(f"START engine={ENGINE_NAME} zip={zip_file} wordlist={wordlist} "
                f"workers={processes} start_chunk={start_chunk} resume={resume}")

    # Dependensi
    if pyzipper is None:
        msg = "pyzipper tidak terpasang. `pip install pyzipper`"
        panel_error(msg)
        logger.write(f"ERROR {msg}")
        logger.close()
        return {"password": "", "tested": 0, "elapsed": 0.0, "rate": 0.0,
                "used_resume": False, "checkpoint_file": None,
                "log_file": log_path, "engine": ENGINE_NAME, "error": msg}

    # Probe enkripsi
    tester_probe = ZipTester(zip_file).probe_encryption()
    if not tester_probe.ok and tester_probe.error:
        panel_error(str(tester_probe.error))
        logger.write(f"ERROR {tester_probe.error}")
        logger.close()
        return {"password": "", "tested": 0, "elapsed": 0.0, "rate": 0.0,
                "used_resume": False, "checkpoint_file": None,
                "log_file": log_path, "engine": ENGINE_NAME, "error": tester_probe.error}

    if not tester_probe.is_encrypted:
        panel_warning("ZIP tidak terenkripsi. Tidak perlu brute.")
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
    state = {
        "line_index": 0,
        "byte_offset": 0,
        "chunk": max(CHUNK_MIN, min(start_chunk, CHUNK_MAX)),
        "tested": 0,
        "workers": processes,
    }
    if resume:
        ckpt = _load_ckpt(ckpt_path)
        if ckpt:
            state["line_index"] = ckpt.line_index
            state["byte_offset"] = ckpt.byte_offset
            state["chunk"] = max(CHUNK_MIN, min(ckpt.chunk or start_chunk, CHUNK_MAX))
            state["tested"] = ckpt.tested
            state["workers"] = processes
            used_resume = True
            panel_info(f"🔁 Resume dari checkpoint: line={format_int(ckpt.line_index)} "
                    f"(~tested {format_int(ckpt.tested)})")

    # Siapkan queue & worker
    task_q: multiprocessing.Queue = multiprocessing.Queue(maxsize=processes * INFLIGHT_SOFT_MAX_PER_WORKER)
    result_q: multiprocessing.Queue = multiprocessing.Queue()
    found_event = multiprocessing.Event()

    workers: list[multiprocessing.Process] = []
    for wid in range(processes):
        p = multiprocessing.Process(
            target=_worker_main,
            args=(zip_file, task_q, result_q, found_event),
            daemon=True
        )
        p.start()
        workers.append(p)

    # Signal handler untuk save ckpt saat Ctrl+C
    stop_requested = {"flag": False}

    def _sigint_handler(signum, frame):
        stop_requested["flag"] = True
        panel_warning("SIGINT diterima: menyimpan checkpoint & berhenti...")
    old_handler = signal.signal(signal.SIGINT, _sigint_handler)

    # Producer (membaca wordlist & mengisi task_q)
    producer_done = threading.Event()

    def producer():
        line_idx = int(state["line_index"])
        byte_offset = int(state["byte_offset"])
        curr_chunk = int(state["chunk"])
        batch_id = 0

        try:
            # Buka file (streaming)
            f = _open_text_maybe_compressed(wordlist)

            # Fast seek by byte_offset untuk resume file besar (hanya untuk file plain)
            if hasattr(f, "buffer") and byte_offset > 0 and not wordlist.lower().endswith((".gz", ".bz2", ".xz", ".lzma")):
                try:
                    f_detached = f.detach()
                    f_detached.seek(byte_offset, io.SEEK_SET)
                    f = io.TextIOWrapper(f_detached, encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            # Skip baris sesuai checkpoint
            skipped = 0
            while skipped < line_idx:
                if not f.readline():
                    break
                skipped += 1

            while not found_event.is_set() and not stop_requested["flag"]:
                # Batasi in-flight
                while task_q.qsize() > processes * INFLIGHT_SOFT_MAX_PER_WORKER and not found_event.is_set():
                    time.sleep(0.02)

                # Susun batch
                pw_batch = []
                for _ in range(curr_chunk):
                    line = f.readline()
                    if not line:
                        break
                    pw = line.rstrip("\r\n")
                    pw_batch.append(pw)
                    line_idx += 1

                if not pw_batch:
                    break

                try:
                    task_q.put(Task(passwords=pw_batch, batch_id=batch_id), timeout=0.2)
                    batch_id += 1
                except queue.Full:
                    # coba lagi
                    time.sleep(0.05)
                    continue

                # Simpan posisi file untuk ckpt
                try:
                    if hasattr(f, "buffer"):
                        raw = f.buffer
                        if hasattr(raw, "tell"):
                            byte_offset = raw.tell()
                except Exception:
                    pass

                # Sync state untuk dashboard & ckpt
                state["line_index"] = line_idx
                state["byte_offset"] = byte_offset
                state["chunk"] = curr_chunk

                # Adaptasi sederhana (prod side): kalau antrean penuh, kecilkan chunk
                if task_q.qsize() >= processes * INFLIGHT_SOFT_MAX_PER_WORKER:
                    curr_chunk = max(CHUNK_MIN, int(curr_chunk * 0.9))

                # Jika stop diminta, break
                if stop_requested["flag"]:
                    break

        except Exception as e:
            panel_error(str(e))
        finally:
            producer_done.set()

    prod_thread = threading.Thread(target=producer, daemon=True)
    prod_thread.start()

    # Dashboard
    tested_total = int(state["tested"])
    found_password: t.Optional[str] = None
    last_adjust = _now()
    last_tested = tested_total
    curr_chunk = int(state["chunk"])

    task_total = total_candidates if total_candidates is not None else None
    with Dashboard(total=task_total, label="Python brute") as dash:

        # Loop hasil worker
        while True:
            # Ambil hasil
            try:
                result: Result | None = result_q.get(timeout=0.2)
            except queue.Empty:
                result = None

            now = _now()

            if result:
                tested_total += int(result.tested or 0)
                if result.password:
                    found_password = result.password
                    found_event.set()

            # Update dashboard
            dash.update(completed=min(tested_total, total_candidates) if total_candidates is not None else tested_total)

            # Adaptive tuning (tiap ADJUST_INTERVAL_S)
            if now - last_adjust >= ADJUST_INTERVAL_S:
                # Rate
                elapsed = max(1e-6, now - start_time)
                rate = tested_total / elapsed

                # CPU/RAM
                cpu = None
                if psutil:
                    try:
                        cpu = psutil.cpu_percent(interval=0.0)
                    except Exception:
                        cpu = None

                # Naik/turun chunk berdasarkan CPU & rate delta
                delta = tested_total - last_tested
                if cpu is not None:
                    if cpu < LOW_CPU_THRESHOLD and delta > 0:
                        curr_chunk = min(CHUNK_MAX, int(curr_chunk * ADJUST_UP_FACTOR))
                    elif cpu > HIGH_CPU_THRESHOLD:
                        curr_chunk = max(CHUNK_MIN, int(curr_chunk * ADJUST_DOWN_FACTOR))

                # Jika rate stagnan, kecilkan sedikit
                if delta < curr_chunk // 2:
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
    rate = tested_total / elapsed if elapsed > 0 else 0.0

    # Pulihkan signal handler
    try:
        signal.signal(signal.SIGINT, old_handler)
    except Exception:
        pass

    # Tuliskan hasil + log
    if found_password:
        panel_success(f"Password ditemukan oleh Python: {found_password}")
        logger.write(f"FOUND pw='{found_password}' tested={tested_total} elapsed={elapsed:.2f}s rate={rate:.0f}/s")
        # Save final checkpoint
        state["tested"] = tested_total
        _save_ckpt(ckpt_path, state)
    else:
        panel_warning("Password tidak ditemukan dalam wordlist (Python).")
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

# ------------------------------ Rekomendasi Engine --------------------------

def recommend_engine_for(wordlist_path: str,
                        max_python_mb: int = 50) -> str:
    """
    Heuristik sederhana untuk pilih engine.
    - File kecil (< 5MB) → python
    - File menengah (5-50MB) → hybrid
    - File sangat besar (> 50MB) → john
    - Jika file kompresi & cukup besar → john
    - Jika RAM kecil vs file besar → john
    """
    try:
        size_bytes = os.path.getsize(wordlist_path)
    except Exception:
        return "hybrid"

    size_mb = size_bytes / (1024 * 1024)

    if size_mb < 5:
        return "python"
    if size_mb < max_python_mb:
        return "hybrid"

    # Jika file kompresi cukup besar → john
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
    return "john"

# ------------------------------ Back-Compat Alias ---------------------------

def brute_python_fast_v10(zip_file: str, wordlist: str, processes: t.Optional[int] = None,
                        start_chunk: int = 1000, resume: bool = True) -> dict:
    """
    Alias ke v11 (kompatibel ke belakang).
    """
    return brute_python_fast_v11(zip_file, wordlist, processes, start_chunk, resume)

# ------------------------------ CLI Quick Test ------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BRUTEZIPER v11 - Python Engine (Advanced, UI Refactor)")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("wordlist", help="Path ke file wordlist (.txt)")
    parser.add_argument("--workers", type=int, default=None, help="Jumlah proses worker (default: cores-1)")
    parser.add_argument("--chunk", type=int, default=1000, help="Ukuran batch awal")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    args = parser.parse_args()

    res = brute_python_fast_v11(
        args.zip,
        args.wordlist,
        processes=args.workers,
        start_chunk=args.chunk,
        resume=(not args.no_resume)
    )
    # Ringkas saja di CLI
    print(res)
