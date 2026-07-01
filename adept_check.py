#!/usr/bin/env python3
"""
Pengecek sekali-jalan (one-shot) untuk form pendaftaran ADEPT Online.
Dirancang untuk dijalankan berkala oleh GitHub Actions (cron).
Mengirim notifikasi ke Telegram begitu ada form yang BUKA atau tanggalnya berubah.

Butuh environment variables:
  TELEGRAM_BOT_TOKEN  - token bot dari @BotFather
  TELEGRAM_CHAT_ID    - chat id tujuan (ID numerik akun Telegram-mu)
"""

import os
import re
import json
import requests

STATE_FILE = "adept_state.json"

FORMS = {
    "Selasa": "https://s.id/daftaradeptselasa",
    "Rabu":   "https://s.id/daftaradeptrabu",
    "Jumat":  "https://s.id/daftaradeptjumat",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def check_form(url):
    """Kembalikan (is_open, title) untuk sebuah URL form."""
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=30)
    final_url = r.url.lower()
    html = r.text
    # TUTUP/PENUH bila diarahkan ke 'closedform' atau ada teks "sudah penuh".
    is_closed = final_url.endswith("closedform") or ("sudah penuh" in html.lower())
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    title = m.group(1).strip() if m else "(judul tidak ditemukan)"
    return (not is_closed, title)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("! TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        }, timeout=30)
    except Exception as e:
        print("! Gagal kirim Telegram:", e)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    state = load_state()
    for hari, url in FORMS.items():
        try:
            is_open, title = check_form(url)
        except Exception as e:
            print(f"{hari}: ERROR - {e}")
            continue

        prev = state.get(hari, {})
        prev_seen = "is_open" in prev
        prev_open = prev.get("is_open")
        prev_title = prev.get("title")

        print(f"{hari}: {'BUKA' if is_open else 'penuh/tutup'} | {title}")

        newly_open = is_open and not prev_open        # tutup -> buka
        new_date = is_open and (title != prev_title)  # tanggal berubah saat buka

        # Hindari alarm palsu di run pertama (belum ada data sebelumnya).
        if prev_seen and (newly_open or new_date):
            send_telegram(
                f"\U0001F389 ADEPT {hari} BUKA!\n\n{title}\n\nDaftar sekarang: {url}"
            )
            print(f"  -> NOTIF TELEGRAM terkirim ({hari})")

        state[hari] = {"is_open": is_open, "title": title}

    save_state(state)


if __name__ == "__main__":
    main()
