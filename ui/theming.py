# ui/theming.py V2
"""
Theming registry v2 dengan style yang lebih antimainstream.
"""

from __future__ import annotations

THEMES = {
    # 🍧 Default aman
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

    # 👾 Hacker vibes
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

    # 🌌 Neon retro (80s cyberpunk)
    "cyberpunk": {
        "info": "bright_magenta",
        "bold_info": "bold bright_magenta",
        "attention": "bright_cyan",
        "white": "bright_white",
        "blue": "bright_blue",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel": "bright_magenta",
        "title": "bold bright_cyan",
        "subtitle": "dim bright_magenta",
        "text": "bright_white",
        "status": "bright_magenta",
    },

    # 🕶 Dracula style
    "dracula": {
        "info": "bright_cyan",
        "bold_info": "bold bright_cyan",
        "attention": "bright_magenta",
        "white": "bright_white",
        "blue": "bright_blue",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel": "bright_magenta",
        "title": "bold bright_white",
        "subtitle": "dim bright_cyan",
        "text": "bright_white",
        "status": "bright_green",
    },

    # 🌅 Sunset vibes
    "sunset": {
        "info": "bright_yellow",
        "bold_info": "bold bright_yellow",
        "attention": "bright_red",
        "white": "bright_white",
        "blue": "bright_magenta",
        "success": "bright_red",
        "warning": "bright_yellow",
        "error": "bright_black",
        "panel": "bright_red",
        "title": "bold bright_yellow",
        "subtitle": "dim bright_magenta",
        "text": "bright_white",
        "status": "bright_red",
    },

    # 🌊 Ocean deep
    "ocean": {
        "info": "bright_cyan",
        "bold_info": "bold bright_cyan",
        "attention": "blue",
        "white": "bright_white",
        "blue": "bright_blue",
        "success": "cyan",
        "warning": "bright_yellow",
        "error": "bright_red",
        "panel": "blue",
        "title": "bold bright_cyan",
        "subtitle": "dim blue",
        "text": "bright_white",
        "status": "cyan",
    },
}

_current_theme = "default"

def set_theme(name: str):
    global _current_theme
    if name not in THEMES:
        raise ValueError(f"Theme '{name}' tidak ditemukan. Pilih dari: {', '.join(THEMES.keys())}")
    _current_theme = name

def get_style(key: str) -> str:
    """Ambil warna dari theme aktif, fallback ke white kalau tidak ada"""
    return THEMES.get(_current_theme, THEMES["default"]).get(key, "white")

def get_current_theme() -> str:
    return _current_theme