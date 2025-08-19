# utils/analyzer.py
from __future__ import annotations
import os
import zipfile
from typing import Dict, Any


def _zipinfo_has_aes(info: zipfile.ZipInfo) -> bool:
    """
    Deteksi indikasi AES:
    - Extra field signature 0x9901 (AES encryption).
    - Beberapa arsip menandai AES via method 99.
    """
    # Cek method 99 (WinZip AES)
    if getattr(info, "compress_type", None) == 99:
        return True

    extra: bytes = getattr(info, "extra", b"") or b""
    # Cari signature 0x9901 (little-endian = b'\x01\x99')
    return b"\x01\x99" in extra or b"\x99\x01" in extra


def get_zip_metadata(zip_file: str) -> Dict[str, Any]:
    """
    Kembalikan metadata dasar zip untuk heuristik:
    {
        encrypted: bool,
        aes: bool,
        file_count: int,
        total_uncompressed: int,
        total_compressed: int
    }
    """
    if not os.path.exists(zip_file):
        raise FileNotFoundError(f"ZIP tidak ditemukan: {zip_file}")

    with zipfile.ZipFile(zip_file, "r") as zf:
        infos = zf.infolist()

        encrypted = any((i.flag_bits & 0x1) == 0x1 for i in infos) if infos else False
        aes = any(_zipinfo_has_aes(i) for i in infos) if infos else False

        total_uncompressed = sum(getattr(i, "file_size", 0) for i in infos)
        total_compressed = sum(getattr(i, "compress_size", 0) for i in infos)

        return {
            "encrypted": bool(encrypted),
            "aes": bool(aes),
            "file_count": len(infos),
            "total_uncompressed": int(total_uncompressed),
            "total_compressed": int(total_compressed),
        }
