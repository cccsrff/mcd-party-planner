# MCP 集成说明

本文档说明「麦麦派对策划师」实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值。

## Server 信息

| 项 | 值 |
| --- | --- |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（MCP 标准） |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 600 次/分钟（超限返回 429） |
| 客户端实现 | [`mcdparty/mcp_client.py`](./mcdparty/mcp_client.py)（纯标准库，约 200 行） |

协议交互严格遵循 MCP 规范：`initialize`（protocolVersion `2025-03-26`）→ `notifications/initialized` → `tools/list` → `tools/call`；客户端跟踪服务端返回的 `Mcp-Session-Id` 头并在后续请求中回带；响应同时兼容 `application/json` 与 `text/event-stream`（SSE）两种内容类型。

## 使用的 Tool（全部来自麦当劳官方 MCP）

| # | Tool | 调用参数 | 用途 | 返回值处理 |
| --- | --- | --- | --- | --- |
| 1 | `query-party-city` | 无 | 获取可举办主题活动的城市列表 | 提取 `cities[]`，按用户输入关键词匹配 |
| 2 | `query-party-store` | `cityId` | 获取该城市可参与主题活动的门店 | 提取 `stores[]`，取首家（可扩展为按距离） |
| 3 | `query-partystore-date` | `storeId` | 获取门店可预约日期 | 提取 `dates[]`，周末优先自动选定 |
| 4 | `query-partystore-session` | `storeId` + `date` | 获取指定日期的可预约场次 | 提取 `sessions[]`，进入评分引擎 |
| 5 | `party-order-create` | `storeId` + `date` + `sessionId` + `people` | 创建主题活动订单 | **仅 `--confirm` 时调用**，默认 dry-run |

另在 `mcdparty tools` 命令中调用 `tools/list` 展示全部 33 个工具，用于连通性自检。

## 调用流程

```text
用户输入（城市/场合/人数/预算）
   │
   ▼
① query-party-city ────────► 城市匹配（如「杭州」）
   │
   ▼
② query-party-store(cityId) ► 门店列表 → 选定门店
   │
   ▼
③ query-partystore-date(storeId) ► 日期列表 → 周末优先选定
   │
   ▼
④ query-partystore-session(storeId, date) ► 场次列表 → 评分选定
   │
   ▼
PartyPlan（含逐步理由 + 完整 tool_trace 审计轨迹）
   │
   ▼
（可选）⑤ party-order-create(...) ── 必须 --confirm，默认 dry-run
```

每次调用的原始请求与响应都记录在 `plan.tool_trace` 中，可用 `--format json` 导出，保证推荐结果可审计、可复现。

## 业务价值

- **把 5 步向导压缩为 1 条命令**：原本用户（或 LLM）需要依次发起 4 次查询并人工决策，现在一次 `plan` 调用即得到带理由的结论。
- **决策可解释**：评分规则透明（周末 +3 / 下午场 +2 / 容量足够 +2 / 超预算 -3），每条推荐附带文字理由，而非黑盒排序。
- **下单安全**：付费动作与查询动作分离，`party-order-create` 默认 dry-run；即使接入 LLM 自主调用，也会被客户端拦截要求人工确认。
- **容错与限流**：401 → `MCPAuthError`（提示检查 Token）、429 → `MCPRateLimitError`（提示降频）；全流程单次执行最多 4~5 次请求，远离 600/分钟的限流上限。

## 复现与录制

真实响应可通过录制脚本落盘为 fixtures，供离线演示与单元测试回放：

```bash
MCD_MCP_TOKEN=xxx python -m mcdparty.record --city 杭州 --out tests/fixtures
```

仓库内 `tests/fixtures/` 即按此格式存储（`call__<tool>__<参数哈希>.json`），测试与 `mcdparty demo` 通过 `ReplayTransport` 回放，不发起任何网络请求。
