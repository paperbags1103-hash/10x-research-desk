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
    "frontier": ["reports"],
    "screener": ["updatedAt", "dataLabel", "universe", "topSummary", "verifiedCandidates", "usTop", "krTop", "tracked", "methodology"],
}

STATUS_KEYS = {"active", "wait", "candidate", "watch", "drop", "closed"}
BLOCK_TYPES = {"section", "table", "kv", "list", "cards", "callout", "prose", "raw"}

SCREENER_AXES = {"growth": 25, "quality": 22, "value": 18, "balance": 18, "trend": 17}
CANDIDATE_STATUS = {"verified", "complete", "hold", "reject"}
RESEARCH_KEYS = ("business", "moat", "growth", "capital", "bear", "invalidation")
BANDS = {"A", "B", "C"}

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

    reports = (store.get("frontier") or {}).get("reports") or []
    seen_reports = set()
    for r in reports:
        rid = r.get("id")
        if not rid:
            errors.append("frontier: id 없는 리포트")
            continue
        if rid in seen_reports:
            errors.append(f"frontier: 중복 id {rid}")
        seen_reports.add(rid)
        for k in ("domain", "title", "lede", "date", "blocks"):
            if not r.get(k):
                errors.append(f"frontier[{rid}]: 필수 키 누락 '{k}'")
        if not isinstance(r.get("stats"), list) or not r.get("stats"):
            warnings.append(f"frontier[{rid}]: stats 없음 — 상단 지표 스트립이 빈다")
        for g in r.get("grades") or []:
            if not isinstance(g.get("pct"), (int, float)):
                errors.append(f"frontier[{rid}].grades: pct 숫자 아님 ({g.get('label')})")
        for blk in r.get("blocks", []):
            t = blk.get("type")
            if t not in BLOCK_TYPES:
                errors.append(f"frontier[{rid}]: 알 수 없는 블록 타입 '{t}'")
            if t == "section":
                for inner in blk.get("blocks", []):
                    if inner.get("type") not in BLOCK_TYPES:
                        errors.append(f"frontier[{rid}]: 알 수 없는 블록 타입 '{inner.get('type')}'")
                if "num" not in blk or "title" not in blk:
                    warnings.append(f"frontier[{rid}]: 섹션 num/title 누락")
        for it in r.get("sources") or []:
            if not it.get("group") or not it.get("items"):
                errors.append(f"frontier[{rid}].sources: group/items 누락")

    check_screener(store.get("screener") or {})


def check_screener(scr: dict) -> None:
    """data/screener.json — 점수는 screener_latest.json에서 오고, 각 후보에는
    정성 기업 리서치(사업모델·해자·촉매·자본배분·반대논리·무효화선)가 붙는다."""
    if not scr:
        return

    uni = scr.get("universe") or {}
    for mk in ("us", "kr"):
        block = uni.get(mk) or {}
        for k in ("total", "passed", "enriched"):
            if block.get(k) is None:
                errors.append(f"screener.universe.{mk}.{k} 누락")

    for listname in ("usTop", "krTop"):
        rows = scr.get(listname) or []
        if len(rows) < 5:
            errors.append(f"screener.{listname}: {len(rows)}개 — 최소 5개 필요")
        for r in rows:
            tag = r.get("ticker") or "?"
            if not r.get("name"):
                errors.append(f"screener.{listname}[{tag}]: name 누락")
            if r.get("band") not in BANDS:
                errors.append(f"screener.{listname}[{tag}]: band '{r.get('band')}' — A/B/C 중 하나여야 함")
            total = r.get("total")
            if not isinstance(total, (int, float)) or not (0 <= total <= 100):
                errors.append(f"screener.{listname}[{tag}]: total 숫자 아님/범위 밖 ({total})")
            axes = r.get("axes") or {}
            for key, mx in SCREENER_AXES.items():
                v = axes.get(key)
                if v is None:
                    continue
                if not isinstance(v, (int, float)) or v < 0 or v > mx + 0.01:
                    errors.append(f"screener.{listname}[{tag}].axes.{key}: {v} (0~{mx})")

    cands = scr.get("verifiedCandidates") or []
    if not cands:
        errors.append("screener.verifiedCandidates: 비어 있음")
    seen = set()
    for c in cands:
        tag = c.get("ticker") or "?"
        if tag in seen:
            errors.append(f"screener: 중복 후보 {tag}")
        seen.add(tag)
        for k in ("name", "status", "statusLabel", "verdict", "research"):
            if not c.get(k):
                errors.append(f"screener[{tag}]: 필수 키 누락 '{k}'")
        if c.get("status") not in CANDIDATE_STATUS:
            errors.append(f"screener[{tag}]: status '{c.get('status')}' — {sorted(CANDIDATE_STATUS)} 중 하나")
        if c.get("band") not in BANDS:
            errors.append(f"screener[{tag}]: band '{c.get('band')}'")
        res = c.get("research") or {}
        for k in RESEARCH_KEYS:
            items = res.get(k)
            if not isinstance(items, list) or len(items) < 2:
                errors.append(f"screener[{tag}].research.{k}: 기업 리서치 최소 2개 항목 필요")
        if not c.get("sources"):
            errors.append(f"screener[{tag}]: sources 없음 — 1차 출처 필요")
        for s in c.get("sources") or []:
            if not s.get("label") or not s.get("url"):
                errors.append(f"screener[{tag}].sources: label/url 누락")

    tracked = scr.get("tracked") or []
    if len(tracked) < 4:
        warnings.append(f"screener.tracked: {len(tracked)}개 — 추적 4종목이 기대값")

    md = scr.get("methodology") or {}
    for k in ("weights", "axes", "bands", "gates", "limits"):
        if not md.get(k):
            errors.append(f"screener.methodology.{k} 누락")
    weights = md.get("weights") or {}
    if weights and sum(weights.values()) != 100:
        errors.append(f"screener.methodology.weights 합계 {sum(weights.values())} (100이어야 함)")


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
    reports = len(((store.get("frontier") or {}).get("reports")) or [])
    cands = len(((store.get("screener") or {}).get("verifiedCandidates")) or [])
    print(f"✓ data OK — memo {memos} · ledger {ideas} · frontier {reports} · screener {cands} · 경고 {len(warnings)}")

    if "--stamp" in sys.argv:
        stamp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
