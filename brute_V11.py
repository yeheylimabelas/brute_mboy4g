#!/usr/bin/env python3
# brute.py – BRUTEZIPER Main Entrypoint
# --------------------------------------------------------------------
# Integrasi semua engine:
#   - python_engine
#   - john_engine
#   - hybrid_engine
#
# CLI Options:
#   --engine {python,john,hybrid,auto}
#   --wordlist (opsional tergantung engine)
#   --workers, --chunk, --resume, --john-path, --live
#
# UI:
#   - panels untuk informasi stage/status
#   - hasil akhir ditampilkan dengan panel_success / panel_warning
# --------------------------------------------------------------------

import sys
import argparse
import os

# Engines
from engines.python_engine import brute_python_fast_v11
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid, brute_auto

# UI
from ui.panels import (
    panel_info,
    panel_success,
    panel_warning,
    panel_error,
)

# Utils
from utils.file_ops import is_txt, is_zip


# ---------------- Main -----------------

def main():
    parser = argparse.ArgumentParser(
        description="BRUTEZIPER – Universal ZIP Password Cracker"
    )
    parser.add_argument("zip", help="Path ke file ZIP terenkripsi")
    parser.add_argument(
        "--engine",
        choices=["python", "john", "hybrid", "auto"],
        default="hybrid",
        help="Pilih engine brute-force (default: hybrid)",
    )
    parser.add_argument(
        "--wordlist",
        help="Path ke file wordlist (.txt). Tidak wajib untuk --engine john incremental",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Jumlah proses worker (python engine, default=cores-1)",
    )
    parser.add_argument(
        "--chunk", type=int, default=1000, help="Ukuran batch awal untuk python engine"
    )
    parser.add_argument(
        "--john-path",
        default="~/john/run",
        help="Path ke folder run/ John (default: ~/john/run)",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Nonaktifkan fitur resume"
    )
    parser.add_argument(
        "--no-live", action="store_true", help="Nonaktifkan live dashboard (untuk John)"
    )
    args = parser.parse_args()

    # Validasi input
    if not is_zip(args.zip):
        panel_error(f"File ZIP tidak valid: {args.zip}")
        sys.exit(1)

    if args.engine in ("python", "hybrid", "auto") and (not args.wordlist or not is_txt(args.wordlist)):
        panel_error("Engine ini memerlukan wordlist (.txt) yang valid.")
        sys.exit(1)

    # Jalankan engine
    try:
        if args.engine == "python":
            res = brute_python_fast_v11(
                args.zip,
                args.wordlist,
                processes=args.workers,
                start_chunk=args.chunk,
                resume=(not args.no_resume),
            )
        elif args.engine == "john":
            res = brute_john(
                args.zip,
                wordlist=args.wordlist,
                john_path=args.john_path,
                live=(not args.no_live),
                resume=(not args.no_resume),
            )
        elif args.engine == "hybrid":
            res = brute_hybrid(
                args.zip,
                args.wordlist,
                processes=args.workers,
                start_chunk=args.chunk,
                resume=(not args.no_resume),
                john_path=args.john_path,
                live=(not args.no_live),
            )
        elif args.engine == "auto":
            res = brute_auto(
                args.zip,
                args.wordlist,
                processes=args.workers,
                start_chunk=args.chunk,
                resume=(not args.no_resume),
                john_path=args.john_path,
                live=(not args.no_live),
            )
        else:
            panel_error(f"Engine tidak dikenal: {args.engine}")
            sys.exit(1)

    except KeyboardInterrupt:
        panel_warning("Dibatalkan oleh user (CTRL+C).")
        sys.exit(130)

    # Tampilkan hasil
    if res.get("password"):
        panel_success(f"🎉 Password ditemukan: [bold]{res['password']}[/bold]")
    else:
        panel_warning("Selesai, tapi password tidak ditemukan.")

    panel_info(f"⏱ Waktu total: {res.get('elapsed', 0):.2f}s")
    panel_info(f"📂 Log: {res.get('log_file')}")


if __name__ == "__main__":
    main()
