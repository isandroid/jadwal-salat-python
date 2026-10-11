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

Tiap waktu salat menempati **satu kotak menyatu**: waktu azan di atas, waktu
iqamat di bawah — **tanpa garis pemisah** di antaranya. Sel jam juga menyatu
(kolom 1, baris 1–2).

```
                    J A D W A L   S A L A T   M A S J I D   N A S R
                        📍 Lokasi: KAB. BOGOR, JAWA BARAT (ID: 1204)
                 📅 Minggu, 11 Oktober 2026  |  🌙 28 Rabi'ul Akhir 1448 H
                     ⏳ Menuju Waktu MAGHRIB: 01 Jam 27 Menit 06 Detik

┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
│           JAM            │          SUBUH           │          DZUHUR          │
│          16:21           │          04:18           │          11:43           │
│             53           │          IQAMAT          │          IQAMAT          │
│                          │          04:33           │          12:13           │
├──────────────────────────┼──────────────────────────┼──────────────────────────┤
│          ASHAR           │         MAGHRIB          │          ISYA'           │
│          14:44           │          17:49           │          18:58           │
│          IQAMAT          │          IQAMAT          │          IQAMAT          │
│          15:04           │          18:04           │          19:13           │
└──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

Baris (grid) yang tersusun:

| Baris | Kolom 1 | Kolom 2 | Kolom 3 |
|---|---|---|---|
| 1 | jam berdetak | azan Subuh | azan Dzuhur |
| 2 | info jam | iqamat Subuh | iqamat Dzuhur |
| 3 | azan Ashar | azan Maghrib | azan Isya' |
| 4 | iqamat Ashar | iqamat Maghrib | iqamat Isya' |

Garis pemisah mendatar hanya ada **satu**, yaitu antara baris 2 dan 3
(pemisah dua kelompok). Sel yang menyatu digambar tanpa garis, dan tingginya
bertambah otomatis.

Rincian:

- **Judul, lokasi, tanggal, dan hitung mundur** berada di header (di atas grid).
- Sel **JAM**: jam `HH:MM` tanpa detik — yang berdetak hanya **titik dua**
  (menyala saat detik genap, padam saat detik ganjil). **Detik** ditampilkan
  sebagai dua digit di baris kedua sel, **tepat di bawah bagian `mm`**
  (kolom 10–16 dari tata letak 17 kolom).
- **Iqamat** = waktu azan + jeda menit dari `config.json`
  (`subuh_iqamat`, `dzuhur_iqamat`, `ashar_iqamat`, `maghrib_iqamat`, `isya_iqamat`).
- Bingkai memakai karakter garis: `┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ ─ │`.

### Padding atas / bawah (bisa diatur)

Diatur dari `config.json`:

```json
"padding_atas": 2,        // minimum baris kosong di atas
"padding_bawah": 2,       // minimum baris kosong di bawah
"padding_ratakan": true   // true = sisa ruang dibagi rata (tampilan di tengah)
```

| Setelan | Hasil pada terminal 168×43 |
|---|---|
| `padding_ratakan: true` (default) | 5 baris atas, 6 baris bawah (tampilan di tengah) |
| `padding_ratakan: false` | tepat **2 baris atas, 2 baris bawah**; sisa ruang dibiarkan di bawah |

Padding juga diperhitungkan saat memilih ukuran grid, dan otomatis diturunkan
(2 → 1 → 0) **hanya bila grid 3 × 4 tidak muat karenanya** — grid selalu
diutamakan.

**Ukuran terminal acuan (layar 1366×768, MATE, font Monospace 10): 168 kolom ×
43 baris.** Di ukuran itu: grid memakai blok lebar 3 (digit besar), lebar total
163 kolom dari 168, tinggi 43 baris — semuanya muat.

Untuk memeriksa ukuran terminal yang sedang dipakai: jalankan `stty size`
(menampilkan `baris kolom`).

### Gaya teks (bold / menonjol)

Terminal tidak bisa mengubah ukuran font, jadi penekanan dilakukan dengan
**bold + warna kontras**, dan judul diberi **jarak antar huruf** agar tampak
lebih besar:

| Elemen | Gaya | Kode ANSI |
|---|---|---|
| Judul | bold kuning terang + jarak antar huruf | `1;38;5;220` |
| Nama waktu salat (JAM, SUBUH, ...) | **bold putih terang** | `1;38;5;231` |
| Waktu salat berikutnya | bold kuning (disorot) | `1;38;5;226` |
| Waktu azan | bold teal | `1;38;5;79` |
| Waktu iqamat | teal (tanpa bold, sekunder) | `38;5;44` |
| Label "IQAMAT", info sel jam | abu-biru muda | `38;5;110` |

Jarak antar huruf pada judul otomatis dimatikan bila versi renggangnya tidak
muat di lebar terminal (diuji: judul 54 karakter pada terminal 120 kolom masih
renggang, 115 kolom; judul yang lebih panjang kembali rapat).

Catatan: ANSI tidak menyediakan pengubah ukuran font. Bila Pak Isa ingin nama
waktu salat benar-benar *lebih tinggi* (bukan sekadar bold), itu harus digambar
sebagai seni blok — konsekuensinya tiap sel bertambah tinggi sehingga layout
3 × 4 tidak lagi muat di terminal 36 baris.

### Detik di bawah `mm`

Detik digambar dengan fungsi `render_peaclock_seconds(ss, block_w)`: grid 17 kolom
yang sama, tetapi kedua digitnya diletakkan pada posisi kolom milik bagian `MM`
(`DIGIT_COLS_NOSEC[2:4]` = kolom 10–12 dan 14–16). Hasilnya detik selalu rata
persis di bawah `mm`, berapa pun ukuran blok yang dipakai.

Terverifikasi: pada `block_w = 2`, detik menempati kolom 20–33 — sama persis
dengan rentang blok `MM` (20–33).

### Penyesuaian otomatis

Ukuran blok, padding sel, tinggi baris, header, dan jarak footer dipilih agar
selalu muat (lebar **dan** tinggi):

| Kondisi terminal | Yang dilakukan |
|---|---|
| lebar ≥ 216 | blok 4, padding 2 |
| lebar ≥ 162 | blok 3, padding 2 |
| lebar ≥ 109 | blok 2, padding 2 |
| lebar < 109 | blok 1, padding 2 → 1 → 0 |
| tinggi pas-pasan | baris iqamat kehilangan label "IQAMAT" (hemat 2 baris) |
| makin pendek | header menyusut: judul+lokasi+kosong → judul+lokasi → judul |
| masih kurang | baris kosong sebelum footer dihilangkan |
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

## Penyimpanan lokal (SQLite) — tidak perlu terus konek internet

Jadwal salat **disimpan di SQLite** (`jadwal_salat.db`, dibuat otomatis) lewat
modul `cache.py`. Internet hanya dihubungi **sekali per bulan**.

| Tabel | Isi |
|---|---|
| `jadwal` | `kota_id`, `tanggal`, `tanggal_teks`, `imsak`, `subuh`, `terbit`, `dhuha`, `dzuhur`, `ashar`, `maghrib`, `isya`, `lokasi`, `daerah`, `diunduh` |

Cara kerja saat aplikasi dijalankan:

1. Cek SQLite — bila **bulan berjalan sudah lengkap** (≥ 28 hari), tidak ada
   koneksi internet sama sekali.
2. Bila belum lengkap, unduh **satu bulan penuh** (`get_jadwal_bulanan`) lalu
   simpan — cukup **satu permintaan** untuk seluruh bulan.
3. Bila tanggal hari ini belum ada (mis. awal bulan), unduh harian sebagai
   cadangan.
4. Pada 5 hari terakhir bulan, bulan **berikutnya** ikut disiapkan agar
   pergantian bulan tidak terputus.
5. Bila internet mati, jadwal tetap tampil dari SQLite (mode **offline**).

Footer dasbor menampilkan statusnya: *diperbarui dari internet* ·
*dari penyimpanan lokal (SQLite)* · *offline — pakai data tersimpan*.

### Perintah terkait

```bash
python3 main.py --data     # lihat isi penyimpanan (berkas, jumlah hari, rentang, terakhir diunduh)
python3 main.py --cli      # jadwal teks — juga bekerja offline
```

`jadwal_salat.db` tidak ikut di-commit (lihat `.gitignore`).

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
