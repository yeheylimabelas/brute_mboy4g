# utils/sysinfo.py
# -------------------------------------------------------------
# Utility functions untuk ambil info sistem
# - CPU usage
# - RAM usage
# - Temperatur (jika tersedia)
# -------------------------------------------------------------

import psutil

def get_sysinfo() -> dict:
    """Return dict info CPU, RAM, suhu"""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram_percent = psutil.virtual_memory().percent
    except Exception:
        cpu_percent = 0.0
        ram_percent = 0.0

    temp = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # ambil sensor pertama
            for name, entries in temps.items():
                if entries:
                    temp = entries[0].current
                    break
    except Exception:
        temp = None

    return {
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "temp": temp,
    }

def format_sysinfo() -> str:
    """Return string ringkas CPU/RAM/Suhu"""
    info = get_sysinfo()
    parts = [
        f"CPU {info['cpu_percent']:.1f}%",
        f"RAM {info['ram_percent']:.1f}%",
    ]
    if info["temp"] is not None:
        parts.append(f"🌡 {info['temp']:.1f}°C")
    return " | ".join(parts)
