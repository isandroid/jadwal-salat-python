# Dasbor Terminal Jadwal Salat Masjid Nasr

Aplikasi **Dasbor Terminal Jam Digital & Jadwal Salat** otomatis yang dioptimalkan untuk tampilan layar lebar (resolusi **1366x768** atau terminal fullscreen). Data jadwal salat resmi bersumber dari Direktorat Jenderal Bimbingan Masyarakat Islam (Bimas Islam) Kementerian Agama RI.

---

## 🌟 Fitur Utama

1. **Judul Kustom**: Menampilkan judul dasbor masjid sesuai konfigurasi di [`config.json`](file:///home/isa/jadwal-salat/config.json) (default: `"Jadwal Salat Masjid Nasr"`).
2. **Jam Digital Real-Time**: Tampilan jam digital besar font blok 5-baris (`HH:MM:SS`) yang berdetak setiap detik secara *smooth* tanpa kedipan (*flicker-free*).
3. **Lokasi & Kalender**: Menampilkan nama lokasi, ID tempat, tanggal Masehi, dan tanggal Hijriah otomatis.
4. **Countdown Waktu Salat**: Menghitung mundur menuju waktu salat berikutnya secara *live* setiap detik.
5. **Kartu Jadwal Salat (8 Waktu)**:
   - IMSAK, SUBUH, TERBIT, DHUHA, DZUHUR, ASHAR, MAGHRIB, ISYA'.
   - Waktu salat berikutnya diberi sorotan (*highlight*) warna emas dengan border tebal `┏━┓` dan label `[BERIKUT]`.
   - Waktu yang sudah terlewat diberi efek redup (*dim*).
6. **Responsif Layar**:
   - Di layar 1366x768 (atau terminal lebar $\ge$ 120 kolom): Seluruh 8 kartu disusun sejajar dalam 1 baris horizontal.
   - Di terminal lebih kecil (< 120 kolom): Otomatis membagi menjadi 2 baris (4 kartu per baris).

---

## ⚙️ File Konfigurasi: [`config.json`](file:///home/isa/jadwal-salat/config.json)

Parameter judul, lokasi, serta jeda waktu iqamat (dalam menit setelah azan) tersimpan dalam format JSON pada file [`config.json`](file:///home/isa/jadwal-salat/config.json):

```json
{
  "judul": "Jadwal Salat Masjid Nasr",
  "lokasi_id": "1204",
  "lokasi_nama": "KAB. BOGOR",
  "subuh_iqamat": 15,
  "dzuhur_iqamat": 20,
  "ashar_iqamat": 15,
  "maghrib_iqamat": 10,
  "isya_iqamat": 15
}
```

---

## 📖 Daftar Perintah Menjalankan Aplikasi

Berikut adalah seluruh perintah yang dapat digunakan:

### 1. Menjalankan Dasbor Terminal (Jam Digital, Jadwal Salat, & Iqamat)
Jalankan perintah ini untuk membuka antarmuka dasbor terminal utama:
```bash
python3 main.py
```
atau dapat dijalankan langsung via file modul dasbor:
```bash
python3 dashboard.py
```
> **Kontrol:** Tekan tombol **`q`** atau kombinasi **`Ctrl + C`** pada keyboard untuk keluar dari dasbor.

---

### 2. Melihat Konfigurasi Aktif
Menampilkan judul, ID lokasi, nama lokasi, dan pengaturan jeda iqamat yang tersimpan di `config.json`:
```bash
python3 main.py --config
```

---

### 3. Mengatur Jeda Waktu Iqamat (5 Waktu Salat)
Mengatur menit jeda iqamat setelah azan untuk Subuh, Dzuhur, Ashar, Maghrib, atau Isya:
```bash
# Contoh mengatur jeda Iqamat Dzuhur menjadi 20 menit
python3 main.py --set-iqamat dzuhur 20

# Contoh mengatur jeda Iqamat Subuh menjadi 15 menit
python3 main.py --set-iqamat subuh 15

# Contoh mengatur jeda Iqamat Maghrib menjadi 10 menit
python3 main.py --set-iqamat maghrib 10
```

---

### 4. Mengubah Judul Dasbor Masjid
Memperbarui judul dasbor yang tersimpan di `config.json`:
```bash
python3 main.py --set-judul "Jadwal Salat Masjid Nasr"
```

---

### 5. Mengubah Lokasi Default yang Tersimpan
Anda dapat mengubah lokasi default menggunakan pencarian nama kota atau langsung dengan ID tempat:

- **Berdasarkan nama kota/kabupaten** (otomatis mencari ID dan menyimpan):
  ```bash
  python3 main.py --set "Bogor"
  python3 main.py --set "Bandung"
  python3 main.py --set "Jakarta"
  ```

- **Berdasarkan ID lokasi secara langsung**:
  ```bash
  python3 main.py --set-id 1204
  ```

---

### 6. Mode Teks Cepat (Non-Interaktif)
Jika Anda hanya ingin melihat jadwal salat hari ini dalam format teks sederhana (tanpa membuka dasbor interaktif):
```bash
python3 main.py --cli
```

---

### 7. Cek Jadwal Kota Lain Tanpa Mengubah Konfigurasi
Untuk memeriksa jadwal salat kota lain secara sementara tanpa mengubah lokasi default yang tersimpan di `config.json`:
```bash
python3 main.py "Surabaya"
python3 main.py "Yogyakarta"
python3 main.py "Makassar"
```

---

### 8. Menampilkan Bantuan Perintah
Melihat ringkasan opsi perintah di terminal:
```bash
python3 main.py --help
```

---

## 📁 Struktur Berkas Proyek

- [`config.json`](file:///home/isa/jadwal-salat/config.json): File konfigurasi parameter judul dan lokasi default.
- [`config.py`](file:///home/isa/jadwal-salat/config.py): Modul pembaca dan penyimpan konfigurasi.
- [`dashboard.py`](file:///home/isa/jadwal-salat/dashboard.py): Modul tampilan dasbor terminal, jam digital real-time, dan kartu jadwal salat.
- [`api_client.py`](file:///home/isa/jadwal-salat/api_client.py): Modul client API jadwal salat resmi Kemenag RI (MyQuran Open API).
- [`bimasislam_client.py`](file:///home/isa/jadwal-salat/bimasislam_client.py): Modul client koneksi langsung ke situs internal Bimas Islam Kemenag.
- [`main.py`](file:///home/isa/jadwal-salat/main.py): Entry point utama aplikasi berbasis CLI.
- [`README.md`](file:///home/isa/jadwal-salat/README.md): Dokumentasi lengkap panduan dan daftar perintah aplikasi.
