# Dasbor Terminal Jadwal Salat — Jam Digital Peaclock

Dasbor jam digital + hitung mundur waktu salat untuk terminal.
Jam besarnya **persis sama** dengan [peaclock](https://github.com/octobanana/peaclock)
`view digital` — tanpa modifikasi.

---

## Ringkasan

| Aspek | Isi |
|---|---|
| Tampilan | Jam digital gaya peaclock (font piksel 3 × 5) + grid 3 kolom × 4 baris berbingkai |
| Isi dasbor | 5 waktu salat (azan + iqamat), jam berdetak, detik, hitung mundur, tanggal Masehi & Hijriah |
| Sumber data | Bimas Islam Kemenag RI (via [MyQuran Open API](https://api.myquran.com/v2/)) |
| Penyimpanan | SQLite lokal (`jadwal_salat.db`) — internet cukup **1× per bulan**, sisanya **offline** |
| Kustomisasi | Lokasi, judul, jeda iqamat per salat, padding, warna ANSI (4/8/24-bit), saklar baris |
| Adaptif | Ukuran blok, padding, dan header menyesuaikan ukuran terminal; ada mode ringkas `--resolusi` |
| Mode lain | Mode teks `--cli` (juga jalan offline) |

Aplikasi murni Python + `requests` — tanpa basis data server, tanpa kerangka kerja (framework).

---

## Mulai cepat

### Prasyarat

- **Python 3.8+** (dikembangkan dan diuji pada Python 3.13, Linux).
- Terminal dengan dukungan **UTF-8**, karakter kotak (`┌ ┬ ┐ …`), dan emoji.
- Satu-satunya dependensi pihak ketiga: **[`requests`](https://pypi.org/project/requests/)**.

### Instalasi

```bash
# 1. pastikan Python tersedia
python3 --version

# 2. pasang dependensi (satu-satunya)
python3 -m pip install requests

# 3. jalankan dari direktori proyek
cd jadwal-salat
python3 main.py
```

Saat pertama dijalankan, `config.json` dan `jadwal_salat.db` **dibuat otomatis**
— tidak ada langkah setup lain. Untuk jadwal kota selain KAB. BOGOR, sekali
jalankan dengan internet lalu pilih lokasi (lihat `--set` di bawah).

### Perintah dasar

```bash
python3 main.py            # dasbor jam interaktif (tekan q untuk keluar)
python3 main.py --cli      # jadwal hari ini sebagai teks
python3 main.py --help     # daftar lengkap perintah
```

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
- Sel **JAM**: jam `HH:MM` tanpa detik, dengan **titik dua statis** (tidak
  berkedip) — karena detiknya sudah tampil. **Detik** ditampilkan sebagai dua
  digit di baris kedua sel, **tepat di bawah bagian `mm`** (kolom 10–16 dari
  tata letak 17 kolom).
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

### Titik dua statis / berkedip

Karena detik sudah tampil di bawah `mm`, **titik dua jam tidak lagi berkedip**
(statis menyala terus). Diatur lewat `config.json`:

```json
"kolon_berkedip": false   // false = statis (default), true = berkedip tiap detik
```

Terverifikasi pada `block_w = 3` (kolom karakter 24–26, baris glyph ke-1 dan ke-3):

| Setelan | detik 10 | detik 11 | detik 12 | detik 13 |
|---|---|---|---|---|
| `false` (statis) | menyala | menyala | menyala | menyala |
| `true` (berkedip) | menyala | padam | menyala | padam |

### Detik di bawah `mm`

Detik digambar dengan fungsi `render_peaclock_seconds(ss, block_w)`: grid 17 kolom
yang sama, tetapi kedua digitnya diletakkan pada posisi kolom milik bagian `MM`
(`DIGIT_COLS_NOSEC[2:4]` = kolom 10–12 dan 14–16). Hasilnya detik selalu rata
persis di bawah `mm`, berapa pun ukuran blok yang dipakai.

Terverifikasi: pada `block_w = 2`, detik menempati kolom 20–33 — sama persis
dengan rentang blok `MM` (20–33).

### Warna (bisa diatur)

Terminal mendukung tiga tingkat warna:

| Tingkat | Jumlah | Format di `config.json` | Contoh |
|---|---|---|---|
| 4-bit (dasar) | 16 | `<nomor>` atau tebal `1;<nomor>` | `"1;9"` (merah terang) |
| **8-bit (palet)** | **256** | `38;5;<nomor>` | `"1;38;5;196"` (merah terang) |
| 24-bit (RGB bebas) | 16,7 juta | `38;2;<R>;<G>;<B>` | `"38;2;255;140;0"` (jingga) |

Nilai boleh diawali `1;` untuk **tebal**, atau dikosongkan (`""`) untuk kembali
ke warna bawaan terminal.

Kunci yang tersedia (bawaan):

| Kunci | Bawaan | Untuk |
|---|---|---|
| `judul` | `1;38;5;220` | judul dasbor |
| `subjudul` | `38;5;153` | lokasi & tanggal |
| `nama` | `1;38;5;231` | nama waktu salat (SUBUH, DZUHUR, ...) |
| `jam` | `1;38;5;79` | jam berdetak + detik |
| `waktu_azan` | `1;38;5;79` | angka waktu azan |
| `waktu_iqamat` | `38;5;44` | angka waktu iqamat |
| `berikutnya` | `1;38;5;226` | waktu salat berikutnya (disorot) |
| `label_iqamat` | `38;5;110` | label "IQAMAT" |
| `hitung_mundur` | `1;38;5;227` | baris hitung mundur di header |
| `garis` | `38;5;240` | garis/bingkai |

```bash
python3 main.py --warna                              # lihat palet 256 warna + warna terpakai
python3 main.py --warna waktu_azan 1;38;5;196        # ubah warna waktu azan
python3 main.py --warna waktu_iqamat 38;2;255;140;0  # pakai RGB bebas
python3 main.py --warna waktu_azan ""                # kembalikan ke warna bawaan terminal
```

Nilai disimpan di `config.json`:

```json
"warna": { "waktu_azan": "1;38;5;196", "judul": "1;38;5;51" }
```

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

## Mode ringkas untuk layar kecil (`--resolusi`)

```bash
python3 main.py --resolusi 1280x720    # mode ringkas
python3 main.py --resolusi             # resolusi dideteksi otomatis (xrandr / DRM)
```

Mode ringkas **menyembunyikan tiga baris** agar grid dapat tempat maksimal:

| Baris | Normal | Mode ringkas |
|---|---|---|
| 📍 Lokasi: ... | tampil | **hilang** |
| ⏳ Menuju Waktu ... xx Jam yy Menit zz Detik | tampil | **hilang** |
| Tekan [q] ... • Sumber Data: ... | tampil | **hilang** |
| Judul | tampil | tampil |
| 📅 Tanggal (Masehi \| Hijriah) | tampil | tampil |
| Grid waktu salat | tampil | tampil (blok lebih besar) |

Argumen resolusi dipakai untuk **memperkirakan ukuran terminal** bila ukuran
sebenarnya tidak terbaca (mis. stdout bukan tty). Perkiraan memakai ukuran sel
karakter dari `ukuran_sel` (bawaan `"8x18"` px); untuk 1280×720 → 160 × 40.
Bila dijalankan di terminal biasa, ukuran sebenarnya tetap lebih diutamakan.

Tiga baris itu juga bisa dimatikan permanen tanpa `--resolusi`, lewat
`config.json`:

```json
"tampilkan_lokasi": false,
"tampilkan_hitung_mundur": false,
"tampilkan_footer": false
```

## Menjalankan

```bash
python3 main.py             # dasbor jam (tekan q untuk keluar)
python3 main.py --dashboard # dasbor — alias eksplisit dari mode bawaan
python3 main.py --cli       # jadwal hari ini sebagai teks
python3 main.py Bogor       # jadwal kota tertentu sebagai teks (cari nama kota)
python3 main.py --config    # lihat konfigurasi tersimpan
python3 main.py --set "Bogor"          # ganti lokasi (cari nama kota)
python3 main.py --set-id 1204          # ganti lokasi via ID
python3 main.py --set-judul "..."      # ganti judul dasbor
python3 main.py --set-iqamat dzuhur 20 # atur jeda iqamat (subuh/dzuhur/ashar/maghrib/isya)
python3 main.py --help                 # tampilkan semua perintah
```

Keluar dari dasbor: tekan `q`, `Esc`, atau `Ctrl+C`.

### Perintah lengkap

| Perintah | Fungsi |
|---|---|
| *(tanpa argumen)* / `--dashboard` | Dasbor terminal interaktif |
| `--cli` | Jadwal hari ini sebagai teks (dari lokasi di `config.json`) |
| `<nama_kota>` | Jadwal kota tertentu sebagai teks (mis. `python3 main.py Bogor`) |
| `--set <nama_kota>` | Cari kota lalu simpan ID + namanya ke `config.json` |
| `--set-id <id>` | Simpan ID lokasi langsung ke `config.json` |
| `--set-judul <teks>` | Ubah judul dasbor |
| `--set-iqamat <salat> <menit>` | Atur jeda iqamat (subuh/dzuhur/ashar/maghrib/isya) |
| `--config` | Tampilkan konfigurasi tersimpan |
| `--data` | Tampilkan isi penyimpanan lokal (SQLite) |
| `--resolusi [WxH]` | Mode ringkas; tanpa argumen → deteksi otomatis (xrandr/DRM) |
| `--warna` | Lihat palet 256 warna + warna yang dipakai |
| `--warna <kunci> <nilai>` | Ubah satu warna (mis. `--warna waktu_azan 1;38;5;196`) |
| `-h`, `--help` | Tampilkan bantuan |

---

## Referensi `config.json`

Semua kunci dikelola `config.py`. Kunci yang belum ada diisi otomatis dengan
nilai bawaan saat konfigurasi dibaca. Sebagian besar bisa diubah lewat CLI
(`--set`, `--set-id`, `--set-judul`, `--set-iqamat`, `--warna`); sisanya bisa
disunting langsung lalu jalankan ulang aplikasi.

| Kunci | Bawaan | Fungsi |
|---|---|---|
| `judul` | `"Jadwal Salat Masjid Nasr"` | judul dasbor (huruf besar + jarak antar huruf bila muat) |
| `lokasi_id` | `"1204"` | ID kota untuk pengambilan jadwal |
| `lokasi_nama` | `"KAB. BOGOR"` | nama lokasi yang tampil di header |
| `subuh_iqamat` | `15` | jeda iqamat Subuh (menit setelah azan) |
| `dzuhur_iqamat` | `20` | jeda iqamat Dzuhur |
| `ashar_iqamat` | `15` | jeda iqamat Ashar |
| `maghrib_iqamat` | `10` | jeda iqamat Maghrib |
| `isya_iqamat` | `15` | jeda iqamat Isya' |
| `padding_atas` | `2` | baris kosong minimum di atas tampilan |
| `padding_bawah` | `2` | baris kosong minimum di bawah tampilan |
| `padding_ratakan` | `true` | `true` = sisa ruang dibagi rata (tampilan di tengah) |
| `kolon_berkedip` | `false` | `true` = titik dua jam berkedip tiap detik |
| `warna` | `{}` | kunci warna yang diubah saja (lihat bagian **Warna**) |
| `tampilkan_lokasi` | `true` | `false` = sembunyikan baris 📍 Lokasi |
| `tampilkan_hitung_mundur` | `true` | `false` = sembunyikan baris ⏳ Menuju Waktu |
| `tampilkan_footer` | `true` | `false` = sembunyikan baris petunjuk + sumber data |
| `ukuran_sel` | `"8x18"` | perkiraan ukuran 1 sel karakter (px) untuk `--resolusi` |

Catatan: isi `config.json` bisa berbeda dari tabel bawaan bila sudah pernah
diubah (mis. jeda iqamat pada proyek ini: Dzuhur 30, Ashar 20, Maghrib 15).

---

## Struktur proyek

| Berkas | Keterangan |
|---|---|
| `main.py` | Entry point CLI — seluruh perintah argumen |
| `dashboard.py` | Dasbor: renderer jam peaclock, grid 3 × 4, header/footer, loop interaktif |
| `config.py` | Baca/tulis `config.json` + definisi nilai bawaan |
| `config.json` | Konfigurasi (dibuat otomatis bila belum ada) |
| `api_client.py` | Klien MyQuran Open API — cari kota, jadwal harian & bulanan |
| `bimasislam_client.py` | Klien alternatif langsung situs Bimas Islam — **tidak dipakai** alur utama |
| `cache.py` | Penyimpanan lokal SQLite (`jadwal_salat.db`) |
| `jadwal_salat.db` | Data jadwal lokal (dibuat otomatis, tidak ikut di-commit) |
| `debug_cards.py` | Skrip debug lama untuk memeriksa render kartu |

Alur data: `main.py` → `dashboard.py` → `cache.py` (bila bulan sudah lengkap,
tanpa internet) → `api_client.py` (hanya bila perlu unduh).

---

## Pemecahan masalah

| Gejala | Penyebab / solusi |
|---|---|
| `ModuleNotFoundError: No module named 'requests'` | `python3 -m pip install requests` |
| Pesan *"belum ada data"* / *"Gagal memuat jadwal"* | Belum pernah terunduh. Jalankan sekali dengan koneksi internet, lalu cek `python3 main.py --data` |
| Ingin unduh ulang jadwal dari awal | Hapus `jadwal_salat.db` (aman — dibuat ulang otomatis), lalu jalankan dengan internet |
| Tampilan terpotong / tidak muat | Perbesar terminal (ideal ≥ 160 kolom), atau pakai mode `python3 main.py --resolusi 1280x720`; ukuran bisa dicek dengan `stty size` |
| Dasbor berantakan saat output di-pipe/direkam | Ukuran tty tidak terbaca → sertakan `--resolusi WxH` |
| Garis bingkai atau emoji meleset lebar | Pakai font monospace dengan dukungan emoji + karakter kotak unicode, dan locale UTF-8 (`echo $LANG`) |
| Internet mati | Tidak masalah — footer menampilkan *"offline — pakai data tersimpan"*, jadwal diambil dari SQLite |
| Data terasa basi / tidak diperbarui | Dasbor otomatis mengambil ulang saat tanggal berganti; bulan berikutnya disiapkan sejak tanggal 25 |
| Lokasi lama masih muncul di `--data` | Cache disimpan per kota — data lama aman dibiarkan |

---

Sumber data jadwal salat: Bimas Islam Kemenag RI.
