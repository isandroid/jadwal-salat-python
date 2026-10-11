"""
Penyimpanan lokal jadwal salat (SQLite).

Tujuan: setelah satu kali unduh, jadwal salat tidak perlu lagi diambil dari
internet. Data disimpan per kota dan per tanggal, sehingga aplikasi dasbor
dapat berjalan sepenuhnya offline.

Sumber data: Bimas Islam Kemenag RI (via MyQuran Open API).
"""

import os
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jadwal_salat.db")

WAKTU_KEYS = ("imsak", "subuh", "terbit", "dhuha", "dzuhur", "ashar", "maghrib", "isya")

_DDL = """
CREATE TABLE IF NOT EXISTS jadwal (
    kota_id  TEXT NOT NULL,
    tanggal  TEXT NOT NULL,            -- YYYY-MM-DD
    tanggal_teks TEXT,                 -- mis. "Minggu, 11/10/2026"
    imsak    TEXT, subuh TEXT, terbit TEXT, dhuha TEXT,
    dzuhur   TEXT, ashar TEXT, maghrib TEXT, isya TEXT,
    lokasi   TEXT,
    daerah   TEXT,
    diunduh  TEXT,                     -- waktu pengambilan (ISO)
    PRIMARY KEY (kota_id, tanggal)
);
CREATE INDEX IF NOT EXISTS idx_jadwal_tanggal ON jadwal (tanggal);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """Membuat tabel bila belum ada, dan menyesuaikan kolom baru."""
    with _connect() as conn:
        conn.executescript(_DDL)
        kolom = {r[1] for r in conn.execute("PRAGMA table_info(jadwal)")}
        for nama, tipe in (("tanggal_teks", "TEXT"),):
            if nama not in kolom:
                conn.execute(f"ALTER TABLE jadwal ADD COLUMN {nama} {tipe}")


def simpan_bulan(kota_id: str, data_bulanan: Dict[str, Any]) -> int:
    """Simpan seluruh jadwal satu bulan. Kembalikan jumlah baris tersimpan."""
    hari_list: List[Dict[str, Any]] = data_bulanan.get("jadwal") or []
    if not hari_list:
        return 0
    lokasi = data_bulanan.get("lokasi", "")
    daerah = data_bulanan.get("daerah", "")
    from datetime import datetime
    stamp = datetime.now().isoformat(timespec="seconds")

    rows = []
    for hari in hari_list:
        tanggal = hari.get("date")
        if not tanggal:
            continue
        rows.append(tuple(
            [str(kota_id), tanggal, hari.get("tanggal", "")]
            + [hari.get(k) for k in WAKTU_KEYS]
            + [lokasi, daerah, stamp]
        ))

    with _connect() as conn:
        conn.executemany(
            """INSERT INTO jadwal
               (kota_id, tanggal, tanggal_teks, imsak, subuh, terbit, dhuha,
                dzuhur, ashar, maghrib, isya, lokasi, daerah, diunduh)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(kota_id, tanggal) DO UPDATE SET
                 tanggal_teks=excluded.tanggal_teks,
                 imsak=excluded.imsak, subuh=excluded.subuh, terbit=excluded.terbit,
                 dhuha=excluded.dhuha, dzuhur=excluded.dzuhur, ashar=excluded.ashar,
                 maghrib=excluded.maghrib, isya=excluded.isya,
                 lokasi=excluded.lokasi, daerah=excluded.daerah,
                 diunduh=excluded.diunduh""",
            rows,
        )
    return len(rows)


def punya_bulan(kota_id: str, tahun: int, bulan: int) -> bool:
    """True bila bulan tersebut sudah tersimpan lengkap dan mutakhir.

    Baris lama yang belum punya kolom `tanggal_teks` (hasil migrasi skema)
    dianggap belum lengkap, sehingga aplikasi mengunduh ulang saat ada internet
    dan tetap bisa memakai data lama saat offline.
    """
    awal = f"{tahun:04d}-{bulan:02d}-01"
    with _connect() as conn:
        n = conn.execute(
            """SELECT COUNT(*) FROM jadwal
               WHERE kota_id=? AND tanggal >= ? AND tanggal < ?
                 AND tanggal_teks IS NOT NULL""",
            (str(kota_id), awal, _bulan_berikut(tahun, bulan)),
        ).fetchone()[0]
    return n >= 28


def _bulan_berikut(tahun: int, bulan: int) -> str:
    return f"{tahun + 1:04d}-01-01" if bulan == 12 else f"{tahun:04d}-{bulan + 1:02d}-01"


def get_hari(kota_id: str, tanggal: str) -> Optional[Dict[str, Any]]:
    """Ambil jadwal satu tanggal. Bentuknya sama dengan respons API harian."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jadwal WHERE kota_id=? AND tanggal=?",
            (str(kota_id), tanggal),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_terakhir(kota_id: str) -> Optional[Dict[str, Any]]:
    """Ambil jadwal terakhir yang tersimpan (untuk mode offline bila tanggal
    yang diminta belum ada)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jadwal WHERE kota_id=? ORDER BY tanggal DESC LIMIT 1",
            (str(kota_id),),
        ).fetchone()
    return _row_to_dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    jadwal = {k: row[k] for k in WAKTU_KEYS}
    jadwal["date"] = row["tanggal"]
    if "tanggal_teks" in row.keys() and row["tanggal_teks"]:
        jadwal["tanggal"] = row["tanggal_teks"]
    return {
        "id": row["kota_id"],
        "lokasi": row["lokasi"] or "",
        "daerah": row["daerah"] or "",
        "jadwal": jadwal,
        "dari_cache": True,
    }


def tanggal_tersimpan(kota_id: str) -> List[str]:
    """Daftar tanggal (YYYY-MM-DD) yang sudah tersimpan untuk satu kota."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT tanggal FROM jadwal WHERE kota_id=? ORDER BY tanggal",
            (str(kota_id),),
        ).fetchall()
    return [r["tanggal"] for r in rows]


def info(kota_id: str) -> Dict[str, Any]:
    """Ringkasan isi cache untuk satu kota."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) n, MIN(tanggal) awal, MAX(tanggal) akhir, MAX(diunduh) diunduh
               FROM jadwal WHERE kota_id=?""",
            (str(kota_id),),
        ).fetchone()
    return {
        "berkas": DB_FILE,
        "jumlah_hari": row["n"],
        "dari": row["awal"],
        "sampai": row["akhir"],
        "diunduh": row["diunduh"],
    }
