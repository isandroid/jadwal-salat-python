#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Jam berdetak = peaclock `view digital` (persis, tanpa modifikasi).

Sumber acuan (kode sumber peaclock):
  src/peaclock/peaclock.hh  -> tabel _symbol (font 3 kolom x 5 baris) + template buffer
  src/peaclock/peaclock.cc  -> set_clock_digital(), fill_digital(), draw_clock()
  cfg/digital               -> block 2 1, padding 2 1, margin 2 1, ratio 2 1
"""

import os
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
import cache

# ==========================================
# PALET WARNA ANSI
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# ==========================================
# WARNA — dapat diatur dari config.json pada kunci "warna".
# Nilainya adalah parameter SGR (isi di dalam  ESC [ ... m ):
#
#   "1;38;5;79"       tebal + warna palet-256 nomor 79
#   "38;5;79"         warna palet-256 nomor 79 (tanpa tebal)
#   "38;2;255;128;0"  warna 24-bit (RGB bebas)
#   "1;33"            warna dasar 4-bit: kuning tebal
#   ""  atau "0"      tanpa warna (ikut warna bawaan terminal)
#
# Lihat daftar nomornya dengan:  python3 main.py --warna
# ==========================================
WARNA_DEFAULT = {
    "judul":         "1;38;5;220",   # judul dasbor
    "subjudul":      "38;5;153",     # lokasi & tanggal
    "nama":          "1;38;5;231",   # nama waktu salat (SUBUH, DZUHUR, ...)
    "jam":           "1;38;5;79",    # jam berdetak + detik
    "waktu_azan":    "1;38;5;79",    # angka waktu azan
    "waktu_iqamat":  "38;5;44",      # angka waktu iqamat
    "berikutnya":    "1;38;5;226",   # waktu salat berikutnya (disorot)
    "label_iqamat":  "38;5;110",     # label "IQAMAT"
    "hitung_mundur": "1;38;5;227",   # baris hitung mundur di header
    "garis":         "38;5;240",     # garis/bingkai
}


def sgr(params: str) -> str:
    """Ubah parameter SGR menjadi urutan ANSI lengkap ('' = tanpa warna)."""
    params = str(params).strip()
    if not params or params == "0":
        return ""
    return f"\033[{params}m"


def warna_dipakai(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Gabungkan nilai bawaan dengan yang ada di config.json."""
    hasil = dict(WARNA_DEFAULT)
    for k, v in (cfg.get("warna") or {}).items():
        if k in WARNA_DEFAULT and v is not None:
            hasil[k] = str(v)
    return hasil


def terapkan_warna(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Terapkan warna dari config.json ke variabel modul."""
    global COLOR_TITLE, COLOR_SUBTITLE, COLOR_BORDER, COLOR_CLOCK, COLOR_TIME
    global COLOR_IQAMAT_TIME, COLOR_NAME, COLOR_IQAMAT_LABEL, COLOR_INFO
    global COLOR_PRAYER, COLOR_PRAYER_NEXT, COLOR_COUNTDOWN

    w = warna_dipakai(cfg)
    COLOR_TITLE        = sgr(w["judul"])
    COLOR_SUBTITLE     = sgr(w["subjudul"])
    COLOR_BORDER       = sgr(w["garis"])
    COLOR_CLOCK        = sgr(w["jam"])
    COLOR_TIME         = sgr(w["waktu_azan"])
    COLOR_IQAMAT_TIME  = sgr(w["waktu_iqamat"])
    COLOR_NAME         = sgr(w["nama"])
    COLOR_IQAMAT_LABEL = sgr(w["label_iqamat"])
    COLOR_INFO         = sgr(w["label_iqamat"])
    COLOR_PRAYER       = COLOR_IQAMAT_TIME
    COLOR_PRAYER_NEXT  = sgr(w["berikutnya"])
    COLOR_COUNTDOWN    = sgr(w["hitung_mundur"])
    return w


# Nilai awal (ditimpa oleh terapkan_warna saat dasbor dijalankan)
COLOR_TITLE = "\033[1;38;5;220m"
COLOR_SUBTITLE = "\033[38;5;153m"
COLOR_BORDER = "\033[38;5;34m"
COLOR_CLOCK = "\033[1;38;5;79m"       # jam berdetak (bold teal)
COLOR_TIME = "\033[1;38;5;79m"        # waktu azan (bold teal)
COLOR_IQAMAT_TIME = "\033[38;5;44m"   # waktu iqamat (teal, tanpa bold)
COLOR_NAME = "\033[1;38;5;231m"       # nama waktu salat: BOLD putih terang
COLOR_IQAMAT_LABEL = "\033[38;5;110m" # label "IQAMAT" (sekunder)
COLOR_INFO = "\033[38;5;110m"         # info di sel jam (tanggal, hitung mundur)
COLOR_PRAYER = "\033[38;5;44m"
COLOR_PRAYER_NEXT = "\033[1;38;5;226m"  # waktu salat berikutnya
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

# ==========================================
# PEACLOCK `default`  (cfg/default: block 2 1, padding 0 0)
# Font 3x5 yang SAMA dengan view digital, tetapi blok rapat tanpa jarak
# sehingga membentuk karakter 3 x 5 padat. Tanpa detik (set seconds off).
# ==========================================

def render_peaclock_default(hh: int, mm: int, block_w: int = 2,
                            colon_on: bool = True) -> List[str]:
    """Render HH:MM gaya peaclock `cfg/default` -> 5 baris, blok rapat.

    colon_on=False membuat titik dua padam (untuk efek kolon berkedip).
    """
    grid = build_grid(hh, mm, 0, show_seconds=False)
    if not colon_on:
        for r in range(NROW):
            for c in COLON_COLS_NOSEC:
                grid[r][c] = OFF
    on = BLOCK_CHAR * block_w
    off = " " * block_w
    return ["".join(on if v in (ON, COLON) else off for v in row) for row in grid]


def render_peaclock_seconds(ss: int, block_w: int = 2) -> List[str]:
    """Render 2 digit DETIK pada kolom milik bagian MM dari tata letak 17 kolom,
    sehingga hasilnya tepat berada di bawah `mm` pada jam HH:MM."""
    grid = [[OFF] * NCOL_NOSEC for _ in range(NROW)]
    for d, cset in zip((ss // 10, ss % 10), DIGIT_COLS_NOSEC[2:4]):
        sym = SYMBOLS[d % 10]
        for r in range(NROW):
            for k, c in enumerate(cset):
                grid[r][c] = sym[r * 3 + k]
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

def sekarang() -> datetime:
    """Waktu sekarang. Bisa dipaksa untuk uji/tangkapan layar: DASDOR_JAM=15:30 (jam:menit).

    Dipakai supaya perilaku sorotan bisa dibuktikan pada jam berapa pun tanpa menunggu waktu
    nyata — mis. "pada 15:30 harus ASHAR yang kuning, pada 18:30 harus MAGHRIB".
    """
    paksa = os.environ.get("DASDOR_JAM")
    if paksa:
        try:
            j, m = (int(x) for x in paksa.strip().split(":")[:2])
            d = datetime.now()
            return d.replace(hour=j % 24, minute=m % 60, second=0, microsecond=0)
        except (ValueError, TypeError):
            pass
    return datetime.now()


def build_prayer_compact(entries, cols: int, highlight: int = -1, sep: int = 3) -> List[str]:
    """Cadangan untuk terminal sempit: daftar teks ringkas, dibungkus sesuai lebar."""
    items = []
    for i, entry in enumerate(entries):
        label = entry[0]
        azan = entry[1] if len(entry) > 1 else None
        iq = entry[2] if len(entry) > 2 else None
        text = f"{label} {azan or '--:--'}"
        if iq:
            text += f"/{iq}"
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

# ==========================================
# GRID 3 KOLOM x 4 BARIS BERBINGKAI
#   baris 1 : JAM (berdetak)      | SUBUH   | DZUHUR     <- nama + waktu azan
#   baris 2 : (info jam)          | IQAMAT  | IQAMAT     <- waktu iqamat
#   baris 3 : ASHAR               | MAGHRIB | ISYA'      <- nama + waktu azan
#   baris 4 : IQAMAT              | IQAMAT  | IQAMAT     <- waktu iqamat
# Sel jam menempati kolom 1 baris 1-2 (menyatu). Semua waktu memakai font
# peaclock `cfg/default` (3 x 5 padat), ukuran blok sama untuk semua sel.
# ==========================================
GRID_COLS = 3
GRID_ROWS = 4
CELL_LINES = 6            # 1 baris label + 5 baris waktu
TOP_PAD = 2               # padding kosong di atas seluruh tampilan (baris)
BOTTOM_PAD = 2            # padding kosong di bawah seluruh tampilan (baris)

BOX_V, BOX_H = "│", "─"
BOX_TL, BOX_TM, BOX_TR = "┌", "┬", "┐"
BOX_ML, BOX_MM, BOX_MR = "├", "┼", "┤"
BOX_BL, BOX_BM, BOX_BR = "└", "┴", "┘"


# Tinggi tiap baris grid. Varian ringkas membuang baris label "IQAMAT".
ROW_LINES_FULL = [6, 6, 6, 6]
ROW_LINES_COMPACT = [6, 5, 6, 5]

# Lebar bantalan kiri-kanan maksimum di dalam sel (kolom). Dipakai choose_grid
# untuk melebarkan grid agar mengisi layar lebar TANPA mengubah ukuran blok
# digit jam (proporsi titik 2 karakter x 1 baris tetap). Turunkan bila ingin
# panel lebih rapat.
PANEL_PAD_MAKS = 8


# Garis pemisah yang dihilangkan karena selnya menyatu.
#   indeks = nomor garis pemisah (setelah baris ke-N), nilai = kolom yang menyatu
MERGED_SEPS = {0: {0, 1, 2}, 2: {0, 1, 2}}


def _seps_skipped(merged=None) -> int:
    m = MERGED_SEPS if merged is None else merged
    return sum(1 for r in range(GRID_ROWS - 1)
               if len(m.get(r, set())) >= GRID_COLS)


def grid_height(row_lines) -> int:
    return sum(row_lines) + (GRID_ROWS + 1) - _seps_skipped()


def choose_grid(cols: int, rows: int, header_h: int, footer_h: int):
    """Pilih (block_w, inner_w, pad, row_lines) terbesar yang muat lebar & tinggi.

    Lebar total = GRID_COLS * (inner_w + 2*pad) + (GRID_COLS + 1)

    `pad` adalah lebar bantalan KIRI-KANAN di dalam tiap sel. Nilai bantalan
    dicoba dari yang paling lebar (PANEL_PAD_MAKS) supaya grid mengisi lebar
    layar sepenuhnya tanpa mengubah ukuran blok digit -> bentuk jam (rasio
    titik 2 karakter x 1 baris) tetap benar di layar lebar.
    """
    avail_h = rows - header_h - footer_h
    for row_lines in (ROW_LINES_FULL, ROW_LINES_COMPACT):
        if grid_height(row_lines) > avail_h:
            continue
        for bw in (4, 3, 2, 1):
            inner_w = NCOL_NOSEC * bw
            for pad in range(PANEL_PAD_MAKS, -1, -1):
                if GRID_COLS * (inner_w + 2 * pad) + (GRID_COLS + 1) <= cols:
                    return bw, inner_w, pad, row_lines
    return None


def _clip(text: str, width: int) -> str:
    """Potong teks agar muat `width` kolom tampilan (emoji dihitung 2)."""
    t = text
    while t and visible_width(t) > width:
        t = t[:-1]
    return t


def _fit(text: str, width: int) -> str:
    """Potong lalu tengahkan berdasarkan lebar tampilan (emoji = 2 kolom)."""
    t = _clip(text, width)
    pad = max(0, width - visible_width(t))
    left = pad // 2
    return " " * left + t + " " * (pad - left)


def build_cells(now: datetime, rows_data, grid_bw: int, colon_on: bool,
                row_lines, highlight: int = -1):
    """Susun isi 4 x 3 sel. Tiap baris = (teks, kode warna)."""
    blank = " " * (NCOL_NOSEC * grid_bw)

    def time_lines(hhmm):
        if not hhmm:
            return [blank] * 5
        hh, mm = (int(x) for x in hhmm.split(":"))
        return render_peaclock_default(hh, mm, grid_bw)

    def fit(lines, n):
        lines = list(lines)
        while len(lines) < n:
            lines.append(("", ""))
        return lines[:n]

    cells: Dict[Tuple[int, int], List[Tuple[str, str]]] = {}

    # kolom 1, baris 1-2 : jam berdetak (menyatu)
    clock = [("JAM", COLOR_NAME)]
    clock += [(t, COLOR_CLOCK) for t in
              render_peaclock_default(now.hour, now.minute, grid_bw, colon_on)]
    cells[(0, 0)] = fit(clock, row_lines[0])

    # baris kedua sel jam: DETIK, tepat di bawah bagian `mm`
    detik = [("", "")] + [(t, COLOR_CLOCK) for t in
                          render_peaclock_seconds(now.second, grid_bw)]
    cells[(1, 0)] = fit(detik, row_lines[1])

    # SUBUH & DZUHUR di baris 1; ASHAR, MAGHRIB, ISYA' di baris 3
    placement = [(0, 1), (0, 2), (2, 0), (2, 1), (2, 2)]
    for idx, ((label, azan, iq), (r, c)) in enumerate(zip(rows_data, placement)):
        is_next = (idx == highlight)
        name_col = COLOR_PRAYER_NEXT if is_next else COLOR_NAME
        t_col = COLOR_PRAYER_NEXT if is_next else COLOR_TIME
        iq_col = COLOR_PRAYER_NEXT if is_next else COLOR_IQAMAT_TIME

        cells[(r, c)] = fit([(label, name_col)] + [(t, t_col) for t in time_lines(azan)],
                            row_lines[r])
        iq_lines = []
        if row_lines[r + 1] == CELL_LINES:
            iq_lines.append(("IQAMAT", COLOR_IQAMAT_LABEL))
        iq_lines += [(t, iq_col) for t in time_lines(iq)]
        cells[(r + 1, c)] = fit(iq_lines, row_lines[r + 1])
    return cells


def render_grid(cells, cols: int, inner_w: int, pad: int = 2,
                row_lines=None) -> List[str]:
    """Gambar grid 3 x 4 berbingkai (kolom 1 baris 1-2 menyatu untuk jam)."""
    if row_lines is None:
        row_lines = ROW_LINES_FULL
    cell_w = inner_w + 2 * pad

    def content_line(r: int, li: int) -> str:
        parts = []
        for col in range(GRID_COLS):
            line = cells.get((r, col), [])
            text, color = line[li] if li < len(line) else ("", "")
            seg = " " * pad + _fit(text, inner_w) + " " * pad
            parts.append(f"{color}{seg}{RESET}" if (color and text.strip()) else seg)
        return BOX_V + BOX_V.join(parts) + BOX_V

    def hline(left, mid, right):
        return left + (BOX_H * cell_w + mid) * (GRID_COLS - 1) + BOX_H * cell_w + right

    def sep_line(merged_cols):
        """Garis pemisah; kolom yang menyatu dibiarkan kosong."""
        def joint(lm, rm):
            if lm and rm:
                return BOX_V          # keduanya menyatu -> hanya garis tegak
            if lm:
                return BOX_ML         # garis hanya ke kanan
            if rm:
                return BOX_MR         # garis hanya ke kiri
            return BOX_MM
        last = GRID_COLS - 1
        line = BOX_V if 0 in merged_cols else BOX_ML
        for c in range(GRID_COLS):
            line += " " * cell_w if c in merged_cols else BOX_H * cell_w
            if c < last:
                line += joint(c in merged_cols, (c + 1) in merged_cols)
        line += BOX_V if last in merged_cols else BOX_MR
        return line

    out: List[str] = []
    out.append(hline(BOX_TL, BOX_TM, BOX_TR))
    for r in range(GRID_ROWS):
        for li in range(row_lines[r]):
            out.append(content_line(r, li))
        if r < GRID_ROWS - 1:
            merged_cols = MERGED_SEPS.get(r, set())
            if len(merged_cols) >= GRID_COLS:
                continue              # seluruh kolom menyatu -> tanpa garis pemisah
            out.append(sep_line(merged_cols))
    out.append(hline(BOX_BL, BOX_BM, BOX_BR))
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
    def __init__(self, ringkas: bool = False, resolusi=None):
        """ringkas=True  -> sembunyikan lokasi, hitung mundur, dan footer.
        resolusi=(W,H) -> dipakai sebagai perkiraan ukuran terminal bila ukuran
                          sebenarnya tidak bisa dibaca (mis. stdout bukan tty).
        """
        self.api = JadwalSalatAPI()
        self.running = True
        self.ringkas = ringkas
        self.resolusi = resolusi
        self.config = load_config()
        self.jadwal_cache: Optional[Dict[str, Any]] = None
        self.last_fetch_date: Optional[date] = None
        self.sumber_data = ""        # internet | cache | offline | kosong
        self.pesan_error = ""
        self.warna = terapkan_warna(self.config)
        cache.init()
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

    def ukuran_terminal(self):
        """Ukuran terminal (kolom, baris). Bila tidak bisa dibaca dan resolusi
        layar diketahui, ukuran diperkirakan dari resolusi + ukuran sel."""
        try:
            if sys.stdout.isatty():
                return shutil.get_terminal_size((120, 36))
        except Exception:
            pass
        if self.resolusi:
            sel = str(self.config.get("ukuran_sel", "8x18")).lower().split("x")
            try:
                lebar_sel, tinggi_sel = max(1, int(sel[0])), max(1, int(sel[1]))
            except Exception:
                lebar_sel, tinggi_sel = 8, 18
            return os.terminal_size((self.resolusi[0] // lebar_sel,
                                     self.resolusi[1] // tinggi_sel))
        return shutil.get_terminal_size((120, 36))

    def _saklar(self) -> Dict[str, bool]:
        """Saklar tampilan: mode ringkas menang atas config.json.

        Mode ringkas (--resolusi) menyembunyikan lokasi, hitung mundur, footer,
        sekaligus JUDUL dan TANGGAL. Dua baris terakhir itu diberikan kepada
        grid supaya baris label IQAMAT dan baris DETIK jam tidak terpotong.
        """
        return {
            "judul":         (not self.ringkas) and bool(self.config.get("tampilkan_judul", True)),
            "tanggal":       (not self.ringkas) and bool(self.config.get("tampilkan_tanggal", True)),
            "lokasi":        (not self.ringkas) and bool(self.config.get("tampilkan_lokasi", True)),
            "hitung_mundur": (not self.ringkas) and bool(self.config.get("tampilkan_hitung_mundur", True)),
            "footer":        (not self.ringkas) and bool(self.config.get("tampilkan_footer", True)),
        }

    def _unduh_bulan(self, kota_id: str, tahun: int, bulan: int) -> bool:
        """Unduh satu bulan penuh dari API lalu simpan ke SQLite."""
        try:
            data = self.api.get_jadwal_bulanan(kota_id, tahun, bulan)
            if data and data.get("jadwal"):
                cache.simpan_bulan(kota_id, data)
                return True
        except Exception as exc:
            self.pesan_error = str(exc)
        return False

    def _unduh_hari(self, kota_id: str, tanggal: date) -> bool:
        """Unduh satu hari (cadangan bila data bulanan belum memuat tanggal itu)."""
        try:
            data = self.api.get_jadwal_harian(kota_id, tanggal)
            if data and data.get("jadwal"):
                cache.simpan_bulan(kota_id, {
                    "lokasi": data.get("lokasi", ""),
                    "daerah": data.get("daerah", ""),
                    "jadwal": [data["jadwal"]],
                })
                return True
        except Exception as exc:
            self.pesan_error = str(exc)
        return False

    def fetch_jadwal(self, force: bool = False):
        """Ambil jadwal hari ini: pakai SQLite bila ada, unduh hanya bila perlu.

        Internet hanya dihubungi sekali per bulan (saat bulan berjalan belum
        lengkap tersimpan). Bila internet mati, jadwal tetap tampil dari SQLite.
        """
        today = date.today()
        if not force and self.jadwal_cache and self.last_fetch_date == today:
            return
        kota_id = str(self.config.get("lokasi_id", "1204"))
        iso = today.isoformat()
        self.pesan_error = ""
        diunduh = False

        # 1. unduh bulan berjalan hanya bila belum lengkap di SQLite
        if not cache.punya_bulan(kota_id, today.year, today.month):
            diunduh = self._unduh_bulan(kota_id, today.year, today.month) or diunduh

        lokal = cache.get_hari(kota_id, iso)

        # 2. tanggal belum ada (mis. awal bulan) -> coba unduh harian
        if lokal is None:
            diunduh = self._unduh_hari(kota_id, today) or diunduh
            lokal = cache.get_hari(kota_id, iso)

        # 3. siapkan bulan depan pada 5 hari terakhir bulan ini
        if today.day >= 25:
            nxt = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            if not cache.punya_bulan(kota_id, nxt.year, nxt.month):
                self._unduh_bulan(kota_id, nxt.year, nxt.month)

        if lokal:
            self.jadwal_cache = lokal
            self.last_fetch_date = today
            self.sumber_data = "internet" if diunduh else "cache"
            return

        # 4. internet gagal & tanggal belum tersimpan -> pakai data terakhir
        fallback = cache.get_terakhir(kota_id)
        if fallback:
            self.jadwal_cache = fallback
            self.last_fetch_date = today
            self.sumber_data = "offline"
            return

        self.sumber_data = "kosong"

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

    def prayer_iqamat_entries(self):
        """[(label, 'HH:MM' azan|None, 'HH:MM' iqamat|None), ...] untuk 5 waktu salat."""
        jadwal = (self.jadwal_cache or {}).get("jadwal") or {}
        out = []
        for label, key in PRAYER_ORDER:
            jk = IQAMAT_KEYS.get(key)
            azan = jadwal.get(key) or None
            delay = self.config.get(jk) if jk else None
            iq = hitung_waktu_iqamat(azan, delay) if (azan and delay is not None) else None
            out.append((label, azan, iq))
        return out

    def next_prayer_index(self, now_dt: datetime) -> int:
        """Indeks kartu waktu salat berikutnya (untuk hitung mundur), -1 bila tidak ada."""
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

    def prayer_aktif_index(self, now_dt: datetime) -> int:
        """Indeks waktu salat yang SEDANG BERJALAN — azannya sudah masuk, waktu berikutnya belum.

        Ini yang disorot kuning (permintaan Isa, 12 Okt 2026): kalau sekarang waktu Ashar, maka
        ASHAR dan IQAMAT-nya yang kuning — bukan Maghrib. Maghrib baru kuning setelah azan
        Maghrib masuk. Sebelum Subuh tidak ada yang kuning: belum ada waktu yang masuk hari ini.
        """
        jadwal = (self.jadwal_cache or {}).get("jadwal") or {}
        today = now_dt.date()
        aktif = -1
        for i, (_, key) in enumerate(PRAYER_ORDER):
            val = jadwal.get(key)
            if not val:
                continue
            hh, mm = map(int, val.split(":"))
            if datetime(today.year, today.month, today.day, hh, mm, 0) <= now_dt:
                aktif = i                     # terus maju: yang terakhir terlewati = yang berjalan
            else:
                break
        return aktif

    def build_frame(self) -> str:
        uk = self.ukuran_terminal()
        cols, rows = uk.columns, uk.lines
        saklar = self._saklar()
        now = sekarang()                 # DASDOR_JAM=<HH:MM> bisa memaksa jam untuk uji
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

        # ---- Countdown ----
        next_prayer, remaining = self.get_upcoming_prayer(now)
        if next_prayer and remaining:
            t = int(remaining.total_seconds())
            cd_short = f"{t // 3600:02d} Jam {(t % 3600) // 60:02d} Menit {t % 60:02d} Detik"
            cd_text = f"⏳ Menuju Waktu {next_prayer}: {cd_short}"
        else:
            cd_short = ""
            cd_text = "Memuat data jadwal salat..."

        # Judul: kapital + spasi antar huruf agar tampak lebih besar (bila muat)
        judul_txt = judul.upper()
        judul_lebar = "  ".join(judul_txt.split())        # jarak antar kata dilebarkan
        judul_lebar = " ".join(judul_lebar)
        if visible_width(judul_lebar) <= cols - 2:
            judul_txt = judul_lebar
        judul_line = center_line(f"{COLOR_TITLE}{judul_txt}{RESET}", cols)

        # Header: judul, lokasi, tanggal, lalu hitung mundur (menyusut bila sempit)
        lokasi_line = center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols)
        tanggal_line = center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols)
        cd_line = center_line(f"{COLOR_COUNTDOWN}{BOLD}{cd_text}{RESET}", cols)
        baris_header = []
        if saklar["judul"]:
            baris_header.append(judul_line)
        if saklar["lokasi"]:
            baris_header.append(lokasi_line)
        if saklar["tanggal"]:
            baris_header.append(tanggal_line)
        if saklar["hitung_mundur"]:
            baris_header.append(cd_line)
        # menyusut dari belakang: hitung mundur -> tanggal -> lokasi (judul selalu tampil)
        header_candidates = [baris_header + [""]]
        for n in range(len(baris_header), 0, -1):
            header_candidates.append(baris_header[:n])
        header_candidates.append([])
        out: List[str] = []
        chosen = None
        footer_gap = 1
        # Padding dari config.json (minimum); kurangi hanya bila grid tidak muat.
        pad_top_max = max(0, int(self.config.get("padding_atas", TOP_PAD)))
        pad_bot_max = max(0, int(self.config.get("padding_bawah", BOTTOM_PAD)))
        pad_steps, seen = [], set()
        for p in range(max(pad_top_max, pad_bot_max), -1, -1):
            pair = (min(p, pad_top_max), min(p, pad_bot_max))
            if pair not in seen:
                seen.add(pair); pad_steps.append(pair)
        top_pad, bottom_pad = pad_steps[0]
        footer_pilihan = (2, 1) if saklar["footer"] else (1, 0)
        # Dua lintasan: utamakan grid PENUH (baris label IQAMAT tampil + baris
        # DETIK utuh), baru kemudian varian ringkas. Di dalam setiap lintasan,
        # padding terbesar yang muat tetap dipilih lebih dulu.
        for wajib_penuh in (True, False):
            for tp, bp in pad_steps:
                for fh in footer_pilihan:  # 2 = baris kosong + footer, 1 = footer saja
                    for hdr in header_candidates:
                        cand = choose_grid(cols, rows, len(hdr) + tp, fh + bp)
                        if not cand:
                            continue
                        if wajib_penuh and cand[3] != ROW_LINES_FULL:
                            continue
                        chosen = cand
                        out.extend(hdr)
                        footer_gap = fh - 1
                        top_pad, bottom_pad = tp, bp
                        break
                    if chosen:
                        break
                if chosen:
                    break
            if chosen:
                break
        if chosen:
            grid_bw, inner_w, grid_pad, row_lines = chosen
            # Detik sudah tampil di bawah `mm`, jadi kolon dibuat STATIS.
            # Setel "kolon_berkedip": true di config.json bila ingin berkedip lagi.
            if self.config.get("kolon_berkedip", False):
                colon_on = (now.second % 2 == 0)
            else:
                colon_on = True
            cells = build_cells(now, self.prayer_iqamat_entries(), grid_bw,
                                colon_on, row_lines,
                                highlight=self.prayer_aktif_index(now))
            # render_grid menghasilkan baris rata-kiri; di sini ditengahkan
            # agar sisa lebar terbagi rata (tampilan simetris di layar lebar).
            for garis in render_grid(cells, cols, inner_w, grid_pad, row_lines):
                sisa = max(0, cols - visible_width(garis))
                out.append(" " * (sisa // 2) + garis)
        else:                                       # terminal sangat sempit
            out.extend(build_prayer_compact(self.prayer_iqamat_entries(), cols,
                                            highlight=self.prayer_aktif_index(now)))
            out.append(center_line(f"{COLOR_COUNTDOWN}{BOLD}{cd_text}{RESET}", cols))
        if footer_gap:
            out.append("")

        # ---- Footer (sebutkan sumber & status penyimpanan) ----
        if not saklar["footer"]:
            body = len(out)
            top_pad, bottom_pad = TOP_PAD, BOTTOM_PAD
            extra = max(0, rows - body - top_pad - bottom_pad)
            if self.config.get("padding_ratakan", True):
                top_extra = extra // 2
                bot_extra = extra - top_extra
            else:
                top_extra = bot_extra = 0
            return ("\n" * (top_pad + top_extra) + "\n".join(out)
                    + "\n" * (bottom_pad + bot_extra))

        status = {
            "internet": "diperbarui dari internet",
            "cache": "dari penyimpanan lokal (SQLite)",
            "offline": "offline — pakai data tersimpan",
            "kosong": "belum ada data",
        }.get(self.sumber_data, "")
        # Petunjuk keluar menyesuaikan saklar "keluar_dengan_q_esc" — jangan
        # menyuruh menekan tombol yang sudah dimatikan.
        if self.config.get("keluar_dengan_q_esc", True):
            petunjuk, petunjuk_pendek = ("Tekan [q] atau [Ctrl+C] untuk keluar",
                                         "Tekan [q] untuk keluar")
        else:
            petunjuk = petunjuk_pendek = "Tekan [Ctrl+C] untuk keluar"
        footer = f"{petunjuk}  •  Sumber Data: Bimas Islam Kemenag RI"
        if status:
            footer += f"  •  {status}"
        if visible_width(footer) > cols - 2:
            footer = f"{petunjuk_pendek}  •  Bimas Islam Kemenag RI"
            if status:
                footer += f"  •  {status}"
        if visible_width(footer) > cols - 2:
            footer = petunjuk_pendek
        out.append(center_line(f"{DIM}{footer}{RESET}", cols))

        # padding atas/bawah; sisa ruang dibagi rata (mode daftar ringkas)
        body = len(out)
        if body + top_pad + bottom_pad > rows:              # jaga agar tidak melampaui
            slack = max(0, rows - body)
            top_pad = min(top_pad, slack // 2)
            bottom_pad = min(bottom_pad, slack - top_pad)
        extra = max(0, rows - body - top_pad - bottom_pad)
        if self.config.get("padding_ratakan", True):
            top_extra = extra // 2
            bot_extra = extra - top_extra
        else:
            top_extra = bot_extra = 0          # tepat sesuai setelan, sisa di bawah
        return ("\n" * (top_pad + top_extra) + "\n".join(out)
                + "\n" * (bottom_pad + bot_extra))

    def run(self):
        self.setup_terminal()
        # Tombol keluar. Bawaannya: q / Q / Esc / Ctrl+C.
        # Bila config "keluar_dengan_q_esc": false, HANYA Ctrl+C yang menutup —
        # supaya tampilan di layar masjid tidak mati karena satu sentuhan tombol.
        if self.config.get("keluar_dengan_q_esc", True):
            tombol_keluar = ("q", "Q", "\x1b", "\x03")
        else:
            tombol_keluar = ("\x03",)
        try:
            self.fetch_jadwal(force=True)
            while self.running:
                if self.last_fetch_date != date.today():
                    self.fetch_jadwal(force=True)
                sys.stdout.write("\033[H\033[J" + self.build_frame())
                sys.stdout.flush()
                if sys.stdin.isatty():
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r and sys.stdin.read(1) in tombol_keluar:
                        self.running = False
                else:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.restore_terminal()


if __name__ == "__main__":
    TerminalDashboard().run()
