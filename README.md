# Dasbor Terminal Jadwal Salat — Jam Digital Peaclock Style

Aplikasi **jam digital + countdown salat** untuk terminal, dengan tampilan jam
bergaya **peaclock** (`view digital`, `block 2 1`, `padding 2 1`, `ratio 2 1`).
Data jadwal salat bersumber dari Bimas Islam Kemenag RI (via MyQuran Open API).

---

## Tampilan

```
                            JADWAL SALAT MASJID NASR
                 📍 Lokasi: KAB. BOGOR, JAWA BARAT (ID: 1204)
              📅 Minggu, 11 Oktober 2026  |  🌙 28 Rabi'ul Akhir 1448 H

        ──────────────────────────────────────────────────────────

                        ██████          ██████
                    ██      ██              ██  ██
                    ██      ██    ██        ██  ██    ██
                        ██████          ██████  ██████
                    ██      ██    ██    ██          ██    ██
                    ██      ██          ██          ██
                        ██████          ██████

                    ⏳ Menuju Waktu ASHAR: 01 Jam 19 Menit 47 Detik
```

Jam besar di tengah = jam berdetak (update tiap detik).

---

## Fitur

1. **Jam digital peaclock** — 7-segment, blok 2×1, glyph 6 kolom (digit & `:`
   sama lebar sehingga grid selalu rata).
2. **Countdown** — hitung mundur ke waktu salat berikutnya, real-time.
3. **Header** — judul, lokasi, tanggal Masehi & Hijriah.
4. **Sumber data resmi** — Bimas Islam Kemenag RI.

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

## File

| File | Keterangan |
|------|-----------|
| `dashboard.py` | Tampilan jam digital peaclock + countdown |
| `main.py` | Entry point CLI |
| `config.py` / `config.json` | Konfigurasi judul, lokasi, jeda iqamat |
| `api_client.py` | Klien MyQuran Open API (Bimas Islam Kemenag) |
| `bimasislam_client.py` | Klien langsung situs Bimas Islam |

---

## Catatan teknis — font peaclock

Setiap glyph dibentuk dari grid **7 baris × 6 kolom** (3 blok × 2 kolom),
mengikuti `block 2 1` + `ratio 2 1`:

```
 ██████      segmen a (atas)
██    ██     segmen f + b
██    ██
 ██████      segmen g (tengah)
██    ██     segmen e + c
██    ██
 ██████      segmen d (bawah)
```

Digit dan titik dua (`:`) **sama-sama 6 kolom**, sehingga `HH:MM:SS` selalu
rata tanpa pergeseran. Digit `1` memakai segmen `b`+`c` sehingga tetap berada
di dalam kotak 6 kolom yang sama.
