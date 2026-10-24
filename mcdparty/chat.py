"""Optional LLM-driven chat mode.

When OPENAI-compatible credentials are present (LLM_API_KEY, LLM_BASE_URL,
LLM_MODEL), ``mcdparty chat`` runs a tool-calling loop against the real MCP
server: the model picks party tools freely, the client executes them.

Without credentials the deterministic planner (``mcdparty plan``) is used -
the Skill never *requires* an LLM key to work.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

from .mcp_client import DEFAULT_URL, MCPClient

SYSTEM_PROMPT = """你是「麦麦派对策划师」，帮用户在麦当劳办派对/团建/生日会。
可用工具来自麦当劳官方 MCP。流程：query-party-city 选城市 → query-party-store 选门店 →
query-partystore-date 选日期 → query-partystore-session 选场次 →（用户确认后）party-order-create 下单。
没拿到用户明确确认前，绝不调用 party-order-create。用简洁中文回复，给出推荐并说明理由。"""


def _llm_chat(messages, tools, base_url, api_key, model):
    payload = {
        "model": model,
        "messages": messages,
        "tools": [
            {"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            }} for t in tools
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_chat(client: MCPClient) -> int:
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "")
    if not (api_key and base_url and model):
        print("未配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL，"
              "请使用确定性模式：python -m mcdparty plan --city 杭州", file=sys.stderr)
        return 2

    tools = client.list_tools()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("麦麦派对策划师（输入 quit 退出）")
    while True:
        try:
            user = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.lower() in ("quit", "exit", "q"):
            break
        messages.append({"role": "user", "content": user})
        data = _llm_chat(messages, tools, base_url, api_key, model)
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            reply = message.get("content", "")
            print(f"策划师 > {reply}")
            messages.append({"role": "assistant", "content": reply})
            continue
        messages.append(message)
        for call in tool_calls:
            fn = call["function"]
            name = fn["name"]
            arguments = json.loads(fn.get("arguments") or "{}")
            if name == "party-order-create":
                print(f"策划师 > [已拦截] 下单需用户明确确认：{json.dumps(arguments, ensure_ascii=False)}")
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": "blocked: awaiting explicit user confirmation"})
                continue
            result = client.call_tool(name, arguments)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
        follow_up = _llm_chat(messages, tools, base_url, api_key, model)
        reply = follow_up["choices"][0]["message"].get("content", "")
        print(f"策划师 > {reply}")
        messages.append({"role": "assistant", "content": reply})
    return 0
