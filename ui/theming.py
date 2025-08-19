# ui/theming.py
"""
Simple theming registry untuk konsistensi warna UI.
`messages.py` bisa membaca warna dari sini kalau ingin.
"""

from __future__ import annotations

THEMES = {
    "default": {
        "info": "cyan",
        "bold_info": "bold cyan",
        "attention": "magenta",
        "white": "white",
        "blue": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "panel": "cyan",
        "title": "bold white",
        "subtitle": "dim",
        "text": "white",
        "status": "green",
    },
    "matrix": {
        "info": "bright_green",
        "bold_info": "bold bright_green",
        "attention": "green",
        "white": "bright_black",
        "blue": "bright_green",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel": "green",
        "title": "bold bright_green",
        "subtitle": "dim bright_green",
        "text": "bright_green",
        "status": "bright_green",
    },
    "neon": {
        "info": "bright_cyan",
        "bold_info": "bold bright_cyan",
        "attention": "bright_magenta",
        "white": "bright_white",
        "blue": "bright_blue",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel": "bright_magenta",
        "title": "bold bright_cyan",
        "subtitle": "dim bright_magenta",
        "text": "bright_white",
        "status": "bright_green",
    },
}

_current_theme = "default"

def set_theme(name: str):
    global _current_theme
    if name not in THEMES:
        raise ValueError(f"Theme '{name}' tidak ditemukan. Pilih dari: {', '.join(THEMES.keys())}")
    _current_theme = name

def get_style(key: str) -> str:
    """ambil warna dari theme aktif, fallback ke white kalau tidak ada"""
    return THEMES.get(_current_theme, THEMES["default"]).get(key, "white")

def get_current_theme() -> str:
    return _current_theme