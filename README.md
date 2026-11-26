# 10X Research Desk — Web

개인 투자 리서치 데스크의 공개 프론트엔드. 빌드 도구 없는 정적 SPA(HTML/CSS/JS)이고,
GitHub Pages(`main` 브랜치 루트)로 서비스된다.

- **Live:** https://paperbags1103-hash.github.io/10x-research-desk/
- **원천 리서치:** `../investment-desk/` (STRATEGY · PLAYBOOK · ledger · memos · scorecard)

## 구성 (4개 탭)

| 탭 | 내용 | 데이터 |
|---|---|---|
| **Overview / Briefing** | 데스크 요지, 핵심 지표, 기준지수(Base 100 → 5Y 목표), 배분 비중(집중안/4바구니안 토글), 추적 변수, 거시 테이프 | `data/briefing.json` |
| **Deep-Dive Memos** | 메모 전문을 카드·표·5년 시나리오 바·무효화 기준·진입 사다리·촉매 타임라인으로 렌더 | `data/memos.json` |
| **Idea Ledger** | 아이디어 상태(진입 대기/후보/탈락) 필터 뷰, 진입가·가설·무효화 | `data/ledger.json` |
| **Self-Eval & Playbook** | 자가평가 점수 링·4개 채점 축·평가 로그·개선 액션·룰북·변경 이력 | `data/scorecard.json` · `data/playbook.json` |

## 파일 구조

```
index.html            셸(헤더·탭바·에러 수집기)
assets/style.css      디자인 시스템 (다크 에디토리얼 + 라임 액센트)
assets/app.js         데이터 로더 + 렌더러 (해시 라우팅: #overview #deepdive #ledger #system)
data/meta.json        사이트 메타 (updatedAt, dataVersion)
data/briefing.json    Overview
data/memos.json       Deep-Dive 메모 (배열 — 메모 추가 시 append)
data/ledger.json      Idea Ledger
data/playbook.json    룰북
data/scorecard.json   자가평가
tools/selfcheck.py    스키마 + 프라이버시 lint (+ --stamp)
tools/sync_ledger.py  ledger.md ↔ data/ledger.json 동기화 (--write 재생성)
publish.sh            검증 → 커밋 → 푸시 (배포)
```

## 매 회차 업데이트 절차 (아침/저녁 브리핑 · 자가개선 루프)

1. `research/investment-desk/` 의 원천 문서를 갱신한다 (ledger.md, memos/*, scorecard.md, PLAYBOOK.md).
2. 사이트 데이터를 갱신한다.
   - 장부: `python3 tools/sync_ledger.py --write` 로 md에서 재생성 (원화 금액은 자동 제거).
   - 브리핑/메모/점수표: 해당 JSON을 직접 수정하거나 새 메모를 `data/memos.json` 배열 끝에 append.
   - 새 메모는 `blocks`에 `section`/`table`/`kv`/`list`/`cards`/`callout`/`prose` 블록을 넣으면 그대로 렌더된다 (아래 예시).
3. `./publish.sh "data: 2026-11-27 아침 브리핑"` — 검증 실패 시 푸시되지 않는다.
4. 30~60초 뒤 라이브 URL 확인.

`selfcheck.py`는 ① 필수 키 ② 배분 비중 합계 100% ③ statusKey 화이트리스트 ④ scorecard 총점=항목합 
⑤ **프라이버시 lint**(휴대폰·이메일·실명·원화 금액)를 검사한다. lint에 걸리면 배포가 막힌다.

## 데이터 규약 (요약)

```jsonc
// briefing.json
{ "headline": "...<em>...</em>",            // HTML 허용 (display 전용)
  "stats": [{ "k": "라벨", "v": "값", "n": "설명", "tone": "hot|green" }],
  "index": { "base": 100, "target": 450, "scale": 500, "ticks": [...] },
  "allocation": { "desk": { "label": "...", "rows": [{ "name": "...", "weight": 45, "color": "#c8ff00", "note": "..." }] } },
  "watch": [{ "tag": "MACRO", "title": "...", "body": "...", "foot": "...", "tone": "red|green|" }],
  "tape": { "rows": [["S&P 500", "7,182.78", "-4.8%", "메모"]] } }

// memos.json — 메모 1건
{ "id": "002", "ticker": "062040", "exchange": "KOSPI", "name": "산일전기",
  "kicker": "Deep-Dive 002 · ...", "title": "제목<br>둘째 줄", "status": "ACTIVE", "date": "2026-12-01",
  "entryPrice": "94700", "weightedMultiple": "3.0x",
  "stats": [{ "label": "현재 주가", "value": "94,700원", "note": "..." }],
  "scenarios": [{ "name": "Base", "multiple": 3.0, "prob": 45, "tone": "base" }],
  "blocks": [
    { "type": "section", "num": "01", "title": "섹션 제목", "aside": "English aside", "blocks": [
        { "type": "prose", "paragraphs": ["...**굵게**..."] },
        { "type": "table", "columns": ["항목", "값"], "rows": [["매출", "$1.38B"]], "align": ["l", "r"], "note": "출처" },
        { "type": "kv", "rows": [["순현금", "$511M", "보조 설명"]] },
        { "type": "list", "items": ["...", "..."], "ordered": false, "check": false },
        { "type": "cards", "columns": 3, "items": [{ "tag": "Bear 1", "tone": "red", "title": "...", "body": "...", "foot": "..." }] },
        { "type": "callout", "tone": "warn|lime|quiet", "title": "제목", "body": "..." }
    ] }
  ],
  "invalidation": [{ "n": "01", "condition": "...", "action": "..." }],
  "entryPlan": { "aside": "Tranche", "stages": [{ "stage": "1차", "weight": 30, "price": "$5.0-5.7", "timing": "...", "basis": "..." }], "note": "...", "warning": "..." },
  "catalysts": [{ "date": "2026-12-07", "event": "...", "note": "...", "now": true }],
  "monitoring": ["...", "..."],
  "gaps": ["..."],
  "sources": [{ "group": "1차 소스", "items": [{ "label": "...", "url": "https://..." }] }] }

// ledger.json
{ "items": [{ "id": "001", "ticker": "EROC", "exchange": "NYSE", "name": "ERock",
  "bucket": "1호 · 비중 45%", "entryPrice": "$5.60", "entryPlan": "(% of sleeve) 30/35/35",
  "thesis": "...", "invalidation": "...", "status": "진입 대기", "statusKey": "wait", "memo": "상세 링크" }] }
```

`statusKey` 허용값: `active` · `wait` · `candidate` · `watch` · `drop` · `closed`.
`**굵게**` 는 렌더 시 `<b>`로 변환된다(모든 텍스트 필드 공통). HTML 태그를 직접 써도 된다.

## 프라이버시 규칙 (공개 페이지)

- 실명 · 전화번호 · 이메일 · 계좌/증권사 · 개인 신상 **금지**.
- 계좌 규모 대신 **비중(%)**, 성과 대신 **기준지수(Base 100)** 로만 표기.
- 원화 금액은 넣지 않는다 (종목의 공개 시세·시총은 예외). `selfcheck.py`가 차단한다.

## 배포

- 저장소: `paperbags1103-hash/10x-research-desk` (public)
- Pages: **`gh-pages` 브랜치 루트**가 배포 소스 (빌드 없음, `.nojekyll`). `publish.sh`가 `main`과 `gh-pages`를 같이 밀어 준다 — 손으로 배포할 때도 두 브랜치를 모두 푸시해야 사이트가 갱신된다.
  ```
  git push origin HEAD && git push origin HEAD:gh-pages
  ```
- 배포 후 검증: 라이브 URL에서 4개 탭 전환 → 콘솔 에러 0 → `window.__deskErrors` 빈 배열.
  `index.html`이 로드 전에 `window.__deskErrors`를 만들고 `window.__deskReady = true`를 세팅하므로
  브라우저 콘솔에서 `__deskReady` / `__deskErrors`로 확인할 수 있다.
