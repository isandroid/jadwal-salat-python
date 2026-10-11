#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Jam berdetak = peaclock `view digital` (persis, tanpa modifikasi).

Sumber acuan (kode sumber peaclock):
  src/peaclock/peaclock.hh  -> tabel _symbol (font 3 kolom x 5 baris) + template buffer
  src/peaclock/peaclock.cc  -> set_clock_digital(), fill_digital(), draw_clock()
  cfg/digital               -> block 2 1, padding 2 1, margin 2 1, ratio 2 1
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
COLOR_CLOCK = "\033[1;38;5;79m"      # teal, sama nuansa dengan peaclock digital
COLOR_PRAYER = "\033[38;5;44m"       # waktu salat (peaclock default, 3x5 padat)
COLOR_PRAYER_NEXT = "\033[1;38;5;226m"  # waktu salat berikutnya
COLOR_PRAYER_LABEL = "\033[38;5;245m"
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
    """Selaraskan teks tepat di tengah berdasarkan lebar visual."""
    pad = max(0, (total_cols - visible_width(text_with_ansi)) // 2)
    return " " * pad + text_with_ansi


# ==========================================
# PEACLOCK DIGITAL  (view digital)  -- PERSIS
# ==========================================

# Tabel _symbol dari peaclock.hh (3 kolom x 5 baris, row-major)
SYMBOLS = [
    (1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1),  # 0
    (0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0),  # 1
    (1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1),  # 2
    (1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1),  # 3
    (1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 1),  # 4
    (1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1),  # 5
    (1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1),  # 6
    (1, 1, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1),  # 7
    (1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1),  # 8
    (1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 1),  # 9
]

OFF, ON, COLON = 0, 1, 3

# Kolom penempatan digit, dari set_clock_digital()
DIGIT_COLS_SEC = [(0, 1, 2), (4, 5, 6), (10, 11, 12), (14, 15, 16), (20, 21, 22), (24, 25, 26)]
DIGIT_COLS_NOSEC = [(0, 1, 2), (4, 5, 6), (10, 11, 12), (14, 15, 16)]
COLON_COLS_SEC = (8, 18)
COLON_COLS_NOSEC = (8,)
NCOL_SEC, NCOL_NOSEC, NROW = 27, 17, 5

BLOCK_CHAR = "\u2588"


def build_grid(hh: int, mm: int, ss: int, show_seconds: bool = True) -> List[List[int]]:
    """Grid 5 baris x N kolom berisi nilai sel peaclock (0/1/3)."""
    digits = [hh // 10, hh % 10, mm // 10, mm % 10]
    cols, ncol, colon_cols = DIGIT_COLS_NOSEC, NCOL_NOSEC, COLON_COLS_NOSEC
    if show_seconds:
        digits += [ss // 10, ss % 10]
        cols, ncol, colon_cols = DIGIT_COLS_SEC, NCOL_SEC, COLON_COLS_SEC

    grid = [[OFF] * ncol for _ in range(NROW)]
    for d, cset in zip(digits, cols):
        sym = SYMBOLS[d]
        for r in range(NROW):
            for k, c in enumerate(cset):
                grid[r][c] = sym[r * 3 + k]
    for c in colon_cols:
        grid[1][c] = COLON
        grid[3][c] = COLON
    return grid


# Kandidat geometri: (blok_w, jarak_w, blok_h, jarak_h) dalam karakter/baris.
# Rasio blok : jarak = 2 : 1 pada kedua arah, persis hasil pengukuran
# screenshot resmi peaclock (dot 40 px, jarak 20 px). Blok tetap persegi
# karena blok_w karakter = blok_h baris (sel karakter ~2x lebih tinggi).
CANDIDATES = [
    (8, 4, 4, 2),   # 320 x 28
    (4, 2, 2, 1),   # 160 x 14  <- geometri persis peaclock resmi
    (2, 1, 1, 1),   #  80 x  9  <- versi kecil, rasio horizontal tetap 2:1
    (1, 1, 1, 1),   #  53 x  9  <- cadangan terminal sangat sempit
]


def choose_geometry(cols: int, rows: int, reserved_rows: int = 0,
                    ncol: int = NCOL_SEC):
    """Pilih geometri terbesar yang muat. Kembalikan (blok_w, blok_h, jarak_w, jarak_h)."""
    avail_w = max(1, cols)
    avail_h = max(1, rows - reserved_rows)
    for bw, gw, bh, gh in CANDIDATES:
        width = ncol * bw + (ncol - 1) * gw
        height = NROW * bh + (NROW - 1) * gh
        if width <= avail_w and height <= avail_h:
            return bw, bh, gw, gh
    bw, gw, bh, gh = CANDIDATES[-1]
    return bw, bh, gw, gh


def render_peaclock_digital(hh: int, mm: int, ss: int,
                            show_seconds: bool = True,
                            x_block: int = 4, y_block: int = 2,
                            x_space: int = 2, y_space: int = 1) -> List[str]:
    """Render jam peaclock digital -> daftar baris teks.

    x_block/y_block = ukuran satu dot (karakter x baris).
    x_space/y_space = jarak antar dot (karakter x baris).
    Rasio resmi peaclock: blok : jarak = 2 : 1.
    """
    grid = build_grid(hh, mm, ss, show_seconds)
    on = BLOCK_CHAR * x_block
    off = " " * x_block
    gap = " " * x_space

    lines: List[str] = []
    for r in range(NROW):
        row = gap.join(on if v in (ON, COLON) else off for v in grid[r])
        for _ in range(y_block):
            lines.append(row)
        if r < NROW - 1:
            for _ in range(y_space):
                lines.append("")
    return lines


# ==========================================
# PEACLOCK `default`  (cfg/default: block 2 1, padding 0 0)
# Font 3x5 yang SAMA dengan view digital, tetapi blok rapat tanpa jarak
# sehingga membentuk karakter 3 x 5 padat. Tanpa detik (set seconds off).
# ==========================================

def render_peaclock_default(hh: int, mm: int, block_w: int = 2) -> List[str]:
    """Render HH:MM gaya peaclock `cfg/default` -> 5 baris, blok rapat."""
    grid = build_grid(hh, mm, 0, show_seconds=False)
    on = BLOCK_CHAR * block_w
    off = " " * block_w
    return ["".join(on if v in (ON, COLON) else off for v in row) for row in grid]


PRAYER_ORDER = [
    ("SUBUH", "subuh"),
    ("DZUHUR", "dzuhur"),
    ("ASHAR", "ashar"),
    ("MAGHRIB", "maghrib"),
    ("ISYA'", "isya"),
]

# pembagian kartu per baris untuk 5 waktu salat
PRAYER_LAYOUTS = [(5,), (3, 2), (2, 2, 1), (1, 1, 1, 1, 1)]


def choose_prayer_layout(cols: int, rows: int, sep: int = 4):
    """Pilih (block_w, layout) terbesar yang muat.

    Tiap baris kartu tinggi 6 baris (1 label + 5 baris waktu), 1 baris jarak
    antar baris kartu. Tata letak <= 2 baris diutamakan; tata letak lebih
    banyak baris dipakai hanya bila perlu (terminal sempit). Di dalam satu
    kelompok, dipilih blok terbesar.
    """
    avail_w = max(1, cols - 4)
    avail_h = max(6, rows - 18)
    for group in ((0, 1), (2, 3)):          # <=2 baris dulu, lalu sisanya
        best = None
        for li in group:
            layout = PRAYER_LAYOUTS[li]
            if len(layout) * 6 + (len(layout) - 1) > avail_h:
                continue
            widest = max(layout)
            for bw in (4, 3, 2, 1):
                card_w = NCOL_NOSEC * bw
                if widest * card_w + (widest - 1) * sep <= avail_w:
                    if best is None or bw > best[0]:
                        best = (bw, layout)
                    break
        if best:
            return best
    return None          # tidak ada tata letak kartu yang muat


def build_prayer_compact(entries, cols: int, highlight: int = -1, sep: int = 3) -> List[str]:
    """Cadangan untuk terminal sempit: daftar teks ringkas, dibungkus sesuai lebar."""
    items = []
    for i, (label, hhmm) in enumerate(entries):
        text = f"{label} {hhmm or '--:--'}"
        color = COLOR_PRAYER_NEXT if i == highlight else COLOR_PRAYER
        items.append((text, color))

    lines: List[str] = []
    cur, cur_w = [], 0
    for text, color in items:
        w = visible_width(text)
        add = w if not cur else sep + w
        if cur and cur_w + add > cols - 2:
            lines.append(_join_items(cur, cols))
            cur, cur_w = [], 0
            add = w
        cur.append((text, color))
        cur_w += add
    if cur:
        lines.append(_join_items(cur, cols))
    return lines


def _join_items(items, cols: int) -> str:
    sep = "   "
    plain = sep.join(t for t, _ in items)
    pad = max(0, (cols - len(plain)) // 2)
    colored = sep.join(f"{c}{t}{RESET}" for t, c in items)
    return " " * pad + colored


def build_prayer_section(entries, block_w: int, layout, cols: int,
                         highlight: int = -1, sep: int = 4) -> List[str]:
    """entries: [(label, 'HH:MM'|None), ...] -> daftar baris siap tayang."""
    card_w = NCOL_NOSEC * block_w

    cards: List[List[str]] = []
    for label, hhmm in entries:
        lines = [label.center(card_w)]
        if hhmm:
            hh, mm = (int(x) for x in hhmm.split(":"))
            lines += render_peaclock_default(hh, mm, block_w)
        else:
            lines += [" " * card_w] * 5
        cards.append(lines)

    out: List[str] = []
    idx = 0
    for ri, n in enumerate(layout):
        row_cards = cards[idx:idx + n]
        idx += n
        total_w = n * card_w + (n - 1) * sep
        left = " " * max(0, (cols - total_w) // 2)
        gap = " " * sep
        for r in range(6):
            parts = []
            for ci, card in enumerate(row_cards):
                gi = idx - n + ci
                seg = card[r] if r < len(card) else " " * card_w
                if r == 0:
                    parts.append(f"{COLOR_PRAYER_LABEL}{seg}{RESET}")
                elif gi == highlight:
                    parts.append(f"{COLOR_PRAYER_NEXT}{seg}{RESET}")
                else:
                    parts.append(f"{COLOR_PRAYER}{seg}{RESET}")
            out.append(left + gap.join(parts))
        if ri < len(layout) - 1:
            out.append("")
    return out



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

    def prayer_entries(self) -> List[Tuple[str, Optional[str]]]:
        """[(label, 'HH:MM'|None), ...] untuk 5 waktu salat hari ini."""
        jadwal = (self.jadwal_cache or {}).get("jadwal") or {}
        out: List[Tuple[str, Optional[str]]] = []
        for label, key in PRAYER_ORDER:
            val = jadwal.get(key)
            out.append((label, val if val else None))
        return out

    def next_prayer_index(self, now_dt: datetime) -> int:
        """Indeks kartu waktu salat berikutnya (untuk disorot), -1 bila tidak ada."""
        jadwal = (self.jadwal_cache or {}).get("jadwal") or {}
        today = now_dt.date()
        for i, (_, key) in enumerate(PRAYER_ORDER):
            val = jadwal.get(key)
            if not val:
                continue
            hh, mm = map(int, val.split(":"))
            if now_dt < datetime(today.year, today.month, today.day, hh, mm, 0):
                return i
        return -1

    def build_frame(self) -> str:
        cols, rows = shutil.get_terminal_size((120, 36))
        now = datetime.now()
        today = now.date()

        judul = self.config.get("judul", "Jadwal Salat Masjid Nasr")
        lokasi_nama = self.config.get("lokasi_nama", "KAB. BOGOR")
        daerah = self.jadwal_cache.get("daerah", "JAWA BARAT") if self.jadwal_cache else ""
        lokasi_str = f"📍 Lokasi: {lokasi_nama}{', ' + daerah if daerah else ''} (ID: {self.config.get('lokasi_id')})"
        masehi_str = f"{NAMA_HARI[today.weekday()]}, {today.day} {NAMA_BULAN[today.month]} {today.year}"
        hijri_str = hitung_hijri(today)
        tanggal_str = f"📅 {masehi_str}  |  🌙 {hijri_str}"
        if visible_width(tanggal_str) > cols - 2:          # terminal sempit
            tanggal_str = f"{masehi_str}  |  {hijri_str}"
        if visible_width(tanggal_str) > cols - 2:
            tanggal_str = masehi_str
        if visible_width(tanggal_str) > cols - 2:
            tanggal_str = f"{today.day}/{today.month}/{today.year}"
        if visible_width(lokasi_str) > cols - 2:
            lokasi_str = f"{lokasi_nama} (ID: {self.config.get('lokasi_id')})"
        if visible_width(lokasi_str) > cols - 2:
            lokasi_str = str(lokasi_nama)

        out: List[str] = []
        out.append(center_line(f"{COLOR_TITLE}{BOLD}{judul.upper()}{RESET}", cols))
        out.append(center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols))
        out.append(center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols))
        out.append("")

        div_w = min(cols - 4, 106)
        div_pad = " " * max(0, (cols - div_w) // 2)
        out.append(f"{div_pad}{COLOR_BORDER}{'─' * div_w}{RESET}")
        out.append("")

        # ---- Waktu-waktu salat: peaclock `default` (font 3x5 padat) ----
        chosen = choose_prayer_layout(cols, rows)
        if chosen:
            prayer_bw, prayer_layout = chosen
            prayer_h = len(prayer_layout) * 6 + (len(prayer_layout) - 1)
        else:
            prayer_bw, prayer_layout, prayer_h = 0, None, 2   # daftar teks ringkas

        # ---- Jam berdetak: peaclock view digital (persis) ----
        reserved = len(out) + 1 + prayer_h + 1 + 2   # + blank + countdown + footer
        x_block, y_block, x_space, y_space = choose_geometry(cols, rows, reserved_rows=reserved)
        clock_lines = render_peaclock_digital(
            now.hour, now.minute, now.second,
            show_seconds=True, x_block=x_block, y_block=y_block,
            x_space=x_space, y_space=y_space,
        )
        clock_w = max((len(l) for l in clock_lines), default=0)
        pad = " " * max(0, (cols - clock_w) // 2)
        for line in clock_lines:
            if line.strip():
                out.append(f"{pad}{COLOR_CLOCK}{line}{RESET}")
            else:
                out.append("")

        out.append("")

        # ---- Waktu salat (peaclock default) ----
        entries = self.prayer_entries()
        hi = self.next_prayer_index(now)
        if prayer_layout:
            out.extend(build_prayer_section(entries, prayer_bw, prayer_layout, cols, highlight=hi))
        else:
            out.extend(build_prayer_compact(entries, cols, highlight=hi))
        out.append("")

        # ---- Countdown ----
        next_prayer, remaining = self.get_upcoming_prayer(now)
        if next_prayer and remaining:
            t = int(remaining.total_seconds())
            cd_text = (f"⏳ Menuju Waktu {next_prayer}: "
                       f"{t // 3600:02d} Jam {(t % 3600) // 60:02d} Menit {t % 60:02d} Detik")
        else:
            cd_text = "Memuat data jadwal salat..."
        out.append(center_line(f"{COLOR_COUNTDOWN}{BOLD}{cd_text}{RESET}", cols))

        # ---- Footer ----
        footer = "Tekan [q] atau [Ctrl+C] untuk keluar  •  Sumber Data: Bimas Islam Kemenag RI"
        if visible_width(footer) > cols - 2:
            footer = "Tekan [q] untuk keluar  •  Bimas Islam Kemenag RI"
        if visible_width(footer) > cols - 2:
            footer = "Tekan [q] untuk keluar"
        out.append(center_line(f"{DIM}{footer}{RESET}", cols))

        top_margin = max(0, (rows - len(out)) // 4)
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
