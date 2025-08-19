# engines/python_engine.py
from __future__ import annotations
import os, time, threading
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

import pyzipper

from .base import BaseEngine
from ui import messages as ui
from ui import dashboard
from utils.io import (
    count_lines_fast, wordlist_stream,
    load_resume, save_resume, clear_resume,
    extract_with_password
)

# worker untuk satu chunk
def _worker_try_chunk(zip_path, pw_chunk, stop_event):
    try:
        with pyzipper.AESZipFile(zip_path) as zf:
            names = zf.namelist()
            if not names:
                return ('COUNT', len(pw_chunk))
            testfile = names[0]
            for pw in pw_chunk:
                if stop_event.is_set():
                    return ('COUNT', 0)
                try:
                    zf.setpassword(pw.encode("utf-8"))
                    with zf.open(testfile) as fp:
                        fp.read(16)
                    return ('FOUND', pw)
                except Exception:
                    pass
        return ('COUNT', len(pw_chunk))
    except Exception:
        return ('COUNT', len(pw_chunk))


class PythonEngine(BaseEngine):
    name = "python"
    mode = "wordlist"

    def __init__(self, zip_file, wordlist,
                processes=4, start_at=0,
                adaptive_chunk=1000, resume=True,
                ui_refresh=0.5, checkpoint_every=50_000):   # ⬅️ tambahin default
        super().__init__("python", zip_file, wordlist)

        self.processes = processes
        self.start_at = start_at
        self.adaptive_chunk = adaptive_chunk
        self.resume = resume
        self.ui_refresh = ui_refresh
        self.checkpoint_every = checkpoint_every   # ✅ sekarang aman

        # tracking progress
        self.remaining_total = 0
        self.tested = 0
        self.in_flight = 0

        # 🔑 fix disini
        self.stop_event = threading.Event()
        self.found_event = threading.Event()


    def run(self):
        if not os.path.exists(self.zip_file):
            ui.error(f"❌ File ZIP tidak ditemukan: {self.zip_file}")
            return None
        if not os.path.exists(self.wordlist):
            ui.error(f"❌ Wordlist tidak ditemukan: {self.wordlist}")
            return None

        total_all = count_lines_fast(self.wordlist)
        if total_all == 0:
            ui.error("⚠ Wordlist kosong")
            return None

        start_index = load_resume(self.zip_file, self.wordlist) if self.resume else -1
        start_at = max(0, start_index + 1)
        if start_at >= total_all:
            start_at = 0
        remaining_total = total_all - start_at

        ui.info(
            f"Menjalankan Python engine\n"
            f"Worker={self.processes}, AdaptiveChunk(start)={self.start_chunk}, Resume={'ON' if self.resume else 'OFF'}")

        # adaptive state
        chunk_size = self.start_chunk
        manager = mp.Manager()
        stop_event = manager.Event()

        tested = 0
        found_pw = None
        start_time = time.time()
        last_resume_save = start_at
        in_flight = 0

        # generator stream
        stream_iter = wordlist_stream(self.wordlist, start_at)

        def _async_extract(pw):
            try:
                outdir = extract_with_password(self.zip_file, pw)
                ui.success(f"✔ Semua file diekstrak ke: {outdir}")
            except Exception as e:
                ui.warning(f"⚠ Password benar tapi ekstraksi gagal:\n{e}")

        from rich.live import Live
        from ui.dashboard import render_dashboard

        with Live("", refresh_per_second=max(4, int(1/self.ui_refresh))) as live:
            while not self.stop_event.is_set():
                elapsed = time.time() - start_time
                live.update(render_dashboard(
                    zip_file=os.path.basename(self.zip_file),
                    wordlist=os.path.basename(self.wordlist),
                    processes=self.processes,
                    start_at=self.start_at,
                    remaining_total=self.remaining_total,
                    tested=self.tested,
                    in_flight=self.in_flight,
                    start_time=start_time,
                    status="Running" if not found_event.is_set() else "FOUND ✅"
                ))
                time.sleep(self.ui_refresh)


            from concurrent.futures import ProcessPoolExecutor
            pending = set()
            with ProcessPoolExecutor(max_workers=self.processes) as ex:
                def submit_one(next_chunk):
                    nonlocal in_flight
                    fut = ex.submit(_worker_try_chunk, self.zip_file, next_chunk, stop_event)
                    fut._chunk_len = len(next_chunk)
                    fut._t0 = time.time()
                    pending.add(fut)
                    in_flight += 1

                # seed awal
                for _ in range(self.processes):
                    next_buf = []
                    for pw in stream_iter:
                        next_buf.append(pw)
                        if len(next_buf) >= chunk_size:
                            break
                    if next_buf:
                        submit_one(next_buf)
                    else:
                        break

                status = "Running"
                from concurrent.futures import wait, FIRST_COMPLETED
                while pending and not stop_event.is_set():
                    done, pending = wait(pending, timeout=self.ui_refresh, return_when=FIRST_COMPLETED)
                    for fut in list(done):
                        clen = getattr(fut, "_chunk_len", 0)
                        t0 = getattr(fut, "_t0", time.time())
                        dt = max(1e-6, time.time() - t0)
                        try:
                            kind, val = fut.result()
                        except Exception:
                            kind, val = ('COUNT', clen)

                        # adaptive chunk sizing
                        if dt < 0.4:
                            chunk_size = min(chunk_size * 2, 100_000)
                        elif dt > 1.0:
                            chunk_size = max(200, chunk_size // 2)

                        if kind == 'FOUND':
                            found_pw = val
                            stop_event.set()
                            tested += clen
                            status = "FOUND ✅"

                            live.update(render_dashboard(...))

                            clear_resume(self.zip_file, self.wordlist)

                            # matikan live dulu sebelum ekstraksi
                            live.stop()  

                            # langsung ekstraksi (tanpa thread)
                            try:
                                outdir = extract_with_password(self.zip_file, found_pw)
                                ui.success(f"✔ Semua file diekstrak ke: {outdir}")
                            except Exception as e:
                                ui.warning(f"⚠ Password benar tapi ekstraksi gagal:\n{e}")

                            for pf in pending: pf.cancel()
                            pending.clear()
                            in_flight = 0
                            break

                        else:
                            tested += val
                            in_flight -= 1
                            if not stop_event.is_set():
                                next_buf = []
                                for pw in stream_iter:
                                    next_buf.append(pw)
                                    if len(next_buf) >= chunk_size:
                                        break
                                if next_buf:
                                    submit_one(next_buf)

                        if self.resume and (tested - (last_resume_save - start_at)) >= self.checkpoint_every:
                            last_index = start_at + tested - 1
                            save_resume(self.zip_file, self.wordlist, last_index)
                            last_resume_save = last_index + 1

                    live.update(render_dashboard(
                        os.path.basename(self.zip_file),
                        os.path.basename(self.wordlist),
                        self.processes, start_at, remaining_total,
                        tested, in_flight, start_time,
                        status=status
                    ))

        elapsed = time.time() - start_time
        rate = tested / elapsed if elapsed > 0 else 0.0

        result = self.result_schema(
            password=found_pw,
            elapsed=elapsed,
            rate=rate,
            status="ok" if found_pw else "not_found",
            mode=self.mode,
            extra={"tested": tested, "total": total_all}
        )
        dashboard.show_summary(result)
        return result

    def run_sample(self, limit=5000):
        """Jalankan brute dengan batas limit kata (benchmark mode)."""
        # load sebagian kecil wordlist
        with open(self.wordlist_path, "r", errors="ignore") as f:
            candidates = [line.strip() for _, line in zip(range(limit), f) if line.strip()]
        if not candidates:
            return {"status": "empty"}
        # brute sederhana (tanpa multiprocess penuh)
        start = time.time()
        found = None
        for pw in candidates:
            if self.try_password(pw):
                found = pw
                break
        elapsed = time.time() - start
        return {
            "status": "ok" if found else "not_found",
            "password": found,
            "elapsed": elapsed,
            "tested": len(candidates),
        }

# wrapper supaya kompatibel
def brute_python_fast(zip_file_path, wordlist_path,
                      processes=None, start_chunk=1000, resume=True,
                      ui_refresh=0.3, checkpoint_every=50_000):
    eng = PythonEngine(zip_file_path, wordlist_path,
                       processes=processes,
                       start_at=start_chunk,
                       resume=resume,
                       ui_refresh=ui_refresh,
                       checkpoint_every=checkpoint_every)
    return eng.run()
