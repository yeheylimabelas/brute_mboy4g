# bruteziper/utils/progress.py
from __future__ import annotations
import time
from multiprocessing import Value, Lock
from typing import Optional


class AtomicCounter:
    """Counter aman untuk multiprocessing."""
    def __init__(self, initial: int = 0):
        self._val = Value("q", initial)  # int64
        self._lock = Lock()

    def inc(self, n: int = 1) -> int:
        with self._lock:
            self._val.value += n
            return self._val.value

    def get(self) -> int:
        with self._lock:
            return self._val.value

    def set(self, v: int) -> None:
        with self._lock:
            self._val.value = v


class RateMeter:
    """
    Hitung kecepatan (percobaan/detik). Panggil .add(n) setiap batch.
    Gunakan .rate() untuk angka terbaru (moving average sederhana).
    """
    def __init__(self, smoothing: float = 0.2):
        self.start_ts = time.perf_counter()
        self.count = 0
        self._rate = 0.0
        self._last = self.start_ts
        self.alpha = smoothing

    def add(self, n: int = 1) -> None:
        now = time.perf_counter()
        dt = max(1e-9, now - self._last)
        inst = n / dt
        # EMA
        self._rate = self.alpha * inst + (1 - self.alpha) * self._rate
        self._last = now
        self.count += n

    def rate(self) -> float:
        return float(self._rate)

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_ts


class ProgressState:
    """
    State sederhana untuk global progress (dipakai dashboard).
    """
    def __init__(self, total: Optional[int] = None):
        self.total = total
        self.counter = AtomicCounter(0)
        self.rate = RateMeter()

    def step(self, n: int = 1):
        self.counter.inc(n)
        self.rate.add(n)

    def get(self):
        done = self.counter.get()
        return {
            "done": done,
            "total": self.total,
            "rate": self.rate.rate(),
            "elapsed": self.rate.elapsed(),
            "pct": (done / self.total * 100.0) if self.total else None,
        }
