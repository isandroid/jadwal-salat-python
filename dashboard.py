#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Jam berdetak bergaya peaclock  ->  `view digital`
  block 2 1      (tiap segmen = blok 2 kolom x 1 baris)
  padding 2 1    (jarak antar blok: 2 kolom, 1 baris)
  ratio 2 1      (blok tampak persegi di terminal)
Semua glyph (0-9 dan ":") lebarnya SAMA = 6 kolom, sehingga grid rata.
"""

import sys
import time
import math
import select
import termios
import tty
import shutil
import re
import unicodedata
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, Tuple, List

from config import load_config
from api_client import JadwalSalatAPI

# ==========================================
# PALET WARNA ANSI
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

COLOR_TITLE = "\033[1;38;5;220m"
COLOR_SUBTITLE = "\033[38;5;153m"
COLOR_BORDER = "\033[38;5;34m"
COLOR_CLOCK = "\033[1;38;5;48m"
COLOR_COUNTDOWN = "\033[1;38;5;227m"


def visible_width(s: str) -> int:
    """Lebar tampilan teks, memperhitungkan karakter lebar (emoji)."""
    clean_s = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for ch in clean_s:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('W', 'F') or ord(ch) >= 0x1f000:
            w += 2
        else:
            w += 1
    return w


def center_line(text_with_ansi: str, total_cols: int) -> str:
    """Menyelaraskan teks tepat di tengah layar berdasarkan lebar visual."""
    pad = max(0, (total_cols - visible_width(text_with_ansi)) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# FONT DIGITAL PEACLOCK  (7-segment, block 2x1)
#
# Pola 7-segmen (tiap segmen = blok 2 kolom):
#      a a a        -> "██████"
#    f       b      -> "██  ██"
#    f       b
#      g g g        -> "██████"
#    e       c      -> "██  ██"
#    e       c
#      d d d        -> "██████"
#
# Lebar tiap glyph = 6 kolom (3 blok x 2 kolom). Tanpa padding internal
# supaya garis segmen menyambung rapi. Digit "1" memakai segmen b+c
# sehingga tetap berada di dalam kotak 6 kolom yang sama.
# ==========================================

BLOCK = "██"
BLANK = "  "


def _seg(segs: str, name: str) -> str:
    """Kembalikan blok ON/OFF untuk satu segmen."""
    return BLOCK if name in segs else BLANK


# Digit 0-9 sesuai pola 7-segmen standar
SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgcde",
    "7": "abc",
    "8": "abcdefg",
    "9": "abfgcd",
}


def _digit_rows(ch: str) -> List[str]:
    """Bangun satu digit: 7 baris x 6 kolom."""
    segs = SEGMENTS.get(ch, "")
    return [
        _seg(segs, "a") * 3,                              # baris 0 : a
        _seg(segs, "f") + BLANK + _seg(segs, "b"),        # baris 1 : f b
        _seg(segs, "f") + BLANK + _seg(segs, "b"),        # baris 2 : f b
        _seg(segs, "g") * 3,                              # baris 3 : g
        _seg(segs, "e") + BLANK + _seg(segs, "c"),        # baris 4 : e c
        _seg(segs, "e") + BLANK + _seg(segs, "c"),        # baris 5 : e c
        _seg(segs, "d") * 3,                              # baris 6 : d
    ]


def _colon_rows() -> List[str]:
    """Titik dua. Lebarnya 6 kolom (sama dengan digit) supaya grid rata."""
    return [
        "      ",
        "      ",
        "  ██  ",
        "      ",
        "  ██  ",
        "      ",
        "      ",
    ]


def render_peaclock_time(time_str: str) -> List[str]:
    """Render jam gaya peaclock digital: 7 baris, tiap glyph 6 kolom + 2 jarak."""
    rows = [""] * 7
    for ch in time_str:
        if ch == ":":
            glyph = _colon_rows()
        elif ch == " ":
            glyph = ["      "] * 7
        else:
            glyph = _digit_rows(ch)
        for i in range(7):
            rows[i] += glyph[i] + "  "
    return rows


# ==========================================
# KALENDER & WAKTU
# ==========================================
IQAMAT_KEYS = {
    "subuh": "subuh_iqamat",
    "dzuhur": "dzuhur_iqamat",
    "ashar": "ashar_iqamat",
    "maghrib": "maghrib_iqamat",
    "isya": "isya_iqamat",
}

NAMA_HARI = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
             4: "Jumat", 5: "Sabtu", 6: "Minggu"}
NAMA_BULAN = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei",
              6: "Juni", 7: "Juli", 8: "Agustus", 9: "September",
              10: "Oktober", 11: "November", 12: "Desember"}
BULAN_HIJRI = ["", "Muharram", "Safar", "Rabi'ul Awwal", "Rabi'ul Akhir",
               "Jumadil Awwal", "Jumadil Akhir", "Rajab", "Sya'ban",
               "Ramadhan", "Syawwal", "Dzulqa'dah", "Dzulhijjah"]


def hitung_waktu_iqamat(waktu_azan_str: str, jeda_menit: int) -> str:
    """Waktu iqamat = waktu azan + jeda menit."""
    if not waktu_azan_str or waktu_azan_str == "--:--":
        return "--:--"
    try:
        jam, menit = map(int, waktu_azan_str.split(":"))
        total = (jam * 60 + menit + int(jeda_menit)) % 1440
        return f"{total // 60:02d}:{total % 60:02d}"
    except Exception:
        return "--:--"


def hitung_hijri(dt: date) -> str:
    """Konversi Masehi -> Hijriah (algoritma tabular Islam)."""
    y, m, d = dt.year, dt.month, dt.day
    if m < 3:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    l = jd - 1948439.5 + 10632
    n = math.floor((l - 1) / 10631)
    l = l - 10631 * n + 354
    j = (math.floor((10985 - l) / 5316)) * (math.floor((50 * l) / 17719)) + \
        (math.floor(l / 5670)) * (math.floor((43 * l) / 15238))
    l = l - (math.floor((30 - j) / 15)) * (math.floor((17719 * j) / 50)) - \
        (math.floor(j / 16)) * (math.floor((15238 * j) / 43)) + 29
    h_month = math.floor((24 * l) / 709)
    h_day = l - math.floor((709 * h_month) / 24)
    h_year = 30 * n + j - 30
    bulan = BULAN_HIJRI[h_month] if 1 <= h_month <= 12 else ""
    return f"{int(h_day)} {bulan} {int(h_year)} H"


# ==========================================
# DASBOR
# ==========================================
class TerminalDashboard:
    def __init__(self):
        self.api = JadwalSalatAPI()
        self.running = True
        self.config = load_config()
        self.jadwal_cache: Optional[Dict[str, Any]] = None
        self.last_fetch_date: Optional[date] = None
        self.old_terminal_settings = None

    def setup_terminal(self):
        sys.stdout.write("\033[?1049h")
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        if sys.stdin.isatty():
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def restore_terminal(self):
        if self.old_terminal_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[?1049l")
        sys.stdout.write(RESET)
        sys.stdout.flush()

    def fetch_jadwal(self, force: bool = False):
        today = date.today()
        if not force and self.jadwal_cache and self.last_fetch_date == today:
            return
        kota_id = self.config.get("lokasi_id", "1204")
        try:
            res = self.api.get_jadwal_harian(kota_id, today)
            if res and "jadwal" in res:
                self.jadwal_cache = res
                self.last_fetch_date = today
        except Exception:
            pass

    def get_upcoming_prayer(self, now_dt: datetime) -> Tuple[Optional[str], Optional[timedelta]]:
        if not self.jadwal_cache or "jadwal" not in self.jadwal_cache:
            return None, None
        jadwal = self.jadwal_cache["jadwal"]
        today = now_dt.date()
        urutan = ["imsak", "subuh", "terbit", "dhuha", "dzuhur", "ashar", "maghrib", "isya"]
        label_map = {"imsak": "IMSAK", "subuh": "SUBUH", "terbit": "TERBIT",
                     "dhuha": "DHUHA", "dzuhur": "DZUHUR", "ashar": "ASHAR",
                     "maghrib": "MAGHRIB", "isya": "ISYA'"}
        for key in urutan:
            val = jadwal.get(key)
            if not val:
                continue
            jam, menit = map(int, val.split(":"))
            target = datetime(today.year, today.month, today.day, jam, menit, 0)
            if now_dt < target:
                return label_map[key], target - now_dt
        val = jadwal.get("imsak", "04:08")
        jam, menit = map(int, val.split(":"))
        besok = datetime(today.year, today.month, today.day, jam, menit, 0) + timedelta(days=1)
        return "IMSAK", besok - now_dt

    def build_frame(self) -> str:
        cols, rows = shutil.get_terminal_size((120, 36))
        now = datetime.now()
        today = now.date()

        judul = self.config.get("judul", "Jadwal Salat Masjid Nasr")
        lokasi_nama = self.config.get("lokasi_nama", "KAB. BOGOR")
        daerah = self.jadwal_cache.get("daerah", "JAWA BARAT") if self.jadwal_cache else ""
        lokasi_str = f"📍 Lokasi: {lokasi_nama}{', ' + daerah if daerah else ''} (ID: {self.config.get('lokasi_id')})"
        masehi_str = f"{NAMA_HARI[today.weekday()]}, {today.day} {NAMA_BULAN[today.month]} {today.year}"
        tanggal_str = f"📅 {masehi_str}  |  🌙 {hitung_hijri(today)}"

        out = []
        out.append(center_line(f"{COLOR_TITLE}{BOLD}{judul.upper()}{RESET}", cols))
        out.append(center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols))
        out.append(center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols))
        out.append("")

        div_w = min(cols - 8, 104)
        div_pad = " " * max(0, (cols - div_w) // 2)
        out.append(f"{div_pad}{COLOR_BORDER}{'─' * div_w}{RESET}")
        out.append("")

        # --- Jam berdetak (peaclock digital) ---
        clock_rows = render_peaclock_time(now.strftime("%H:%M:%S"))
        for r in clock_rows:
            out.append(center_line(f"{COLOR_CLOCK}{BOLD}{r}{RESET}", cols))

        out.append("")
        out.append("")

        # --- Countdown ---
        next_prayer, remaining = self.get_upcoming_prayer(now)
        if next_prayer and remaining:
            t = int(remaining.total_seconds())
            cd_text = (f"⏳ Menuju Waktu {next_prayer}: "
                       f"{t // 3600:02d} Jam {(t % 3600) // 60:02d} Menit {t % 60:02d} Detik")
        else:
            cd_text = "Memuat data jadwal salat..."
        out.append(center_line(f"{COLOR_COUNTDOWN}{BOLD}{cd_text}{RESET}", cols))
        out.append("")

        # --- Footer ---
        out.append(center_line(
            f"{DIM}Tekan [q] atau [Ctrl+C] untuk keluar  •  Sumber Data: Bimas Islam Kemenag RI{RESET}",
            cols))

        top_margin = max(0, (rows - len(out)) // 3)
        return "\n" * top_margin + "\n".join(out)

    def run(self):
        self.setup_terminal()
        try:
            self.fetch_jadwal(force=True)
            while self.running:
                if self.last_fetch_date != date.today():
                    self.fetch_jadwal(force=True)
                sys.stdout.write("\033[H\033[J" + self.build_frame())
                sys.stdout.flush()
                if sys.stdin.isatty():
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r and sys.stdin.read(1) in ("q", "Q", "\x1b", "\x03"):
                        self.running = False
                else:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.restore_terminal()


if __name__ == "__main__":
    TerminalDashboard().run()
