#!/usr/bin/env bash
# 登录后一键收尾：录制真实 MCP 响应 -> 真实数据演示 -> 测试 -> 提交
# 用法： MCD_MCP_TOKEN=<token> bash scripts/finalize_after_token.sh
#
# 目录约定：
#   tests/fixtures/     合成测试替身（确定性，单元测试用，永不改动）
#   examples/recorded/  真实录制的 MCP 响应（演示与透明性用）
set -euo pipefail
cd "$(dirname "$0")/.."

PY="C:/Users/34701/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
if [ -z "${MCD_MCP_TOKEN:-}" ]; then
  echo "错误：请先设置 MCD_MCP_TOKEN（open.mcd.cn/mcp 控制台激活领取）" >&2
  exit 1
fi

echo "==> 1/5 连通性自检（tools/list，真实连接）"
"$PY" -m mcdparty tools | tee examples/tools-live.txt | head -3

echo "==> 2/5 录制真实 MCP 响应 -> examples/recorded/（杭州）"
"$PY" -m mcdparty.record --city 杭州 --out examples/recorded

echo "==> 3/5 用真实录制数据跑演示"
"$PY" -m mcdparty demo --fixtures examples/recorded \
  --city 杭州 --occasion birthday --size 12 | tee examples/live-plan.md | head -14
"$PY" -m mcdparty demo --fixtures examples/recorded \
  --city 杭州 --occasion team --size 15 --format html -o examples/invite-live.html
echo "  邀请函: examples/invite-live.html"

echo "==> 4/5 全量测试（合成 fixtures，确定性）"
"$PY" -m unittest discover -s tests 2>&1 | tail -3

echo "==> 5/5 提交"
git add -A
git commit -q -m "data: 灌入真实 MCP 录制数据（examples/recorded），更新演示" || echo "  (无变化可提交)"
git log --oneline | head -3
echo "DONE - 真实数据已就位；README 演示段待更新，然后执行 scripts/github_release.py --go"
