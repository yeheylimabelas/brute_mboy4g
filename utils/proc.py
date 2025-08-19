# utils/proc.py
# -------------------------------------------------------------------
# Utility untuk jalankan subprocess dengan live streaming + dashboard
# -------------------------------------------------------------------

import subprocess
from typing import Optional
from ui.dashboard import Dashboard
from ui.panels import panel_info


def run_with_dashboard(
    cmd: str,
    cwd: Optional[str] = None,
    logger=None,
    label: str = "Process",
) -> int:
    """
    Jalankan command dengan Dashboard (progress CPU/RAM spinner).
    Tidak menghitung total karena sebagian besar CLI (John) tidak expose total kandidat.
    """
    panel_info(f"$ {cmd}")
    if logger:
        logger.write(f"RUN {cmd}")

    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    with Dashboard(total=None, label=label) as dash:
        for line in proc.stdout:
            s = line.rstrip("\n")
            if s and logger:
                logger.write(s)
            dash.update()  # refresh CPU/RAM
        return proc.wait()
