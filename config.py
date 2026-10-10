"""
Modul konfigurasi untuk membaca dan menyimpan parameter dasbor ke file config.json.
"""

import json
import os
from typing import Dict, Any

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "judul": "Jadwal Salat Masjid Nasr",
    "lokasi_id": "1204",
    "lokasi_nama": "KAB. BOGOR",
    "subuh_iqamat": 15,
    "dzuhur_iqamat": 20,
    "ashar_iqamat": 15,
    "maghrib_iqamat": 10,
    "isya_iqamat": 15
}

def load_config() -> Dict[str, Any]:
    """Membaca parameter dari file config.json."""
    if not os.path.exists(CONFIG_FILE_PATH):
        save_config(**DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Pastikan field wajib ada
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val
            return data
    except Exception as e:
        print(f"[!] Gagal membaca file konfigurasi ({e}), menggunakan default.")

    return DEFAULT_CONFIG.copy()

def save_config(**kwargs) -> None:
    """Menyimpan parameter konfigurasi ke file config.json."""
    current = load_config()
    for key, val in kwargs.items():
        if val is not None:
            current[key] = val

    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
