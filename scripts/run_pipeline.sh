#!/bin/bash
# JYKC 日报采集全流程：采集 → 回测 → 构建页面 → 推送
# 设计目标：单次前台运行，避免 cron agent 空等后台进程导致超时
set -e
cd "$(dirname "$0")/.."

echo "=== [1/4] 采集研报 ==="
python3 scripts/collect_jykc_reports.py 2>&1 | tail -5

echo "=== [2/4] 回测 ==="
python3 scripts/run_daily_backtest.py 2>&1 | tail -5

echo "=== [3/4] 构建页面 ==="
python3 scripts/build_pages.py 2>&1 | tail -3

echo "=== [4/4] Git 推送 ==="
if git diff --quiet && git diff --cached --quiet; then
    echo "[SKIP] 无数据变更，不推送"
else
    git add -A
    git commit -m "data: 日报采集+回测+页面更新 $(date +%F)"
    git push origin main
    echo "[OK] 已推送 main"
fi

echo "=== PIPELINE DONE ==="
