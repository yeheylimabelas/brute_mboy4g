# engines/hybrid_engine.py
from __future__ import annotations
import time
from typing import Optional, Dict, Any

from .base import BaseEngine
from ui import messages as ui
from ui import dashboard

try:
    from engines.python_engine import brute_python_fast
except Exception:  # pragma: no cover
    brute_python_fast = None

try:
    from engines.john_engine import brute_john
except Exception:  # pragma: no cover
    brute_john = None


class HybridEngine(BaseEngine):
    name = "hybrid"
    mode = "sequential"

    def __init__(
        self,
        zip_file: str,
        wordlist: Optional[str],
        *,
        processes: Optional[int] = None,
        start_chunk: int = 1000,
        resume: bool = True,
        parallel: bool = False,  # placeholder untuk v12.x
        john_path: str = "~/john/run",
        live: bool = True,
        **kwargs,
    ):
        super().__init__(zip_file, wordlist, **kwargs)
        self.processes = processes
        self.start_chunk = start_chunk
        self.resume = resume
        self.parallel = parallel
        self.john_path = john_path
        self.live = live

    def run(self) -> Dict[str, Any]:
        t0 = time.perf_counter()

        if not brute_python_fast or not brute_john:
            ui.error("Engine dependency belum lengkap (python_engine / john_engine).")
            result = self.result_schema(
                password=None, elapsed=0.0, status="error",
                extra={"reason": "missing_dependency"}
            )
            dashboard.show_summary(result)
            return result

        # Tahap 1: Python wordlist
        ui.info("🧪 Tahap 1: Python (wordlist). Jika gagal, lanjut John incremental.", title="HYBRID")
        py_result = brute_python_fast(
            self.zip_file,
            self.wordlist,
            processes=self.processes,
            start_chunk=self.start_chunk,
            resume=self.resume,
        )

        if py_result and py_result.get("password"):
            elapsed = time.perf_counter() - t0
            result = self.result_schema(
                password=py_result.get("password"),
                elapsed=elapsed,
                rate=py_result.get("rate"),
                status="ok",
                mode="python-first",
                extra={"source": "python"}
            )
            dashboard.show_summary(result)
            return result

        # Tahap 2: John incremental
        ui.attention("➡️  Lanjut brute dengan John incremental ...", title="HYBRID")
        john_result = brute_john(
            self.zip_file,
            wordlist=None,
            john_path=self.john_path,
            live=self.live
        )

        elapsed = time.perf_counter() - t0
        if john_result and john_result.get("password"):
            result = self.result_schema(
                password=john_result.get("password"),
                elapsed=elapsed,
                rate=john_result.get("rate"),
                status="ok",
                mode="john-incremental",
                extra={"source": "john", "format": john_result.get("format")}
            )
            dashboard.show_summary(result)
            return result

        result = self.result_schema(
            password=None,
            elapsed=elapsed,
            status="not_found",
            mode="sequential"
        )
        dashboard.show_summary(result)
        return result


# Wrapper fungsi agar kompatibel dengan main.py lama
def brute_hybrid(zip_file: str, wordlist: str, **kwargs) -> Dict[str, Any]:
    eng = HybridEngine(zip_file, wordlist, **kwargs)
    return eng.run()
