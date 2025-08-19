# utils/file_ops.py
# ----------------------------------------------------
# Helper file utilities:
# - File picker pakai ranger
# - Cek ekstensi (ZIP / TXT)
# - Path expand (absolute + tilde)
# - Hitung ukuran file (dalam format human readable)
# ----------------------------------------------------

import os
import subprocess
import tempfile
from typing import Generator
from rich.panel import Panel
from rich.console import Console

console = Console()

def expand(path: str) -> str:
    """Expand ~ dan jadikan path absolut"""
    return os.path.abspath(os.path.expanduser(path))


def is_zip(path: str) -> bool:
    """Cek apakah file ekstensi .zip"""
    return path.lower().endswith(".zip")


def is_txt(path: str) -> bool:
    """Cek apakah file ekstensi .txt"""
    return path.lower().endswith(".txt")

def count_lines(path: str) -> int:
    """Hitung jumlah baris pada file wordlist"""
    with open(path, "rb") as f:
        return sum(1 for _ in f)

def yield_passwords(wordlist: str, start_index: int = 0) -> Generator[str, None, None]:
    """Generator password dari wordlist mulai dari index tertentu"""
    with open(wordlist, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f):
            if idx < start_index:
                continue
            yield line.strip()

def file_size(path: str) -> str:
    """Kembalikan ukuran file dalam format human readable (KB, MB, GB)."""
    try:
        size = os.path.getsize(path)
    except Exception:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def pick_file_with_ranger(prompt_title="Pilih file"):
    """Gunakan ranger sebagai file picker, fallback ke input manual."""
    fd, tmpfile = tempfile.mkstemp(prefix="ranger_select_", suffix=".txt")
    os.close(fd)

    console.print(Panel(f"[cyan]📂 {prompt_title}[/]", border_style="cyan"))
    try:
        subprocess.call(["ranger", "--choosefiles", tmpfile])
    except FileNotFoundError:
        console.print(Panel("[red]❌ Ranger tidak ditemukan. Input manual...[/]", border_style="red"))
        return input("Path file: ").strip()

    console.print("[yellow]📑 Ranger selesai. Cek file pilihan...[/]")

    if os.path.exists(tmpfile):
        with open(tmpfile, "r") as f:
            path = f.readline().strip()
        try:
            os.remove(tmpfile)
        except Exception:
            pass

        if path:
            console.print(f"[green]✅ Terpilih:\n{path}[/]")
            return expand(path)
        else:
            console.print("[red]⚠ Tidak ada yang dipilih.[/]")
            return None
    else:
        console.print("[red]❌ File hasil pilihan tidak ditemukan.[/]")
        return None