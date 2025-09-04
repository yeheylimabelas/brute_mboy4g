# tools/benchmark.py
import os, tempfile, random, string
from ui import messages as ui
from ui import dashboard
from engines.python_engine import brute_python_fast
from engines.john_engine import brute_john

def make_dummy_zip(zip_path: str, password: str):
    """Bikin ZIP dummy kecil dengan password tertentu"""
    import pyzipper
    with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zf:
        zf.setpassword(password.encode())
        zf.writestr("dummy.txt", "Hello from BRUTEZIPER v12!")

def make_dummy_wordlist(path: str, password: str, size=50000):
    """Bikin wordlist random dan selipkan password benar di tengah"""
    with open(path, "w") as f:
        for i in range(size):
            if i == size // 2:
                f.write(password + "\n")
            else:
                f.write("".join(random.choices(string.ascii_lowercase, k=6)) + "\n")

def run_benchmark():
    ui.info("⚡ Menjalankan benchmark engine (Python v12 vs John)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "dummy.zip")
        wordlist_path = os.path.join(tmpdir, "dummy.txt")
        password = "brute123"

        # generate dummy files
        make_dummy_zip(zip_path, password)
        make_dummy_wordlist(wordlist_path, password)

        results = {}

        # Benchmark PythonEngine
        res_py = brute_python_fast(zip_path, wordlist_path, processes=2, start_chunk=500)
        results["PythonEngine v12"] = res_py

        # Benchmark JohnEngine
        res_john = brute_john(zip_path, wordlist=wordlist_path, john_path="~/john/run", live=False)
        results["JohnEngine"] = res_john

        # Show results
        for name, res in results.items():
            if res:
                ui.info(f"\n📊 Hasil benchmark {name}:")
                dashboard.show_summary(res)
