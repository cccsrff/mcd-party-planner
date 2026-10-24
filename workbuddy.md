# workbuddy.md — WorkBuddy 开发上下文导出

> 本文件记录「麦麦派对策划师」在 **腾讯 WorkBuddy** 中的真实开发过程，用于核验联动活动奖励条件。
> 开发时间：2026-10-24（北京时间），开发环境：WorkBuddy Agent 模式 + Windows + Git Bash 沙箱。

## 一、任务输入

用户发送活动截图（1024 造物挑战 / 麦当劳程序员创意开发大赛），要求「帮我完成一下，做的好一点」。
大赛硬性要求（从官方仓库 M-China/mcd-developer-innovation-challenge 拉取）：

- 基于麦当劳 MCP（`https://mcp.mcd.cn`）开发 Skill，**必须真实调用**
- 公开 GitHub 仓库 + 5 个规定文件（README / CONTEST_DECLARATION / MCP_INTEGRATION / mcp-config.example.json / workbuddy.md）
- 2026-10-25 23:59 前通过官方 Issue 模板报名；排名按 Star 数

## 二、开发轮次记录（WorkBuddy 对话实录摘要）

### 第 1 轮：规则摸底与选题

- WorkBuddy 拉取 `activityGuidelines.md`、`mcd-mcp-server` README、`CONTEST_DECLARATION.md` 原文
- 枚举 MCP 全部 33 个 Tool，判断赛道：官方示例（点餐/省钱/活动推荐）必然扎堆；
  **v1.0.7 新增的派对工具链（query-party-city → store → date → session → order）使用人数最少**
- 选题确定：**「麦麦派对策划师」**——把 4 次查询压成 1 条命令，可解释推荐 + HTML 邀请函 + 默认 dry-run 下单
- 与用户确认两件只能由用户做的事：MCP Token 申请（open.mcd.cn/mcp 手机登录）、GitHub 推送授权

### 第 2 轮：架构与编码（纯标准库，无第三方依赖）

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

### 第 3 轮：测试驱动修复（3 轮迭代）

WorkBuddy 编写 39 个单元测试（`tests/`，纯 unittest），首轮 12 个失败，逐根因修复：

1. **回放信封缺陷**：`ReplayTransport` 未把业务 payload 包成 `tools/call` 的 `content` 信封 → `_unwrap_content` 解不出数据。修复：新增 `_tool_envelope()`。
2. **`as_list` 不递归**：`{"data": {"list": [...]}}` 嵌套结构返回空。修复：键名匹配时递归进 dict 值。
3. **stdout 污染**：demo 横幅打印到 stdout，`--format json` 输出不可解析。修复：横幅与调用链改走 stderr。
4. **fixture 精度**：指定日期 2026-11-08 时回放仍返回 10-31 的场次。修复：新增参数级 fixture（digest 必须用 Python `json.dumps(sort_keys=True)` 计算，JS 序列化哈希不一致——踩坑后修正）。
5. **`tools` 子命令崩溃**：`_client` 访问不存在的 `args.demo`。修复：parent parser 统一注入 `--demo`。

每轮修复后全量回归，最终 **39/39 通过**。

### 第 4 轮：参赛合规与文档

- `CONTEST_DECLARATION.md`：从官方仓库拉取原文，**程序化逐字节比对确认一致**（官方要求内容不可改动）
- `mcp-config.example.json`：仅 `${MCD_MCP_TOKEN}` 环境变量占位符
- `MCP_INTEGRATION.md`：Server 信息、5 个 Tool 的参数与返回处理、调用链、错误映射、录制回放
- `README.md`：价值主张、快速开始、命令表、评分规则、安全边界、下单前须知
- `skill/SKILL.md`：WorkBuddy Skill 打包（工作规则 6 条：查询与下单分离、理由必须转述、Token 保密等）
- `py_compile` 全量通过；本地仓库初始化并提交

### 第 5 轮：三轮独立审查与优化

3 个独立子代理分别从**视觉美学**、**风格化文案**、**用途价值**三个视角审查，循环「审查 → 优化 → 复审」三轮：

- 第 1 轮修掉三处会被评委戳穿的口径：「5 步变 1 条」不成立、测试数 32/33 不一致、离线演示自称实时数据；同时补上安全边界（日期不可约直接报错、`--session` 锁定场次、未知城市不兜底、回放参数校验）
- 第 2 轮修掉残留话术与视觉缺陷：demo 产物仍写「实时返回」、演示稿印出 `--confirm` 下单命令、邀请函理由列表缩进错位 58px、兜底分支会把内部评分日志印上邀请函
- 第 3 轮：终审复核
- 结果：测试从 33 增至 39，README 从约 180 行压到 140 行，全仓库 emoji 归零

## 三、验证证据（以下为真实终端转录）

```text
$ python -m unittest discover -s tests
Ran 39 tests in 0.077s

OK

$ python -m mcdparty tools --demo
共 33 个工具，其中派对相关 5 个：
   list-nutrition-foods         餐品营养信息列表：获取麦当劳常见餐品的营养成分数据
   ...（省略 27 行）...
 ★ query-partystore-date        主题活动可预约日期查询：查询指定门店下主题活动的可预约日期列表
 ★ query-partystore-session     主题活动可预约日期场次查询：查询指定门店、指定日期下主题活动的可预约场次列表
 ★ party-order-create           主题活动订单创建：创建主题活动订单

$ python -m mcdparty demo --city 杭州 --occasion birthday --size 12
# 生日派对策划案
- 城市：杭州
- 门店：杭州湖滨餐厅（上城区平海路 118 号）
- 日期：10 月 31 日（周六）
- 场次：14:00 - 16:00
- 人数：12 人
- 参考价：¥168/人

## 选择理由

- 门店取列表首家「杭州湖滨餐厅」（当前未按距离或评分排序，3 家可选）
- 自动选定最近周末 2026-10-31（共 5 天可约，全部是周末）
- 周末场，亲友到场率最高
- 下午场，适合小朋友作息
- 容量 20 人 ≥ 预计 12 人

## 其他可约日期（4 天）

11 月 1 日（周日）、11 月 7 日（周六）、11 月 8 日（周日）、11 月 14 日（周六）
```

`demo` 是离线回放（内置 fixtures），输出中会明确标注非实时数据；真实 MCP 路径需配置 `MCD_MCP_TOKEN`。

## 四、后续步骤（需用户配合）

1. 用户获取麦当劳 MCP Token → 用 `python -m mcdparty.record` 录制真实响应、跑通在线 `plan`
2. 用户完成 GitHub 授权 → 创建公开仓库、推送代码
3. 真实数据入库后提交官方报名 Issue

---

*本文件由参赛者从 WorkBuddy 开发会话自行导出。项目为独立开发作品，非麦当劳官方产品。*
