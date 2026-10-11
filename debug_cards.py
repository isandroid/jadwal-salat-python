#!/usr/bin/env python3
"""Debug card rendering."""
from dashboard import TerminalDashboard
from datetime import datetime, date, timedelta

d = TerminalDashboard()
d.fetch_jadwal(force=True)

cols, rows = 140, 36
now = datetime.now()
today = now.date()

jadwal = d.jadwal_cache.get('jadwal', {}) if d.jadwal_cache else {}
print('jadwal keys:', list(jadwal.keys()))

urutan_keys = [
    ('IMSAK', 'imsak'), ('SUBUH', 'subuh'), ('TERBIT', 'terbit'), ('DHUHA', 'dhuha'),
    ('DZUHUR', 'dzuhur'), ('ASHAR', 'ashar'), ('MAGHRIB', 'maghrib'), ("ISYA'", 'isya')
]

visible = [k for k in urutan_keys if k[1] not in d.HIDDEN_KEYS]
print('visible:', visible)

next_prayer, remaining = d.get_upcoming_prayer(now)
print('next_prayer:', next_prayer)

half = (len(visible) + 1) // 2
top_keys = visible[:half]
bot_keys = visible[half:]

print('top_keys:', top_keys)
print('bot_keys:', bot_keys)

CARD_W = 34
CARD_GAP = '  '

def chunk_total_w(count):
    return count * CARD_W + (count - 1) * len(CARD_GAP)

print(f'chunk_total_w(3) = {chunk_total_w(3)}')
print(f'chunk_total_w(2) = {chunk_total_w(2)}')

# Now test the actual render_cards_chunk by calling the method directly
# The render_cards_chunk is a local function inside build_frame, so we can't call it directly
# Let's just check if build_frame returns the cards

frame = d.build_frame()
idx = frame.find('┏')
if idx >= 0:
    print('FOUND card border at index', idx)
    print(frame[idx:idx+500])
else:
    print('NO card border found in frame')
    print('Frame length:', len(frame))
    # Search for any box drawing chars
    for ch in ['┏', '╭', '┃', '│', '┗', '╰']:
        pos = frame.find(ch)
        if pos >= 0:
            print(f'  Found {ch} at {pos}')
        else:
            print(f'  {ch} NOT FOUND')