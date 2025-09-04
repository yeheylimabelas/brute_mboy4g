# engines/hybrid_engine.py
from __future__ import annotations
import time
from ui import messages as ui
from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john

class HybridEngine:
    name = "hybrid"
    mode = "wordlist+incremental"

    def __init__(self, zip_file: str, wordlist: str, **kwargs):
        self.zip_file = zip_file
        self.wordlist = wordlist
        self.kwargs = kwargs

    def run(self):
        ui.info("🚀 HybridEngine dimulai: PythonEngine → JohnEngine (fallback)")

        # tahap 1: PythonEngine
        t0 = time.time()
        result_python = brute_python_fast(self.zip_file, self.wordlist, **self.kwargs)
        if result_python and result_python.get("password"):
            ui.success("✔ Password ditemukan oleh PythonEngine")
            return {
                **result_python,
                "engine": "hybrid-python",
                "elapsed": time.time() - t0
            }

        ui.warning("❌ PythonEngine gagal menemukan password, lanjut ke JohnEngine...")

        # tahap 2: JohnEngine
        result_john = brute_john(self.zip_file, wordlist=None, **self.kwargs)
        if result_john and result_john.get("password"):
            ui.success("✔ Password ditemukan oleh JohnEngine")
            return {
                **result_john,
                "engine": "hybrid-john",
                "elapsed": time.time() - t0
            }

        ui.error("❌ HybridEngine gagal menemukan password")
        return {
            "password": None,
            "elapsed": time.time() - t0,
            "rate": 0.0,
            "status": "not_found",
            "engine": "hybrid",
        }


# wrapper agar tetap bisa dipanggil langsung
def brute_hybrid(zip_file: str, wordlist: str, **kwargs):
    return HybridEngine(zip_file, wordlist, **kwargs).run()
