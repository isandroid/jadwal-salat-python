#!/usr/bin/env python3
"""
Dasbor Terminal Jadwal Salat & Jam Digital Masjid
Dioptimalkan untuk resolusi layar 1366x768 (atau terminal modern).
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
# FONT DIGITAL 5-BARIS BESAR (HH:MM:SS)
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

    def render_clock_lines(self, time_str: str) -> List[str]:
        """Merender jam digital 5 baris."""
        lines = ['', '', '', '', '']
        for ch in time_str:
            glyph = DIGITS_5.get(ch, DIGITS_5[' '])
            for i in range(5):
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

        # 1. HEADER (Tanpa border)
        output.append(center_line(f"{COLOR_TITLE}{BOLD}{judul.upper()}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{lokasi_str}{RESET}", cols))
        output.append(center_line(f"{COLOR_SUBTITLE}{tanggal_str}{RESET}", cols))
        output.append("")

        # Baris pemisah di antara tanggal dan jam digital
        div_w = min(cols - 8, 104)
        div_pad = " " * max(0, (cols - div_w) // 2)
        output.append(f"{div_pad}{COLOR_BORDER}{'─' * div_w}{RESET}")
        output.append("")

        # 2. JAM DIGITAL BESAR (5 BARIS)
        time_str = now.strftime("%H:%M:%S")
        clock_lines = self.render_clock_lines(time_str)
        clock_w = len(clock_lines[0])
        clock_pad = " " * ((cols - clock_w) // 2)

        for line in clock_lines:
            output.append(f"{clock_pad}{COLOR_CLOCK}{BOLD}{line}{RESET}")
        
        output.append("")
        wib_label = "— WAKTU INDONESIA BARAT (WIB) —"
        output.append(f"{' ' * ((cols - len(wib_label)) // 2)}{COLOR_CLOCK_SEC}{wib_label}{RESET}")
        output.append("")

        # 3. COUNTDOWN MENUJU SALAT BERIKUTNYA
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

        # 4. KARTU JADWAL SALAT
        urutan_keys = [
            ("IMSAK", "imsak"),
            ("SUBUH", "subuh"),
            ("TERBIT", "terbit"),
            ("DHUHA", "dhuha"),
            ("DZUHUR", "dzuhur"),
            ("ASHAR", "ashar"),
            ("MAGHRIB", "maghrib"),
            ("ISYA'", "isya")
        ]

        jadwal = self.jadwal_cache.get("jadwal", {}) if self.jadwal_cache else {}

        # Kartu yang di-HIDE (Subuh, Terbit, Dhuha) - tampilkan sebagai ruang kosong
        # (nilai tersimpan di self.HIDDEN_KEYS)
        #
        # Ukuran kartu diperbesar (34 kolom) supaya waktu salat mudah dilihat
        # dari kejauhan. Komposisi dibagi 3 kartu atas + 2 kartu bawah (keduanya
        # di tengah-tengah), dan lebar total dihitung dari kartu yang benar-benar
        # merender (bukan dari urutan_keys lengkap 8).

        CARD_W = 34
        CARD_GAP = "  "

        def chunk_total_w(count):
            return count * CARD_W + (count - 1) * len(CARD_GAP)

        def can_fit_single_row(count):
            return cols >= chunk_total_w(count) + 20

        def render_cards_chunk(keys):
            card_lines = ['', '', '', '', '', '', '']
            rendered = 0
            for label, key in keys:
                # Kartu tersembunyi: biarkan baris kosong, tidak dihitung
                if key in self.HIDDEN_KEYS:
                    continue
                rendered += 1
                waktu_val = jadwal.get(key, "--:--")
                is_active = (label == next_prayer)

                # Hitung waktu iqamat jika termasuk 5 waktu salat fardhu
                iqamat_cfg_key = IQAMAT_KEYS.get(key)
                if iqamat_cfg_key and iqamat_cfg_key in self.config:
                    jeda = self.config.get(iqamat_cfg_key, 15)
                    iqamat_lbl = "IQAMAT"
                    iqamat_val = hitung_waktu_iqamat(waktu_val, jeda)
                else:
                    iqamat_lbl = " "
                    iqamat_val = " "

                # Cek apakah waktu azan sudah lewat
                is_past = False
                if waktu_val != "--:--":
                    try:
                        j_h, j_m = map(int, waktu_val.split(":"))
                        j_dt = datetime(today.year, today.month, today.day, j_h, j_m)
                        if now > j_dt and not is_active:
                            is_past = True
                    except Exception:
                        pass

                if is_active:
                    border_c = COLOR_ACTIVE_CARD
                    text_c = COLOR_ACTIVE_CARD + BOLD
                    iqamat_lbl_c = COLOR_ACTIVE_CARD
                    iqamat_val_c = COLOR_ACTIVE_CARD + BOLD
                    top = f"{border_c}┏{'━' * (CARD_W - 2)}┓{RESET}"
                    l1 = f"{border_c}┃{text_c}{label.center(CARD_W - 2)}{border_c}┃{RESET}"
                    l2 = f"{border_c}┃{text_c}{waktu_val.center(CARD_W - 2)}{border_c}┃{RESET}"
                    l3 = f"{border_c}┃{' '.center(CARD_W - 2)}{border_c}┃{RESET}"
                    l4 = f"{border_c}┃{iqamat_lbl_c}{iqamat_lbl.center(CARD_W - 2)}{border_c}┃{RESET}"
                    l5 = f"{border_c}┃{iqamat_val_c}{iqamat_val.center(CARD_W - 2)}{border_c}┃{RESET}"
                    bot = f"{border_c}┗{'━' * (CARD_W - 2)}┛{RESET}"
                elif is_past:
                    border_c = COLOR_BORDER_DIM
                    text_c = COLOR_PASSED_CARD
                    iqamat_lbl_c = COLOR_BORDER_DIM
                    iqamat_val_c = COLOR_PASSED_CARD
                    top = f"{border_c}╭{'─' * (CARD_W - 2)}╮{RESET}"
                    l1 = f"{border_c}│{text_c}{label.center(CARD_W - 2)}{border_c}│{RESET}"
                    l2 = f"{border_c}│{text_c}{waktu_val.center(CARD_W - 2)}{border_c}│{RESET}"
                    l3 = f"{border_c}│{' '.center(CARD_W - 2)}{border_c}│{RESET}"
                    l4 = f"{border_c}│{iqamat_lbl_c}{iqamat_lbl.center(CARD_W - 2)}{border_c}│{RESET}"
                    l5 = f"{border_c}│{iqamat_val_c}{iqamat_val.center(CARD_W - 2)}{border_c}│{RESET}"
                    bot = f"{border_c}╰{'─' * (CARD_W - 2)}╯{RESET}"
                else:
                    border_c = COLOR_BORDER
                    text_c = COLOR_NORMAL_CARD
                    iqamat_lbl_c = COLOR_IQAMAT_LABEL
                    iqamat_val_c = COLOR_IQAMAT_TIME
                    top = f"{border_c}╭{'─' * (CARD_W - 2)}╮{RESET}"
                    l1 = f"{border_c}│{text_c}{BOLD}{label.center(CARD_W - 2)}{border_c}│{RESET}"
                    l2 = f"{border_c}│{text_c}{waktu_val.center(CARD_W - 2)}{border_c}│{RESET}"
                    l3 = f"{border_c}│{' '.center(CARD_W - 2)}{border_c}│{RESET}"
                    l4 = f"{border_c}│{iqamat_lbl_c}{iqamat_lbl.center(CARD_W - 2)}{border_c}│{RESET}"
                    l5 = f"{border_c}│{iqamat_val_c}{iqamat_val.center(CARD_W - 2)}{border_c}│{RESET}"
                    bot = f"{border_c}╰{'─' * (CARD_W - 2)}╯{RESET}"

                gap = CARD_GAP
                card_lines[0] += top + gap
                card_lines[1] += l1 + gap
                card_lines[2] += l2 + gap
                card_lines[3] += l3 + gap
                card_lines[4] += l4 + gap
                card_lines[5] += l5 + gap
                card_lines[6] += bot + gap

            # Lebar total hanya menghitung kartu yang benar-benar di-render
            total_w = chunk_total_w(rendered)
            cards_pad = " " * ((cols - total_w) // 2)

            res_lines = []
            for cl in card_lines:
                res_lines.append(f"{cards_pad}{cl}")
            return res_lines, total_w

        visible = [k for k in urutan_keys if k[1] not in self.HIDDEN_KEYS]

        if can_fit_single_row(len(visible)):
            # Single row: all 5 cards side by side
            output.extend(render_cards_chunk(urutan_keys)[0])
        else:
            # 2 baris: 3 kartu atas, 2 kartu bawah (masing-masing di tengah)
            half = (len(visible) + 1) // 2
            top_keys = visible[:half]
            bot_keys = visible[half:]

            if top_keys:
                output.extend(render_cards_chunk(top_keys)[0])
            if bot_keys:
                output.append("")
                output.extend(render_cards_chunk(bot_keys)[0])

        output.append("")

        # 5. FOOTER INFORMASI
        footer_info = "Tekan [q] atau [Ctrl+C] untuk keluar  \u2022  Sumber Data: Bimas Islam Kemenag RI"
        footer_pad = " " * ((cols - len(footer_info)) // 2)
        output.append(f"{footer_pad}{DIM}{footer_info}{RESET}")

        # Tambahkan padding atas jika terminal cukup tinggi (misal pada 1366x768)
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
