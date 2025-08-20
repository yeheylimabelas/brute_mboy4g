# engines/base.py
from __future__ import annotations
from typing import Optional, Dict, Any


class BaseEngine:
    """
    Fondasi semua engine. Gunakan result_schema() untuk menyatukan format hasil.
    Engine turunan minimal implement `run()` dan mengembalikan dict schema ini.
    """

    name: str = "base"
    mode: str = "unknown"

    def __init__(self, zip_file: str, wordlist: Optional[str] = None, **kwargs):
        self.zip_file = zip_file
        self.wordlist = wordlist
        self.kwargs = kwargs or {}

    def run(self) -> Dict[str, Any]:
        """Override di engine turunan."""
        raise NotImplementedError

    # --- helper schema konsisten ---
    def result_schema(
        self,
        password: Optional[str],
        elapsed: float,
        rate: Optional[float] = None,
        status: str = "ok",
        mode: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "engine": self.name,
            "mode": mode or self.mode,
            "password": password,
            "elapsed": float(elapsed) if elapsed is not None else None,
            "rate": float(rate) if rate is not None else None,
            "status": status,
            **(extra or {}),
        }
