#!/usr/bin/env bash
# ============================================================================
#  10X Research Desk — publish to GitHub Pages
#  사용법:  ./publish.sh "data: 2026-11-27 아침 브리핑 반영"
#  하는 일: ① data/*.json 검증(+프라이버시 lint, meta 스탬프) ② 장부 동기화 확인
#          ③ commit ④ push  →  main 브랜치 루트가 Pages로 서비스된다.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

NAME="10X Research Desk"
EMAIL="10x-research-desk@users.noreply.github.com"
MSG="${1:-data: desk update $(date -u '+%Y-%m-%d %H:%M UTC')}"
URL="https://paperbags1103-hash.github.io/10x-research-desk/"

echo "▸ 1/4  데이터 검증 + 스탬프"
python3 tools/selfcheck.py --stamp

echo "▸ 2/4  장부 동기화 확인"
if ! python3 tools/sync_ledger.py; then
  echo "! ledger.md ↔ data/ledger.json 불일치 — data/ledger.json을 갱신하는 것을 권장 (계속 진행)"
fi

echo "▸ 3/4  스테이징"
git add -A
if git diff --cached --quiet; then
  echo "• 변경 없음 — 배포 생략"
  exit 0
fi
git diff --cached --stat | tail -n 6

echo "▸ 4/4  커밋 & 푸시"
git -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "$MSG"
git push -q origin HEAD
echo "✓ 푸시 완료 — Pages 반영까지 보통 30~60초"
echo "  $URL"
