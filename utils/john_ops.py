# utils/john_ops.py
# -------------------------------------------------------------------
# Utility khusus untuk integrasi John the Ripper
# -------------------------------------------------------------------

import os
import subprocess
from typing import Optional
from utils.file_ops import expand


def run_cmd(
    cmd: str,
    cwd: Optional[str] = None,
    logger=None,
) -> tuple[int, str]:
    """Jalankan perintah shell dan kembalikan (exit_code, output)."""
    if logger:
        logger.write(f"RUN {cmd}")

    try:
        out = subprocess.check_output(
            cmd, shell=True, cwd=cwd, stderr=subprocess.STDOUT, text=True
        )
        if logger:
            logger.write(out.strip())
        return 0, out
    except subprocess.CalledProcessError as e:
        if logger:
            logger.write(e.output)
        return e.returncode, e.output
    except Exception as e:
        if logger:
            logger.write(f"ERROR run_cmd: {e}")
        return 1, str(e)


def zip2john(zip_file: str, john_path: str, logger=None) -> Optional[str]:
    """Konversi ZIP → hash file untuk John."""
    john_path = expand(john_path)
    zip2john_bin = os.path.join(john_path, "zip2john")
    hash_file = os.path.splitext(os.path.basename(zip_file))[0] + ".hash"

    cmd = f"{zip2john_bin} '{zip_file}' > '{hash_file}'"
    code, _ = run_cmd(cmd, cwd=john_path, logger=logger)
    if code != 0 or not os.path.exists(os.path.join(john_path, hash_file)):
        return None
    return os.path.join(john_path, hash_file)


def john_show(hash_file: str, john_path: str, logger=None) -> Optional[str]:
    """Ambil password hasil crack dari John (via `john --show`)."""
    john_path = expand(john_path)
    john_bin = os.path.join(john_path, "john")
    cmd = f"{john_bin} --show '{hash_file}'"

    code, out = run_cmd(cmd, cwd=john_path, logger=logger)
    if code != 0:
        return None

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    return None


def john_cmd(hash_file: str, john_path: str, wordlist: Optional[str] = None, resume: bool = True) -> str:
    """Buat command line untuk John (wordlist / incremental / restore)."""
    john_path = expand(john_path)
    john_bin = os.path.join(john_path, "john")
    restore_file = os.path.join(john_path, "restore")

    if resume and os.path.exists(restore_file):
        return f"{john_bin} --restore"

    if wordlist:
        return f"{john_bin} --format=zip --wordlist='{wordlist}' '{hash_file}'"
    return f"{john_bin} --format=zip --incremental '{hash_file}'"
