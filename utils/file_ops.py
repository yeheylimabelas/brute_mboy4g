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
from typing import Generator

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


def pick_file_with_ranger(prompt: str = "Pilih file") -> str:
    """
    Launch ranger sebagai file picker.
    Ranger akan menulis file terpilih ke /tmp/ranger_choice.
    Kalau ranger tidak tersedia → fallback input manual.
    """
    print(f"\n📂 {prompt}")
    try:
        tmpfile = "/tmp/ranger_choice"
        result = subprocess.run(
            ["ranger", f"--choosefile={tmpfile}"],
            check=False
        )
        if result.returncode != 0:
            print("⚠️ Ranger dibatalkan.")
            return ""

        if os.path.exists(tmpfile):
            with open(tmpfile) as f:
                path = f.read().strip()
            os.remove(tmpfile)
            if path:
                return expand(path)
        return ""
    except FileNotFoundError:
        # fallback kalau ranger tidak ada
        return input("Path file: ").strip()
