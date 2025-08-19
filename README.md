# 🔐 BRUTEZIPER v11

BRUTEZIPER adalah **multi-engine ZIP password brute-forcer** dengan dukungan:

* Engine Python (multiprocessing, resume, adaptive chunk)
* Engine John the Ripper (wordlist + incremental, live support)
* Hybrid engine (Python + John otomatis)
* Auto engine (heuristik memilih Python/John)
* Theming (ubah warna/style tampilan)
* Resume & Extract cerdas

Didesain agar **mudah dipakai di Termux/Android**, Linux, maupun sistem lain yang punya Python 3.9+.

---

## 🚀 Fitur Utama

* 🐍 **Python Engine** – brute force cepat pakai multiprocessing, resume otomatis.
* 🔑 **John Engine** – integrasi dengan [John the Ripper](https://www.openwall.com/john/), mendukung mode wordlist & incremental.
* ⚡ **Hybrid Engine** – coba Python dulu, lalu fallback ke John.
* 🤖 **Auto Engine** – memilih engine otomatis (berdasarkan ukuran wordlist).
* 🎨 **Theming** – ubah tampilan warna output (pilih di menu).
* 📊 **Live Dashboard** – real-time statistik (rate, ETA, tested, status).
* 📂 **Smart Extract** – hasil ekstrak selalu masuk ke `OutputExtract/`, dengan opsi:

  * Timpa
  * Ganti Nama
  * Exit

---

## 📦 Instalasi

### Clone Repo & Masuk Folder

```bash
git clone https://github.com/mboy4g/bruteziper.git
cd bruteziper
```

### Install Dependensi

Pastikan **Python ≥ 3.9** sudah ada.

```bash
pip install rich pyzipper psutil readchar
```

### Opsional: Install John the Ripper

Kalau mau pakai John engine:

```bash
# di Termux
pkg install john

# di Ubuntu/Debian
sudo apt install john
```

---

## ▶️ Cara Menjalankan

### Mode Interaktif (disarankan 🚀)

```bash
python brute_V11.py
```

Kamu akan melihat menu:

```
╭─────────── Pilih Engine Untuk Brute ───────────╮
│ [*] Python   [ ] John   [ ] John Live           │
│ [ ] Hybrid   [ ] Auto   [ ] Theme   [ ] Exit!   │
╰────────────────────────────────────────────────╯
```

#### Flow:

1. Pilih Engine (Python/John/Hybrid/Auto).
2. Pilih file ZIP via ranger.
3. Pilih wordlist (kalau perlu).
4. Dashboard live jalan otomatis.
5. Setelah selesai, muncul **Summary + Extract**.

### Mode CLI Langsung

Contoh:

```bash
# Python engine pakai wordlist rockyou.txt
python brute_V11.py --engine python --zip file.zip --wordlist rockyou.txt

# John engine incremental
python brute_V11.py --engine john --mode incremental --zip file.zip

# Hybrid engine
python brute_V11.py --engine hybrid --zip file.zip --wordlist wordlist.txt

# Auto engine
python brute_V11.py --engine auto --zip file.zip --wordlist big.txt

## 📂 Struktur Proyek

```
bruteziper/
├── brute_V11.py          # Entry point utama (CLI + interaktif)
├── engines/
│   ├── base.py           # BaseEngine class
│   ├── python_engine.py  # Engine Python
│   ├── john_engine.py    # Engine John
│   ├── hybrid_engine.py  # Engine Hybrid
├── ui/
│   ├── theming.py        # Tema warna
│   ├── messages.py       # Helper pesan UI
│   ├── dashboard.py      # Live dashboard & summary
│   └── menu.py           # Menu interaktif (radio grid, ranger)
├── utils/
│   ├── io.py             # Resume, extract, file ops
└── requirements.txt
```

---

## 📖 Catatan

* Disarankan pakai **ranger** untuk pemilihan file di menu interaktif.
* Jika ZIP terenkripsi kompleks, **John Engine** lebih andal.
* Hasil ekstrak selalu ada di folder `OutputExtract/`.
* Gunakan `--resume` untuk melanjutkan brute force Python.

---

## ✨ Credits

* Dibuat oleh **MBOY4G**
* As **Ryven Novyr Asmadeus**
