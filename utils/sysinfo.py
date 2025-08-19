# utils/sysinfo.py
# -------------------------------------------------------------------
# Ambil informasi sistem (CPU, RAM, Temperatur) secara cross-platform.
# Khusus Termux/Android mungkin terbatas (temp kadang None).
# -------------------------------------------------------------------

import os
import psutil

# CPU %
def get_cpu_percent(interval: float = 0.1) -> float:
    try:
        return psutil.cpu_percent(interval=interval)
    except Exception:
        return 0.0

# RAM usage %
def get_ram_usage() -> float:
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0

# Temperatur (°C), fallback None kalau tidak ada
def get_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # ambil sensor pertama yang ada
        for name, entries in temps.items():
            if entries:
                return entries[0].current
        return None
    except Exception:
        return None

# Jumlah CPU cores
def count_cpu() -> int:
    try:
        return psutil.cpu_count(logical=True) or 1
    except Exception:
        return 1
