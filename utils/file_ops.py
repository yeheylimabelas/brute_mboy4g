# utils/file_ops.py
# ----------------------------------------------------
# Helper file utilities:
# - File picker pakai ranger
# - Cek ekstensi (ZIP / TXT)
# - Path expand (absolute + tilde)
# ----------------------------------------------------

import os
import subprocess


def expand(path: str) -> str:
    """Expand ~ dan jadikan path absolut"""
    return os.path.abspath(os.path.expanduser(path))


def is_zip(path: str) -> bool:
    """Cek apakah file ekstensi .zip"""
    return path.lower().endswith(".zip")


def is_txt(path: str) -> bool:
    """Cek apakah file ekstensi .txt"""
    return path.lower().endswith(".txt")


def pick_file_with_ranger(prompt: str = "Pilih file") -> str:
    """
    Launch ranger sebagai file picker.
    Ranger akan menulis file terpilih ke /tmp/ranger_choice.
    Kalau ranger tidak tersedia → fallback input manual.
    """
    print(f"\n📂 {prompt}")
    try:
        # --choosefile = output ke file
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
