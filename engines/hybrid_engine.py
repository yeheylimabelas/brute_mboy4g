from rich.console import Console
from rich.panel import Panel

from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john
from ui import messages as ui

console = Console()

def brute_hybrid(zip_file, wordlist, processes=None, start_chunk=1000, resume=True):
    """
    Hybrid engine:
    1. Coba Python engine dengan wordlist
    2. Jika gagal, lanjut John incremental
    Return dict {password, source, elapsed, ...}
    """
    ui.attention(
        "[cyan]🧪 Tahap 1: Python (wordlist) — jika gagal lanjut John incremental")

    # === Tahap 1: Python brute dengan wordlist ===
    py_result = brute_python_fast(
        zip_file, 
        wordlist, 
        processes=processes, 
        start_chunk=start_chunk, 
        resume=resume
    )

    if py_result and py_result.get("password"):
        ui.success(f"✅ Password ditemukan oleh Python: {py_result['password']}")
        return {
            "password": py_result["password"],
            "source": "python",
            "tested": py_result["tested"],
            "elapsed": py_result["elapsed"],
            "rate": py_result["rate"]
        }

    # === Tahap 2: John incremental ===
    ui.warning(
        "❌ Password tidak ditemukan dalam wordlist. "
        "➡️  Lanjut brute dengan John incremental...")

    john_result = brute_john(
        zip_file, 
        wordlist=None,   # abaikan wordlist, langsung incremental
        john_path="~/john/run", 
        live=True        # tampilkan live output
    )

    if john_result and john_result.get("password"):
        return {
            "password": john_result["password"],
            "source": "john",
            "elapsed": john_result["elapsed"],
            "mode": john_result["mode"],
            "format": john_result["format"]
        }

    return {
        "password": None,
        "source": "hybrid",
        "elapsed": (py_result["elapsed"] if py_result else 0) + (john_result["elapsed"] if john_result else 0),
        "tested": py_result["tested"] if py_result else None
    }
