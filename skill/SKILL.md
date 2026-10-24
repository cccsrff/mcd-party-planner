---
name: mcd-party-planner
description: 麦麦派对策划师 - 在麦当劳办派对/生日会/团建。基于麦当劳官方 MCP 的主题活动（party）工具链，一条命令完成「城市→门店→日期→场次」查询并给出带理由的推荐，可生成 HTML 邀请函；默认 dry-run，确认后才下单。当用户提到麦当劳派对、生日会、团建、主题活动预订时使用。
---

# 麦麦派对策划师（McParty Planner）

帮用户在麦当劳办派对：查询可约城市/门店/日期/场次，给出可解释的推荐，生成邀请函，按需下单。

## 前置条件

- 麦当劳 MCP Token：到 https://open.mcd.cn/mcp 手机号登录，控制台「激活」领取（免费）
- 本 Skill 的 CLI：`mcd-party-planner/`（纯标准库 Python，无第三方依赖）

Token 通过环境变量注入：`MCD_MCP_TOKEN`。也可以直接在 WorkBuddy 里配置自定义连接器
（`https://mcp.mcd.cn` + `Authorization: Bearer <token>`），用对话方式驱动。

## 使用方式

在本 Skill 目录下执行（或 `pip install .` 后用 `mcdparty` 命令）：

```bash
# 1. 列出可办派对的城市
python -m mcdparty cities --keyword 杭州

# 2. 生成策划案（默认 dry-run，不会下单）
python -m mcdparty plan --city 杭州 --occasion birthday --size 12

# 3. 生成 HTML 邀请函
python -m mcdparty plan --city 杭州 --date 2026-11-08 --format html -o invite.html

# 4. 确认无误后真正下单
python -m mcdparty book --city 杭州 --date 2026-11-08 --size 12 --confirm
```

## 工作规则（给 Agent 的铁律）

1. **查询与下单分离**：`plan` 可以自由执行；`book` 默认 dry-run，只有在用户明确说「确认/下单/订这个」时才追加 `--confirm`。
2. **先看理由再推荐**：输出里的「为什么选这一场」必须原样转述给用户，不允许只给结论。
3. **日期以 MCP 实时数据为准**：不要用训练数据里的门店/日期信息回答，一律以 `plan` 的实际返回为准。
4. **Token 保密**：不要把 `MCD_MCP_TOKEN` 的值写进任何文件或回复。
5. **失败处理**：401 → 让用户检查/重新领取 Token；429 → 稍后重试，不要连续轰炸。

##  occasions 参考

| 场合 | 行为差异 |
| --- | --- |
| `birthday` 生日会 | 优先周末 + 下午场（小朋友作息） |
| `team` 团建 | 优先周末 + 傍晚场（下班后） |
| `family` 家庭聚会 | 优先周末，场次不限 |
| `tasting` 品鉴会 | 按可约日期顺序 |

## 离线演示（无 Token）

```bash
python -m mcdparty demo --city 杭州 --occasion birthday --size 12
```

仓库 `tests/fixtures/` 内为录制的真实 MCP 响应，demo 与单元测试（`python -m unittest discover -s tests`，32 个用例）均离线可跑。
