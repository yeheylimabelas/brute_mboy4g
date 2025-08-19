import os, time, threading
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from ui import messages as ui

# import helper dari utils & ui
from utils.io import (
    count_lines_fast, wordlist_stream,
    load_resume, save_resume, clear_resume,
    extract_with_password
)
from ui.dashboard import render_dashboard

console = Console()

# =========================
# Worker untuk uji chunk
# =========================
import pyzipper

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

# =========================
# Engine utama (v11)
# =========================
def brute_python_fast(zip_file_path, wordlist_path,
                      processes=None, start_chunk=1000, resume=True,
                      ui_refresh=0.3, checkpoint_every=50_000):
    """
    Python brute-force engine untuk ZIP.
    Return dict {password, tested, elapsed, rate}
    """
    if not os.path.exists(zip_file_path):
        ui.error(f"❌ File ZIP tidak ditemukan: {zip_file_path}")
        ui.error(f"❌ File ZIP tidak ditemukan: {zip_file_path}")
        return None
    if not os.path.exists(wordlist_path):
        ui.error(f"❌ Wordlist tidak ditemukan: {wordlist_path}")
        return None

    # auto detect jumlah worker
    if processes is None:
        processes = max(1, mp.cpu_count() - 1)

    total_all = count_lines_fast(wordlist_path)
    if total_all == 0:
        ui.error("⚠ Wordlist kosong[/]")
        return None

    start_index = load_resume(zip_file_path, wordlist_path) if resume else -1
    start_at = max(0, start_index + 1)
    if start_at >= total_all:
        start_at = 0
    remaining_total = total_all - start_at

    ui.info(
        f"Menjalankan Python engine\n"
        f"Worker={processes}, AdaptiveChunk(start)={start_chunk}, Resume={'ON' if resume else 'OFF'}")

    # adaptive state
    chunk_size = start_chunk
    manager = mp.Manager()
    stop_event = manager.Event()

    tested = 0
    found_pw = None
    start_time = time.time()
    last_resume_save = start_at
    in_flight = 0

    # generator stream
    stream_iter = wordlist_stream(wordlist_path, start_at)

    # extraction async
    def _async_extract(pw):
        try:
            outdir = extract_with_password(zip_file_path, pw)
            ui.success(f"✔ Semua file diekstrak ke: {outdir}")
        except Exception as e:
            ui.warning(f"⚠ Password benar tapi ekstraksi gagal:\n{e}")

    with Live(render_dashboard(
        os.path.basename(zip_file_path),
        os.path.basename(wordlist_path),
        processes, start_at, remaining_total,
        tested, in_flight, start_time
    ), refresh_per_second=max(4, int(1/ui_refresh)), console=console) as live:

        with ProcessPoolExecutor(max_workers=processes) as ex:
            pending = set()

            def submit_one(next_chunk):
                nonlocal in_flight
                fut = ex.submit(_worker_try_chunk, zip_file_path, next_chunk, stop_event)
                fut._chunk_len = len(next_chunk)
                fut._t0 = time.time()
                pending.add(fut)
                in_flight += 1

            # seed awal
            for _ in range(processes):
                next_buf = []
                try:
                    for pw in stream_iter:
                        next_buf.append(pw)
                        if len(next_buf) >= chunk_size:
                            break
                except StopIteration:
                    next_buf = []
                if next_buf:
                    submit_one(next_buf)
                else:
                    break

            status = "Running"
            while pending and not stop_event.is_set():
                done, pending = wait(pending, timeout=ui_refresh, return_when=FIRST_COMPLETED)

                for fut in list(done):
                    clen = getattr(fut, "_chunk_len", 0)
                    t0 = getattr(fut, "_t0", time.time())
                    dt = max(1e-6, time.time() - t0)

                    try:
                        kind, val = fut.result()
                    except Exception:
                        kind, val = ('COUNT', clen)

                    # === Adaptive chunk sizing lebih pintar ===
                    target_low, target_high = 0.4, 1.0
                    if dt < target_low:
                        chunk_size = min(chunk_size * 2, 100_000)
                    elif dt > target_high:
                        chunk_size = max(200, chunk_size // 2)

                    if kind == 'FOUND':
                        found_pw = val
                        stop_event.set()
                        tested += clen
                        status = "FOUND ✅"
                        live.update(render_dashboard(
                            os.path.basename(zip_file_path),
                            os.path.basename(wordlist_path),
                            processes, start_at, remaining_total,
                            tested, in_flight, start_time,
                            status=status
                        ))

                        # clear resume
                        clear_resume(zip_file_path, wordlist_path)

                        # ekstraksi async
                        t = threading.Thread(target=_async_extract, args=(found_pw,), daemon=True)
                        t.start()

                        # cancel sisa
                        for pf in pending:
                            pf.cancel()
                        pending.clear()
                        in_flight = 0
                        break
                    else:
                        tested += val
                        in_flight -= 1
                        if not stop_event.is_set():
                            next_buf = []
                            got = 0
                            for pw in stream_iter:
                                next_buf.append(pw)
                                got += 1
                                if got >= chunk_size:
                                    break
                            if next_buf:
                                submit_one(next_buf)

                    # checkpoint resume
                    if resume and (tested - (last_resume_save - start_at)) >= checkpoint_every:
                        last_index = start_at + tested - 1
                        save_resume(zip_file_path, wordlist_path, last_index)
                        last_resume_save = last_index + 1

                # update UI
                live.update(render_dashboard(
                    os.path.basename(zip_file_path),
                    os.path.basename(wordlist_path),
                    processes, start_at, remaining_total,
                    tested, in_flight, start_time,
                    status=status
                ))

    # ringkasan
    elapsed = time.time() - start_time
    rate = tested / elapsed if elapsed > 0 else 0.0
    result = {
        "password": found_pw,
        "tested": tested,
        "elapsed": elapsed,
        "rate": rate
    }

    if found_pw:
        ui.password_found(found_pw, elapsed, rate, source="Python")
    else:
        if resume:
            last_index = start_at + tested - 1
            if last_index >= 0:
                save_resume(zip_file_path, wordlist_path, last_index)
        ui.password_not_found(elapsed, rate, source="Python")

    return result
