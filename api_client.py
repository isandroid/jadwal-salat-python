"""
Client API Jadwal Salat resmi Kemenag (via MyQuran Open API).
Menyediakan jadwal salat harian dan bulanan yang bersumber dari Bimas Islam Kemenag RI.
Dokumentasi: https://api.myquran.com/v2/
"""

import requests
from typing import List, Dict, Any, Optional
from datetime import date

class JadwalSalatAPI:
    BASE_URL = "https://api.myquran.com/v2/sholat"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AplikasiJadwalSalat/1.0"
        })

    def get_semua_kota(self) -> List[Dict[str, str]]:
        """Mendapatkan daftar seluruh Kabupaten dan Kota di Indonesia."""
        url = f"{self.BASE_URL}/kota/semua"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def cari_kota(self, keyword: str) -> List[Dict[str, str]]:
        """Mencari kota/kabupaten berdasarkan nama atau kata kunci."""
        keyword_clean = keyword.strip().upper()
        semua = self.get_semua_kota()
        return [kota for kota in semua if keyword_clean in kota["lokasi"].upper()]

    def get_jadwal_harian(self, kota_id: str, tanggal: Optional[date] = None) -> Dict[str, Any]:
        """
        Mengambil jadwal salat untuk tanggal tertentu.
        Jika tanggal tidak diisi, menggunakan tanggal hari ini.
        """
        if tanggal is None:
            tanggal = date.today()

        url = f"{self.BASE_URL}/jadwal/{kota_id}/{tanggal.year}/{tanggal.month:02d}/{tanggal.day:02d}"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("data", {})

    def get_jadwal_bulanan(self, kota_id: str, tahun: int, bulan: int) -> Dict[str, Any]:
        """Mengambil jadwal salat lengkap selama 1 bulan."""
        url = f"{self.BASE_URL}/jadwal/{kota_id}/{tahun}/{bulan:02d}"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("data", {})
