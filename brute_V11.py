#!/usr/bin/env python3
# BRUTEZIPER v11 – main entry
# -------------------------------------------------------------
# Bisa jalan dengan argparse (CLI mode) atau interactive menu.
# -------------------------------------------------------------

import sys
import argparse

from ui.interactive import interactive_flow
from engines.python_engine import brute_python_fast_v11
from engines.john_engine import brute_john
from engines.hybrid_engine import brute_hybrid


def main():
    # kalau user gak kasih argumen → fallback ke interactive mode
    if len(sys.argv) == 1:
        interactive_flow()
        return

    parser = argparse.ArgumentParser(
        description="BRUTEZIPER v11 – Universal ZIP Password Cracker"
    )
    parser.add_argument("zip", help="Path ke file ZIP terenkripsi")
    parser.add_argument(
        "--engine",
        choices=["python", "john", "hybrid", "auto"],
        default="hybrid",
        help="Pilih engine brute-force (default: hybrid)",
    )
    parser.add_argument("--wordlist", help="Path ke file wordlist (.txt)")
    parser.add_argument("--workers", type=int, default=8, help="Jumlah worker (Python)")
    parser.add_argument("--chunk", type=int, default=1000, help="Ukuran chunk awal (Python)")
    parser.add_argument("--john-path", default="~/john/run", help="Path folder John the Ripper")
    parser.add_argument("--no-resume", action="store_true", help="Matikan fitur resume")
    parser.add_argument("--no-live", action="store_true", help="Matikan live dashboard")

    args = parser.parse_args()

    # jalankan sesuai engine
    if args.engine == "python":
        if not args.wordlist:
            sys.exit("❌ Wordlist wajib untuk Python engine.")
        brute_python_fast_v11(
            args.zip,
            args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=not args.no_resume,
        )

    elif args.engine == "john":
        brute_john(
            args.zip,
            wordlist=args.wordlist,
            john_path=args.john_path,
            live=not args.no_live,
        )

    elif args.engine == "hybrid":
        if not args.wordlist:
            sys.exit("❌ Wordlist wajib untuk Hybrid engine (untuk tahap Python).")
        brute_hybrid(
            args.zip,
            args.wordlist,
            processes=args.workers,
            start_chunk=args.chunk,
            resume=not args.no_resume,
        )

    elif args.engine == "auto":
        # simple auto: coba python dulu, kalau gagal fallback john
        if args.wordlist:
            ok = brute_python_fast_v11(
                args.zip,
                args.wordlist,
                processes=args.workers,
                start_chunk=args.chunk,
                resume=not args.no_resume,
            )
            if ok:
                return
        brute_john(
            args.zip,
            wordlist=None,
            john_path=args.john_path,
            live=not args.no_live,
        )


if __name__ == "__main__":
    main()
