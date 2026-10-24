# workbuddy.md — WorkBuddy 开发上下文导出

> 本文件记录「麦麦派对策划师」在 **腾讯 WorkBuddy** 中的真实开发过程，用于核验联动活动奖励条件。
> 开发时间：2026-10-24（北京时间），开发环境：WorkBuddy Agent 模式 + Windows + Git Bash 沙箱。

## 一、任务输入

用户发送活动截图（1024 造物挑战 / 麦当劳程序员创意开发大赛），要求"帮我完成一下，做的好一点"。
大赛硬性要求（从官方仓库 M-China/mcd-developer-innovation-challenge 拉取）：

- 基于麦当劳 MCP（`https://mcp.mcd.cn`）开发 Skill，**必须真实调用**
- 公开 GitHub 仓库 + 5 个规定文件（README / CONTEST_DECLARATION / MCP_INTEGRATION / mcp-config.example.json / workbuddy.md）
- 2026-10-25 23:59 前通过官方 Issue 模板报名；排名按 Star 数

## 二、开发轮次记录（WorkBuddy 对话实录摘要）

### 第 1 轮：规则摸底与选题

- WorkBuddy 拉取 `activityGuidelines.md`、`mcd-mcp-server` README、`CONTEST_DECLARATION.md` 原文
- 枚举 MCP 全部 33 个 Tool，判断赛道：官方示例（点餐/省钱/活动推荐）必然扎堆；
  **v1.0.7 新增的派对工具链（query-party-city → store → date → session → order）使用人数最少**
- 选题确定：**「麦麦派对策划师」**——把 5 步预订向导压缩为 1 条命令，可解释推荐 + HTML 邀请函 + 默认 dry-run 下单
- 与用户确认两件只能由用户做的事：MCP Token 申请（open.mcd.cn/mcp 手机登录）、GitHub 推送授权

### 第 2 轮：架构与编码（纯标准库，零依赖）

WorkBuddy 一次性产出全部源码（`mcdparty/` 包，约 1200 行）：

| 模块 | 职责 | 关键决策 |
| --- | --- | --- |
| `mcp_client.py` | MCP Streamable-HTTP 客户端 | JSON-RPC 2.0；initialize→notifications/initialized→tools/list→tools/call；跟踪 `Mcp-Session-Id`；同时解析 `application/json` 与 SSE；401→MCPAuthError、429→MCPRateLimitError |
| `models.py` | 数据模型 + 防御式解析 | MCP 响应字段未完全文档化，所有解析器兼容多套键名（`cityId`/`id`、`startTime`/`start`、`capacity`/`maxPeople`…） |
| `planner.py` | 5 工具决策链 | 可解释评分：周末 +3 / 下午场 +2（生日）/ 傍晚 +2（团建）/ 容量足够 +2 / 超预算 -3；每条推荐附文字理由 |
| `render.py` | markdown / json / html | HTML 邀请函为自包含单文件，无外部依赖 |
| `replay.py` | 离线回放传输层 | 测试与 demo 不碰网络；fixtures 按 `call__<tool>__<参数sha1前8位>.json` 存储 |
| `record.py` | 真实响应录制器 | 拿到 Token 后一键录制为 fixtures |
| `cli.py` | 命令行 | `plan`/`book`/`cities`/`tools`/`demo`/`chat`；`book` 默认 dry-run |
| `chat.py` | 可选 LLM 模式 | OpenAI 兼容端点驱动工具调用；**下单调用强制拦截**待人工确认 |

### 第 3 轮：测试驱动修复（3 轮迭代，零静默失败）

WorkBuddy 编写 33 个单元测试（`tests/`，纯 unittest），首轮 12 个失败，逐根因修复：

1. **回放信封缺陷**：`ReplayTransport` 未把业务 payload 包成 `tools/call` 的 `content` 信封 → `_unwrap_content` 解不出数据。修复：新增 `_tool_envelope()`。
2. **`as_list` 不递归**：`{"data": {"list": [...]}}` 嵌套结构返回空。修复：键名匹配时递归进 dict 值。
3. **stdout 污染**：demo 横幅打印到 stdout，`--format json` 输出不可解析。修复：横幅与调用链改走 stderr。
4. **fixture 精度**：指定日期 2026-11-08 时回放仍返回 10-31 的场次。修复：新增参数级 fixture（digest 必须用 Python `json.dumps(sort_keys=True)` 计算，JS 序列化哈希不一致——踩坑后修正）。
5. **`tools` 子命令崩溃**：`_client` 访问不存在的 `args.demo`。修复：parent parser 统一注入 `--demo`。

每轮修复后全量回归，最终 **33/33 通过**。

### 第 4 轮：参赛合规与文档

- `CONTEST_DECLARATION.md`：从官方仓库拉取原文，**程序化逐字节比对确认一致**（官方要求内容不可改动）
- `mcp-config.example.json`：仅 `${MCD_MCP_TOKEN}` 环境变量占位符
- `MCP_INTEGRATION.md`：Server 信息、5 个 Tool 的参数/用途/返回处理、调用流程图、业务价值、限流策略
- `README.md`：痛点表、30 秒离线体验、真实输出转录、架构图、设计取舍
- `skill/SKILL.md`：WorkBuddy Skill 打包（含 Agent 铁律：查询与下单分离、理由必须转述、Token 保密）
- `py_compile` 全量通过；git 本地仓库初始化并完成 2 次提交

## 三、验证证据

```text
$ python -m unittest discover -s tests
Ran 33 tests in 0.056s
OK

$ python -m mcdparty tools --demo
共 33 个工具，其中派对相关 5 个：
 ★ query-party-city / query-party-store / query-partystore-date
 ★ query-partystore-session / party-order-create

$ python -m mcdparty demo --city 杭州 --occasion birthday --size 12
# 🎂 生日派对 · 麦麦派对策划案
- 门店：杭州湖滨餐厅 | 日期：10 月 31 日（周六）| 场次：14:00 - 16:00
- 理由：周末场 +3 / 下午场适合小朋友 / 容量 20 ≥ 12 人
MCP 调用链: query-party-city -> query-party-store -> query-partystore-date -> query-partystore-session
```

## 四、后续步骤（需用户配合）

1. 用户获取麦当劳 MCP Token → WorkBuddy 用 `python -m mcdparty.record` 录制真实响应、跑通在线 `plan`
2. 用户完成 GitHub 浏览器授权 → WorkBuddy 创建公开仓库、推送、提交官方报名 Issue
3. 定榜前持续运营（README 演示、开发实录文章）争取 Star

---

*本文件由参赛者从 WorkBuddy 开发会话自行导出。项目为独立开发作品，非麦当劳官方产品。*
