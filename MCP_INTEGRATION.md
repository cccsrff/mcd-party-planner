# MCP 集成说明

## Server

| 项 | 值 |
| --- | --- |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 600 次/分钟（超限返回 429） |
| 客户端 | [`mcdparty/mcp_client.py`](./mcdparty/mcp_client.py)，纯标准库 |

协议交互：`initialize`（protocolVersion `2025-03-26`）→ `notifications/initialized` → `tools/list` → `tools/call`。客户端跟踪服务端返回的 `Mcp-Session-Id` 并在后续请求回带；响应同时兼容 `application/json` 与 `text/event-stream`。

## 使用的 Tool

| # | Tool | 参数 | 用途 | 返回值处理 |
| --- | --- | --- | --- | --- |
| 1 | `query-party-city` | 无 | 可办主题活动的城市 | 取 `cities[]`，按关键词精确匹配；不匹配直接报错，不做兜底 |
| 2 | `query-party-store` | `cityId` | 该城市可参与活动的门店 | 取 `stores[]`，当前取首家（未按距离排序） |
| 3 | `query-partystore-date` | `storeId` | 门店可预约日期 | 取 `dates[]`，优先最近周末 |
| 4 | `query-partystore-session` | `storeId` + `date` | 指定日期的可预约场次 | 取 `sessions[]`，进入评分 |
| 5 | `party-order-create` | `storeId` + `date` + `sessionId` + `people` | 创建主题活动订单 | 仅 `--confirm` 时调用 |

`mcdparty tools` 通过 `tools/list` 展示全部 33 个工具，用于连通性自检。

## 调用流程

```text
query-party-city          → 城市匹配（不匹配即报错）
query-party-store         → 门店列表 → 取首家
query-partystore-date     → 日期列表 → 最近周末
query-partystore-session  → 场次列表 → 评分选场
        ↓
PartyPlan（选择理由 + 完整 tool_trace）
        ↓
party-order-create        → 必须 --confirm，默认 dry-run
```

每次调用的请求与响应都记录在 `plan.tool_trace` 中，`--format json` 可导出，结果可审计、可复现。

## 错误处理

| 情况 | 行为 |
| --- | --- |
| 401 | 抛 `MCPAuthError`，提示检查 Token |
| 429 | 抛 `MCPRateLimitError`，提示降频 |
| `isError: true` | 抛 `MCPToolError` 并带上工具名 |
| 城市不在可办列表 | 报错并列出可选城市，不换城市 |
| 指定日期不可约（book） | 报错并列出可约日期，不改期 |
| 场次 ID 不存在（book） | 报错并列出可选场次 |

## 录制与回放

```bash
MCD_MCP_TOKEN=xxx python -m mcdparty.record --city 杭州 --out examples/recorded
```

真实响应按 `call__<tool>__<参数哈希>.json` 落盘，回放层 `ReplayTransport` 会**校验录制参数与本次请求是否一致**，不一致直接报错，避免用杭州的数据回答北京的请求。
