# 麦麦派对策划师

[![test](https://github.com/cccsrff/mcd-party-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/cccsrff/mcd-party-planner/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

麦当劳 MCP 开放了 33 个工具。外卖、优惠券、积分商城是红海；只有 5 个工具属于**主题活动（派对）**，而它恰好是决策链最长的一条：城市 → 门店 → 日期 → 场次，4 次查询加人工比价。

这个 Skill 把 4 次查询压成 1 条命令，给出选场结论与理由，并生成一张可转发的邀请函。下单独立成第 2 条命令，默认 dry-run。

![邀请函](docs/invite.png)

## 为什么是派对

- **决策最长**：4 个维度 × 多个候选，人工试错成本最高
- **最少人做**：33 个工具里只有 5 个派对工具，赛道几乎空白
- **有交付物**：最终产出是一张能发给家人的邀请函，而不只是一段 JSON

## 快速开始（不需要 Token）

```bash
git clone https://github.com/cccsrff/mcd-party-planner.git
cd mcd-party-planner
python -m mcdparty demo
```

输出见 [demo/demo.md](demo/demo.md)。这是**离线回放**：内置 fixtures 复刻了 MCP 响应结构，仅覆盖杭州 1 城 3 店 1 组日期，不是实时数据，也不会联网或下单。

生成邀请函网页：

```bash
python -m mcdparty demo --format html -o invite.html
```

## 接入真实 MCP

1. 打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp)，手机号登录 → 右上角「控制台」→ 点「激活」→ 同意协议 → 复制 Token（免费）
2. 写入环境变量：

```bash
export MCD_MCP_TOKEN="你的 Token"
```

3. 查真实数据：

```bash
python -m mcdparty plan --city 杭州 --size 12
python -m mcdparty plan --city 杭州 --date 2026-11-08 --format html -o invite.html
```

也可以在 WorkBuddy / Cursor 等客户端里挂成 MCP 连接器，配置见 [mcp-config.example.json](mcp-config.example.json)。

## 命令

| 命令 | 作用 |
| --- | --- |
| `mcdparty tools` | 列出 MCP 全部工具（连通性自检） |
| `mcdparty cities --keyword 杭州` | 查询可办派对的城市 |
| `mcdparty plan --city 杭州 --size 12` | 4 次查询 + 选场结论，输出 markdown / json / html |
| `mcdparty book --city 杭州 --date ... --size 12` | 下单，默认 dry-run |
| `mcdparty demo` | 离线回放，无网络无 Token |

## 它做什么，不做什么

**场次评分是真正的算法**，规则写在 [planner.py](mcdparty/planner.py)，每条推荐都附理由：

| 条件 | 分值 |
| --- | --- |
| 周末场 | +3 |
| 生日/家庭 + 下午场，团建 + 傍晚场 | +2 |
| 容量 ≥ 预计人数 | +2（不足则 -5） |
| 人均价 ≤ 预算 | +1（超出则 -3） |

**门店与日期是最简启发式**：门店取列表首家（未按距离或评分排序），日期取最近周末。这两步没有评分，代码里也如实标注。补门店排序是下一步计划。

**下单安全边界**：

- `plan` 与 `book` 分离，`book` 默认 dry-run，不加 `--confirm` 不碰下单接口
- 指定日期不可约时**直接报错**，不会悄悄改期
- `--session` 可锁定你要的那一场，跳过重新评分——看到哪场就订哪场
- 城市不在可办列表时直接报错，不会替你换到别的城市

## 下单前需要知道

- `party-order-create` 只提交门店、日期、场次、人数，不含联系人与支付信息；订单状态与到店支付方式以麦当劳返回为准
- 麦当劳 MCP 有 `cancel-order`，本项目**尚未接入**取消流程
- 与直接用麦当劳 App 的区别：App 能订，但不会跨门店比场次、也不会解释为什么推荐这一场，更不会生成邀请函

## 安装（可选）

```bash
pip install .
mcdparty plan --city 杭州 --size 12
```

要求 Python 3.9+，无第三方依赖。

## 测试

```bash
python -m unittest discover -s tests
```

37 个用例，全部离线（无网络、无 Token），每次 push 由 GitHub Actions 跑一遍。覆盖 MCP 协议握手与 SSE 解析、401/429 错误映射、选场决策、严格日期、场次锁定、回放参数校验、CLI 与渲染。

## 项目结构

<details>
<summary>展开</summary>

```text
mcdparty/
  mcp_client.py   MCP Streamable-HTTP 客户端（JSON-RPC 2.0，纯标准库）
  planner.py      4 步查询 + 场次评分
  render.py       markdown / json / html
  replay.py       离线回放传输层（含 fixtures 参数校验）
  record.py       录制真实响应为 fixtures
  chat.py         可选的 LLM 工具调用模式
  cli.py          命令行入口
tests/            37 个用例 + fixtures
skill/SKILL.md    WorkBuddy Skill 打包
```

</details>

## 限制与声明

- 真实可约城市、门店、场次以 MCP 接口实时返回为准；内置 fixtures 只是杭州的一组示例
- 本项目为独立开发的参赛作品，非麦当劳官方产品；价格与余位以麦当劳官方渠道为准
- 使用麦当劳 MCP 服务须遵守 [MCP 服务规则](https://cdn.mcd.cn/cms/pages/MCPServerRules.html)

MIT License
