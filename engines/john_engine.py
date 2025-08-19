import os, time, subprocess
from rich.console import Console
from rich.panel import Panel

from utils.io import extract_with_password
from ui import messages as ui

console = Console()

# =========================
# Helper: jalankan command
# =========================
def run_command(cmd, cwd=None, live=False):
    if live:
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd)
        proc.wait()
        return "", "", proc.returncode
    else:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return res.stdout.strip(), res.stderr.strip(), res.returncode

# =========================
# Ambil password dari hasil John
# =========================
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

# =========================
# Engine John
# =========================
def brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False):
    """
    Jalankan brute force dengan John the Ripper.
    Bisa pakai wordlist atau incremental mode.
    Return dict {password, elapsed, mode, format}
    """
    john_path = os.path.expanduser(john_path)
    if not os.path.exists(zip_file):
        ui.error(f"❌ File ZIP tidak ditemukan: {zip_file}")
        return None
    if not os.path.exists(john_path):
        ui.error(f"❌ Folder John the Ripper tidak ditemukan: {john_path}")
        return None

    zip2john_bin = os.path.join(john_path, "zip2john")
    john_bin = os.path.join(john_path, "john")

    basename = os.path.splitext(os.path.basename(zip_file))[0]
    hash_file = f"john_{basename}.txt"
    hash_abs = os.path.abspath(hash_file)

    ui.attention(f"🔑 Generate hash dengan zip2john")
    out, err, code = run_command(f"{zip2john_bin} '{zip_file}'")
    if code != 0 or not out:
        ui.error(f"Gagal generate hash:\n{err or '(output kosong)'}")
        return None
    with open(hash_file, "w") as f:
        f.write(out)

    tried = []
    start = time.time()
    found_pw = None
    chosen_fmt = None

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
            chosen_fmt = fmt
            found_pw = pw
            console.print(Panel(f"[green]✅ Password ditemukan: {pw}[/]\n📦 File: {os.path.basename(zip_file)}", border_style="green"))
            console.print(Panel(f"[cyan]⏳ Waktu: {elapsed:.2f} detik[/]", border_style="cyan"))
            # ekstraksi sinkron
            try:
                outdir = extract_with_password(zip_file, pw)
                console.print(Panel(f"[green]✔ Semua file diekstrak ke: {outdir}[/]", border_style="green"))
            except Exception as e:
                console.print(Panel(f"[yellow]⚠ Password benar tapi ekstraksi gagal:\n{e}[/]", border_style="yellow"))
            try:
                os.remove(hash_abs)
            except Exception as e:
                console.print(f"[yellow]⚠ Gagal hapus hash file: {e}[/]")
            return {
                "password": found_pw,
                "elapsed": elapsed,
                "mode": "wordlist" if wordlist else "incremental",
                "format": chosen_fmt
            }

    # kalau sampai sini: gagal
    elapsed = time.time() - start
    ui.error(
        f"❌ Password tidak ditemukan oleh John\n"
        f"[white]Format yang dicoba: {', '.join(tried)}[/]\n"
        f"[cyan]⏳ Total waktu: {elapsed:.2f} detik[/]\n"
        f"[cyan]Tips: coba wordlist berbeda atau jalankan manual John untuk verifikasi[/]",
        title="JOHN ENGINE"
    )

    try:
        os.remove(hash_abs)
    except Exception as e:
        console.print(f"[yellow]⚠ Gagal hapus hash file: {e}[/]")

    return {
        "password": None,
        "elapsed": elapsed,
        "mode": "wordlist" if wordlist else "incremental",
        "format": tried
    }
