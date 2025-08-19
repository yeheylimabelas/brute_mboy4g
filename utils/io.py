import os
import json
import time
import psutil
import pyzipper
from datetime import timedelta
from rich.console import Console
from ui.theming import get_style

console = Console()

# =========================
# Resume (checkpoint) helpers
# =========================
def resume_path(zip_path, wordlist_path):
    z = os.path.splitext(os.path.basename(zip_path))[0]
    w = os.path.splitext(os.path.basename(wordlist_path))[0]
    return f".resume_{z}_{w}.json"

def load_resume(zip_path, wordlist_path):
    try:
        p = resume_path(zip_path, wordlist_path)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("zip") == os.path.abspath(zip_path) and data.get("wordlist") == os.path.abspath(wordlist_path):
                return int(data.get("last_index", -1))
    except Exception:
        pass
    return -1

def save_resume(zip_path, wordlist_path, last_index):
    try:
        p = resume_path(zip_path, wordlist_path)
        data = {
            "zip": os.path.abspath(zip_path),
            "wordlist": os.path.abspath(wordlist_path),
            "last_index": int(last_index),
            "timestamp": time.time(),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        console.print(f"[{get_style('warning')}]⚠ Gagal menyimpan resume: {e}[/]")

def clear_resume(zip_path, wordlist_path):
    try:
        p = resume_path(zip_path, wordlist_path)
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
# Wordlist utils
# =========================
def count_lines_fast(path):
    with open(path, "rb") as f:
        buf = f.read(1024*1024)
        count = 0
        while buf:
            count += buf.count(b"\n")
            buf = f.read(1024*1024)
    if count == 0:
        with open(path, "rb") as f:
            if f.read(1):
                return 1
    return count

def wordlist_stream(path, start_index=0):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i < start_index:
                continue
            pw = line.strip()
            if pw:
                yield pw

# =========================
# Auto select engine
# =========================
def auto_select_engine(zip_file, wordlist, force=None):
    """
    Pilih engine otomatis berdasarkan ukuran wordlist dan RAM.
    force: "python" atau "john" untuk override.
    """
    if force in ["python", "john"]:
        return force

    size = os.path.getsize(wordlist)
    ram = psutil.virtual_memory().total if psutil else None

    # heuristik sederhana
    if size <= 5 * 10**6:   # wordlist < 5MB
        return "python"
    if ram and ram < 1 * 1024**3:   # RAM < 1GB
        return "john"

    # default: wordlist besar → john, sisanya python
    return "john" if size > 500_000 * 10 else "python"