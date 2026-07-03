#!/usr/bin/env python3
"""
Pengecek sekali-jalan (one-shot) untuk form pendaftaran ADEPT Online.
Dirancang untuk dijalankan berkala oleh GitHub Actions (cron).
Mengirim notifikasi ke Telegram begitu ada form yang BUKA atau tanggalnya berubah.
Juga mengirim ringkasan status harian (semua form, buka atau tutup) agar
selalu ada bukti bot masih berjalan.

Butuh environment variables:
  TELEGRAM_BOT_TOKEN  - token bot dari @BotFather
  TELEGRAM_CHAT_ID    - chat id tujuan (ID numerik akun Telegram-mu)
  IS_DAILY_DIGEST     - "true" untuk memicu ringkasan harian (diset oleh workflow)
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
IS_DAILY_DIGEST = os.environ.get("IS_DAILY_DIGEST", "false").lower() == "true"


def check_form(url):
    """Kembalikan (is_open, title) untuk sebuah URL form."""
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=30)
    final_url = r.url.lower()
    html = r.text
    # TUTUP/PENUH bila diarahkan ke 'closedform' atau ada teks "sudah penuh".
    is_closed = final_url.endswith("closedform") or ("sudah penuh" in html.lower())
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if not m:
        # Form yang valid (baik buka maupun tutup) selalu punya og:title.
        # Kalau tidak ketemu, halaman yang kefetch bukan form asli (glitch/error
        # sesaat di sisi Google) - jangan percaya is_open, anggap gagal saja.
        raise ValueError(f"og:title tidak ditemukan (final_url={r.url})")
    title = m.group(1).strip()
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


def build_digest(results):
    lines = ["\U0001F4CB Ringkasan Harian ADEPT (bot masih berjalan ✅)", ""]
    for hari, url, is_open, title in results:
        status = "\U0001F7E2 BUKA" if is_open else "\U0001F534 sudah penuh/tutup"
        lines.append(f"{hari}: {status}\n{title}\nCek: {url}\n")
    return "\n".join(lines).rstrip()


def main():
    state = load_state()
    results = []  # (hari, url, is_open, title) - dipakai utk ringkasan harian

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
        results.append((hari, url, is_open, title))

    save_state(state)

    if IS_DAILY_DIGEST and results:
        send_telegram(build_digest(results))
        print("  -> RINGKASAN HARIAN terkirim")


if __name__ == "__main__":
    main()
