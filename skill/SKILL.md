---
name: mcd-party-planner
description: 麦麦派对策划师 - 在麦当劳办派对/生日会/团建。基于麦当劳官方 MCP 的主题活动工具链，一条命令完成城市→门店→日期→场次查询并给出选场理由，可生成 HTML 邀请函；下单默认 dry-run，确认后才执行。当用户提到麦当劳派对、生日会、团建、主题活动预订时使用。
---

# 麦麦派对策划师

## 前置条件

- 麦当劳 MCP Token：到 https://open.mcd.cn/mcp 手机号登录，控制台「激活」领取（免费）
- 本 Skill 的 CLI：`mcd-party-planner/`（纯标准库 Python，无第三方依赖）

Token 通过环境变量注入：`MCD_MCP_TOKEN`。也可以在客户端里配置自定义连接器
（`https://mcp.mcd.cn` + `Authorization: Bearer <token>`），用对话方式驱动。

## 使用方式

```bash
# 查询可办派对的城市
python -m mcdparty cities --keyword 杭州

# 生成策划案（默认 dry-run，不下单）
python -m mcdparty plan --city 杭州 --occasion birthday --size 12

# 生成 HTML 邀请函
python -m mcdparty plan --city 杭州 --date 2026-11-08 --format html -o invite.html

# 确认无误后下单
python -m mcdparty book --city 杭州 --date 2026-11-08 --session S102 --size 12 --confirm
```

## 工作规则

1. 查询与下单分离：`plan` 可自由执行；`book` 默认 dry-run，只有用户明确说「确认/下单/订这个」时才追加 `--confirm`。
2. 理由必须转述：输出里的「选择理由」需要原样告诉用户，不要只给结论。
3. 数据以 MCP 实时返回为准，不要用训练数据里的门店或日期回答。
4. Token 保密：不要把 `MCD_MCP_TOKEN` 的值写进任何文件或回复。
5. 失败处理：401 让用户检查 Token；429 稍后重试，不要连续请求。
6. 城市或日期不可用时命令会直接报错，不要绕过报错自己编一个结果。

## 场合参考

| 场合 | 行为差异 |
| --- | --- |
| `birthday` 生日会 | 优先周末 + 下午场（小朋友作息） |
| `team` 团建 | 优先周末 + 傍晚场（下班后） |
| `family` 家庭聚会 | 优先周末，场次不限 |
| `tasting` 品鉴会 | 按可约日期顺序 |

## 离线演示

```bash
python -m mcdparty demo
```

内置 fixtures 仅覆盖杭州，用于演示与测试，不是实时数据。单元测试：`python -m unittest discover -s tests`。
