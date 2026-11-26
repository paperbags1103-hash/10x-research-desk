#!/usr/bin/env python3
"""Keep data/ledger.json in step with the markdown ledger (research/investment-desk/ledger.md).

The markdown ledger is where the desk writes every idea; this site renders the
JSON. Two modes:

    python3 tools/sync_ledger.py            # report drift (md ↔ json). Exit 1 if drifted.
    python3 tools/sync_ledger.py --write    # regenerate data/ledger.json from ledger.md
                                            # (keeps existing per-item "memo" notes by id)

The markdown table must keep the 8-column shape:
    ID | 제시일 | 자산/티커 | 구분 | 진입 기준가 | 핵심 가설 | 무효화(손절) 기준 | 상태
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT.parent / "investment-desk" / "ledger.md"
OUT = ROOT / "data" / "ledger.json"

STATUS_MAP = [
    ("탈락", "drop"),
    ("후보", "candidate"),
    ("대기", "wait"),
    ("보유", "active"),
    ("종료", "closed"),
]


def rows(md_path: Path) -> list[list[str]]:
    out = []
    if not md_path.exists():
        raise SystemExit(f"ledger.md 없음: {md_path}")
    for line in md_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 8:
            continue
        if cells[0].upper() in {"ID", "---"} or set(cells[0]) <= {"-", ":", " "}:
            continue
        out.append(cells)
    return out


def strip_md(s: str) -> str:
    return s.replace("**", "").replace("__", "").strip()


MONEY = re.compile(r"\s*[,·]?\s*\d[\d,]*\s*(?:만|억)\s*원")


def sanitize(s: str) -> str:
    """The site is public — account sizes and seed amounts never ship.
    The ledger is written for the desk (원 amounts included), so they are
    stripped here and only weights (%) reach the page."""
    s = MONEY.sub("", str(s))
    s = re.sub(r"\s*\(\s*\)", "", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def parse_asset(cell: str) -> tuple[str, str, str]:
    t = strip_md(cell)
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", t)
    lead, inner = (m.group(1).strip(), m.group(2).strip()) if m else (t, "")
    parts = [p.strip() for p in inner.split(",")]
    exchange = parts[-1] if parts and re.fullmatch(r"[A-Z]{2,6}", parts[-1] or "") else ""
    name_hint = parts[0] if len(parts) > 1 else ""

    m2 = re.match(r"^([A-Z0-9]{3,6})\s+(.+)$", lead)
    if m2:
        return m2.group(1), m2.group(2).strip(), exchange
    if re.fullmatch(r"[A-Z]{1,6}", lead):
        return lead, (name_hint or lead), exchange
    m3 = re.match(r"^(\d{6})\s+(.+)$", lead)
    if m3:
        return m3.group(1), m3.group(2).strip(), exchange
    return "", lead, exchange


def status_key(status: str) -> str:
    for word, key in STATUS_MAP:
        if word in status:
            return key
    return "watch"


def entry_price(cell: str) -> str:
    m = re.search(r"\$[\d,]+(?:\.\d+)?", cell)
    if m:
        return m.group(0)
    m = re.search(r"[\d,]+\s*원", cell)
    return m.group(0) if m else "—"


def build() -> dict:
    prev = {}
    if OUT.exists():
        try:
            for it in json.loads(OUT.read_text(encoding="utf-8")).get("items", []):
                prev[it.get("id")] = it
        except json.JSONDecodeError:
            pass

    items = []
    for c in rows(MD):
        ticker, name, exchange = parse_asset(c[2])
        item = {
            "id": strip_md(c[0]),
            "ticker": ticker,
            "exchange": exchange,
            "name": sanitize(name),
            "bucket": sanitize(c[3]),
            "entryPrice": sanitize(entry_price(c[4])),
            "entryPlan": sanitize(c[4]),
            "thesis": sanitize(c[5]),
            "invalidation": sanitize(c[6]),
            "status": sanitize(c[7]),
            "statusKey": status_key(c[7]),
        }
        memo = prev.get(item["id"], {}).get("memo")
        if memo:
            item["memo"] = memo
        items.append(item)

    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}

    return {
        "updatedLabel": items[0].get("date") or old.get("updatedLabel", ""),
        "items": items,
        "footnote": old.get("footnote", ""),
    }


def main() -> int:
    new = build()
    md_ids = [i["id"] for i in new["items"]]

    if "--write" in sys.argv:
        OUT.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✓ data/ledger.json 재생성 — {len(new['items'])} items ({', '.join(md_ids)})")
        return 0

    cur = {}
    if OUT.exists():
        try:
            cur = {i["id"]: i for i in json.loads(OUT.read_text(encoding="utf-8")).get("items", [])}
        except json.JSONDecodeError:
            print("✗ data/ledger.json 파싱 실패 — --write로 재생성할 것")
            return 1

    drift = []
    for i in new["items"]:
        j = cur.get(i["id"])
        if not j:
            drift.append(f"+ ledger.md에만 있음: {i['id']} {i['name']}")
            continue
        if j.get("statusKey") != i["statusKey"]:
            drift.append(f"~ {i['id']} 상태분류: json '{j.get('statusKey')}' ({j.get('status')}) ↔ md '{i['statusKey']}' ({i['status']})")
        if j.get("entryPrice") != i["entryPrice"]:
            drift.append(f"~ {i['id']} 진입가: json '{j.get('entryPrice')}' ↔ md '{i['entryPrice']}'")
    for k in cur:
        if k not in md_ids:
            drift.append(f"- data/ledger.json에만 있음: {k}")

    if drift:
        for d in drift:
            print(f"! {d}")
        print(f"\n{len(drift)}건 불일치 — `python3 tools/sync_ledger.py --write` 후 내용 보강.")
        return 1
    print(f"✓ ledger 동기화 OK — {len(md_ids)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
