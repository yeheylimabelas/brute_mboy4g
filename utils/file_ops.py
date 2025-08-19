# utils/file_ops.py
# -------------------------------------------------------------
# Utility functions untuk operasi file
# - validasi ekstensi
# - hitung baris wordlist
# - iterasi password dari wordlist
# - path helper (expanduser)
# -------------------------------------------------------------

import os
from typing import Generator

def is_txt(path: str) -> bool:
    return path.lower().endswith(".txt")

def is_zip(path: str) -> bool:
    return path.lower().endswith(".zip")

def expand(path: str) -> str:
    return os.path.expanduser(path)

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

def file_size(path: str) -> int:
    """Return ukuran file dalam byte"""
    return os.path.getsize(path)
