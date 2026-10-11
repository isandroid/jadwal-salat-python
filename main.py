import sys
from datetime import date
from api_client import JadwalSalatAPI
from config import load_config, save_config, CONFIG_FILE_PATH
from dashboard import (TerminalDashboard, hitung_waktu_iqamat,
                       WARNA_DEFAULT, warna_dipakai)
import cache as cache_mod

def tampilkan_jadwal(jadwal_item: dict, cfg: dict):
    print("-------------------------------------------------------")
    print(f" Tanggal : {jadwal_item.get('tanggal', '-')}")
    print("-------------------------------------------------------")
    print(f" IMSAK   : {jadwal_item.get('imsak', '-')}")

    subuh = jadwal_item.get('subuh', '-')
    subuh_iq = hitung_waktu_iqamat(subuh, cfg.get('subuh_iqamat', 15))
    print(f" SUBUH   : {subuh}  (Iqamat: {subuh_iq} [+ {cfg.get('subuh_iqamat', 15)}m])")

    print(f" TERBIT  : {jadwal_item.get('terbit', '-')}")
    print(f" DHUHA   : {jadwal_item.get('dhuha', '-')}")

    dzuhur = jadwal_item.get('dzuhur', '-')
    dzuhur_iq = hitung_waktu_iqamat(dzuhur, cfg.get('dzuhur_iqamat', 20))
    print(f" DZUHUR  : {dzuhur}  (Iqamat: {dzuhur_iq} [+ {cfg.get('dzuhur_iqamat', 20)}m])")

    ashar = jadwal_item.get('ashar', '-')
    ashar_iq = hitung_waktu_iqamat(ashar, cfg.get('ashar_iqamat', 15))
    print(f" ASHAR   : {ashar}  (Iqamat: {ashar_iq} [+ {cfg.get('ashar_iqamat', 15)}m])")

    maghrib = jadwal_item.get('maghrib', '-')
    maghrib_iq = hitung_waktu_iqamat(maghrib, cfg.get('maghrib_iqamat', 10))
    print(f" MAGHRIB : {maghrib}  (Iqamat: {maghrib_iq} [+ {cfg.get('maghrib_iqamat', 10)}m])")

    isya = jadwal_item.get('isya', '-')
    isya_iq = hitung_waktu_iqamat(isya, cfg.get('isya_iqamat', 15))
    print(f" ISYA    : {isya}  (Iqamat: {isya_iq} [+ {cfg.get('isya_iqamat', 15)}m])")
    print("-------------------------------------------------------")

def print_help():
    print("""Penggunaan Aplikasi Jadwal Salat:
  python3 main.py                   -> Buka Dasbor Terminal (Jam digital, jadwal salat, & iqamat)
  python3 main.py --cli             -> Tampilkan jadwal salat versi teks cepat
  python3 main.py <nama_kota>       -> Cek jadwal kota tertentu versi teks
  python3 main.py --set <nama_kota> -> Cari kota dan simpan ID ke config.json
  python3 main.py --set-id <id>     -> Simpan ID lokasi langsung ke config.json
  python3 main.py --set-judul <teks>-> Ubah judul dasbor di config.json
  python3 main.py --set-iqamat <salat> <menit> -> Atur jeda iqamat (subuh/dzuhur/ashar/maghrib/isya)
  python3 main.py --config          -> Tampilkan konfigurasi saat ini
  python3 main.py --data            -> Tampilkan isi penyimpanan lokal (SQLite)
  python3 main.py --warna           -> Lihat palet 256 warna + warna yang dipakai
  python3 main.py --warna <kunci> <nilai> -> Ubah satu warna (mis. --warna waktu_azan 1;38;5;196)
""")

def main():
    api = JadwalSalatAPI()
    today = date.today()
    cfg = load_config()

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ("-h", "--help"):
            print_help()
            return

        if arg == "--dashboard":
            dashboard = TerminalDashboard()
            dashboard.run()
            return

        if arg == "--warna":
            if len(sys.argv) > 3:                     # --warna <kunci> <nilai>
                kunci, nilai = sys.argv[2], sys.argv[3]
                if kunci not in WARNA_DEFAULT:
                    print(f"[-] Kunci '{kunci}' tidak dikenal.")
                    print(f"    Pilihan: {', '.join(WARNA_DEFAULT)}")
                    return
                save_config(warna={**warna_dipakai(cfg), kunci: nilai})
                print(f"[\u2713] Warna '{kunci}' disimpan di config.json: {nilai}")
                print(f"    Contoh tampilannya: {chr(27)}[{nilai}m███ contoh warna{chr(27)}[0m")
                return

            dipakai = warna_dipakai(cfg)
            print("=== Warna yang dipakai sekarang (dari config.json) ===")
            for k, v in dipakai.items():
                tanda = " (bawaan)" if v == WARNA_DEFAULT[k] else " (diubah)"
                sw = (f"{chr(27)}[{v}m\u2588\u2588\u2588{chr(27)}[0m"
                      if v and v != "0" else "   ")
                print(f"  {sw} {k:15s} = {v or '(tanpa warna)'}{tanda}")
            print()
            print("=== Palet 256 warna (8-bit) — pakai nomornya, mis. 1;38;5;<nomor> ===")
            for baris in range(16):
                bagian = []
                for kolom in range(16):
                    n = baris * 16 + kolom
                    bagian.append(f"{chr(27)}[38;5;{n};48;5;{n}m\u2588\u2588\u2588{chr(27)}[0m{n:3d}")
                print(" " + " ".join(bagian))
            print()
            print("=== 16 warna dasar (4-bit) — mis. 1;<nomor> atau <nomor> ===")
            nama = ["hitam", "merah", "hijau", "kuning", "biru", "magenta", "sian", "putih",
                    "hitam-t", "merah-t", "hijau-t", "kuning-t", "biru-t", "magenta-t", "sian-t", "putih-t"]
            for i in range(16):
                print(f"  \033[38;5;{i};48;5;{i}m\u2588\u2588\u2588\033[0m {i:2d} "
                      f"\033[38;5;{i}mcontoh\033[0m  {nama[i]:<10s}", end="")
                if i % 4 == 3:
                    print()
            print()
            print("=== 24-bit (RGB bebas) — format 38;2;<R>;<G>;<B> ===")
            for r, g, b in ((255,140,0),(255,0,128),(0,200,255),(124,252,0)):
                print(f"  \033[38;2;{r};{g};{b};48;2;{r};{g};{b}m\u2588\u2588\u2588\033[0m "
                      f"\033[38;2;{r};{g};{b}mcontoh\033[0m  ->  38;2;{r};{g};{b}")
            print()
            print("Cara mengubah:  python3 main.py --warna <kunci> <nilai>")
            print("Contoh        :  python3 main.py --warna waktu_azan 1;38;5;196")
            return

        if arg in ("--data", "--cache"):
            kota_id = str(cfg.get("lokasi_id", "1204"))
            info = cache_mod.info(kota_id)
            print("=== Penyimpanan Jadwal Salat (SQLite) ===")
            print(f"Berkas      : {info['berkas']}")
            print(f"Kota        : {cfg.get('lokasi_nama')} (ID {kota_id})")
            print(f"Jumlah hari : {info['jumlah_hari']} hari")
            print(f"Rentang     : {info['dari'] or '-'}  s.d.  {info['sampai'] or '-'}")
            print(f"Terakhir    : diunduh {info['diunduh'] or '-'}")
            if info["jumlah_hari"]:
                print("Catatan     : jadwal dapat ditampilkan tanpa internet selama")
                print("              rentang tanggal di atas masih tersedia.")
            else:
                print("Catatan     : belum ada data. Jalankan 'python3 main.py' sekali")
                print("              dengan internet untuk mengunduh satu bulan penuh.")
            return

        if arg == "--config":
            print("=== Konfigurasi Dasbor Tersimpan ===")
            print(f"File  : {CONFIG_FILE_PATH}")
            print(f"Judul : {cfg.get('judul')}")
            print(f"ID    : {cfg.get('lokasi_id')}")
            print(f"Lokasi: {cfg.get('lokasi_nama')}")
            print("--- Waktu Iqamat (menit setelah azan) ---")
            print(f"Subuh  : {cfg.get('subuh_iqamat', 15)} menit")
            print(f"Dzuhur : {cfg.get('dzuhur_iqamat', 20)} menit")
            print(f"Ashar  : {cfg.get('ashar_iqamat', 15)} menit")
            print(f"Maghrib: {cfg.get('maghrib_iqamat', 10)} menit")
            print(f"Isya'  : {cfg.get('isya_iqamat', 15)} menit")
            return

        if arg == "--set-judul" and len(sys.argv) > 2:
            judul_baru = " ".join(sys.argv[2:])
            save_config(judul=judul_baru)
            print(f"[✓] Berhasil memperbarui judul dasbor di config.json:")
            print(f"    Judul: {judul_baru}")
            return

        if arg == "--set-iqamat" and len(sys.argv) > 3:
            salat_key = sys.argv[2].lower().replace("'", "")
            try:
                menit_val = int(sys.argv[3])
            except ValueError:
                print("[-] Nilai menit harus berupa angka bulat.")
                return

            valid_keys = ["subuh", "dzuhur", "ashar", "maghrib", "isya"]
            if salat_key not in valid_keys:
                print(f"[-] Salat '{salat_key}' tidak valid. Pilihan: {', '.join(valid_keys)}")
                return

            cfg_key = f"{salat_key}_iqamat"
            save_config(**{cfg_key: menit_val})
            print(f"[✓] Berhasil memperbarui waktu iqamat di config.json:")
            print(f"    {salat_key.capitalize()}: +{menit_val} menit setelah azan")
            return

        if arg == "--set" and len(sys.argv) > 2:
            query_kota = " ".join(sys.argv[2:])
            print(f"[+] Mencari kota: '{query_kota}'...")
            hasil = api.cari_kota(query_kota)
            if not hasil:
                print(f"[-] Kota '{query_kota}' tidak ditemukan.")
                return
            
            pilihan = hasil[0]
            save_config(lokasi_id=pilihan["id"], lokasi_nama=pilihan["lokasi"])
            print(f"[✓] Berhasil menyimpan lokasi ke config.json:")
            print(f"    ID    : {pilihan['id']}")
            print(f"    Lokasi: {pilihan['lokasi']}")
            return

        if arg == "--set-id" and len(sys.argv) > 2:
            target_id = sys.argv[2]
            semua = api.get_semua_kota()
            matched = [k for k in semua if k["id"] == str(target_id)]
            lokasi_nama = matched[0]["lokasi"] if matched else f"ID {target_id}"
            save_config(lokasi_id=target_id, lokasi_nama=lokasi_nama)
            print(f"[✓] Berhasil menyimpan lokasi ke config.json:")
            print(f"    ID    : {target_id}")
            print(f"    Lokasi: {lokasi_nama}")
            return

        if arg == "--cli":
            kota_id = cfg.get("lokasi_id", "1204")
            nama_lokasi = cfg.get("lokasi_nama", "KAB. BOGOR")
        else:
            # Jika user memberikan nama kota secara langsung
            nama_kota = " ".join(sys.argv[1:])
            print(f"[+] Mencari jadwal untuk: '{nama_kota}'...")
            hasil = api.cari_kota(nama_kota)
            if not hasil:
                print(f"[-] Kota '{nama_kota}' tidak ditemukan.")
                return
            kota_terpilih = hasil[0]
            kota_id = kota_terpilih["id"]
            nama_lokasi = kota_terpilih["lokasi"]

        print(f"[+] Jadwal salat hari ini ({today.strftime('%Y-%m-%d')})...\n")
        dash = TerminalDashboard()
        dash.config["lokasi_id"] = kota_id
        dash.fetch_jadwal(force=True)
        data_jadwal = dash.jadwal_cache or {}
        asal = {"internet": "diperbarui dari internet",
                "cache": "dari penyimpanan lokal (SQLite)",
                "offline": "offline — memakai data tersimpan",
                "kosong": "belum ada data"}.get(dash.sumber_data, "")
        if asal:
            print(f"[i] Sumber: Bimas Islam Kemenag RI — {asal}\n")

        if "jadwal" in data_jadwal:
            jadwal = data_jadwal["jadwal"]
            daerah = data_jadwal.get("daerah", "")
            print(f"JADWAL SALAT: {nama_lokasi}{' - ' + daerah if daerah else ''}")
            tampilkan_jadwal(jadwal, cfg)
        else:
            print("[-] Gagal memuat jadwal: belum ada data tersimpan dan internet")
            print("    tidak dapat dihubungi. Jalankan sekali dengan internet.")
    else:
        # Default tanpa argumen: Jalankan dasbor terminal interaktif
        dashboard = TerminalDashboard()
        dashboard.run()

if __name__ == "__main__":
    main()
