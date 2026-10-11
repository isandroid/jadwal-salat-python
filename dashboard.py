#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Peaclock-style Digital Clock (view digital, block 2x1, padding 2x1, ratio 2:1)
Exact replica of peaclock's `view digital` with `block 2 1`, `padding 2 1`, `ratio 2:1`
"""

import os
import sys
import time
import math
import select
import signal
import termios
import tty
import shutil
import re
import unicodedata
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, Tuple, List

from config import load_config
from api_client import JadwalSalatAPI


def visible_width(s: str) -> int:
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for ch in clean:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('W', 'F') or ord(ch) >= 0x1f000:
            w += 2
        else:
            w += 1
    return w


def center_line(text_with_ansi: str, total_cols: int) -> str:
    w = visible_width(text_with_ansi)
    pad = max(0, (total_cols - w) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# PEACLOCK EXACT - Digital View (block 2x1, padding 2x1, ratio 2:1)
# Exact replica of peaclock's `view digital` with `block 2 1`, `padding 2 1`, `ratio 2:1`
# Each segment = 2x1 block (██ = on, '  ' = off)
# Digit: 7 rows x 6 chars (3 blocks x 2 chars per block)
# ==========================================

SEGMENTS = {
    '0': 'abcefd',  '1': 'bc',      '2': 'abged',
    '3': 'abgcd',   '4': 'fgbc',    '5': 'afgcd',
    '6': 'afgcde',  '7': 'abc',     '8': 'abcdefg',
    '9': 'abfgcd',
}

def _peaclock_digit(segs: str) -> list[str]:
    """Exact peaclock digital digit: 7 rows x 6 chars (3 blocks x 2 chars)."""
    return [
        ('██' if 'a' in segs else '  ') * 3,
        ('██' if 'f' in segs else '  ') + '  ' + ('██' if 'b' in segs else '  '),
        ('██' if 'f' in segs else '  ') + '  ' + ('██' if 'b' in segs else '  '),
        ('██' if 'g' in segs else '  ') * 3,
        ('██' if 'e' in segs else '  ') + '  ' + ('██' if 'c' in segs else '  '),
        ('██' if 'e' in segs else '  ') + '  ' + ('██' if 'c' in segs else '  '),
        ('██' if 'd' in segs else '  ') * 3,
    ]

def _peaclock_colon() -> list[str]:
    return ['   ', '   ', ' ● ', '   ', ' ● ', '   ', '   ']

def _render_peaclock_time_main(time_str: str) -> list[str]:
    """Exact peaclock digital style: 7 rows."""
    rows = [''] * 7
    for ch in time_str:
        if ch == ':':
            glyph = ['   ', '   ', ' ● ', '   ', ' ● ', '   ', '   ']
        elif ch == ' ':
            glyph = ['   '] * 7
        else:
            segs = SEGMENTS.get(ch, '')
            glyph = [
                ('██' if 'a' in segs else '  ') * 3,
                ('██' if 'f' in segs else '  ') + '  ' + ('██' if 'b' in segs else '  '),
                ('██' if 'f' in segs else '  ') + '  ' + ('██' if 'b' in segs else '  '),
                ('██' if 'g' in segs else '  ') * 3,
                ('██' if 'e' in segs else '  ') + '  ' + ('██' if 'c' in segs else '  '),
                ('██' if 'e' in segs else '  ') + '  ' + ('██' if 'c' in segs else '  '),
                ('██' if 'd' in segs else '  ') * 3,
            ]
        for i in range(7):
            rows[i] += glyph[i] + '  '
    return rows

def render_peaclock_time_main(time_str: str) -> list[str]:
    return _render_peaclock_time_main(time_str)

def render_peaclock_time_small(time_str: str) -> list[str]:
    rows = [''] * 5
    for ch in time_str:
        if ch == ':':
            glyph = ['  ', '  ', ' ● ', '  ', ' ● ']
        elif ch == ' ':
            glyph = ['  '] * 5
        else:
            segs = SEGMENTS.get(ch, '')
            on = lambda s: '██' if s in segs else '  '
            glyph = [on('a')*2, on('f')+on('b'), on('g')*2, on('e')+on('c'), on('d')*2]
        for i in range(5):
            rows[i] += glyph[i] + '  '
    return rows


SEGMENTS = {
    '0': 'abcefd',  '1': 'bc',      '2': 'abged',
    '3': 'abgcd',   '4': 'fgbc',    '5': 'afgcd',
    '6': 'afgcde',  '7': 'abc',     '8': 'abcdefg',
    '9': 'abfgcd',
}


NAMA_HARI = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}
NAMA_BULAN = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"}
BULAN_HIJRI = ['', 'Muharram', 'Safar', "Rabi'ul Awwal", "Rabi'ul Akhir", 'Jumadil Awwal', 'Jumadil Akhir', 'Rajab', "Sya'ban", 'Ramadhan', 'Syawwal', "Dzulqa'dah", "Dzulhijjah"]


def hitung_hijri(dt: date) -> str:
    y, m, d = dt.year, dt.month, dt.day
    if m < 3: y -= 1; m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    jd_epoch = 1948439.5
    l = jd - jd_epoch + 10632
    n = math.floor((l - 1) / 10631)
    l = l - 10631 * n + 354
    j = (math.floor((10985 - l) / 5316)) * (math.floor((50 * l) / 17719)) + (math.floor(l / 5670)) * (math.floor((43 * l) / 15238))
    l = l - (math.floor((30 - j) / 15)) * (math.floor((17719 * j) / 50)) - (math.floor(j / 16)) * (math.floor((15238 * j) / 43)) + 29
    h_month = math.floor((24 * l) / 709)
    h_day = l - math.floor((709 * h_month) / 24)
    h_year = 30 * n + j - 30
    bulan_str = BULAN_HIJRI[h_month] if 1 <= h_month <= 12 else ''
    return f"{int(h_day)} {bulan_str} {int(h_year)} H"


def hitung_waktu_iqamat(waktu_azan_str: str, jeda_menit: int) -> str:
    if not waktu_azan_str or waktu_azan_str == "--:--": return "--:--"
    try:
        jam, menit = map(int, waktu_azan_str.split(":"))
        total_menit = (jam * 60 + menit + int(jeda_menit)) % 1440
        return f"{total_menit // 60:02d}:{total_menit % 60:02d}"
    except Exception: return "--:--"


def visible_width(s: str) -> int:
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for ch in clean:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('W', 'F') or ord(ch) >= 0x1f000: w += 2
        else: w += 1
    return w


def center_line(text_with_ansi: str, total_cols: int) -> str:
    w = visible_width(text_with_ansi)
    pad = max(0, (total_cols - w) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# COLOR PALETTE
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLOR_TITLE = "\033[1;38;5;220m"
COLOR_SUBTITLE = "\033[38;5;153m"
COLOR_BORDER = "\033[38;5;34m"
COLOR_BORDER_DIM = "\033[38;5;240m"
COLOR_CLOCK = "\033[1;38;5;48m"
COLOR_CLOCK_SEC = "\033[38;5;120m"
COLOR_COUNTDOWN = "\033[1;38;5;227m"
COLOR_ACTIVE_CARD = "\033[1;38;5;226m"
BG_ACTIVE_CARD = "\033[48;5;22m"
COLOR_PASSED_CARD = "\033[38;5;244m"
COLOR_NORMAL_CARD = "\033[38;5;159m"
COLOR_IQAMAT_LABEL = "\033[38;5;214m"
COLOR_IQAMAT_TIME = "\033[1;38;5;220m"

IQAMAT_KEYS = {"subuh": "subuh_iqamat", "dzuhur": "dzuhur_iqamat", "ashar": "ashar_iqamat", "maghrib": "maghrib_iqamat", "isya": "isya_iqamat"}


def hitung_waktu_iqamat(waktu_azan_str: str, jeda_menit: int) -> str:
    if not waktu_azan_str or waktu_azan_str == "--:--": return "--:--"
    try:
        jam, menit = map(int, waktu_azan_str.split(":"))
        total_menit = (jam * 60 + menit + int(jeda_menit)) % 1440
        return f"{total_menit // 60:02d}:{total_menit % 60:02d}"
    except Exception: return "--:--"


def visible_width(s: str) -> int:
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for ch in clean:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('W', 'F') or ord(ch) >= 0x1f000: w += 2
        else: w += 1
    return w


def center_line(text_with_ansi: str, total_cols: int) -> str:
    w = visible_width(text_with_ansi)
    pad = max(0, (total_cols - w) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# COLOR PALETTE (duplicate for build_frame access)
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLOR_TITLE = "\033[1;38;5;220m"
COLOR_SUBTITLE = "\033[38;5;153m"
COLOR_BORDER = "\033[38;5;34m"
COLOR_BORDER_DIM = "\033[38;5;240m"
COLOR_CLOCK = "\033[1;38;5;48m"
COLOR_CLOCK_SEC = "\033[38;5;120m"
COLOR_COUNTDOWN = "\033[1;38;5;227m"
COLOR_ACTIVE_CARD = "\033[1;38;5;226m"
BG_ACTIVE_CARD = "\033[48;5;22m"
COLOR_PASSED_CARD = "\033[38;5;244m"
COLOR_NORMAL_CARD = "\033[38;5;159m"
COLOR_IQAMAT_LABEL = "\033[38;5;214m"
COLOR_IQAMAT_TIME = "\033[1;38;5;220m"

IQAMAT_KEYS = {"subuh": "subuh_iqamat", "dzuhur": "dzuhur_iqamat", "ashar": "ashar_iqamat", "maghrib": "maghrib_iqamat", "isya": "isya_iqamat"}


def hitung_waktu_iqamat(waktu_azan_str: str, jeda_menit: int) -> str:
    if not waktu_azan_str or waktu_azan_str == "--:--": return "--:--"
    try:
        jam, menit = map(int, waktu_azan_str.split(":"))
        total_menit = (jam * 60 + menit + int(jeda_menit)) % 1440
        return f"{total_menit // 60:02d}:{total_menit % 60:02d}"
    except Exception: return "--:--"


def visible_width(s: str) -> int:
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for ch in clean:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('W', 'F') or ord(ch) >= 0x1f000: w += 2
        else: w += 1
    return w


def center_line(text_with_ansi: str, total_cols: int) -> str:
    w = visible_width(text_with_ansi)
    pad = max(0, (total_cols - w) // 2)
    return " " * pad + text_with_ansi


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
        if not force and self.jadwal_cache and self.last_fetch_date == today: return
        kota_id = self.config.get("lokasi_id", "1204")
        try:
            res = self.api.get_jadwal_harian(kota_id, today)
            if res and "jadwal" in res:
                self.jadwal_cache = res
                self.last_fetch_date = today
        except Exception: pass

    def get_upcoming_prayer(self, now_dt: datetime) -> Tuple[Optional[str], Optional[timedelta]]:
        if not self.jadwal_cache or "jadwal" not in self.jadwal_cache: return None, None
        jadwal = self.jadwal_cache["jadwal"]
        today = now_dt.date()
        urutan = ["imsak", "subuh", "terbit", "dhuha", "dzuhur", "ashar", "maghrib", "isya"]
        label_map = {"imsak": "IMSAK", "subuh": "SUBUH", "terbit": "TERBIT", "dhuha": "DHUHA", "dzuhur": "DZUHUR", "ashar": "ASHAR", "maghrib": "MAGHRIB", "isya": "ISYA'"}
        for key in urutan:
            val_str = jadwal.get(key)
            if not val_str: continue
            jam, menit = map(int, val_str.split(":"))
            waktu_salat_dt = datetime(today.year, today.month, today.day, jam, menit, 0)
            if now_dt < waktu_salat_dt:
                return label_map[key], waktu_salat_dt - now_dt
        val_imsak = jadwal.get("imsak", "04:08")
        jam, menit = map(int, val_imsak.split(":"))
        imsak_besok = datetime(today.year, today.month, today.day, jam, menit, 0) + timedelta(days=1)
        return "IMSAK", imsak_besok - now_dt

    def build_frame(self) -> str:
        cols, rows = shutil.get_terminal_size((120, 36))
        now = datetime.now()
        today = now.date()

        judul = self.config.get("judul", "Jadwal Salat Masjid Nasr")
        lokasi_nama = self.config.get("lokasi_nama", "KAB. BOGOR")
        daerah = self.jadwal_cache.get("daerah", "JAWA BARAT") if self.jadwal_cache else ""
        lokasi_str = f"📍 Lokasi: {lokasi_nama}{', ' + daerah if daerah else ''} (ID: {self.config.get('lokasi_id')})"
        hari_nama = NAMA_HARI[today.weekday()]
        bulan_nama = NAMA_BULAN[today.month]
        masehi_str = f"{hari_nama}, {today.day} {bulan_nama} {today.year}"
        hijri_str = hitung_hijri(today)
        tanggal_str = f"📅 {masehi_str}  |  🌙 {hijri_str}"

        output = []
        output.append(center_line(f"{COLOR_TITLE}{BOLD}{judul.upper()}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols))
        output.append("")

        div_w = min(cols - 8, 104)
        div_pad = " " * max(0, (cols - div_w) // 2)
        output.append(f"{div_pad}{COLOR_BORDER}{'─' * div_w}{RESET}")
        output.append("")

        # JAM BERDETAK SAJA - PEACLOCK DIGITAL EXACT (block 2x1, padding 2x1, ratio 2:1)
        time_str = now.strftime("%H:%M:%S")
        clock_lines = _render_peaclock_time_main(time_str)
        
        for line in clock_lines:
            pad = " " * ((cols - len(line)) // 2)
            output.append(f"{pad}{COLOR_CLOCK}{BOLD}{line}{RESET}")
        output.append("")
        output.append("")

        # COUNTDOWN
        next_prayer, remaining = self.get_upcoming_prayer(now)
        if next_prayer and remaining:
            tot_sec = int(remaining.total_seconds())
            hours = tot_sec // 3600
            mins = (tot_sec % 3600) // 60
            secs = tot_sec % 60
            cd_text = f"⏳ Menuju Waktu {next_prayer}: {hours:02d} Jam {mins:02d} Menit {secs:02d} Detik"
            countdown_line = f"{COLOR_COUNTDOWN}{BOLD}{cd_text}{RESET}"
        else:
            cd_text = "Memuat data jadwal salat..."
            countdown_line = f"{DIM}{cd_text}{RESET}"
        output.append(f"{' ' * ((cols - len(cd_text)) // 2)}{countdown_line}")
        output.append("")

        # FOOTER
        footer_info = "Tekan [q] atau [Ctrl+C] untuk keluar  •  Sumber Data: Bimas Islam Kemenag RI"
        footer_pad = " " * ((cols - len(footer_info)) // 2)
        output.append(f"{footer_pad}{DIM}{footer_info}{RESET}")

        content_height = len(output)
        top_margin = max(0, (rows - content_height) // 3)
        full_screen = "\n" * top_margin + "\n".join(output)
        return full_screen

    def run(self):
        self.setup_terminal()
        try:
            self.fetch_jadwal(force=True)
            while self.running:
                today = date.today()
                if self.last_fetch_date != today: self.fetch_jadwal(force=True)
                frame = self.build_frame()
                sys.stdout.write(f"\033[H\033[J{frame}")
                sys.stdout.flush()
                if sys.stdin.isatty():
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch in ('q', 'Q', '\x1b', '\x03'): self.running = False
                else: time.sleep(1.0)
        except KeyboardInterrupt: self.running = False
        finally: self.restore_terminal()


if __name__ == "__main__":
    dashboard = TerminalDashboard()
    dashboard.run()
