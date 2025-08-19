#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BRUTEZIPER v10
# Python(Fast+Resume+mmap+Adaptive) + John + Hybrid
# Live Dashboard (Rich) + Radio Grid Menu (readchar)
# Default: workers=8, adaptive chunk start=1000, resume=ON
# Gunakan hanya untuk file ZIP milik Anda sendiri.

import os
import sys
import json
import time
import math
import mmap
import tempfile
import threading
import subprocess
import multiprocessing as mp
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED, ThreadPoolExecutor

# third-party
import pyzipper
import readchar
try:
    import psutil
except Exception:
    psutil = None

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.align import Align
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TimeElapsedColumn, MofNCompleteColumn

console = Console()

# =========================
# UI: banner & helpers
# =========================
def banner():
    os.system("cls" if os.name == "nt" else "clear")
    console.print(Panel(
        "[bold magenta]BRUTEZIPER v10[/]\n"
        "By [bold bright_blue]MBOY4G[/]\n"
        "As [bold bright_blue]Ryven Novyr Asmadeus[/]\n"
        "Mode Python · John · John Live · Hybrid",
        title="[cyan]SCRIPT[/]", border_style="magenta"
    ))

def _is_zip(path): return path and path.lower().endswith(".zip") and os.path.isfile(path)
def _is_txt(path): return path and path.lower().endswith(".txt") and os.path.isfile(path)

def _format_eta(seconds):
    if seconds is None or math.isinf(seconds):
        return "—"
    if seconds > 10**8:   # guard overflow timedelta on some builds
        return "∞"
    try:
        return str(timedelta(seconds=int(max(0, seconds))))
    except OverflowError:
        return "∞"

def _safe_cpu_percent():
    if not psutil: return None
    try:
        # non-blocking snapshot (first call may be 0.0—itu normal)
        return psutil.cpu_percent(interval=0.0)
    except PermissionError:
        return None
    except Exception:
        return None

def _safe_mem_percent():
    if not psutil: return None
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return None

def _safe_temp():
    if not psutil: return None
    try:
        ts = psutil.sensors_temperatures()
        if not ts: return None
        for _, entries in ts.items():
            if entries:
                return f"{entries[0].current:.0f}°C"
    except Exception:
        pass
    return None

# =========================
# Radio-grid menu (responsif) + Cancel
# =========================
from rich.table import Table
from rich.panel import Panel

def radio_grid_menu(title, options, default=0, cols=2, border_style="magenta"):
    idx = default

    def render():
        table = Table.grid(expand=True)
        for _ in range(cols):
            table.add_column(justify="left", ratio=1, no_wrap=True)

        rows = [options[i:i+cols] for i in range(0, len(options), cols)]
        for r in rows:
            cells = []
            for opt in r:
                pos = options.index(opt)
                if pos == idx:
                    if opt.lower() == "exit!":
                        cells.append(f"[bold red][*] {opt}[/]")
                    else:
                        cells.append(f"[bold cyan][*] {opt}[/]")
                else:
                    if opt.lower() == "exit!":
                        cells.append(f"[dim red][ ] {opt}[/]")
                    else:
                        cells.append(f"[dim][ ] {opt}[/]")
            while len(cells) < cols:
                cells.append("")
            table.add_row(*cells)

        return Panel(table, title=title, border_style=border_style)

    with Live(render(), refresh_per_second=24, console=console) as live:
        while True:
            key = readchar.readkey()
            if key == readchar.key.RIGHT:
                idx = (idx + 1) % len(options); live.update(render())
            elif key == readchar.key.LEFT:
                idx = (idx - 1) % len(options); live.update(render())
            elif key == readchar.key.UP:
                idx = (idx - cols) % len(options); live.update(render())
            elif key == readchar.key.DOWN:
                idx = (idx + cols) % len(options); live.update(render())
            elif key == readchar.key.ENTER:
                return options[idx]

# =========================
# Ranger picker
# =========================
def _ensure_ranger():
    try:
        subprocess.check_call(["ranger", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        console.print(Panel("[red]❌ Ranger tidak ditemukan. Install dulu: pkg install ranger[/]", border_style="red"))
        return False

def pick_file_with_ranger(prompt_title="Pilih file"):
    if not _ensure_ranger():
        return None
    fd, tmpfile = tempfile.mkstemp(prefix="ranger_select_", suffix=".txt")
    os.close(fd)
    console.print(Panel(f"[cyan]📂 {prompt_title}[/]", border_style="cyan"))
    try:
        subprocess.call(["ranger", "--choosefiles", tmpfile])
    except FileNotFoundError:
        console.print(Panel("[red]❌ Ranger tidak ditemukan.[/]", border_style="red"))
        return None

    console.print("[yellow]📑 Ranger selesai. Cek file pilihan...[/]")
    if os.path.exists(tmpfile):
        with open(tmpfile, "r") as f:
            path = f.readline().strip()
        try: os.remove(tmpfile)
        except Exception: pass
        if path:
            console.print(f"[green]✅ Terpilih: {path}[/]")
            return path
        else:
            console.print("[red]⚠ Tidak ada yang dipilih.[/]")
            return None
    else:
        console.print("[red]❌ File hasil pilihan tidak ditemukan.[/]")
        return None

# =========================
# Resume (checkpoint) helpers
# =========================
def _resume_path(zip_path, wordlist_path):
    z = os.path.splitext(os.path.basename(zip_path))[0]
    w = os.path.splitext(os.path.basename(wordlist_path))[0]
    return f".resume_{z}_{w}.json"

def _load_resume(zip_path, wordlist_path):
    try:
        p = _resume_path(zip_path, wordlist_path)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("zip") == os.path.abspath(zip_path) and data.get("wordlist") == os.path.abspath(wordlist_path):
                return int(data.get("last_index", -1))
    except Exception:
        pass
    return -1

def _save_resume(zip_path, wordlist_path, last_index):
    try:
        p = _resume_path(zip_path, wordlist_path)
        data = {
            "zip": os.path.abspath(zip_path),
            "wordlist": os.path.abspath(wordlist_path),
            "last_index": int(last_index),
            "timestamp": time.time(),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        console.print(f"[yellow]⚠ Gagal menyimpan resume: {e}[/]")

def _clear_resume(zip_path, wordlist_path):
    try:
        p = _resume_path(zip_path, wordlist_path)
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass

# =========================
# Ekstraksi
# =========================
def extract_with_password(zip_file_path, password):
    base = os.path.splitext(os.path.basename(zip_file_path))[0]
    out_dir = os.path.join(os.getcwd(), base)
    os.makedirs(out_dir, exist_ok=True)
    with pyzipper.AESZipFile(zip_file_path) as zf:
        zf.extractall(path=out_dir, pwd=password.encode("utf-8"))
    return out_dir

# =========================
# Python engine (FAST v10)
# - mmap/streaming
# - adaptive chunk
# - dynamic scheduler
# - resume checkpoint
# - live dashboard + CPU/MEM (optional)
# =========================
def _count_lines_fast(path):
    # cepat & hemat mem
    with open(path, "rb") as f:
        buf = f.read(1024*1024)
        count = 0
        while buf:
            count += buf.count(b"\n")
            buf = f.read(1024*1024)
    # jika file tidak diakhiri newline, tambahkan 1 baris
    if count == 0:
        # bisa empty file OR single line w/o newline
        with open(path, "rb") as f:
            data = f.read(1)
            if data:
                return 1
    return count

def _wordlist_stream(path, start_index=0):
    # generator baris string (skip sampai start_index)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i < start_index:
                continue
            pw = line.strip()
            if pw:
                yield pw

def _make_chunks(stream_iter, chunk_size):
    buf = []
    for pw in stream_iter:
        buf.append(pw)
        if len(buf) >= chunk_size:
            yield buf
            buf = []
    if buf:
        yield buf

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

def brute_python_fast_v10(zip_file_path, wordlist_path,
                          processes=8, start_chunk=1000, resume=True,
                          ui_refresh=0.3, checkpoint_every=50_000):
    if not os.path.exists(zip_file_path):
        console.print(Panel(f"[red]❌ File ZIP tidak ditemukan: {zip_file_path}[/]", border_style="red")); return
    if not os.path.exists(wordlist_path):
        console.print(Panel(f"[red]❌ Wordlist tidak ditemukan: {wordlist_path}[/]", border_style="red")); return

    total_all = _count_lines_fast(wordlist_path)
    if total_all == 0:
        console.print(Panel("[red]⚠ Wordlist kosong[/]", border_style="red")); return

    start_index = _load_resume(zip_file_path, wordlist_path) if resume else -1
    start_at = max(0, start_index + 1)
    if start_at >= total_all:
        start_at = 0
    remaining_total = total_all - start_at

    console.print(Panel(
        "[bold magenta]Menjalankan Python engine[/]\n"
        f"Worker={processes}, AdaptiveChunk(start)={start_chunk}, Resume={'ON' if resume else 'OFF'}",
        border_style="magenta"
    ))

    # adaptive state
    chunk_size = start_chunk
    manager = mp.Manager()
    stop_event = manager.Event()

    tested = 0
    found_pw = None
    start_time = time.time()
    last_resume_save = start_at
    in_flight = 0

    # stream → chunks generator (on-demand)
    stream_iter = _wordlist_stream(wordlist_path, start_at)

    # dashboard
    def _render_dashboard(status="Running"):
        elapsed = time.time() - start_time
        rate = tested / elapsed if elapsed > 0 else 0.0
        eta = _format_eta((remaining_total - tested) / rate) if (rate > 0 and tested < remaining_total) else "—"
        cpu = _safe_cpu_percent()
        mem = _safe_mem_percent()
        temp = _safe_temp()

        table = Table(title="BRUTEZIPER v10 – Python Engine", show_header=False, expand=True)
        table.add_row("📦 ZIP", os.path.basename(zip_file_path))
        table.add_row("📝 Wordlist", os.path.basename(wordlist_path))
        table.add_row("🧠 Worker", str(processes))
        table.add_row("🔢 Total", f"{remaining_total:,} kandidat (mulai idx {start_at:,})")
        table.add_row("✅ Tested", f"{tested:,}")
        table.add_row("⚡ Rate", f"{rate:,.0f} pw/s")
        table.add_row("⏳ ETA", eta)
        if cpu is not None: table.add_row("🖥 CPU", f"{cpu:.1f}%")
        if mem is not None: table.add_row("🧩 RAM", f"{mem:.1f}%")
        if temp is not None: table.add_row("🌡 Suhu", f"{temp}")
        table.add_row("📦 In-Flight", str(in_flight))
        table.add_row("📈 Status", status)
        return Panel(Align.center(table), border_style="cyan", title="Live Dashboard", subtitle="Gunakan untuk file Anda sendiri")

    # extraction thread (dijalankan setelah FOUND)
    def _async_extract(pw):
        try:
            outdir = extract_with_password(zip_file_path, pw)
            console.print(Panel(f"[green]✔ Semua file diekstrak ke: {outdir}[/]", border_style="green"))
        except Exception as e:
            console.print(Panel(f"[yellow]⚠ Password benar tapi ekstraksi gagal:\n{e}[/]", border_style="yellow"))

    with Live(_render_dashboard(), refresh_per_second=max(4, int(1/ui_refresh)), console=console) as live:
        with ProcessPoolExecutor(max_workers=processes) as ex:
            pending = set()
            # seed awal: isi slot sebanyak worker
            def submit_one(next_chunk):
                nonlocal in_flight
                fut = ex.submit(_worker_try_chunk, zip_file_path, next_chunk, stop_event)
                fut._chunk_len = len(next_chunk)
                fut._t0 = time.time()
                pending.add(fut); in_flight += 1

            # isi awal
            for _ in range(processes):
                # ambil next chunk dari stream; kalau habis, stop loop seed
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
            # loop monitor
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

                    # adaptive sizing (sederhana): target ~0.4–1.2s per chunk
                    # jika terlalu cepat, naikkan chunk; jika terlalu lambat, kecilkan
                    target_low, target_high = 0.4, 1.2
                    if dt < target_low:
                        chunk_size = min(chunk_size * 2, 50_000)
                    elif dt > target_high:
                        chunk_size = max(max(100, chunk_size // 2), 200)

                    if kind == 'FOUND':
                        found_pw = val
                        stop_event.set()
                        tested += clen
                        status = "FOUND ✅"
                        live.update(_render_dashboard(status=status))

                        # simpan & bersih resume
                        _clear_resume(zip_file_path, wordlist_path)

                        # ekstraksi async agar UI masih hidup selama ekstraksi
                        t = threading.Thread(target=_async_extract, args=(found_pw,), daemon=True)
                        t.start()
                        # drain yang lain
                        for pf in pending:
                            pf.cancel()
                        pending.clear()
                        in_flight = 0
                        break
                    else:
                        tested += val
                        in_flight -= 1
                        # refill slot dengan chunk baru
                        if not stop_event.is_set():
                            next_buf = []
                            got = 0
                            for pw in stream_iter:
                                next_buf.append(pw); got += 1
                                if got >= chunk_size:
                                    break
                            if next_buf:
                                submit_one(next_buf)

                    # checkpoint resume
                    if resume and (tested - (last_resume_save - start_at)) >= checkpoint_every:
                        last_index = start_at + tested - 1
                        _save_resume(zip_file_path, wordlist_path, last_index)
                        last_resume_save = last_index + 1

                # update UI periodik
                live.update(_render_dashboard(status=status))

    # ringkasan
    elapsed = time.time() - start_time
    rate = tested / elapsed if elapsed > 0 else 0.0
    if found_pw:
        console.print(Panel(f"[green]✅ Password ditemukan: {found_pw}[/]\n"
                            f"[cyan]⏳ Waktu: {elapsed:.2f}s · ⚡ {rate:,.0f} pw/s[/]",
                            border_style="green"))
    else:
        # simpan posisi terakhir
        if resume:
            last_index = start_at + tested - 1
            if last_index >= 0:
                _save_resume(zip_file_path, wordlist_path, last_index)
        console.print(Panel(f"[red]❌ Password tidak ditemukan dalam wordlist[/]\n"
                            f"[cyan]⏳ Total waktu: {elapsed:.2f}s · ⚡ {rate:,.0f} pw/s[/]",
                            border_style="red"))

# =========================
# John engine
# =========================
def run_command(cmd, cwd=None, live=False):
    if live:
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd)
        proc.wait()
        return "", "", proc.returncode
    else:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return res.stdout.strip(), res.stderr.strip(), res.returncode

def _john_show_password(john_bin, hash_abs, fmt, john_path):
    out, _, _ = run_command(f"{john_bin} --show --format={fmt} '{hash_abs}'", cwd=john_path)
    if not out:
        return None, ""
    for line in out.splitlines():
        if ":" in line and not line.strip().lower().startswith("1 password hash") \
            and not line.strip().lower().startswith("no password hashes"):
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[1].strip(), out
    return None, out

def brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False):
    john_path = os.path.expanduser(john_path)
    if not os.path.exists(zip_file):
        console.print(Panel(f"[red]❌ File ZIP tidak ditemukan: {zip_file}[/]", border_style="red")); return
    if not os.path.exists(john_path):
        console.print(Panel(f"[red]❌ Folder John the Ripper tidak ditemukan: {john_path}[/]", border_style="red")); return

    zip2john_bin = os.path.join(john_path, "zip2john")
    john_bin = os.path.join(john_path, "john")

    basename = os.path.splitext(os.path.basename(zip_file))[0]
    hash_file = f"john_{basename}.txt"
    hash_abs = os.path.abspath(hash_file)

    console.print(Panel(f"[cyan]🔑 Generate hash dengan zip2john[/]", border_style="cyan"))
    out, err, code = run_command(f"{zip2john_bin} '{zip_file}'")
    if code != 0 or not out:
        console.print(Panel(f"[red]Gagal generate hash:\n{err or '(output kosong)'}[/]", border_style="red")); return
    with open(hash_file, "w") as f:
        f.write(out)

    tried = []
    start = time.time()

    for fmt in ["ZIP", "PKZIP"]:
        tried.append(fmt)
        if wordlist:
            console.print(Panel(f"[yellow]🚀 Jalankan John ({fmt}) dengan wordlist {os.path.basename(wordlist)}[/]", border_style="yellow"))
            run_command(f"{john_bin} --format={fmt} --wordlist='{os.path.abspath(wordlist)}' '{hash_abs}'",
                        cwd=john_path, live=live)
        else:
            console.print(Panel(f"[yellow]🚀 Jalankan John ({fmt}) dengan mode incremental[/]", border_style="yellow"))
            run_command(f"{john_bin} --format={fmt} --incremental '{hash_abs}'",
                        cwd=john_path, live=live)

        pw, _raw = _john_show_password(john_bin, hash_abs, fmt, john_path)
        if pw:
            elapsed = time.time() - start
            console.print(Panel(f"[green]✅ Password ditemukan: {pw}[/]\n📦 File: {os.path.basename(zip_file)}", border_style="green"))
            console.print(Panel(f"[cyan]⏳ Waktu: {elapsed:.2f} detik[/]", border_style="cyan"))
            # ekstraksi (sinkron—biasanya cepat)
            try:
                outdir = extract_with_password(zip_file, pw)
                console.print(Panel(f"[green]✔ Semua file diekstrak ke: {outdir}[/]", border_style="green"))
            except Exception as e:
                console.print(Panel(f"[yellow]⚠ Password benar tapi ekstraksi gagal:\n{e}[/]", border_style="yellow"))
            try:
                os.remove(hash_abs)
            except Exception as e:
                console.print(f"[yellow]⚠ Gagal hapus hash file: {e}[/]")
            return

    elapsed = time.time() - start
    console.print(Panel(f"[red]❌ Password tidak ditemukan oleh John[/]\n"
                        f"[white]Format yang dicoba: {', '.join(tried)}[/]\n"
                        f"[cyan]⏳ Total waktu: {elapsed:.2f} detik[/]\n"
                        f"[cyan]Tips: coba wordlist berbeda atau jalankan manual John untuk verifikasi[/]",
                        border_style="red"))
    try:
        os.remove(hash_abs)
    except Exception as e:
        console.print(f"[yellow]⚠ Gagal hapus hash file: {e}[/]")

# =========================
# HYBRID: Python → (jika gagal) John incremental
# =========================
def brute_hybrid(zip_file, wordlist, processes=8, start_chunk=1000, resume=True):
    console.print(Panel(
        "[cyan]🧪 Tahap 1: Python (wordlist) — jika gagal lanjut John incremental[/]", 
        border_style="cyan"
    ))

    # === Tahap 1: Python brute dengan wordlist ===
    password = brute_python_fast_v10(
        zip_file, 
        wordlist, 
        processes=processes, 
        start_chunk=start_chunk, 
        resume=resume
    )

    if password:
        # Kalau Python berhasil
        console.print(Panel(f"[green]✅ Password ditemukan oleh Python: {password}[/]", border_style="green"))
        return password

    # === Tahap 2: John incremental ===
    console.print(Panel(
        "[yellow]❌ Password tidak ditemukan dalam wordlist. "
        "➡️  Lanjut brute dengan John incremental...[/]", 
        border_style="yellow"
    ))

    # Pastikan path John bener
    john_path = os.path.expanduser("~/john/run")
    return brute_john(
        zip_file, 
        wordlist=None,   # abaikan wordlist, langsung incremental
        john_path=john_path, 
        live=True        # pakai live biar keliatan prosesnya
    )

# =========================
# INTERACTIVE FLOW
# =========================
def interactive_flow():
    engine = radio_grid_menu("Pilih Engine Untuk Brute",
        ["Python", "John", "John Live", "Hybrid", "Exit!"], cols=2).lower()

    if engine.startswith("exit!"):
        console.print("[yellow]⚠️ Program dibatalkan oleh user.[/]")
        sys.exit(0)

    # pilih ZIP
    zip_file = pick_file_with_ranger("Pilih file ZIP")
    if not _is_zip(zip_file):
        console.print(Panel("[red]❌ File ZIP tidak valid/dipilih.[/]", border_style="red")); sys.exit(1)

    if engine == "python":
        wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
        if not _is_txt(wordlist):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
        brute_python_fast_v10(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)

    elif engine == "john":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit!"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not _is_txt(wordlist):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=False)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False)

    elif engine == "john live":
        mode = radio_grid_menu("Mode John", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
        if mode.startswith("exit!"):
            console.print("[yellow]⚠️ Dibatalkan.[/]")
            sys.exit(0)
        if mode == "wordlist":
            wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
            if not _is_txt(wordlist):
                console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red")); sys.exit(1)
            brute_john(zip_file, wordlist=wordlist, john_path="~/john/run", live=True)
        else:
            brute_john(zip_file, wordlist=None, john_path="~/john/run", live=True)

    elif engine == "hybrid":
        wordlist = pick_file_with_ranger("Pilih file wordlist (.txt) [untuk tahap Python]")
        if not _is_txt(wordlist):
            console.print(Panel("[red]❌ Wordlist harus file .txt yang valid.[/]", border_style="red"))
            sys.exit(1)

        brute_hybrid(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)

# =========================
# CLI FLOW
# =========================
def usage():
    console.print(Panel(
        "📌 Penggunaan:\n"
        "  python brute_v10.py                (mode interaktif)\n"
        "  python brute_v10.py --engine python <zip> <wordlist>\n"
        "  python brute_v10.py --engine john   <zip> [wordlist] [--live] [--john-path <dir>]\n"
        "  python brute_v10.py --engine hybrid <zip> <wordlist>\n",
        border_style="blue"))

def cli_flow():
    if len(sys.argv) < 3 or sys.argv[1] != "--engine":
        usage(); sys.exit(1)

    engine = sys.argv[2].lower()
    if engine == "python":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        if not _is_zip(zip_file) or not _is_txt(wordlist):
            console.print(Panel("[red]❌ Argumen tidak valid (cek zip/wordlist).[/]", border_style="red")); sys.exit(1)
        brute_python_fast_v10(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)

    elif engine == "john":
        if len(sys.argv) < 4:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]
        wordlist = None
        if len(sys.argv) >= 5 and not sys.argv[4].startswith("--"):
            wordlist = sys.argv[4]
        live = "--live" in sys.argv
        john_path = "~/john/run"
        if "--john-path" in sys.argv:
            try: john_path = sys.argv[sys.argv.index("--john-path")+1]
            except Exception: pass
        brute_john(zip_file, wordlist=wordlist, john_path=john_path, live=live)

    elif engine == "hybrid":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        zip_file = sys.argv[3]; wordlist = sys.argv[4]
        brute_hybrid(zip_file, wordlist, processes=8, start_chunk=1000, resume=True)
    else:
        usage(); sys.exit(1)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    banner()
    if len(sys.argv) == 1:
        interactive_flow()
    else:
        cli_flow()
