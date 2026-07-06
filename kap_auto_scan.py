# -*- coding: utf-8 -*-

import json
import os
from datetime import date, datetime, timedelta

from kap_risk_app import (
    fetch_member_directory,
    resolve_default_members,
    scan_company,
    _load_prev_keys,
    _save_keys,
)

DATA_DIR = "data"
OUT_FILE = os.path.join(DATA_DIR, "latest_scan.json")


def finding_to_dict(f):
    return {
        "hisse": f.get("hisse"),
        "sirket": f.get("sirket"),
        "tarih": f.get("tarih_str"),
        "kategori": f.get("kategori"),
        "siddet": f.get("siddet"),
        "agirlik": f.get("agirlik"),
        "baslik": f.get("baslik"),
        "ozet": f.get("ozet"),
        "gerekce": f.get("gerekce"),
        "link": f.get("link"),
        "bildirim_no": f.get("bildirim_no"),
        "yeni": f.get("yeni", False),
    }


def result_to_dict(r):
    member = r.get("member", {})
    return {
        "hisse": member.get("hisse"),
        "sirket": member.get("unvan"),
        "skor": r.get("skor", 0),
        "not": r.get("not", "-"),
        "seviye": r.get("seviye", "-"),
        "emoji": r.get("emoji", ""),
        "renk": r.get("renk", ""),
        "taranan": r.get("taranan", 0),
        "veri_hatasi": r.get("veri_hatasi", 0),
        "findings": [finding_to_dict(f) for f in r.get("findings", [])],
        "improvements": [finding_to_dict(f) for f in r.get("improvements", [])],
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    today = date.today()
    start = today - timedelta(days=2)
    years = tuple(range(start.year, today.year + 1))
    date_range = (start, today)

    print("KAP otomatik tarama başlıyor...")
    print(f"Tarih aralığı: {start} - {today}")

    directory = fetch_member_directory()
    oids, unmatched = resolve_default_members(directory)
    members = directory[directory.oid.isin(oids)].to_dict("records")

    print(f"Taranacak default şirket sayısı: {len(members)}")

    results = []

    for i, m in enumerate(members, 1):
        print(f"[{i}/{len(members)}] {m['hisse']} - {m['unvan'][:60]}")
        try:
            r = scan_company(
                member=m,
                years=years,
                deep=True,
                date_range=date_range,
            )
            results.append(r)
        except Exception as exc:
            print(f"  HATA: {m.get('hisse')} taranamadı: {exc}")
            results.append({
                "member": m,
                "taranan": 0,
                "findings": [],
                "improvements": [],
                "skor": 0,
                "not": "-",
                "seviye": "HATA",
                "emoji": "⚠️",
                "renk": "#666",
                "veri_hatasi": 1,
                "hata": str(exc),
            })

    prev_keys = _load_prev_keys()
    cur_keys = set()

    for r in results:
        for f in r.get("findings", []):
            key = f"{f.get('hisse')}:{f.get('bildirim_no')}"
            cur_keys.add(key)
            f["yeni"] = bool(prev_keys) and key not in prev_keys

    _save_keys(prev_keys | cur_keys)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "date_start": str(start),
        "date_end": str(today),
        "company_count": len(results),
        "total_disclosures": sum(r.get("taranan", 0) for r in results),
        "total_findings": sum(len(r.get("findings", [])) for r in results),
        "new_findings": sum(
            1
            for r in results
            for f in r.get("findings", [])
            if f.get("yeni")
        ),
        "unmatched_groups": unmatched,
        "results": [result_to_dict(r) for r in results],
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Otomatik tarama tamamlandı: {OUT_FILE}")


if __name__ == "__main__":
    main()