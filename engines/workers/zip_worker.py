# workers/zip_worker.py
"""
Persistent worker untuk brute force ZIP.
Worker ini buka file ZIP sekali, lalu menerima chunk password lewat Queue.
"""

import pyzipper

def worker_process(zip_path, task_queue, result_queue, stop_event):
    """
    Worker loop:
      - Ambil chunk password dari task_queue
      - Coba semua password
      - Kalau ketemu → kirim ke result_queue
      - Kalau stop_event diset → keluar
    """
    try:
        with pyzipper.AESZipFile(zip_path) as zf:
            names = zf.namelist()
            if not names:
                result_queue.put(("ERROR", "ZIP kosong"))
                return
            testfile = names[0]

            while not stop_event.is_set():
                try:
                    pw_chunk = task_queue.get(timeout=0.5)  # tunggu sebentar
                except Exception:
                    continue

                if pw_chunk is None:
                    # sinyal untuk berhenti
                    break

                for pw in pw_chunk:
                    if stop_event.is_set():
                        break
                    try:
                        zf.setpassword(pw.encode("utf-8"))
                        with zf.open(testfile) as fp:
                            fp.read(16)
                        # password benar
                        result_queue.put(("FOUND", pw))
                        stop_event.set()
                        return
                    except Exception:
                        pass

                # kalau semua gagal, balikin jumlah yg sudah dites
                result_queue.put(("COUNT", len(pw_chunk)))

    except Exception as e:
        result_queue.put(("ERROR", str(e)))
