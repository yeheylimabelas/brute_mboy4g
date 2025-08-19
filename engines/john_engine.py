from __future__ import annotations
import os, time, subprocess
from typing import Optional, Dict, Any, List

from .base import BaseEngine
from ui import messages as ui
from ui import dashboard
from ui.menu import radio_grid_menu, pick_file_with_ranger
from ui.theming import get_style
from utils.io import extract_with_password


# helper run
def run_command(cmd: str, cwd: Optional[str] = None, live: bool = False):
    if live:
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd)
        proc.wait()
        return "", "", proc.returncode
    else:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return res.stdout.strip(), res.stderr.strip(), res.returncode


def _john_show_password(john_bin: str, hash_abs: str, fmt: str, john_path: str):
    out, _, _ = run_command(f"{john_bin} --show --format={fmt} '{hash_abs}'", cwd=john_path)
    if not out:
        return None, ""
    for line in out.splitlines():
        if ":" in line and not line.lower().startswith("1 password hash") \
           and not line.lower().startswith("no password hashes"):
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[1].strip(), out
    return None, out


class JohnEngine(BaseEngine):
    name = "john"

    def __init__(self, zip_file: str,
                 wordlist: Optional[str] = None,
                 john_path: str = "~/john/run",
                 live: bool = False,
                 resume: bool = False,
                 mode: str = "wordlist",
                 **kwargs):
        super().__init__(zip_file, wordlist, **kwargs)
        self.john_path = os.path.expanduser(john_path)
        self.live = live
        self.resume = resume
        self.mode = mode

    def run(self) -> Dict[str, Any]:
        if not os.path.exists(self.zip_file):
            ui.error(f"❌ File ZIP tidak ditemukan: {self.zip_file}")
            return None
        if not os.path.exists(self.john_path):
            ui.error(f"❌ Folder John the Ripper tidak ditemukan: {self.john_path}")
            return None

        zip2john_bin = os.path.join(self.john_path, "zip2john")
        john_bin = os.path.join(self.john_path, "john")

        basename = os.path.splitext(os.path.basename(self.zip_file))[0]
        hash_file = f"john_{basename}.txt"
        hash_abs = os.path.abspath(hash_file)

        ui.attention("🔑 Generate hash dengan zip2john", title="JOHN ENGINE")
        out, err, code = run_command(f"{zip2john_bin} '{self.zip_file}'")
        if code != 0 or not out:
            ui.error(f"Gagal generate hash:\n{err or '(output kosong)'}")
            return None
        with open(hash_file, "w") as f:
            f.write(out)

        tried: List[str] = []
        start = time.time()
        found_pw: Optional[str] = None
        chosen_fmt: Optional[str] = None

        for fmt in ["ZIP", "PKZIP"]:
            tried.append(fmt)
            if self.wordlist:
                ui.warning(f"🚀 Jalankan John ({fmt}) dengan wordlist {os.path.basename(self.wordlist)}")
                run_command(
                    f"{john_bin} --format={fmt} --wordlist='{os.path.abspath(self.wordlist)}' '{hash_abs}'",
                    cwd=self.john_path, live=self.live
                )
            else:
                ui.warning(f"🚀 Jalankan John ({fmt}) dengan mode incremental")
                run_command(
                    f"{john_bin} --format={fmt} --incremental '{hash_abs}'",
                    cwd=self.john_path, live=self.live
                )

            pw, _raw = _john_show_password(john_bin, hash_abs, fmt, self.john_path)
            if pw:
                found_pw = pw
                chosen_fmt = fmt
                break

        elapsed = time.time() - start
        try:
            os.remove(hash_abs)
        except Exception as e:
            ui.warning(f"⚠ Gagal hapus hash file: {e}")

        result = self.result_schema(
            password=found_pw,
            elapsed=elapsed,
            rate=None,
            status="ok" if found_pw else "not_found",
            mode="wordlist" if self.wordlist else "incremental",
            extra={"tried": tried, "format": chosen_fmt}
        )

        # tampilkan ringkasan
        dashboard.show_summary(result)

        if found_pw:
            try:
                outdir = extract_with_password(self.zip_file, found_pw)
                ui.success(f"✔ Semua file diekstrak ke: {outdir}", title="JOHN ENGINE")
            except Exception as e:
                ui.warning(f"⚠ Password benar tapi ekstraksi gagal:\n{e}")
        else:
            ui.error(
                f"❌ Password tidak ditemukan oleh John\n"
                f"[{get_style('white')}]Format yang dicoba: {', '.join(tried)}[/]\n"
                f"[{get_style('info')}]⏳ Total waktu: {elapsed:.2f} detik[/]\n"
                f"[{get_style('info')}]Tips: coba wordlist berbeda atau jalankan manual John untuk verifikasi[/]",
                title=f"[{get_style('error')}]JOHN ENGINE"
            )
            # Retry menu
            mode = radio_grid_menu("Mau Coba Lagi?", ["Wordlist", "Incremental", "Exit!"], cols=2).lower()
            if mode == "wordlist":
                new_wordlist = pick_file_with_ranger("Pilih file wordlist (.txt)")
                if new_wordlist and new_wordlist.lower().endswith(".txt"):
                    return JohnEngine(self.zip_file, wordlist=new_wordlist,
                                      john_path=self.john_path, live=self.live).run()
            elif mode == "incremental":
                return JohnEngine(self.zip_file, wordlist=None,
                                  john_path=self.john_path, live=self.live).run()
            else:
                ui.warning("⚠️ Dibatalkan oleh user.")

        return result


# wrapper lama supaya kompatibel
def brute_john(zip_file, wordlist=None, john_path="~/john/run", live=False, resume=False):
    mode = "wordlist" if wordlist else "incremental"
    eng = JohnEngine(zip_file, wordlist, john_path=john_path, live=live, resume=resume, mode=mode)
    return eng.run()
