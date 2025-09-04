# utils/retry.py
from ui import messages as ui
from ui.menu import radio_grid_menu, pick_file_with_ranger
from engines.john_engine import JohnEngine

def john_retry(zip_file, john_path="~/john/run", live=False):
    """
    Retry helper untuk JohnEngine.
    Dipanggil kalau hasil awal JohnEngine NOT_FOUND.
    """
    mode = radio_grid_menu("Mau Coba Lagi?", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
    if mode == "wordlist":
        new_wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
        if new_wordlist and new_wordlist.lower().endswith(".txt"):
            return JohnEngine(zip_file, wordlist=new_wordlist,
                              john_path=john_path, live=live).run()
    elif mode == "incremental":
        return JohnEngine(zip_file, wordlist=None,
                          john_path=john_path, live=live).run()
    else:
        ui.warning("⚠️ Dibatalkan oleh user.")
        return None
