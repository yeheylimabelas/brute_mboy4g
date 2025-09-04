# engines/python_engine.py
from __future__ import annotations
import os, time, multiprocessing as mp

from .base import BaseEngine
from ui import messages as ui
from ui import dashboard
from utils.io import (
    count_lines_fast, wordlist_stream,
    load_resume, save_resume, clear_resume,
    extract_with_password
)
from workers.zip_worker import worker_process  # 🚀 worker persistent


class PythonEngine(BaseEngine):
    name = "python"
    mode = "wordlist"

    def __init__(self, zip_file: str, wordlist: str,
                 processes=None, start_chunk=1000, resume=True,
                 ui_refresh=0.3, checkpoint_every=50_000, **kwargs):
        super().__init__(zip_file, wordlist, **kwargs)
        self.processes = processes or max(1, mp.cpu_count() - 1)
        self.start_chunk = start_chunk
        self.resume = resume
        self.ui_refresh = ui_refresh
        self.checkpoint_every = checkpoint_every

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
            f"Menjalankan Python engine (v12 persistent)\n"
            f"Worker={self.processes}, AdaptiveChunk(start)={self.start_chunk}, Resume={'ON' if self.resume else 'OFF'}"
        )

        return self._run_persistent(total_all, start_at, remaining_total)

    # ==================================================
    # 🚀 MODE BARU: Persistent Worker Pool
    # ==================================================
    def _run_persistent(self, total_all, start_at, remaining_total):
        manager = mp.Manager()
        task_q = manager.Queue()
        result_q = manager.Queue()
        stop_event = manager.Event()

        # start workers
        workers = []
        for _ in range(self.processes):
            p = mp.Process(target=worker_process,
                           args=(self.zip_file, task_q, result_q, stop_event))
            p.start()
            workers.append(p)

        tested = 0
        found_pw = None
        start_time = time.time()
        last_resume_save = start_at
        chunk_size = self.start_chunk

        from rich.live import Live
        from ui.dashboard import render_dashboard

        stream_iter = wordlist_stream(self.wordlist, start_at)

        # seed awal
        for _ in range(self.processes):
            buf = []
            for pw in stream_iter:
                buf.append(pw)
                if len(buf) >= chunk_size:
                    break
            if buf:
                task_q.put(buf)

        status = "Running"
        with Live("", refresh_per_second=max(4, int(1/self.ui_refresh))) as live:
            while not stop_event.is_set():
                try:
                    kind, val = result_q.get(timeout=self.ui_refresh)
                except Exception:
                    live.update(render_dashboard(
                        os.path.basename(self.zip_file),
                        os.path.basename(self.wordlist),
                        self.processes, start_at, remaining_total,
                        tested, 0, start_time, status=status
                    ))
                    continue

                if kind == "FOUND":
                    found_pw = val
                    status = "FOUND ✅"
                    stop_event.set()
                    clear_resume(self.zip_file, self.wordlist)

                    live.stop()
                    try:
                        outdir = extract_with_password(self.zip_file, found_pw)
                        ui.success(f"✔ Semua file diekstrak ke: {outdir}")
                    except Exception as e:
                        ui.warning(f"⚠ Password benar tapi ekstraksi gagal:\n{e}")
                    break

                elif kind == "COUNT":
                    tested += val
                    # refill
                    buf = []
                    for pw in stream_iter:
                        buf.append(pw)
                        if len(buf) >= chunk_size:
                            break
                    if buf:
                        task_q.put(buf)

                    # simpan resume tiap sekian
                    if self.resume and (tested - (last_resume_save - start_at)) >= self.checkpoint_every:
                        last_index = start_at + tested - 1
                        save_resume(self.zip_file, self.wordlist, last_index)
                        last_resume_save = last_index + 1

                elif kind == "ERROR":
                    ui.error(f"Worker error: {val}")

                live.update(render_dashboard(
                    os.path.basename(self.zip_file),
                    os.path.basename(self.wordlist),
                    self.processes, start_at, remaining_total,
                    tested, 0, start_time, status=status
                ))

        elapsed = time.time() - start_time
        rate = tested / elapsed if elapsed > 0 else 0.0

        result = self.result_schema(
            password=found_pw,
            elapsed=elapsed,
            rate=rate,
            status="ok" if found_pw else "not_found",
            mode="persistent",
            extra={"tested": tested, "total": total_all}
        )
        dashboard.show_summary(result)

        for p in workers:
            p.terminate()
        return result


# wrapper supaya kompatibel
def brute_python_fast(zip_file_path, wordlist_path,
                      processes=None, start_chunk=1000, resume=True,
                      ui_refresh=0.3, checkpoint_every=50_000):
    eng = PythonEngine(zip_file_path, wordlist_path,
                       processes=processes,
                       start_chunk=start_chunk,
                       resume=resume,
                       ui_refresh=ui_refresh,
                       checkpoint_every=checkpoint_every)
    return eng.run()
