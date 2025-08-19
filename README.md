# 🔐 BRUTEZIPER v11

Brute-force tool untuk file **ZIP** dengan berbagai engine:
- **Python Engine** → brute force native Python (multi-core, adaptive chunking, resume support).
- **John Engine** → pakai [John the Ripper](https://www.openwall.com/john/) (mode wordlist & incremental).
- **Hybrid Engine** → gabungan Python (awal) lalu fallback ke John.
- **Auto Engine** → pilih engine otomatis berdasarkan ukuran wordlist.

Dibuat oleh **MBOY4G**  
_As Ryven Novyr Asmadeus_

---

## ✨ Fitur Utama
- 🧩 **Multi-engine**: Python, John, Hybrid, Auto.
- ⚡ **Adaptive parallelism**: menyesuaikan jumlah worker & batch.
- 🔄 **Resume**: bisa lanjut brute force dari posisi terakhir.
- 📊 **Live Dashboard**: status real-time (tested, rate, ETA, CPU/RAM).
- 🎨 **Theming**: pilih warna/tampilan (Matrix, Neon, Monokai, dll).
- 📂 **Smart Extraction**: hasil ekstrak otomatis ke `OutputExtract/` dengan opsi:
  - **Timpa**
  - **Ganti Nama**
  - **Exit**
- 🧠 **Auto Engine Selector**:  
  - Wordlist < 5MB → Python.  
  - Wordlist besar → John.  
- 🔍 **Brute Summary**: laporan hasil (engine, mode, password, elapsed, rate).

---

## 📦 Struktur Project
