# utils/benchmark.py
from __future__ import annotations
import os
import time
from typing import Callable, Dict, Any, Optional, List


def dry_run(zip_file: str, wordlist: Optional[str] = None) -> Dict[str, Any]:
    """
    Validasi cepat input tanpa brute force.
    """
    issues: List[str] = []

    if not zip_file or not os.path.exists(zip_file):
        issues.append("ZIP tidak ditemukan.")
    elif not zip_file.lower().endswith(".zip"):
        issues.append("File bukan .zip.")

    if wordlist is not None:
        if not os.path.exists(wordlist):
            issues.append("Wordlist tidak ditemukan.")
        elif not wordlist.lower().endswith(".txt"):
            issues.append("Wordlist harus .txt.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "paths": {"zip": zip_file, "wordlist": wordlist},
    }


def benchmark_engine(
    label: str,
    func: Callable[[], Dict[str, Any]],
    repeat: int = 1,
) -> Dict[str, Any]:
    """
    Jalankan callable engine kecil beberapa kali, hitung waktu rata-rata.
    `func` diharapkan menjalankan brute pada sampel kecil (misal 5k baris).
    """
    times: List[float] = []
    last_result: Dict[str, Any] = {}
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = func()
        dt = time.perf_counter() - t0
        times.append(dt)
        last_result = result or {}
    avg = sum(times) / len(times) if times else 0.0
    return {"label": label, "avg_seconds": avg, "sample_result": last_result}
