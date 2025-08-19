# bruteziper/ui/theming.py
"""
Simple theming registry untuk konsistensi warna UI.
`messages.py` bisa membaca warna dari sini kalau ingin.
"""

from __future__ import annotations
from typing import Dict

_THEMES: Dict[str, Dict[str, str]] = {
    "default": {
        "info": "magenta",
        "attention": "cyan",
        "white": "white",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "panel_title": "bold white",
    },
    "neon": {
        "info": "bright_magenta",
        "attention": "bright_cyan",
        "white": "bright_white",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel_title": "bold bright_white",
    },
    "matrix": {
        "info": "green",
        "attention": "bright_black",
        "white": "white",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "panel_title": "bold green",
    },
}

_active = "default"


def set_theme(name: str) -> None:
    global _active
    if name in _THEMES:
        _active = name
    else:
        raise ValueError(f"Theme '{name}' tidak ditemukan. Pilihan: {list(_THEMES.keys())}")


def get_theme() -> Dict[str, str]:
    return _THEMES[_active].copy()


def resolve_color(kind: str) -> str:
    theme = get_theme()
    return theme.get(kind, "white")
