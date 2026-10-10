"""
Module untuk berinteraksi langsung dengan endpoint internal Bimas Islam Kemenag.
Website: https://bimasislam.kemenag.go.id/jadwalshalat
"""

import requests
import re
from typing import Dict, Any, List, Optional

class BimasIslamClient:
    BASE_URL = "https://bimasislam.kemenag.go.id"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.BASE_URL}/jadwalshalat",
            "Origin": self.BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
        })

    def init_session(self) -> str:
        """Mengunjungi halaman utama untuk mendapatkan session cookies."""
        resp = self.session.get(f"{self.BASE_URL}/jadwalshalat")
        resp.raise_for_status()
        return resp.text

    def get_provinsi_list(self) -> List[Dict[str, str]]:
        """
        Mengambil daftar provinsi langsung dari HTML select #search_prov.
        Nilai 'value' adalah token terenkripsi yang di-generate server per session.
        """
        html = self.init_session()
        match = re.search(r'<select[^>]*id=["\']search_prov["\'][^>]*>([\s\S]*?)</select>', html)
        if not match:
            return []
        
        options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', match.group(1))
        results = []
        for val, text in options:
            clean_text = text.strip()
            if val and clean_text and not clean_text.startswith("--") and "PILIH" not in clean_text.upper():
                results.append({"token": val, "nama": clean_text})
        return results

    def get_kabkota_list(self, token_provinsi: str) -> List[Dict[str, str]]:
        """
        Mengambil daftar kabupaten/kota via AJAX POST /ajax/getKabkoshalat.
        Param 'x' memerlukan token provinsi terenkripsi yang valid dari session yang sama.
        """
        url = f"{self.BASE_URL}/ajax/getKabkoshalat"
        resp = self.session.post(url, data={"x": token_provinsi})
        resp.raise_for_status()
        
        # Server mengembalikan string HTML kumpulan <option>
        options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', resp.text)
        results = []
        for val, text in options:
            clean_text = text.strip()
            if val and clean_text and "PILIH" not in clean_text.upper():
                results.append({"token": val, "nama": clean_text})
        return results

    def get_jadwal_bulan(self, token_provinsi: str, token_kabkota: str, bulan: int, tahun: int) -> Dict[str, Any]:
        """
        Mengambil jadwal salat satu bulan via AJAX POST /ajax/getShalatbln.
        Jika token salah / expired, server mengembalikan {'status': 'Illegal key'}.
        """
        url = f"{self.BASE_URL}/ajax/getShalatbln"
        data = {
            "x": token_provinsi,
            "y": token_kabkota,
            "bln": str(bulan),
            "thn": str(tahun)
        }
        resp = self.session.post(url, data=data)
        resp.raise_for_status()
        return resp.json()
