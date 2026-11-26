#!/usr/bin/env python3
"""10X Research Desk — data self-check.

Run before every publish. It does three jobs:

  1. Schema/contract check   — every data/*.json parses and has the keys the
                               renderer (assets/app.js) expects.
  2. Privacy lint            — the site is a PUBLIC GitHub Pages page, so no
                               real name, phone, e-mail, account size or seed
                               amount may ever land in the data files. Weights
                               are %, performance is an index (Base 100).
  3. --stamp                 — bump data/meta.json updatedAt + dataVersion so
                               the header "last updated" is always honest.

Usage:
    python3 tools/selfcheck.py            # check only
    python3 tools/selfcheck.py --stamp    # check + stamp meta.json
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

KST = dt.timezone(dt.timedelta(hours=9))

REQUIRED = {
    "meta": ["title", "updatedAt", "dataVersion"],
    "briefing": ["headline", "lede", "stats", "index", "allocation"],
    "memos": ["memos"],
    "ledger": ["items"],
    "playbook": ["version", "rules"],
    "scorecard": ["criteria", "total", "history"],
}

STATUS_KEYS = {"active", "wait", "candidate", "watch", "drop", "closed"}
BLOCK_TYPES = {"section", "table", "kv", "list", "cards", "callout", "prose", "raw"}

# Patterns that must never appear in a public data file.
PRIVACY = [
    (re.compile(r"(?<![\dA-Za-z])01[016789][-.\s]\d{3,4}[-.\s]\d{4}(?!\d)"), "휴대폰 번호 형태"),
    (re.compile(r"(?<![\dA-Za-z])01[016789]\d{7,8}(?![\dA-Za-z])"), "휴대폰 번호 형태"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"), "이메일 주소"),
    (re.compile(r"심\s*규\s*범|치레아|\b규범\b"), "실명/호칭"),
    (re.compile(r"\d[\d,]*\s*만\s*원"), "원화 금액(계좌 규모 노출)"),
    (re.compile(r"\d[\d,]*\s*억\s*원(?!\s*(?:규모|이상|이하|대))"), "원화 금액(계좌 규모 노출)"),
    (re.compile(r"시드\s*(?:금액|자금)"), "시드 금액 표현"),
]

errors: list[str] = []
warnings: list[str] = []


def load(name: str):
    path = DATA / f"{name}.json"
    if not path.exists():
        errors.append(f"{name}.json 파일 없음")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{name}.json JSON 오류 — line {exc.lineno}: {exc.msg}")
        return None


def check_structure(store: dict) -> None:
    for name, keys in REQUIRED.items():
        obj = store.get(name)
        if obj is None:
            continue
        for k in keys:
            if k not in obj:
                errors.append(f"{name}.json: 필수 키 누락 '{k}'")

    b = store.get("briefing") or {}
    alloc = b.get("allocation") or {}
    for key, block in alloc.items():
        rows = block.get("rows") or []
        total = sum(r.get("weight", 0) for r in rows)
        if rows and total != 100:
            errors.append(f"briefing.allocation.{key} 비중 합계 {total}% (100%여야 함)")
        for r in rows:
            if not r.get("color"):
                warnings.append(f"briefing.allocation.{key}.{r.get('name')} 색상 미지정")
    idx = b.get("index") or {}
    if idx and not (idx.get("base") is not None and idx.get("target")):
        warnings.append("briefing.index: base/target 누락 — 기준지수 바가 비어 보인다")

    memos = (store.get("memos") or {}).get("memos") or []
    seen = set()
    for m in memos:
        mid = m.get("id")
        if not mid:
            errors.append("memos: id 없는 메모")
            continue
        if mid in seen:
            errors.append(f"memos: 중복 id {mid}")
        seen.add(mid)
        for k in ("ticker", "title", "lede", "blocks"):
            if k not in m:
                errors.append(f"memos[{mid}]: 필수 키 누락 '{k}'")
        if m.get("scenarios"):
            for s in m["scenarios"]:
                if not isinstance(s.get("multiple"), (int, float)):
                    errors.append(f"memos[{mid}].scenarios: multiple 숫자 아님 ({s.get('name')})")
        for blk in m.get("blocks", []):
            t = blk.get("type")
            if t not in BLOCK_TYPES:
                errors.append(f"memos[{mid}]: 알 수 없는 블록 타입 '{t}'")
            if t == "section":
                for inner in blk.get("blocks", []):
                    if inner.get("type") not in BLOCK_TYPES:
                        errors.append(f"memos[{mid}]: 알 수 없는 블록 타입 '{inner.get('type')}'")
                if "num" not in blk or "title" not in blk:
                    warnings.append(f"memos[{mid}]: 섹션 num/title 누락")

    ledger = (store.get("ledger") or {}).get("items") or []
    for it in ledger:
        if not it.get("id") or not it.get("name"):
            errors.append("ledger: id/name 누락 항목")
        if it.get("statusKey") not in STATUS_KEYS:
            errors.append(f"ledger[{it.get('id')}]: statusKey '{it.get('statusKey')}' — {sorted(STATUS_KEYS)} 중 하나여야 함")
        for k in ("entryPrice", "thesis", "invalidation"):
            if not it.get(k):
                warnings.append(f"ledger[{it.get('id')}]: '{k}' 비어 있음")

    sc = store.get("scorecard") or {}
    crit = sc.get("criteria") or []
    if crit:
        s = sum(c.get("score", 0) for c in crit)
        if sc.get("total") != s:
            errors.append(f"scorecard: total {sc.get('total')} ≠ 항목 합계 {s}")


def lint_privacy(store: dict) -> None:
    for name in store:
        path = DATA / f"{name}.json"
        text = path.read_text(encoding="utf-8")
        for rx, label in PRIVACY:
            for m in rx.finditer(text):
                start = max(0, m.start() - 40)
                snippet = text[start:m.end() + 40].replace("\n", " ")
                errors.append(f"{name}.json: {label} 의심 — …{snippet}…")


def stamp() -> None:
    path = DATA / "meta.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    now = dt.datetime.now(KST)
    day = now.strftime("%Y.%m.%d")
    prev = str(meta.get("dataVersion", ""))
    letter = "a"
    if prev.startswith(day + "-"):
        tail = prev.split("-")[-1]
        if len(tail) == 1 and tail.isalpha() and tail < "z":
            letter = chr(ord(tail) + 1)
    meta["updatedAt"] = now.replace(microsecond=0).isoformat()
    meta["dataVersion"] = f"{day}-{letter}"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"· stamped meta.json → {meta['dataVersion']} ({meta['updatedAt']})")


def main() -> int:
    store = {}
    for name in REQUIRED:
        obj = load(name)
        if obj is not None:
            store[name] = obj

    if not errors:
        check_structure(store)
        lint_privacy(store)

    for w in warnings:
        print(f"! {w}")
    for e in errors:
        print(f"✗ {e}")

    if errors:
        print(f"\nFAIL — {len(errors)}개 오류. 수정 후 다시 실행할 것.")
        return 1

    memos = len(((store.get("memos") or {}).get("memos")) or [])
    ideas = len(((store.get("ledger") or {}).get("items")) or [])
    print(f"✓ data OK — memo {memos} · ledger {ideas} · 경고 {len(warnings)}")

    if "--stamp" in sys.argv:
        stamp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
