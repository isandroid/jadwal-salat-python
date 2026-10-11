#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Dioptimalkan untuk resolusi layar 1366x768 (atau terminal modern).
Layout 3x2 (peaclock style):
  Baris 1: [JAM BERDETAK] [SUBUH] [DZUHUR]
  Baris 2: [ASHAR] [MAGHRIB] [ISYA]
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
    """Menghitung lebar tampilan teks dengan memperhitungkan karakter lebar (emoji)."""
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
    """Menyelaraskan teks tepat di tengah layar berdasarkan lebar visual."""
    w = visible_width(text_with_ansi)
    pad = max(0, (total_cols - w) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# PALET WARNA ANSI & GAYA
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Teks
COLOR_TITLE = "\033[1;38;5;220m"       # Emas menyala
COLOR_SUBTITLE = "\033[38;5;153m"      # Biru langit lembut
COLOR_BORDER = "\033[38;5;34m"         # Hijau Masjid
COLOR_BORDER_DIM = "\033[38;5;240m"     # Abu-abu border
COLOR_CLOCK = "\033[1;38;5;48m"        # Hijau digital neon
COLOR_CLOCK_SEC = "\033[38;5;120m"     # Hijau muda
COLOR_COUNTDOWN = "\033[1;38;5;227m"    # Kuning menyala
COLOR_ACTIVE_CARD = "\033[1;38;5;226m"  # Kuning / Emas aktif
BG_ACTIVE_CARD = "\033[48;5;22m"        # Background hijau tua
COLOR_PASSED_CARD = "\033[38;5;244m"    # Abu-abu lewat
COLOR_NORMAL_CARD = "\033[38;5;159m"    # Cyan lembut
COLOR_IQAMAT_LABEL = "\033[38;5;214m"   # Oranye/Amber Iqamat
COLOR_IQAMAT_TIME = "\033[1;38;5;220m"  # Emas terang waktu Iqamat

IQAMAT_KEYS = {
    "subuh": "subuh_iqamat",
    "dzuhur": "dzuhur_iqamat",
    "ashar": "ashar_iqamat",
    "maghrib": "maghrib_iqamat",
    "isya": "isya_iqamat"
}


def hitung_waktu_iqamat(waktu_azan_str: str, jeda_menit: int) -> str:
    """Menghitung waktu iqamat = waktu azan + jeda menit."""
    if not waktu_azan_str or waktu_azan_str == "--:--":
        return "--:--"
    try:
        jam, menit = map(int, waktu_azan_str.split(":"))
        total_menit = (jam * 60 + menit + int(jeda_menit)) % 1440
        return f"{total_menit // 60:02d}:{total_menit % 60:02d}"
    except Exception:
        return "--:--"


# ==========================================
# FONT DIGITAL 5-BARIS BESAR (HH:MM:SS) - untuk jam utama
# ==========================================
DIGITS_5 = {
    '0': [
        ' ████ ',
        ' █  █ ',
        ' █  █ ',
        ' █  █ ',
        ' ████ '
    ],
    '1': [
        '   ██ ',
        '  ███ ',
        '   ██ ',
        '   ██ ',
        '  ████'
    ],
    '2': [
        ' ████ ',
        '    █ ',
        ' ████ ',
        ' █    ',
        ' ████ '
    ],
    '3': [
        ' ████ ',
        '    █ ',
        ' ████ ',
        '    █ ',
        ' ████ '
    ],
    '4': [
        ' █  █ ',
        ' █  █ ',
        ' ████ ',
        '    █ ',
        '    █ '
    ],
    '5': [
        ' ████ ',
        ' █    ',
        ' ████ ',
        '    █ ',
        ' ████ '
    ],
    '6': [
        ' ████ ',
        ' █    ',
        ' ████ ',
        ' █  █ ',
        ' ████ '
    ],
    '7': [
        ' ████ ',
        '    █ ',
        '   █  ',
        '  █   ',
        '  █   '
    ],
    '8': [
        ' ████ ',
        ' █  █ ',
        ' ████ ',
        ' █  █ ',
        ' ████ '
    ],
    '9': [
        ' ████ ',
        ' █  █ ',
        ' ████ ',
        '    █ ',
        ' ████ '
    ],
    ':': [
        '    ',
        ' ██ ',
        '    ',
        ' ██ ',
        '    '
    ],
    ' ': [
        '    ',
        '    ',
        '    ',
        '    ',
        '    '
    ]
}


# ==========================================
# FONT DIGITAL PEACLOCK STYLE (7-SEGMENT)
# Based on peaclock's digital view (block 2x1, 7-segment)
# Main clock: 5 rows × 12 cols per digit (block 2x1, 7-seg)
# Small clock: 4 rows × 10 cols per digit
# ==========================================

# 7-segment patterns for peaclock digital style
# Each segment is a 2×1 block (██ for on, '  ' for off)
# Layout:  aaaa  (top)
#        f    b (upper)
#        gggg  (middle)
#        e    c (lower)
#        dddd  (bottom)

SEG_ON = '██'
SEG_OFF = '  '

# 7-segment patterns: a, b, c, d, e, f, g
SEGMENTS = {
    '0': 'abcefd',  # a,b,c,d,e,f (no g)
    '1': 'bc',       # b,c only
    '2': 'abged',   # a,b,g,e,d
    '3': 'abgcd',   # a,b,c,d,g
    '4': 'fgbc',    # f,g,b,c
    '5': 'afgcd',   # a,f,g,c,d
    '6': 'afgcde',  # a,f,g,c,d,e
    '7': 'abc',     # a,b,c
    '8': 'abcdefg', # all
    '9': 'abfgcd',  # a,b,f,g,c,d
}

def build_peaclock_digit_5rows(segs):
    """Build 5-row peaclock digital digit (block 2x1 style)"""
    # Each row is 12 chars wide (6 segments × 2 chars)
    rows = [''] * 5
    
    # Row 0: segment a (top horizontal) - 6 blocks wide
    row0 = ''
    for _ in range(6):
        row0 += SEG_ON if 'a' in segs else SEG_OFF
    rows[0] = row0
    
    # Rows 1-2: segments f (left) and b (right) - 2 rows for upper verticals
    row1 = row2 = ''
    for _ in range(2):
        row1 += SEG_ON if 'f' in segs else SEG_OFF
    for _ in range(4):
        row1 += SEG_OFF  # middle gap
    for _ in range(2):
        row1 += SEG_ON if 'b' in segs else SEG_OFF
    rows[1] = row1
    
    for _ in range(2):
        row2 += SEG_ON if 'f' in segs else SEG_OFF
    for _ in range(4):
        row2 += SEG_OFF
    for _ in range(2):
        row2 += SEG_ON if 'b' in segs else SEG_OFF
    rows[2] = row2
    
    # Row 3: segment g (middle horizontal)
    row3 = ''
    for _ in range(6):
        row3 += SEG_ON if 'g' in segs else SEG_OFF
    rows[3] = row3
    
    # Rows 4: segments e (left) and c (right) - lower verticals + d (bottom)
    row4 = ''
    for _ in range(2):
        row4 += SEG_ON if 'e' in segs else SEG_OFF
    for _ in range(4):
        row4 += SEG_OFF
    for _ in range(2):
        row4 += SEG_ON if 'c' in segs else SEG_OFF
    rows[4] = row4
    
    # Actually peaclock uses 5 rows for digital view with block 2x1
    # Let me reconsider - peaclock digital view has different rendering
    # Let me use a simpler but accurate approach
    pass


NAMA_HARI = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu"
}

NAMA_BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

BULAN_HIJRI = [
    '', 'Muharram', 'Safar', "Rabi'ul Awwal", "Rabi'ul Akhir",
    'Jumadil Awwal', 'Jumadil Akhir', 'Rajab', "Sya'ban",
    'Ramadhan', 'Syawwal', "Dzulqa'dah", "Dzulhijjah"
]


def hitung_hijri(dt: date) -> str:
    """Mengonversi tanggal Masehi ke kalender Hijriah (Algoritma Tabular Islam)."""
    y = dt.year
    m = dt.month
    d = dt.day

    if m < 3:
        y -= 1
        m += 12

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


class TerminalDashboard:
    def __init__(self):
        self.api = JadwalSalatAPI()
        self.running = True
        self.config = load_config()
        self.jadwal_cache: Optional[Dict[str, Any]] = None
        self.last_fetch_date: Optional[date] = None
        self.old_terminal_settings = None
        # Kartu yang tersembunyi (Subuh, Terbit, Dhuha) — tampilkan sebagai ruang kosong
        self.HIDDEN_KEYS = {"imsak", "terbit", "dhuha"}

    def setup_terminal(self):
        """Menyiapkan terminal: alternate screen, sembunyikan kursor, dan non-blocking raw input."""
        sys.stdout.write("\033[?1049h")  # Masuk alternate screen buffer
        sys.stdout.write("\033[?25l")    # Sembunyikan kursor
        sys.stdout.flush()

        if sys.stdin.isatty():
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def restore_terminal(self):
        """Mengembalikan pengaturan terminal seperti semula."""
        if self.old_terminal_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
        sys.stdout.write("\033[?25h")    # Tampilkan kembali kursor
        sys.stdout.write("\033[?1049l")  # Keluar alternate screen buffer
        sys.stdout.write(RESET)
        sys.stdout.flush()

    def fetch_jadwal(self, force: bool = False):
        """Mengambil data jadwal salat dari API sesuai tanggal hari ini."""
        today = date.today()
        if not force and self.jadwal_cache and self.last_fetch_date == today:
            return

        kota_id = self.config.get("lokasi_id", "1204")
        try:
            res = self.api.get_jadwal_harian(kota_id, today)
            if res and "jadwal" in res:
                self.jadwal_cache = res
                self.last_fetch_date = today
        except Exception as e:
            # Jika koneksi gagal, pertahankan cache sebelumnya jika ada
            pass

    def get_upcoming_prayer(self, now_dt: datetime) -> Tuple[Optional[str], Optional[timedelta]]:
        """
        Menentukan jadwal salat berikutnya serta hitung mundur (countdown).
        Returns: (nama_salat, sisa_waktu)
        """
        if not self.jadwal_cache or "jadwal" not in self.jadwal_cache:
            return None, None

        jadwal = self.jadwal_cache["jadwal"]
        today = now_dt.date()

        urutan = ["imsak", "subuh", "terbit", "dhuha", "dzuhur", "ashar", "maghrib", "isya"]
        label_map = {
            "imsak": "IMSAK", "subuh": "SUBUH", "terbit": "TERBIT", "dhuha": "DHUHA",
            "dzuhur": "DZUHUR", "ashar": "ASHAR", "maghrib": "MAGHRIB", "isya": "ISYA'"
        }

        # Cari waktu berikutnya
        for key in urutan:
            val_str = jadwal.get(key)
            if not val_str:
                continue
            jam, menit = map(int, val_str.split(":"))
            waktu_salat_dt = datetime(today.year, today.month, today.day, jam, menit, 0)

            if now_dt < waktu_salat_dt:
                diff = waktu_salat_dt - now_dt
                return label_map[key], diff

        # Jika sudah melewati Isya, target berikutnya adalah Imsak besok
        val_imsak = jadwal.get("imsak", "04:08")
        jam, menit = map(int, val_imsak.split(":"))
        imsak_besok = datetime(today.year, today.month, today.day, jam, menit, 0) + timedelta(days=1)
        diff = imsak_besok - now_dt
        return "IMSAK", diff

    def render_peaclock_time_main(self, time_str: str) -> List[str]:
        """Render time in peaclock digital style (5 rows, block 2x1)."""
        lines = [''] * 5
        for ch in time_str:
            if ch == ':':
                glyph = self._build_peaclock_colon_main()
            elif ch == ' ':
                glyph = ['     '] * 5
            else:
                glyph = self._build_peaclock_digit_main(SEGMENTS.get(ch, ''))
            for i in range(5):
                lines[i] += glyph[i]
        return lines

    def render_peaclock_time_small(self, time_str: str) -> List[str]:
        """Render time in peaclock digital style (4 rows, small)."""
        lines = [''] * 4
        for ch in time_str:
            if ch == ':':
                glyph = self._build_peaclock_colon_small()
            elif ch == ' ':
                glyph = ['     '] * 4
            else:
                glyph = self._build_peaclock_digit_small(SEGMENTS.get(ch, ''))
            for i in range(4):
                lines[i] += glyph[i]
        return lines

    def _build_peaclock_digit_main(self, segs: str) -> List[str]:
        """Build 5-row peaclock digital digit (block 2x1 style) - 12 chars wide."""
        rows = [''] * 5
        # Row 0: segment a (top) - 6 blocks
        rows[0] = (SEG_ON if 'a' in segs else SEG_OFF) * 6
        # Rows 1-2: f (left) and b (right)
        for r in range(1, 3):
            left = SEG_ON * 2 if 'f' in segs else SEG_OFF * 2
            mid = SEG_OFF * 4
            right = SEG_ON * 2 if 'b' in segs else SEG_OFF * 2
            rows[r] = left + SEG_OFF * 4 + right
        # Row 3: segment g (middle)
        rows[3] = (SEG_ON if 'g' in segs else SEG_OFF) * 6
        # Row 4: e (left), c (right)
        rows[4] = (SEG_ON * 2 if 'e' in segs else SEG_OFF * 2) + SEG_OFF * 4 + (SEG_ON * 2 if 'c' in segs else SEG_OFF * 2)
        return rows

    def _build_peaclock_digit_small(self, segs: str) -> List[str]:
        """Build 4-row small peaclock digit - 10 chars wide."""
        rows = [''] * 4
        # Row 0: segment a
        rows[0] = (SEG_ON if 'a' in segs else SEG_OFF) * 5
        # Row 1: f and b
        left = SEG_ON * 2 if 'f' in segs else SEG_OFF * 2
        right = SEG_ON * 2 if 'b' in segs else SEG_OFF * 2
        rows[1] = left + SEG_OFF * 3 + right
        # Row 2: segment g (middle)
        rows[2] = (SEG_ON if 'g' in segs else SEG_OFF) * 5
        # Row 3: e, c, d
        rows[3] = (SEG_ON * 2 if 'e' in segs else SEG_OFF * 2) + SEG_OFF * 3 + (SEG_ON * 2 if 'c' in segs else SEG_OFF * 2)
        return rows

    def _build_peaclock_colon_main(self) -> List[str]:
        """Build main clock colon (5 rows)."""
        return ['     ', '  ██  ', '     ', '  ██  ', '     ']

    def _build_peaclock_colon_small(self) -> List[str]:
        """Build small clock colon (4 rows)."""
        return ['     ', '  ██  ', '     ', '  ██  ']

    def render_peaclock_time_main(self, time_str: str) -> List[str]:
        """Render time in peaclock digital style (5 rows, block 2x1)."""
        lines = [''] * 5
        for ch in time_str:
            if ch == ':':
                glyph = self._build_peaclock_colon_main()
            elif ch == ' ':
                glyph = ['     '] * 5
            else:
                glyph = self._build_peaclock_digit_main(SEGMENTS.get(ch, ''))
            for i in range(5):
                lines[i] += glyph[i]
        return lines

    def render_peaclock_time_small(self, time_str: str) -> List[str]:
        """Render time in peaclock digital style (4 rows, small)."""
        lines = [''] * 4
        for ch in time_str:
            if ch == ':':
                glyph = self._build_peaclock_colon_small()
            elif ch == ' ':
                glyph = ['     '] * 4
            else:
                glyph = self._build_peaclock_digit_small(SEGMENTS.get(ch, ''))
            for i in range(4):
                lines[i] += glyph[i]
        return lines

    def build_frame(self) -> str:
        """Menyusun seluruh tampilan frame dasbor dalam string tunggal."""
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

        # 1. HEADER
        output.append(center_line(f"{COLOR_TITLE}{BOLD}{judul.upper()}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols))
        output.append("")

        # Baris pemisah
        div_w = min(cols - 8, 104)
        div_pad = " " * max(0, (cols - div_w) // 2)
        output.append(f"{div_pad}{COLOR_BORDER}{'─' * div_w}{RESET}")
        output.append("")

        # ============================================================
        # LAYOUT 3x2 (peaclock style)
        # Baris 1: [JAM BERDETAK] [SUBUH] [DZUHUR]
        # Baris 2: [ASHAR] [MAGHRIB] [ISYA]
        # ============================================================

        # Cell dimensions
        gap = 4
        available_w = cols - 4
        cell_w = max(22, (available_w - gap * 2) // 3)
        cell_h = 7  # top border + label + 4 waktu + bottom border

        # Data
        jadwal = self.jadwal_cache.get("jadwal", {}) if self.jadwal_cache else {}
        next_prayer, remaining = self.get_upcoming_prayer(now)

        # Grid labels: 2 rows x 3 cols
        grid_labels = [
            [("JAM", None), ("SUBUH", "subuh"), ("DZUHUR", "dzuhur")],
            [("ASHAR", "ashar"), ("MAGHRIB", "maghrib"), ("ISYA'", "isya")]
        ]

        def build_cell(label, key, is_active, is_past):
            """Build a single grid cell with label + time (7 lines). ALL use LARGE format."""
            lines = []

            # Determine colors
            if is_active:
                border_c = COLOR_ACTIVE_CARD
                text_c = COLOR_ACTIVE_CARD + BOLD
            elif is_past:
                border_c = COLOR_BORDER_DIM
                text_c = COLOR_PASSED_CARD
            else:
                border_c = COLOR_BORDER
                text_c = COLOR_NORMAL_CARD

            # Top border
            lines = [f"{border_c}┏{'━' * (cell_w - 2)}┓{RESET}"]

            # Label
            lines.append(f"{border_c}┃{text_c}{label.center(cell_w - 2)}{border_c}┃{RESET}")

            # ALL cells use LARGE format (5 rows) - peaclock digital style
            waktu_val = "--:--"
            if key:
                waktu_val = jadwal.get(key, "--:--")
            
            clock_lines = self.render_peaclock_time_main(waktu_val)
            for line in clock_lines:
                pad_w = max(0, (cell_w - len(line)) // 2)
                lines.append(f"{border_c}┃{' ' * pad_w}{text_c}{line}{' ' * (cell_w - 2 - pad_w - len(line))}{border_c}┃{RESET}")

            # Bottom border
            lines.append(f"{border_c}┗{'━' * (cell_w - 2)}┛{RESET}")

            return lines

        def is_prayer_past(key):
            if not key or key not in jadwal:
                return False
            waktu_val = jadwal[key]
            if waktu_val == "--:--":
                return False
            try:
                j_h, j_m = map(int, waktu_val.split(":"))
                j_dt = datetime(today.year, today.month, today.day, j_h, j_m)
                return now > j_dt
            except:
                return False

        # Cell dimensions
        gap = 4
        available_w = cols - 4
        cell_w = max(22, (available_w - gap * 2) // 3)
        cell_h = 7

        # Grid labels: 2 rows x 3 cols
        grid_labels = [
            [("JAM", None), ("SUBUH", "subuh"), ("DZUHUR", "dzuhur")],
            [("ASHAR", "ashar"), ("MAGHRIB", "maghrib"), ("ISYA'", "isya")]
        ]

        # Build all cells
        cells = [[], []]
        for row_idx in range(2):
            for col_idx in range(3):
                label, key = grid_labels[row_idx][col_idx]
                is_active = (key == next_prayer)
                is_past = False
                if key:
                    waktu_val = jadwal.get(key, "--:--")
                    if waktu_val != "--:--":
                        try:
                            j_h, j_m = map(int, waktu_val.split(":"))
                            j_dt = datetime(today.year, today.month, today.day, j_h, j_m)
                            is_past = now > j_dt
                        except:
                            pass
                # Jam (key=None) tidak pernah past/active
                if key is None:
                    is_active = False
                    is_past = False
                else:
                    is_active = (key == next_prayer)

                cells[row_idx].append(build_cell(label, key, is_active, is_past))

        # Render clock first (top-left area)
        time_str = now.strftime("%H:%M:%S")
        clock_lines = self.render_peaclock_time_main(time_str)
        clock_w = len(clock_lines[0])
        clock_pad = " " * 2
        for line in clock_lines:
            output.append(f"{clock_pad}{COLOR_CLOCK}{BOLD}{line}{RESET}")
        output.append("")

        # Render grid: 2 rows x 3 cols
        gap = 4
        for row_idx in range(2):
            for line_idx in range(cell_h):
                row_parts = []
                for col_idx in range(3):
                    row_parts.append(cells[row_idx][col_idx][line_idx])
                gap_str = " " * gap
                row_line = gap_str.join(row_parts)
                pad = " " * ((cols - len(row_line)) // 2)
                output.append(f"{pad}{row_line}")
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
            cd_len = len(cd_text)
        else:
            cd_text = "Memuat data jadwal salat..."
            countdown_line = f"{DIM}{cd_text}{RESET}"
            cd_len = len(cd_text)

        output.append(f"{' ' * max(0, (cols - cd_len) // 2)}{countdown_line}")
        output.append("")

        # FOOTER
        footer_info = "Tekan [q] atau [Ctrl+C] untuk keluar  •  Sumber Data: Bimas Islam Kemenag RI"
        footer_pad = " " * ((cols - len(footer_info)) // 2)
        output.append(f"{footer_pad}{DIM}{footer_info}{RESET}")

        # Top margin
        content_height = len(output)
        top_margin = max(0, (rows - content_height) // 3)

        full_screen = "\n" * top_margin + "\n".join(output)
        return full_screen

    def run(self):
        """Loop utama dasbor terminal."""
        self.setup_terminal()
        try:
            # Muat jadwal pertama kali
            self.fetch_jadwal(force=True)

            while self.running:
                # Periksa apakah pergantian hari (00:00) untuk refresh jadwal
                today = date.today()
                if self.last_fetch_date != today:
                    self.fetch_jadwal(force=True)

                # Render frame
                frame = self.build_frame()

                # Tulis frame ke terminal tanpa flicker (\033[H memindahkan kursor ke pojok kiri atas)
                sys.stdout.write(f"\033[H\033[J{frame}")
                sys.stdout.flush()

                # Tunggu 1 detik atau deteksi tombol input 'q' secara non-blocking
                if sys.stdin.isatty():
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch in ('q', 'Q', '\x1b', '\x03'):  # 'q', Esc, atau Ctrl+C
                            self.running = False
                else:
                    time.sleep(1.0)

        except KeyboardInterrupt:
            self.running = False
        finally:
            self.restore_terminal()


if __name__ == "__main__":
    dashboard = TerminalDashboard()
    dashboard.run()