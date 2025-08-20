import os
import json
import time
import psutil
import pyzipper
from datetime import timedelta
from rich.console import Console
from ui.theming import get_style
from ui import messages as ui
from ui.menu import radio_grid_menu

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
    out_root = os.path.join(os.getcwd(), "OutputExtract")
    os.makedirs(out_root, exist_ok=True)

    out_dir = os.path.join(out_root, base)

    # stop live dashboard dulu (opsional, tergantung cara kita panggil)
    # kalau dashboard masih running → harus dipastikan .stop() dipanggil

    if os.path.exists(out_dir) and os.listdir(out_dir):
        ui.warning(f"📂 Folder output sudah ada: {out_dir}")

        # ⛔ di sini radio_grid_menu aman dipanggil
        action = radio_grid_menu(
            "Folder sudah ada, pilih tindakan:",
            ["Timpa", "Ganti Nama", "Exit!"],
            cols=2
        ).lower()

        if action.startswith("exit"):
            ui.info("❌ Ekstraksi dibatalkan user.")
            return None
        elif action == "ganti nama":
            suffix = 1
            new_out_dir = f"{out_dir}_{suffix}"
            while os.path.exists(new_out_dir):
                suffix += 1
                new_out_dir = f"{out_dir}_{suffix}"
            out_dir = new_out_dir
            ui.info(f"📂 Output diganti ke: {out_dir}")
        else:
            ui.attention("⚠ Folder lama akan ditimpa.")

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
def auto_select_engine(zip_file: str, wordlist: str) -> str:
    """
    Auto pilih engine terbaik berdasarkan ukuran wordlist & RAM.
    - PythonEngine v12 persistent sekarang jauh lebih cepat → threshold dinaikkan.
    """
    try:
        size = os.path.getsize(wordlist)
    except Exception:
        size = 0

    # ambil RAM
    try:
        ram_total = psutil.virtual_memory().total
    except Exception:
        ram_total = 0

    # Heuristik baru v12
    if size <= 3 * 10**6:  # wordlist <= 3 MB
        ui.info(f"🤖 Auto: memilih PythonEngine (wordlist {size/1e6:.1f} MB ≤ 50 MB)")
        return "python"

    elif ram_total > 2 * 10**9:  # RAM > 2 GB
        ui.info(f"🤖 Auto: memilih PythonEngine (RAM cukup besar: {ram_total/1e9:.1f} GB)")
        return "python"

    else:
        ui.info(f"🤖 Auto: memilih JohnEngine (wordlist {size/1e6:.1f} MB, RAM {ram_total/1e9:.1f} GB)")
        return "john"