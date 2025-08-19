# engines/python_engine.py
# BRUTEZIPER – Python Engine v11 (Advanced, UI Refactor)
# ------------------------------------------------------------------
# Fitur Utama:
# - Multiprocess producer/consumer (task/result queue) dengan stop-event.
# - Adaptive chunk (berdasarkan CPU & throughput) dgn batas min/max.
# - Resume canggih: simpan line_index + byte_offset + tested + chunk.
# - Wordlist besar &/atau terkompresi (.gz/.bz2/.xz) via streaming.
# - Logging ke file, checkpoint periodik & on-signal (Ctrl+C).
# - UI modern: ui.panels + ui.dashboard (konsisten dgn john/hybrid).
# - Heuristik rekomendasi engine + alias v10 -> v11 (back-compat).
#
# Dependensi:
# - pyzipper (AES/ZipCrypto)  -> pip install pyzipper
# - psutil (opsional untuk CPU/RAM/Suhu) -> pip install psutil
#
# Catatan:
# - Fokus perubahan dibanding v10: layer UI saja (logic dipertahankan).
# ------------------------------------------------------------------

from __future__ import annotations

import os
import io
import sys
import time
import json
import gzip
import bz2
import lzma
import queue
import signal
import typing as t
import threading
import multiprocessing
from dataclasses import dataclass, asdict
from datetime import datetime

# === Optional deps ===
try:
    import pyzipper  # untuk ZIP AES + ZipCrypto
except Exception:
    pyzipper = None

try:
    import psutil
except Exception:
    psutil = None

# === UI (baru) ===
from ui.panels import panel_info, panel_success, panel_warning, panel_error, panel_stage
from ui.dashboard import Dashboard

# === Utils (baru) ===
from utils.file_ops import file_size as _file_size
from utils.file_ops import count_lines as _count_lines_plain
from utils.file_ops import yield_passwords as _yield_pw_plain
from utils.sysinfo import get_sysinfo as _get_sysinfo

# ------------------------------ Konstanta -----------------------------------

ENGINE_NAME = "python"
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

CKPT_SUFFIX = ".py_ckpt.json"
LOG_PREFIX = "python"

CHUNK_MIN = 200
CHUNK_MAX = 20_000
DEFAULT_START_CHUNK = 1_000

ADJUST_WIN_SEC = 2.0
ADJUST_UP = 1.25
ADJUST_DOWN = 0.85
CPU_LOW = 35.0
CPU_HIGH = 85.0
QUEUE_INFLIGHT_SOFT = 3  # per worker

# ------------------------------ Helper umum ---------------------------------

def _now() -> float:
    return time.time()

def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def _mk_log_file(zip_file: str) -> str:
    base = os.path.splitext(os.path.basename(zip_file))[0]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(DEFAULT_LOG_DIR, f"{LOG_PREFIX}_{base}_{ts}.log")

class Logger:
    def __init__(self, path: str):
        self.path = path
        self._fh = open(self.path, "a", encoding="utf-8", errors="ignore")

    def write(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._fh.write(f"[{ts}] {msg}\n")
        self._fh.flush()

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass

# --------------------------- Wordlist & Reader ------------------------------

def _open_text_any(path: str) -> t.IO[str]:
    """
    Buka wordlist: txt / .gz / .bz2 / .xz sebagai text stream utf-8.
    """
    lower = path.lower()
    if lower.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="ignore")
    if lower.endswith(".bz2"):
        return io.TextIOWrapper(bz2.open(path, "rb"), encoding="utf-8", errors="ignore")
    if lower.endswith((".xz", ".lzma")):
        return io.TextIOWrapper(lzma.open(path, "rb"), encoding="utf-8", errors="ignore")
    return open(path, "r", encoding="utf-8", errors="ignore")

def _is_compressed(path: str) -> bool:
    lower = path.lower()
    return lower.endswith((".gz", ".bz2", ".xz", ".lzma"))

def _count_lines_smart(path: str) -> t.Optional[int]:
    """
    Hitung baris cepat untuk file plain. Untuk file kompresi -> None (biar nggak lambat).
    """
    if _is_compressed(path):
        return None
    try:
        return _count_lines_plain(path)
    except Exception:
        return None

# NOTE: currently unused by python_engine,
# but kept for potential reuse by hybrid_engine or CLI tools.
def _yield_passwords_smart(path: str, start_index: int = 0) -> t.Generator[str, None, None]:
    """
    Generator password. Untuk file plain gunakan util; compress pakai reader internal.
    """
    if not _is_compressed(path):
        yield from _yield_pw_plain(path, start_index)
        return

    with _open_text_any(path) as f:
        for i, line in enumerate(f):
            if i < start_index:
                continue
            yield line.rstrip("\r\n")

# --------------------------- ZIP Tester -------------------------------------

@dataclass
class ZipTestResult:
    ok: bool
    is_encrypted: bool
    error: t.Optional[str] = None

class ZipTester:
    def __init__(self, zip_path: str):
        self.zip_path = zip_path

    def probe(self) -> ZipTestResult:
        """
        Cek apakah ZIP terenkripsi. Jika pyzipper raising saat probe, anggap terenkripsi.
        """
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                for zinfo in zf.infolist():
                    if not (zinfo.flag_bits & 0x1):
                        return ZipTestResult(ok=True, is_encrypted=False)
            return ZipTestResult(ok=True, is_encrypted=True)
        except Exception as e:
            # Banyak file terenkripsi akan raise disini tanpa password, ini normal
            return ZipTestResult(ok=True, is_encrypted=True, error=str(e))

    def test(self, password: str) -> bool:
        try:
            with pyzipper.AESZipFile(self.zip_path) as zf:
                zf.pwd = password.encode("utf-8", "ignore")
                zf.testzip()  # akan raise jika salah
            return True
        except Exception:
            return False

# --------------------------- Checkpoint (Resume) ----------------------------

@dataclass
class CheckpointState:
    line_index: int = 0
    byte_offset: int = 0
    tested: int = 0
    chunk: int = DEFAULT_START_CHUNK
    workers: int = 1

def _ckpt_path(zip_file: str, wordlist: str) -> str:
    z = os.path.basename(zip_file)
    w = os.path.basename(wordlist)
    return f"{z}.{w}{CKPT_SUFFIX}"

def _ckpt_load(path: str) -> t.Optional[CheckpointState]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        return CheckpointState(**data)
    except Exception:
        return None

def _ckpt_save(path: str, st: CheckpointState | dict):
    try:
        data = asdict(st) if isinstance(st, CheckpointState) else dict(st)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# --------------------------- Multiprocess Worker ----------------------------

@dataclass
class Task:
    batch_id: int
    passwords: list[str]

@dataclass
class Result:
    tested: int
    password: t.Optional[str] = None

def _worker_main(
    zip_path: str,
    task_q: multiprocessing.Queue,
    result_q: multiprocessing.Queue,
    found_event: t.Event,
):
    tester = ZipTester(zip_path)
    while not found_event.is_set():
        try:
            task: Task | None = task_q.get(timeout=0.2)
        except queue.Empty:
            continue
        if task is None:
            break

        hit = None
        for pw in task.passwords:
            if found_event.is_set():
                break
            if tester.test(pw):
                hit = pw
                found_event.set()
                break

        result_q.put(Result(tested=len(task.passwords), password=hit))

# --------------------------- Engine Utama -----------------------------------

def brute_python_fast_v11(
    zip_file: str,
    wordlist: str,
    processes: t.Optional[int] = None,
    start_chunk: int = DEFAULT_START_CHUNK,
    resume: bool = True,
) -> dict:
    """
    Brute-force ZIP dengan Python wordlist:
        - Multiprocess queue
        - Adaptive chunk
        - Resume canggih (line_index + byte_offset + tested + chunk)
        - Logging + UI dashboard
    """
    t0 = _now()

    # ---- UI header
    panel_stage(
        f"[bold cyan]BRUTEZIPER – Python Engine[/]\n"
        f"[white]📦 ZIP       :[/] {os.path.basename(zip_file)}\n"
        f"[white]📝 Wordlist  :[/] {os.path.basename(wordlist)}",
        color="cyan",
    )

    # ---- logging
    log_path = _mk_log_file(zip_file)
    logger = Logger(log_path)
    logger.write(f"START engine={ENGINE_NAME} zip={zip_file} wordlist={wordlist}")

    # ---- deps check
    if pyzipper is None:
        msg = "pyzipper tidak terpasang. Install: pip install pyzipper"
        panel_error(msg)
        logger.write(f"ERROR {msg}")
        logger.close()
        return _ret("", 0, _now() - t0, 0.0, False, None, log_path, msg)

    # ---- probe zip
    probe = ZipTester(zip_file).probe()
    if not probe.ok and probe.error:
        panel_error(f"Gagal probe ZIP: {probe.error}")
        logger.write(f"ERROR probe: {probe.error}")
        logger.close()
        return _ret("", 0, _now() - t0, 0.0, False, None, log_path, probe.error)

    if not probe.is_encrypted:
        panel_warning("ZIP tidak terenkripsi. Tidak perlu brute.")
        logger.write("ZIP not encrypted")
        logger.close()
        return _ret("", 0, _now() - t0, 0.0, False, None, log_path, None)

    # ---- core & proses
    cores = (psutil.cpu_count(logical=True) if psutil else multiprocessing.cpu_count())
    if processes is None:
        processes = max(1, (cores or 2) - 1)

    # ---- total kandidat (opsional)
    total_candidates = _count_lines_smart(wordlist)

    # ---- checkpoint
    ckpt = _ckpt_path(zip_file, wordlist)
    used_resume = False
    state: dict[str, int] = {
        "line_index": 0,
        "byte_offset": 0,
        "tested": 0,
        "chunk": max(CHUNK_MIN, min(start_chunk, CHUNK_MAX)),
        "workers": processes,
    }
    if resume:
        prev = _ckpt_load(ckpt)
        if prev:
            state["line_index"] = prev.line_index
            state["byte_offset"] = prev.byte_offset
            state["tested"] = prev.tested
            state["chunk"] = max(CHUNK_MIN, min(prev.chunk, CHUNK_MAX))
            used_resume = True
            panel_info(
                f"🔁 Resume checkpoint: line={_fmt_int(prev.line_index)} | tested≈{_fmt_int(prev.tested)} | chunk={prev.chunk}"
            )
            logger.write(f"RESUME ckpt @ line={prev.line_index} tested={prev.tested} chunk={prev.chunk}")

    # ---- queues & workers
    task_q: multiprocessing.Queue = multiprocessing.Queue(maxsize=processes * QUEUE_INFLIGHT_SOFT)
    result_q: multiprocessing.Queue = multiprocessing.Queue()
    found_event = multiprocessing.Event()

    workers: list[multiprocessing.Process] = []
    for wid in range(processes):
        p = multiprocessing.Process(
            target=_worker_main,
            args=(zip_file, task_q, result_q, found_event),
            daemon=True,
        )
        p.start()
        workers.append(p)

    # ---- SIGINT → save ckpt + stop
    stop_flag = {"stop": False}

    def _sigint(signum, frame):
        stop_flag["stop"] = True
        panel_warning("SIGINT diterima. Menyimpan checkpoint & menghentikan…")

    old_sig = signal.signal(signal.SIGINT, _sigint)

    # ---- Producer thread
    producer_done = threading.Event()

    def producer():
        line_idx = int(state["line_index"])
        curr_chunk = int(state["chunk"])
        batch_id = 0

        try:
            f = _open_text_any(wordlist)

            # fast-seek by byte_offset (hanya untuk file plain-text)
            if not _is_compressed(wordlist) and state["byte_offset"] > 0:
                try:
                    raw = f.detach()
                    raw.seek(state["byte_offset"], io.SEEK_SET)
                    f = io.TextIOWrapper(raw, encoding="utf-8", errors="ignore")
                except Exception:
                    # kalau gagal detach/seek, fallback lanjut line skip
                    pass

            # skip baris sesuai checkpoint
            skipped = 0
            while skipped < line_idx:
                if not f.readline():
                    break
                skipped += 1

            while not found_event.is_set() and not stop_flag["stop"]:
                # kontrol antrean (jangan terlalu penuh)
                while task_q.qsize() >= processes * QUEUE_INFLIGHT_SOFT and not found_event.is_set():
                    time.sleep(0.02)

                batch: list[str] = []
                for _ in range(curr_chunk):
                    line = f.readline()
                    if not line:
                        break
                    pw = line.rstrip("\r\n")
                    batch.append(pw)
                    line_idx += 1

                if not batch:
                    break

                try:
                    task_q.put(Task(batch_id=batch_id, passwords=batch), timeout=0.2)
                    batch_id += 1
                except queue.Full:
                    time.sleep(0.05)
                    continue

                # simpan approximate byte_offset (untuk resume cepat)
                try:
                    if hasattr(f, "buffer") and hasattr(f.buffer, "tell"):
                        state["byte_offset"] = f.buffer.tell()
                except Exception:
                    pass

                # propagate ukuran chunk adaptif dari consumer
                curr_chunk = int(state["chunk"])

                if stop_flag["stop"]:
                    break

        except Exception as e:
            panel_error(f"Producer error: {e}")
        finally:
            producer_done.set()

    prod = threading.Thread(target=producer, daemon=True)
    prod.start()

    # ---- Consumer loop + Dashboard
    tested = int(state["tested"])
    found_pw: t.Optional[str] = None
    last_adj_t = _now()
    last_count = tested

    total_for_dash = total_candidates if total_candidates is not None else None
    with Dashboard(zip_file, wordlist, processes, total_for_dash, start_at=start_chunk, label="Python Engine") as dash:
        while True:
            # ambil hasil worker
            try:
                res: Result | None = result_q.get(timeout=0.2)
            except queue.Empty:
                res = None

            if res:
                tested += int(res.tested)
                if res.password:
                    found_pw = res.password
                    found_event.set()

            # update dashboard (completed)
            dash.update(completed=min(tested, total_candidates) if total_candidates is not None else tested)

            # adaptive tuning setiap ADJUST_WIN_SEC
            now = _now()
            if now - last_adj_t >= ADJUST_WIN_SEC:
                # throughput
                delta = tested - last_count
                rate = delta / (now - last_adj_t) if now > last_adj_t else 0.0

                # CPU/RAM
                sysi = _get_sysinfo() if psutil else {"cpu_percent": None, "ram_percent": None, "temp": None}
                cpu = sysi.get("cpu_percent")

                # adjust chunk
                new_chunk = int(state["chunk"])
                if cpu is not None:
                    if cpu < CPU_LOW and delta > 0:
                        new_chunk = min(CHUNK_MAX, int(new_chunk * ADJUST_UP))
                    elif cpu > CPU_HIGH:
                        new_chunk = max(CHUNK_MIN, int(new_chunk * ADJUST_DOWN))
                # jika delta kecil dari separuh chunk → kecilkan sedikit (hindari idle/IO-bound)
                if delta < max(1, state["chunk"] // 2):
                    new_chunk = max(CHUNK_MIN, int(new_chunk * 0.9))

                if new_chunk != state["chunk"]:
                    state["chunk"] = new_chunk

                # save ckpt periodik
                state["tested"] = tested
                _ckpt_save(ckpt, state)

                last_adj_t = now
                last_count = tested

            # selesai?
            if found_event.is_set():
                break

            # producer sudah habis + antrean kosong
            if producer_done.is_set() and task_q.empty() and result_q.empty():
                # beri sedikit waktu untuk hasil terakhir
                time.sleep(0.2)
                if result_q.empty():
                    break

    # ---- tutup workers
    for p in workers:
        try:
            p.join(timeout=0.2)
        except Exception:
            pass

    # kembalikan signal handler
    try:
        signal.signal(signal.SIGINT, old_sig)
    except Exception:
        pass

    # ---- hasil akhir
    elapsed = _now() - t0
    rate_overall = tested / elapsed if elapsed > 0 else 0.0

    if found_pw:
        panel_success(f"Password ditemukan oleh Python: {found_pw}")
        logger.write(f"FOUND pw='{found_pw}' tested={tested} elapsed={elapsed:.2f}s rate={rate_overall:.0f}/s")
    else:
        panel_warning("Password tidak ditemukan dalam wordlist (Python).")
        logger.write(f"NOTFOUND tested={tested} elapsed={elapsed:.2f}s rate={rate_overall:.0f}/s")

    # save ckpt final
    state["tested"] = tested
    _ckpt_save(ckpt, state)

    logger.close()
    return _ret(found_pw or "", tested, elapsed, rate_overall, used_resume, ckpt, log_path, None)

# --------------------------- Return Helper ----------------------------------

def _ret(
    password: str,
    tested: int,
    elapsed: float,
    rate: float,
    used_resume: bool,
    ckpt_path: t.Optional[str],
    log_path: str,
    error: t.Optional[str],
) -> dict:
    return {
        "password": password or None,
        "tested": tested,
        "elapsed": elapsed,
        "rate": rate,
        "used_resume": used_resume,
        "checkpoint_file": ckpt_path,
        "log_file": log_path,
        "engine": ENGINE_NAME,
        "error": error,
    }

# --------------------------- Heuristik Engine -------------------------------

def recommend_engine_for(wordlist_path: str, max_python_mb: int = 50) -> str:
    """
    Heuristik kasar memilih engine:
        < 5 MB           -> python
        5..50 MB         -> hybrid
        > 50 MB          -> john
    Jika file kompresi & besar, condong ke john.
    Jika RAM kecil terhadap ukuran file, condong ke john.
    """
    try:
        size_b = _file_size(wordlist_path)
    except Exception:
        return "hybrid"

    size_mb = size_b / (1024 * 1024)

    if size_mb < 5:
        return "python"
    if size_mb < max_python_mb:
        return "hybrid"

    if _is_compressed(wordlist_path) and size_mb > max_python_mb / 2:
        return "john"

    if psutil:
        try:
            vm = psutil.virtual_memory()
            if size_b > vm.total * 0.25:
                return "john"
        except Exception:
            pass

    return "john"

# --------------------------- Back-compat alias ------------------------------

def brute_python_fast_v10(
    zip_file: str,
    wordlist: str,
    processes: t.Optional[int] = None,
    start_chunk: int = DEFAULT_START_CHUNK,
    resume: bool = True,
) -> dict:
    return brute_python_fast_v11(zip_file, wordlist, processes, start_chunk, resume)

# --------------------------- CLI Quick Test ---------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BRUTEZIPER – Python Engine v11 (Advanced)")
    parser.add_argument("zip", help="Path ke file .zip terenkripsi")
    parser.add_argument("wordlist", help="Path ke file wordlist (.txt/.gz/.bz2/.xz)")
    parser.add_argument("--workers", type=int, default=None, help="Jumlah proses worker (default: cores-1)")
    parser.add_argument("--chunk", type=int, default=DEFAULT_START_CHUNK, help="Ukuran batch awal")
    parser.add_argument("--no-resume", action="store_true", help="Nonaktifkan resume")
    args = parser.parse_args()

    res = brute_python_fast_v11(
        args.zip,
        args.wordlist,
        processes=args.workers,
        start_chunk=args.chunk,
        resume=(not args.no_resume),
    )
    print(res)
