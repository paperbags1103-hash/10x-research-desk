#!/usr/bin/env python3
"""Keep data/screener.json in step with the screener run, its notes and the company research.

Three sources feed this site file:

  1. research/investment-desk/data/screener_latest.json   ← tools/screener.py output
       (universe counts, US/KR Top, tracked names, scores, axes, metrics)
  2. scheduled-actions/🌱-성장주-발굴-스크리너/notes.md     ← the desk's round log
       (round label, run summary, US/KR Top lines, tracked line, next checks, banned list)
  3. research/investment-desk/company_research.json       ← qualitative company research
       (business model, moat, growth drivers, capital/governance, bear case,
        invalidation line, sources — keyed by ticker)

Scores and metrics are never typed by hand: they always come from 1.
The research text comes from 3. The round narrative comes from 2.
If notes.md and company_research.json disagree about a candidate's status, the
research file wins and a warning is printed (it is the hand-checked record).

Usage:
    python3 tools/sync_screener.py            # report drift (exit 1 if data/screener.json is stale)
    python3 tools/sync_screener.py --write    # regenerate data/screener.json
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent                 # …/investment-desk-web
DESK = ROOT.parent / "investment-desk"                        # …/research/investment-desk
SRC = DESK / "data" / "screener_latest.json"
RESEARCH = DESK / "company_research.json"
NOTES = ROOT.parent.parent / "scheduled-actions" / "🌱-성장주-발굴-스크리너" / "notes.md"
OUT = ROOT / "data" / "screener.json"

STATUS_TONES = {
    "verified": "active",     # 검증 통과
    "complete": "candidate",  # 1차 검증 완료
    "hold": "wait",           # 검증 보류
    "reject": "drop",         # 탈락
}

AXES = [
    ("growth", "성장", 25, "매출 TTM·분기 가속·EPS·CAGR·지속성"),
    ("quality", "마진", 22, "GPM·마진 추세·영업레버리지·ROIC·ROE"),
    ("value", "밸류", 18, "PEG·Rule of 40·FCF 마진·멀티플"),
    ("balance", "건전성", 18, "순현금·희석률·FCF/부채"),
    ("trend", "추세", 17, "52주 고점 근접·상대강도·수급·내부자"),
]

BANDS = [
    ("A", "$300M–$5B", "3,000억–5조", "5년 10배 수학이 성립하는 핵심 탐색대"),
    ("B", "$5B–$20B", "5조–20조", "2~5배 고확률 복리 후보"),
    ("C", "$20B+", "20조+", "해자는 크지만 배수 여력은 낮음 — 비중만 조절"),
]

GATES = [
    "no_growth_data", "not_growth", "micro_base", "cash_burn", "illiquid",
    "fund_like", "finance", "theme_only", "cyclical_spike", "defensive_dilution",
    "negative_growth_fy",
]

LIMITS = [
    "PEG는 컨센서스 장기성장률이 없어 후행 성장률로 근사했다 — '싸다'가 아니라 '터무니없지 않다'의 증거로만 쓴다.",
    "미국 내부자 매매는 건수만 반영하고 매수·매도 방향은 반영하지 않는다.",
    "한국 GPM·ROIC는 TradingView 추정 의존도가 높아 DART 원문 대조 전에는 확정치가 아니다.",
    "모멘텀 축은 시장 레짐에 민감하다 — 급락장에서는 우량 성장주도 5축에서 깎인다.",
    "섹터 분류 오류가 있을 수 있다(TradingView sector/industry). 1차 공시에서 사업모델을 먼저 확인한다.",
]


# --------------------------------------------------------------------- helpers

def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"파일 없음: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def num(x, d=1, sign=False, suffix=""):
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    s = f"{v:+.{d}f}" if sign else f"{v:.{d}f}"
    return s + suffix


def market_cap_label(v: float, market: str) -> str:
    if v is None:
        return "—"
    if market == "kr":
        if v >= 1e12:
            return f"{v / 1e12:,.1f}조"
        return f"{v / 1e8:,.0f}억"
    if v >= 1e9:
        return f"${v / 1e9:,.2f}B"
    return f"${v / 1e6:,.0f}M"


def label_as_of(raw: str) -> str:
    try:
        d = dt.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
        return d.strftime("%Y-%m-%d %H:%M") + " KST"
    except (TypeError, ValueError):
        return raw or "—"


def collect_items(sc: dict) -> dict:
    """ticker → item, across every list a candidate might appear in."""
    out = {}
    for mk in ("us", "kr"):
        m = (sc.get("markets") or {}).get(mk) or {}
        for key in ("top", "band_a_top", "tracked", "near_miss", "final_gate_rejects"):
            for it in m.get(key) or []:
                t = str(it.get("ticker") or "").upper()
                if t and t not in out:
                    out[t] = it
        # tracked tickers are the ones we always want a score for, keep them newest
        for it in m.get("tracked") or []:
            t = str(it.get("ticker") or "").upper()
            if t:
                out[t] = it
    return out


# ----------------------------------------------------------------- notes.md

ROUND_RE = re.compile(r"^##\s+(?P<date>\d{4}-\d{2}-\d{2})\s*(?:\((?P<label>[^)]*)\))?\s*$")
KEY_RE = re.compile(r"^[-*]\s+\*\*(?P<k>[^*]+)\*\*\s*[—:-]?\s*(?P<v>.*)$")


def parse_notes(path: Path) -> list:
    if not path.exists():
        return []
    rounds, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = ROUND_RE.match(line)
        if m:
            cur = {
                "date": m.group("date"),
                "label": (m.group("label") or "").strip(),
                "lines": [],
                "nextChecks": [],
                "banned": "",
            }
            rounds.append(cur)
            continue
        if cur is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  - "):  # nested bullet → belongs to the previous key
            if cur["lines"] and cur["lines"][-1]["k"].startswith("다음 회차"):
                cur["nextChecks"].append(stripped[2:].strip())
                cur["lines"][-1]["sub"].append(stripped[2:].strip())
            elif cur["lines"]:
                cur["lines"][-1]["sub"].append(stripped[2:].strip())
            continue
        if not stripped.startswith(("- ", "* ")):
            continue
        body = stripped[2:].strip()
        m = KEY_RE.match(stripped)
        if m:
            k = m.group("k").strip().rstrip(":")
            v = m.group("v").strip().lstrip("—").strip()
        elif ":" in body:
            k, v = body.split(":", 1)
            k, v = k.strip(), v.strip()
        else:
            k, v = "", body
        if k.startswith(("신규 후보", "신규 진입", "신규 지목")):
            k = "신규 후보"
        if k.startswith("재탐색 금지"):
            cur["banned"] = v
            continue
        cur["lines"].append({"k": k, "v": v, "sub": []})
    return rounds


def notes_status(rounds: list, ticker: str, name: str) -> str:
    """Look for the candidate's judgement in the round log (cross-check only).

    The judgement sits at the end of the bullet ('… — **검증 통과**'), and the
    candidate bullets are nested under '신규 후보', so the last status word in
    the latest round that names the ticker wins.
    """
    words = ["검증 통과", "검증 보류", "1차 검증 완료", "탈락"]
    for r in reversed(rounds):
        for ln in r["lines"]:
            for text in [ln["k"] + " " + ln["v"]] + ln.get("sub", []):
                if not (ticker in text or (name and name in text)):
                    continue
                hits = [(text.rfind(w), w) for w in words if w in text]
                if hits:
                    return max(hits)[1]
    return ""


# ------------------------------------------------------------- site payload

def build_top(rows: list, market: str) -> list:
    out = []
    for it in rows:
        axes = it.get("axes") or {}
        met = it.get("metrics") or {}
        out.append({
            "rank": it.get("rank"),
            "ticker": it.get("ticker"),
            "name": it.get("name"),
            "mc": market_cap_label(it.get("market_cap"), market),
            "band": it.get("band"),
            "total": round(float(it.get("total") or 0), 1),
            "axes": {k: (round(float(axes.get(k)), 1) if axes.get(k) is not None else None)
                     for k, _, _, _ in AXES},
            "rev": None if met.get("rev_growth_ttm") is None else round(float(met["rev_growth_ttm"]), 1),
            "opm": None if met.get("opm") is None else round(float(met["opm"]), 1),
            "per": None if met.get("pe") is None else round(float(met["pe"]), 1),
            "peg": None if met.get("peg") is None else round(float(met["peg"]), 2),
            "high52": None if met.get("high_52w_dist") is None else round(float(met["high_52w_dist"]), 1),
            "flags": it.get("flags") or [],
        })
    return out


def build_candidates(research: dict, items: dict, rounds: list, warnings: list) -> list:
    out = []
    companies = research.get("companies") or {}
    for ticker, c in companies.items():
        key = str(ticker).upper()
        it = items.get(key) or {}
        axes = it.get("axes") or {}
        met = it.get("metrics") or {}
        band = it.get("band") or c.get("band") or "—"
        total = it.get("total")
        if total is None:
            warnings.append(f"research: {c.get('name')} ({ticker}) — 이번 회차 Top/추적에 없어 점수 없이 게시")

        status = c.get("status") or "hold"
        if status not in STATUS_TONES:
            warnings.append(f"research: {ticker} status '{status}' 알 수 없음 — hold로 처리")
            status = "hold"
        ns = notes_status(rounds, str(ticker), c.get("name") or "")
        if ns and ns != (c.get("statusLabel") or ""):
            warnings.append(
                f"! {c.get('name')} ({ticker}) 상태 불일치 — notes.md '{ns}' ↔ company_research.json "
                f"'{c.get('statusLabel')}' (리서치 파일 기준으로 게시)"
            )

        key_metrics = [
            {"k": "매출 TTM", "v": num(met.get("rev_growth_ttm"), 1, sign=True, suffix="%")},
            {"k": "영업이익률", "v": num(met.get("opm"), 1, suffix="%")},
            {"k": "FCF 마진", "v": num(met.get("fcf_margin"), 1, suffix="%")},
            {"k": "PER", "v": num(met.get("pe"), 1)},
            {"k": "52주 고점", "v": num(met.get("high_52w_dist"), 1, sign=True, suffix="%")},
        ]

        links = []
        urls = it.get("source_urls") or {}
        if urls.get("primary"):
            links.append({"label": "1차 공시", "url": urls["primary"]})
        if urls.get("quote_and_factors"):
            links.append({"label": "시세·팩터", "url": urls["quote_and_factors"]})

        out.append({
            "ticker": it.get("ticker") or ticker,
            "name": c.get("name") or it.get("name") or ticker,
            "nameEn": c.get("nameEn") or it.get("name_en") or "",
            "market": (c.get("market") or it.get("market") or "").lower(),
            "exchange": c.get("exchange") or it.get("exchange") or "",
            "band": band,
            "rank": it.get("rank"),
            "total": None if total is None else round(float(total), 1),
            "axes": {k: (round(float(axes.get(k)), 1) if axes.get(k) is not None else None)
                     for k, _, _, _ in AXES},
            "status": status,
            "tone": STATUS_TONES[status],
            "statusLabel": c.get("statusLabel") or "",
            "oneLiner": c.get("oneLiner") or "",
            "verdict": c.get("verdict") or "",
            "facts": c.get("facts") or [],
            "keyMetrics": key_metrics,
            "research": c.get("research") or {},
            "watch": c.get("watch") or [],
            "sources": c.get("sources") or [],
            "links": links,
        })

    order = {"verified": 0, "complete": 1, "hold": 2, "reject": 3}
    out.sort(key=lambda x: (order.get(x["status"], 9), -(x["total"] or 0)))
    return out


def build_tracked(sc: dict) -> list:
    out = []
    for mk in ("us", "kr"):
        m = (sc.get("markets") or {}).get(mk) or {}
        for it in m.get("tracked") or []:
            axes = it.get("axes") or {}
            out.append({
                "market": "US" if mk == "us" else "KR",
                "ticker": it.get("ticker"),
                "name": it.get("name"),
                "total": round(float(it.get("total") or 0), 1),
                "axes": {k: (round(float(axes.get(k)), 1) if axes.get(k) is not None else None)
                         for k, _, _, _ in AXES},
                "gate": it.get("gate"),
            })
    return out


def build() -> dict:
    sc = load_json(SRC)
    research = load_json(RESEARCH) if RESEARCH.exists() else {"companies": {}}
    rounds = parse_notes(NOTES)
    warnings: list = []
    items = collect_items(sc)

    us = (sc.get("markets") or {}).get("us") or {}
    kr = (sc.get("markets") or {}).get("kr") or {}

    def uni(m):
        return {
            "total": m.get("universe_total"),
            "passed": m.get("prefilter_passed"),
            "enriched": m.get("shortlist_size"),
        }

    us_top = build_top(us.get("top") or [], "us")
    kr_top = build_top(kr.get("top") or [], "kr")

    def top1(rows):
        if not rows:
            return "—"
        r = rows[0]
        return f"{r['name']} {r['total']:.1f} ({r['band']})"

    latest = rounds[-1] if rounds else {"label": "", "date": ""}
    payload = {
        "updatedAt": sc.get("generated_at"),
        "dataLabel": label_as_of(sc.get("generated_at") or ""),
        "roundLabel": latest.get("label") or "",
        "roundDate": latest.get("date") or "",
        "universe": {
            "us": uni(us),
            "kr": uni(kr),
            "elapsedSec": sc.get("elapsed_s"),
            "errors": len(sc.get("errors") or []),
        },
        "topSummary": f"US Top1 {top1(us_top)} · KR Top1 {top1(kr_top)}",
        "verifiedCandidates": build_candidates(research, items, rounds, warnings),
        "usTop": us_top,
        "krTop": kr_top,
        "tracked": build_tracked(sc),
        "rounds": rounds,
        "banned": latest.get("banned") or "",
        "nextChecks": latest.get("nextChecks") or [],
        "methodology": {
            "weights": (sc.get("config") or {}).get("weights") or {k: w for k, _, w, _ in AXES},
            "axes": [{"key": k, "label": lab, "max": w, "desc": desc} for k, lab, w, desc in AXES],
            "bands": [{"band": b, "us": u, "kr": k, "note": n} for b, u, k, n in BANDS],
            "gates": GATES,
            "limits": LIMITS,
        },
        "footnote": "스크리너는 후보를 좁히는 도구다. 매수·매도 지시나 비중 제안이 아니며, 최종 판단은 1차 공시 검증과 무효화 기준을 통과해야 한다.",
    }
    return {"payload": payload, "warnings": warnings, "rounds": rounds}


def main() -> int:
    built = build()
    payload, warnings = built["payload"], built["warnings"]

    for w in warnings:
        print(("  " + w) if w.startswith("!") else f"! {w}")

    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cands = payload["verifiedCandidates"]
        print(
            f"✓ data/screener.json 재생성 — 후보 {len(cands)} · "
            f"US Top {len(payload['usTop'])} · KR Top {len(payload['krTop'])} · "
            f"추적 {len(payload['tracked'])} · 회차 {len(payload['rounds'])}"
        )
        return 0

    if not OUT.exists():
        print("✗ data/screener.json 없음 — --write로 생성할 것")
        return 1
    cur = json.loads(OUT.read_text(encoding="utf-8"))
    drift = []
    for k in payload:
        if k not in cur:
            drift.append(f"+ 새 키: {k}")
        elif cur[k] != payload[k]:
            drift.append(f"~ 변경: {k}")
    for k in cur:
        if k not in payload:
            drift.append(f"- 사라진 키: {k}")
    if drift:
        for d in drift:
            print(f"! {d}")
        print(f"\n{len(drift)}건 불일치 — `python3 tools/sync_screener.py --write` 후 배포.")
        return 1
    print(f"✓ screener 동기화 OK — 후보 {len(payload['verifiedCandidates'])} · 기준 {payload['dataLabel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
