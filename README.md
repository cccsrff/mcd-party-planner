# 🎂 麦麦派对策划师 McParty Planner

> 在麦当劳办一场派对，要连续问 5 个问题：哪个城市？哪家门店？哪天？哪场？然后下单。
> **这个 Skill 把 5 步变成 1 条命令**——基于麦当劳官方 MCP 实时数据，给出带理由的推荐，一键生成可分享的派对策划案。

[![tests](https://img.shields.io/badge/tests-32%2F32%20passing-brightgreen)](./tests)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](./mcdparty)
[![license](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![mcp](https://img.shields.io/badge/McDonald's%20MCP-party--tools-yellow)](./MCP_INTEGRATION.md)

**1024 程序员节 · 麦当劳程序员创意开发大赛参赛作品**（使用腾讯 WorkBuddy 全程开发）

---

## 解决什么问题

麦当劳中国 MCP 开放了完整的「主题活动（派对）」预订能力，但原始工具链是 **5 步顺序向导**：
`query-party-city` → `query-party-store` → `query-partystore-date` → `query-partystore-session` → `party-order-create`。

家长想给孩子办生日派对、HR 想组织团建时，真实痛点是：

| 痛点 | 麦麦派对策划师怎么做 |
| --- | --- |
| 不知道哪些城市能办派对 | `mcdparty cities` 列出全部可约城市 |
| 门店、日期、场次要一步步试 | 一条命令自动走完 4 步查询，实时数据 |
| 不知道选哪天哪场 | 可解释的评分引擎：周末 +3、下午场 +2（小朋友作息）、容量够 +2、超预算 -3……每条推荐都附理由 |
| 怕下错单 | **默认 dry-run**，看清参数后才加 `--confirm` 真正下单 |
| 想发给家人看 | `--format html` 生成一张派对邀请函网页 |

## 30 秒跑起来（无需 Token）

仓库内置演示数据（结构复刻真实 MCP 响应），离线即可完整体验：

```bash
git clone https://github.com/<you>/mcd-party-planner.git
cd mcd-party-planner
python -m mcdparty demo --city 杭州 --occasion birthday --size 12
```

真实输出：

```text
# 🎂 生日派对 · 麦麦派对策划案

- 城市：**杭州**
- 门店：**杭州湖滨餐厅**（上城区平海路 118 号）
- 日期：**10 月 31 日（周六）**
- 场次：**14:00 - 16:00**
- 人数：**12 人**
- 参考价：**¥168 / 人**

## 为什么选这一场

- 城市匹配「杭州」
- 门店选择「杭州湖滨餐厅」（该城市共 3 家可选）
- 自动选定最近周末 2026-10-31（共 5 个周末可约）
- 周末场，亲友到场率最高
- 下午场，适合小朋友作息
- 容量 20 人 ≥ 预计 12 人
...
MCP 调用链: query-party-city -> query-party-store -> query-partystore-date -> query-partystore-session
```

## 接入真实 MCP

1. 到 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 手机号登录，控制台「激活」领取免费 MCP Token
2. 配置环境变量（或参考 [mcp-config.example.json](./mcp-config.example.json)）：

```bash
export MCD_MCP_TOKEN="你的 Token"
```

3. 直接跑：

```bash
python -m mcdparty plan --city 杭州 --date 2026-11-08 --size 15 --format html -o invite.html
```

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `mcdparty tools` | 列出 MCP 全部 33 个工具（验证真实连接） |
| `mcdparty cities --keyword 杭州` | 列出可办派对的城市 |
| `mcdparty plan` | 全流程查询 + 可解释推荐（markdown / json / html） |
| `mcdparty book --confirm` | 真正下单（不加 `--confirm` 就是 dry-run） |
| `mcdparty demo` | 离线回放，CI 也能跑 |
| `mcdparty chat` | LLM 驱动模式（可选，需自备 OpenAI 兼容端点） |

作为库使用：

```python
from mcdparty import MCPClient, PartyPlanner
from mcdparty.models import PartyRequest

client = MCPClient(token=os.environ["MCD_MCP_TOKEN"])
plan = PartyPlanner(client).plan(PartyRequest(city="杭州", occasion="birthday", party_size=12))
print(plan.chosen.start, plan.chosen.date, plan.reasons)
```

## 它是怎么工作的

```text
                ┌─────────────────────────────┐
                │  PartyRequest 人数/日期/场合 │
                └──────────────┬──────────────┘
                               ▼
 query-party-city ──► 城市匹配 ──► query-party-store ──► 门店选择
                                                    │
                            query-partystore-date ◄──┘
                                    │ 日期评分（周末优先）
                                    ▼
                        query-partystore-session
                                    │ 场次评分（下午场/容量/预算）
                                    ▼
                          PartyPlan（含全部理由）
                                    │
                 render ──► markdown │ json │ html 邀请函
                                    ▼
                     book()  ── dry-run ──► --confirm 才真下单
```

设计取舍：

- **纯标准库**：零第三方依赖，`pip install` 什么都不装也能跑
- **可解释**：每个推荐都带 `reasons`，不是一个黑盒分数
- **安全默认**：`party-order-create` 必须显式 `--confirm`；LLM 模式里下单调用会被拦截
- **防御式解析**：MCP 响应字段未完全文档化，所有解析器兼容多种键名（`cityId`/`id`、`startTime`/`start`……）
- **离线可测**：`ReplayTransport` 回放录制的真实响应，32 个测试不碰网络

## 测试

```bash
python -m unittest discover -s tests -v
# Ran 32 tests - OK
```

覆盖：MCP 协议握手 / SSE 解析 / 401·429 错误映射 / isError 处理、规划决策（周末优先、容量过滤、预算惩罚、指定日期、团建傍晚场）、CLI 全链路、渲染器、防御式解析。

## 项目结构

```text
mcd-party-planner/
├── mcdparty/
│   ├── mcp_client.py    # MCP Streamable-HTTP 客户端（JSON-RPC 2.0）
│   ├── planner.py       # 5 工具决策链 + 可解释评分
│   ├── render.py        # markdown / json / html 邀请函
│   ├── replay.py        # 离线回放传输层（测试 & demo）
│   ├── record.py        # 录制真实 MCP 响应为 fixtures
│   ├── chat.py          # 可选 LLM 工具调用模式
│   └── cli.py           # 命令行入口
├── tests/               # 32 个单元测试 + 录制 fixtures
├── skill/SKILL.md       # WorkBuddy Skill 打包
└── demo/                # 演示输出
```

## 路线图

- [ ] 接入 `campaign-calendar`：派对推荐叠加当月营销活动
- [ ] 接入 `query-nearby-stores`：按定位自动选最近可办派对的餐厅
- [ ] 邀请函支持自定义主题色与二维码

## 声明

本项目为独立开发的参赛作品，**非麦当劳官方产品**；输出仅供参考，不构成任何专业建议。餐品、价格与供应状态以麦当劳官方渠道实时结果为准。使用麦当劳 MCP 服务须遵守[MCP 服务规则](https://cdn.mcd.cn/cms/pages/MCPServerRules.html)。

License: [MIT](./LICENSE)
