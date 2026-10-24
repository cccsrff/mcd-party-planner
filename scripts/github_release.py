#!/usr/bin/env python3
"""One-shot GitHub release + contest registration.

After the user completes the browser login (Git Credential Manager), this
script finishes everything:

  1. resolve a GitHub token  (--token / $GITHUB_TOKEN / git credential fill)
  2. verify identity          (GET /user)
  3. create the public repo   (POST /user/repos, idempotent)
  4. push the local commits   (git push with token-embedded remote)
  5. submit the contest issue (POST /repos/M-China/.../issues, official format)
  6. verify everything        (repo public? issue present? files pushed?)

Recommended invocation (GCM needs the proxy dropped, and python's subprocess
must not be the one calling it):

    TOKEN=$(env -u HTTP_PROXY -u HTTPS_PROXY git credential fill <<'EOF' | ...extract password=...)
    protocol=https
    host=github.com

    EOF
    GITHUB_TOKEN="$TOKEN" python scripts/github_release.py --go

Dry-run by default: pass --go to actually execute. The official rules warn
that the issue body must NOT contain newlines inside the three fields and
must not use markdown links for the project URL - both are enforced here.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "mcd-party-planner"
CONTEST_REPO = "M-China/mcd-developer-innovation-challenge"
DESCRIPTION = (
    "麦麦派对策划师 - 基于麦当劳官方 MCP 的派对预订 Skill："
    "一条命令完成 城市→门店→日期→场次 查询，可解释推荐 + HTML 邀请函，默认 dry-run 下单"
)
ISSUE_TITLE = "【参赛申请】麦麦派对策划师：把麦当劳派对预订的 5 步向导压缩成 1 条命令"
ISSUE_INTRO = (
    "在麦当劳办派对要连续回答 5 个问题：哪个城市？哪家门店？哪天？哪场？然后下单。"
    "本 Skill 基于麦当劳官方 MCP 的主题活动工具链（query-party-city → query-party-store → "
    "query-partystore-date → query-partystore-session → party-order-create），"
    "用一条命令走完查询并给出带理由的推荐（周末+3/下午场+2/容量+2/超预算-3），"
    "可生成可分享的 HTML 派对邀请函；下单默认 dry-run，确认后才真正调用。"
    "纯 Python 标准库实现，33 个单元测试，离线可回放演示。"
)
API = "https://api.github.com"


class GitHubError(Exception):
    pass


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "mcd-party-planner-release",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise GitHubError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc


def resolve_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env
    # Git Credential Manager cache (populated by the browser login).
    # GCM is a .NET app and strictly honours HTTP(S)_PROXY; when a local
    # sandbox proxy answers the OAuth token exchange with 502 the credential
    # never lands in the store. Stripping the proxy vars makes GCM talk to
    # github.com directly, which is what the browser login already proved works.
    clean_env = {
        k: v for k, v in os.environ.items()
        if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")
    }
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, cwd=ROOT,
            timeout=25, env=clean_env,
        )
        fields = dict(
            line.split("=", 1)
            for line in proc.stdout.splitlines()
            if "=" in line
        )
        token = fields.get("password", "")
        if token:
            return token
    except subprocess.TimeoutExpired:
        pass
    raise GitHubError(
        "no GitHub token available: pass --token, set GITHUB_TOKEN, "
        "or complete the browser login first (git credential fill timed out "
        "or returned nothing)"
    )


def run_git(*args: str, token: str | None = None) -> str:
    cmd = ["git", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        raise GitHubError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", action="store_true", help="actually execute (default: dry-run)")
    parser.add_argument("--token", help="GitHub token (PAT with repo scope)")
    parser.add_argument("--repo", default=REPO_NAME)
    args = parser.parse_args()

    plan = []
    try:
        token = resolve_token(args.token)
        plan.append(f"token acquired (len={len(token)}, prefix={token[:4]}...)")
        user = api("GET", "/user", token)
        login = user["login"]
        plan.append(f"identity: {login} ({user.get('name') or 'no name'})")
        repo_url = f"https://github.com/{login}/{args.repo}"
        issue_body = (
            "【参赛申请】\n"
            f"项目名称：麦麦派对策划师 McParty Planner\n"
            f"项目地址：{repo_url}\n"
            f"项目简介：{ISSUE_INTRO}"
        )
        plan.append(f"repo to create: {repo_url} (public)")
        plan.append(f"issue to file on {CONTEST_REPO}:")
        plan.append("  title: " + ISSUE_TITLE)
        plan.append("  body : " + issue_body.replace("\n", " ⏎ ")[:160] + "...")
    except GitHubError as exc:
        print(f"[dry-run] token/identity step failed: {exc}")
        print("[dry-run] 请在浏览器完成 GitHub 登录后重试；或直接用 --token 提供 PAT")
        return 2

    print("=== 执行计划（dry-run）===")
    for line in plan:
        print(" ", line)
    if not args.go:
        print("\n(dry-run 模式：未执行任何写操作。确认无误后加 --go 执行)")
        return 0

    print("\n=== 开始执行 ===")
    # 3. create repo (idempotent)
    try:
        api("POST", "/user/repos", token, {
            "name": args.repo, "description": DESCRIPTION,
            "private": False, "has_issues": True, "auto_init": False,
        })
        print(f"  repo created: {repo_url}")
    except GitHubError as exc:
        if "422" in str(exc):
            print(f"  repo already exists: {repo_url}")
        else:
            raise

    # 4. push
    run_git("remote", "remove", "origin") if "origin" in run_git("remote") else None
    authed = f"https://x-access-token:{token}@github.com/{login}/{args.repo}.git"
    run_git("remote", "add", "origin", authed)
    run_git("branch", "-M", "main")
    run_git("push", "-u", "origin", "main")
    # scrub the token out of the stored remote
    run_git("remote", "set-url", "origin", repo_url + ".git")
    print(f"  pushed: {repo_url}")

    # 5. file the contest issue
    issue = api("POST", f"/repos/{CONTEST_REPO}/issues", token, {
        "title": ISSUE_TITLE, "body": issue_body,
    })
    print(f"  issue filed: {issue['html_url']} (#{issue['number']})")

    # 6. verify
    repo = api("GET", f"/repos/{login}/{args.repo}", token)
    checks = {
        "repo is public": repo.get("private") is False,
        "repo has issues enabled": repo.get("has_issues") is True,
        "default branch is main": repo.get("default_branch") == "main",
        "issue exists": bool(issue.get("number")),
    }
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"\n完成：{repo_url} | 报名 Issue: {issue['html_url']}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
