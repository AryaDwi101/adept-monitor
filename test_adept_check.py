#!/usr/bin/env python3
"""
Harness test lokal untuk adept_check.py.
MEMALSUKAN transisi state (tanpa menyentuh network/form asli) untuk
membuktikan logika trigger notifikasi benar, sebelum form asli benar-benar berubah.

Skenario yang diuji:
  1. Run pertama (belum ada state) -> TIDAK boleh kirim notif, walau form "buka".
  2. Transisi tutup -> buka (dengan tanggal baru) -> HARUS kirim notif.
  3. Sudah buka, tanggal berubah lagi -> HARUS kirim notif.
  4. Sudah buka, tanggal sama -> TIDAK boleh kirim notif (no-op run).
"""

import json
import os
import tempfile
from unittest import mock

import adept_check


def run_case(name, fake_state, fake_results, expect_notif_for):
    """
    fake_state: dict lama untuk ditulis ke STATE_FILE sebelum run (atau None = tidak ada file sama sekali)
    fake_results: dict {hari: (is_open, title)} yang akan dikembalikan check_form()
    expect_notif_for: set hari yang SEHARUSNYA memicu notif Telegram
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "adept_state.json")

        if fake_state is not None:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(fake_state, f)

        sent = []

        def fake_check_form(url):
            for hari, u in adept_check.FORMS.items():
                if u == url:
                    return fake_results[hari]
            raise AssertionError(f"URL tak dikenal: {url}")

        def fake_send_telegram(text):
            sent.append(text)

        with mock.patch.object(adept_check, "STATE_FILE", state_path), \
             mock.patch.object(adept_check, "check_form", side_effect=fake_check_form), \
             mock.patch.object(adept_check, "send_telegram", side_effect=fake_send_telegram):
            adept_check.main()

        notified_hari = set()
        for text in sent:
            for hari in adept_check.FORMS:
                if f"ADEPT {hari} BUKA" in text:
                    notified_hari.add(hari)

        ok = notified_hari == expect_notif_for
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        print(f"    expect notif: {expect_notif_for or '(tidak ada)'}")
        print(f"    actual notif: {notified_hari or '(tidak ada)'}")
        if sent:
            for t in sent:
                print(f"    -> pesan: {t.splitlines()[0]}")

        with open(state_path, encoding="utf-8") as f:
            new_state = json.load(f)
        return ok, new_state


def main():
    results = []

    # --- Kasus 1: run pertama, belum ada state sama sekali, form BUKA ---
    # Tidak boleh notif walau is_open=True karena belum ada baseline sebelumnya.
    ok, state1 = run_case(
        "Run pertama (tanpa state) - form BUKA - TIDAK boleh notif",
        fake_state=None,
        fake_results={
            "Selasa": (True, "Pendaftaran Tes ADEPT Online (Selasa, 14 Juli 2026)"),
            "Rabu": (True, "Pendaftaran Tes ADEPT Online (Rabu, 15 Juli 2026)"),
            "Jumat": (True, "Pendaftaran Tes ADEPT Online (Jumat, 17 Juli 2026)"),
        },
        expect_notif_for=set(),
    )
    results.append(ok)

    # --- Kasus 2: state lama semua "penuh" (7-10 Juli), lalu slot baru (14-17 Juli) dibuka ---
    old_state = {
        "Selasa": {"is_open": False, "title": "Pendaftaran Tes ADEPT Online (Selasa, 7 Juli 2026)"},
        "Rabu": {"is_open": False, "title": "Pendaftaran Tes ADEPT Online (Rabu, 8 Juli 2026 )"},
        "Jumat": {"is_open": False, "title": "Pendaftaran Tes ADEPT Online (Jum&#39;at, 10 Juli 2026)"},
    }
    ok, state2 = run_case(
        "Transisi tutup->buka dengan tanggal baru - HARUS notif utk semua hari",
        fake_state=old_state,
        fake_results={
            "Selasa": (True, "Pendaftaran Tes ADEPT Online (Selasa, 14 Juli 2026)"),
            "Rabu": (True, "Pendaftaran Tes ADEPT Online (Rabu, 15 Juli 2026)"),
            "Jumat": (True, "Pendaftaran Tes ADEPT Online (Jum&#39;at, 17 Juli 2026)"),
        },
        expect_notif_for={"Selasa", "Rabu", "Jumat"},
    )
    results.append(ok)

    # --- Kasus 3: sudah buka (14 Juli), lalu tanggal berubah lagi (mis. jadi 21 Juli) tanpa pernah tutup ---
    ok, state3 = run_case(
        "Sudah buka, tanggal berubah lagi - HARUS notif",
        fake_state={
            "Selasa": {"is_open": True, "title": "Pendaftaran Tes ADEPT Online (Selasa, 14 Juli 2026)"},
        },
        fake_results={
            "Selasa": (True, "Pendaftaran Tes ADEPT Online (Selasa, 21 Juli 2026)"),
            "Rabu": (False, "x"),
            "Jumat": (False, "x"),
        },
        expect_notif_for={"Selasa"},
    )
    results.append(ok)

    # --- Kasus 4: tidak ada perubahan sama sekali - TIDAK boleh notif ---
    same_state = {
        "Selasa": {"is_open": True, "title": "Pendaftaran Tes ADEPT Online (Selasa, 14 Juli 2026)"},
        "Rabu": {"is_open": False, "title": "tutup"},
        "Jumat": {"is_open": False, "title": "tutup"},
    }
    ok, state4 = run_case(
        "Tidak ada perubahan - TIDAK boleh notif",
        fake_state=same_state,
        fake_results={
            "Selasa": (True, "Pendaftaran Tes ADEPT Online (Selasa, 14 Juli 2026)"),
            "Rabu": (False, "tutup"),
            "Jumat": (False, "tutup"),
        },
        expect_notif_for=set(),
    )
    results.append(ok)

    print()
    if all(results):
        print(f"SEMUA {len(results)} KASUS UJI LULUS.")
    else:
        print(f"ADA KASUS GAGAL: {results.count(False)} dari {len(results)}.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
