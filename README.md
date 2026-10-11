# Dasbor Terminal Jadwal Salat — Jam Digital Peaclock

Dasbor jam digital + hitung mundur waktu salat untuk terminal.
Jam besarnya **persis sama** dengan [peaclock](https://github.com/octobanana/peaclock)
`view digital` — tanpa modifikasi.

---

## Bentuk jam (persis peaclock `view digital`)

Diambil langsung dari kode sumber peaclock:

| Berkas sumber peaclock | Yang diambil |
|---|---|
| `src/peaclock/peaclock.hh` | tabel `_symbol` — font piksel **3 kolom × 5 baris** per digit |
| `src/peaclock/peaclock.cc` | `set_clock_digital()`, `fill_digital()`, `draw_clock()` |
| `cfg/digital` | `block 2 1`, `padding 2 1`, `margin 2 1`, `ratio 2 1` |

Aturan gambar:

- Setiap **digit** = grid **3 × 5 blok**.
- **Rasio blok : jarak = 2 : 1** pada kedua arah — hasil pengukuran piksel
  screenshot resmi `res/cfg/digital.png`:

  | Ukuran pada screenshot resmi | Nilai |
  |---|---|
  | lebar 1 dot | 40 px |
  | jarak antar dot | 20 px |
  | ➜ rasio | **2 : 1** |
  | tinggi dot / jarak vertikal | 42 px / 21 px → **2 : 1** |

- Blok harus tampak **persegi**, jadi `blok_w` karakter = `blok_h` baris.
- **Titik dua** = 1 blok pada baris ke-2 dan ke-4.
- Susunan kolom mengikuti `set_clock_digital()`:

```
 H  H  H  ·  H  H  H  ·  :  ·  M  M  M  ·  M  M  M  ·  :  ·  S  S  S  ·  S  S  S
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
```

Contoh hasil (`05:54:05`, x_block=2, x_space=2):

```
██  ██  ██      ██  ██  ██              ██  ██  ██      ██      ██              ██  ██  ██      ██  ██  ██
```

### Ukuran menyesuaikan terminal (`choose_geometry`)

Dipilih geometri terbesar yang muat, semuanya dengan rasio blok : jarak = 2 : 1:

| Terminal | Blok | Jarak | Hasil |
|---|---|---|---|
| ≥ 160 kolom | 4 × 2 | 2 × 1 | **persis peaclock resmi** (160 × 14) |
| 82 – 159 kolom | 2 × 1 | 1 × 1 | 80 × 9 |
| < 82 kolom | 1 × 1 | 1 × 1 | 53 × 9 |

Catatan: pada terminal < 160 kolom, jarak vertikal tidak bisa lebih kecil dari
1 baris, sehingga rasio vertikal menjadi 1 : 1 (rasio horizontal tetap 2 : 1,
sesuai screenshot resmi). Untuk tampilan paling persis, lebarkan terminal
minimal 160 kolom.

---

## Tampilan: grid 3 kolom × 4 baris berbingkai

Semua waktu memakai **satu font yang sama**: peaclock `cfg/default`
(tabel `_symbol` 3 × 5, `padding 0 0` → blok rapat membentuk karakter padat).

```
┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
│           JAM            │          SUBUH           │          DZUHUR          │
│          14:32           │          04:18           │          11:43           │
│                          ├──────────────────────────┼──────────────────────────┤
│   Minggu, 11 Okt 2026    │          IQAMAT          │          IQAMAT          │
│   28 Rabi'ul Akhir 1448H │          04:33           │          12:13           │
│      ⏳ MENUJU ASHAR      │                          │                          │
│   00 Jam 03 Menit 27 Dtk │                          │                          │
├──────────────────────────┼──────────────────────────┼──────────────────────────┤
│          ASHAR           │         MAGHRIB          │          ISYA'           │
│          14:44           │          17:49           │          18:58           │
├──────────────────────────┼──────────────────────────┼──────────────────────────┤
│          IQAMAT          │          IQAMAT          │          IQAMAT          │
│          15:04           │          18:04           │          19:13           │
└──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

- **Baris 1** : jam berdetak + azan Subuh + azan Dzuhur.
- **Baris 2** : info jam + iqamat Subuh + iqamat Dzuhur.
- **Baris 3** : azan Ashar + azan Maghrib + azan Isya'.
- **Baris 4** : iqamat Ashar + iqamat Maghrib + iqamat Isya'.

Rincian:

- Sel **JAM** menempati kolom 1 baris 1–2 (menyatu, tanpa garis pemisah di dalamnya)
  berisi jam `HH:MM` **tanpa detik**; yang berdetak hanya **titik dua**
  (menyala saat detik genap, padam saat detik ganjil), lalu tanggal Masehi,
  Hijriah, dan hitung mundur ke waktu salat berikutnya.
- **Iqamat** = waktu azan + jeda menit dari `config.json`
  (`subuh_iqamat`, `dzuhur_iqamat`, `ashar_iqamat`, `maghrib_iqamat`, `isya_iqamat`).
- Semua sel berukuran **sama**; bingkai kotak antar waktu salat memakai
  karakter garis (`┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ ─ │`).

### Penyesuaian otomatis

Ukuran blok, padding sel, dan tinggi baris dipilih agar selalu muat
(lebar **dan** tinggi):

| Kondisi terminal | Yang dilakukan |
|---|---|
| lebar ≥ 216 | blok 4, padding 2 |
| lebar ≥ 162 | blok 3, padding 2 |
| lebar ≥ 109 | blok 2, padding 2 |
| lebar < 109 | blok 1, padding 2 → 1 → 0 |
| tinggi pas-pasan | baris iqamat kehilangan label "IQAMAT" (hemat 2 baris) |
| makin pendek | header menyusut: judul+lokasi+kosong → judul+lokasi → judul |
| terlalu kecil | beralih ke daftar teks ringkas (`SUBUH 04:18/04:33 ...`) |

### Asal-usul font

| Berkas sumber peaclock | Yang diambil |
|---|---|
| `src/peaclock/peaclock.hh` | tabel `_symbol` — font piksel **3 kolom × 5 baris** |
| `src/peaclock/peaclock.cc` | `set_clock_digital()`, `fill_digital()`, `draw_clock()` |
| `cfg/default` | `block 2 1`, `padding 0 0`, `set seconds off` |

Peta kolom dari `set_clock_digital()` (dipakai untuk `HH:MM`):

```
idx:  0  1  2 | 3 | 4  5  6 | 7 | 8 | 9 | 10 11 12 | 13 | 14 15 16
      H  H  H |   | h  h  h |   | : |   |  M  M  M |    |  m   m  m
```

---

## Menjalankan

```bash
python3 main.py            # dasbor jam (tekan q untuk keluar)
python3 main.py --cli      # jadwal hari ini sebagai teks
python3 main.py --config   # lihat konfigurasi tersimpan
python3 main.py --set "Bogor"          # ganti lokasi (cari nama kota)
python3 main.py --set-id 1204          # ganti lokasi via ID
python3 main.py --set-judul "..."      # ganti judul dasbor
python3 main.py --set-iqamat dzuhur 20 # atur jeda iqamat
```

---

## Berkas

| Berkas | Keterangan |
|---|---|
| `dashboard.py` | Dasbor + renderer jam peaclock digital & `cfg/default` |
| `main.py` | Entry point CLI |
| `config.py` / `config.json` | Judul, lokasi, jeda iqamat |
| `api_client.py` | Klien MyQuran Open API (Bimas Islam Kemenag) |
| `bimasislam_client.py` | Klien langsung situs Bimas Islam |

Sumber data jadwal salat: Bimas Islam Kemenag RI.
