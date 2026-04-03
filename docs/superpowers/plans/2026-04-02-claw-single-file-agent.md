# Claw 单文件 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `claw.py` 单文件 Python Agent，支持 OpenAI-compatible LLM、5种内置工具、Skills懒加载、Memory自动总结，通过 console 交互。

**Architecture:** 单文件顺序结构，无类封装。流式 LLM 调用 + 工具执行循环（最多40轮），退出时自动提炼记忆写回 memory.md。System prompt 由 agent.md + memory.md + skills摘要(yaml) + 环境快照拼接而成，skill.md 全文按需懒加载。

**Tech Stack:** Python 3.11+, openai>=1.0.0, requests>=2.28.0

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `/Users/moka/project/work/mini_claw/claw.py` | 主程序（单文件，全部逻辑） |
| `/Users/moka/project/work/mini_claw/tests/test_claw.py` | 单元测试（纯函数：工具、配置、prompt组装；跳过 LLM/网络调用） |

**Workspace 约定（运行目录下）：**
```
./agent.md       # 角色指令（不存在用内置默认）
./memory.md      # 持久记忆（不存在自动创建）
./claw.json      # 模型+skills配置
./skills/<name>/skill.md  # 各 skill
```

---

## Task 1: 脚手架 — 导入、常量、PROVIDER_ENV_KEYS

**Files:**
- Create: `/Users/moka/project/work/mini_claw/claw.py`
- Create: `/Users/moka/project/work/mini_claw/tests/test_claw.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p /Users/moka/project/work/mini_claw/tests
touch /Users/moka/project/work/mini_claw/tests/__init__.py
```

- [ ] **Step 2: 写第一个失败测试**

```python
# /Users/moka/project/work/mini_claw/tests/test_claw.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_constants_exist():
    import claw
    assert claw.MAX_TOOL_ITERATIONS == 40
    assert claw.EXEC_TIMEOUT == 60
    assert claw.EXEC_OUTPUT_LIMIT == 8000

def test_provider_env_keys():
    import claw
    assert claw.PROVIDER_ENV_KEYS["openai"] == "OPENAI_API_KEY"
    assert claw.PROVIDER_ENV_KEYS["deepseek"] == "DEEPSEEK_API_KEY"
    assert claw.PROVIDER_ENV_KEYS["anthropic"] == "ANTHROPIC_API_KEY"
    assert claw.PROVIDER_ENV_KEYS["qwen"] == "DASHSCOPE_API_KEY"
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v
```
预期：`ModuleNotFoundError: No module named 'claw'`

- [ ] **Step 4: 创建 claw.py 脚手架**

```python
#!/usr/bin/env python3
"""Claw — 单文件 AI Agent"""

# ── 标准库
import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime

# ── 第三方
try:
    from openai import OpenAI
except ImportError:
    print("请先安装依赖: pip install openai requests")
    sys.exit(1)

# ── 常量
MAX_TOOL_ITERATIONS = 40
EXEC_TIMEOUT = 60
EXEC_OUTPUT_LIMIT = 8000

# ── Provider → 环境变量映射
PROVIDER_ENV_KEYS: dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek":  "DEEPSEEK_API_KEY",
    "qwen":      "DASHSCOPE_API_KEY",
    "moonshot":  "MOONSHOT_API_KEY",
    "zhipu":     "ZHIPUAI_API_KEY",
    "baidu":     "QIANFAN_API_KEY",
}
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v
```
预期：2 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git init && git add . && git commit -m "feat(claw): scaffold with constants and provider env key mapping"
```

---

## Task 2: 内置工具函数 + TOOLS_SCHEMA + execute_tool

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`（追加工具区块）
- Modify: `/Users/moka/project/work/mini_claw/tests/test_claw.py`

注意：`web_fetch` 和 `web_search` 需要网络，**不写单元测试**，只测试 exec/read/write 和 schema结构。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_claw.py

def test_exec_tool_success():
    import claw
    result = claw.exec_tool("echo hello")
    assert "hello" in result

def test_exec_tool_timeout():
    import claw
    result = claw.exec_tool("sleep 100")
    assert "超时" in result

def test_read_file_exists(tmp_path):
    import claw
    f = tmp_path / "test.txt"
    f.write_text("内容abc")
    assert claw.read_file(str(f)) == "内容abc"

def test_read_file_missing():
    import claw
    result = claw.read_file("/nonexistent/xyz.txt")
    assert "错误" in result

def test_write_file(tmp_path):
    import claw
    path = str(tmp_path / "out.txt")
    result = claw.write_file(path, "写入内容")
    assert "写入" in result
    with open(path) as f:
        assert f.read() == "写入内容"

def test_execute_tool_dispatch():
    import claw
    result = claw.execute_tool("exec", {"command": "echo dispatch_ok"})
    assert "dispatch_ok" in result

def test_execute_tool_unknown():
    import claw
    result = claw.execute_tool("unknown_tool", {})
    assert "未知工具" in result

def test_tools_schema_structure():
    import claw
    names = {t["function"]["name"] for t in claw.TOOLS_SCHEMA}
    assert names == {"exec", "read_file", "write_file", "web_fetch", "web_search"}
    for tool in claw.TOOLS_SCHEMA:
        assert tool["type"] == "function"
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "tool or schema or dispatch or read or write or exec"
```
预期：全部 FAILED

- [ ] **Step 3: 实现工具函数**

追加到 `claw.py`（PROVIDER_ENV_KEYS 之后）：

```python
# ── 工具函数

def exec_tool(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=EXEC_TIMEOUT
        )
        output = (result.stdout or "") + (result.stderr or "")
        if len(output) > EXEC_OUTPUT_LIMIT:
            output = output[:EXEC_OUTPUT_LIMIT] + f"\n...[截断，共{len(output)}字符]"
        return output or "(无输出)"
    except subprocess.TimeoutExpired:
        return f"[超时: 命令执行超过 {EXEC_TIMEOUT}s]"
    except Exception as e:
        return f"[错误: {e}]"


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[错误: {e}]"


def write_file(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已写入 {path}"
    except Exception as e:
        return f"[错误: {e}]"


def web_fetch(url: str) -> str:
    try:
        import re
        import requests
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:EXEC_OUTPUT_LIMIT]
    except Exception as e:
        return f"[错误: {e}]"


def _brave_search(query: str, api_key: str) -> str:
    try:
        import requests
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        lines = [f"**{r['title']}**\n{r['url']}\n{r.get('description', '')}" for r in results]
        return "\n\n".join(lines) or "无结果"
    except Exception as e:
        return f"[搜索错误: {e}]"


def _ddg_search(query: str) -> str:
    try:
        import requests
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        parts = []
        if data.get("AbstractText"):
            parts.append(f"**摘要**: {data['AbstractText']}")
        for r in data.get("RelatedTopics", [])[:5]:
            if isinstance(r, dict) and r.get("Text"):
                parts.append(f"- {r['Text']}\n  {r.get('FirstURL', '')}")
        return "\n\n".join(parts) or "无即时结果（建议设置 BRAVE_API_KEY）"
    except Exception as e:
        return f"[搜索错误: {e}]"


def web_search(query: str) -> str:
    brave_key = os.environ.get("BRAVE_API_KEY")
    return _brave_search(query, brave_key) if brave_key else _ddg_search(query)


# ── 工具 Schema（OpenAI tools 格式）

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "exec",
            "description": "执行 shell 命令，返回 stdout+stderr",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "要执行的 shell 命令"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入文件（覆盖）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "抓取网页内容，返回纯文本正文",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "要抓取的 URL"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网页。优先使用 BRAVE_API_KEY，无则用 DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
        },
    },
]


# ── 工具分发

def execute_tool(name: str, args: dict) -> str:
    if name == "exec":
        return exec_tool(args.get("command", ""))
    elif name == "read_file":
        return read_file(args.get("path", ""))
    elif name == "write_file":
        return write_file(args.get("path", ""), args.get("content", ""))
    elif name == "web_fetch":
        return web_fetch(args.get("url", ""))
    elif name == "web_search":
        return web_search(args.get("query", ""))
    else:
        return f"[未知工具: {name}]"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "tool or schema or dispatch or read or write or exec"
```
预期：全部 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add built-in tools and TOOLS_SCHEMA"
```

---

## Task 3: 配置加载 + API Key + 环境快照

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`
- Modify: `/Users/moka/project/work/mini_claw/tests/test_claw.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_claw.py

def test_load_config_defaults(tmp_path):
    import claw
    config = claw.load_config(str(tmp_path))
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o"
    assert config["active_skills"] == []

def test_load_config_from_file(tmp_path):
    import claw, json
    (tmp_path / "claw.json").write_text(json.dumps({
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "active_skills": ["github"]
    }))
    config = claw.load_config(str(tmp_path))
    assert config["provider"] == "deepseek"
    assert config["active_skills"] == ["github"]

def test_get_api_key_found(monkeypatch):
    import claw
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    assert claw.get_api_key("deepseek") == "test-key-123"

def test_get_api_key_missing(monkeypatch):
    import claw
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    try:
        claw.get_api_key("deepseek")
        assert False, "should raise"
    except ValueError as e:
        assert "DEEPSEEK_API_KEY" in str(e)

def test_get_api_key_unknown_provider(monkeypatch):
    import claw
    monkeypatch.setenv("MYCO_API_KEY", "xyz")
    assert claw.get_api_key("myco") == "xyz"

def test_get_system_context_contains_fields():
    import claw
    ctx = claw.get_system_context()
    assert "工作目录" in ctx
    assert "Python" in ctx
    assert "时间" in ctx
    assert "系统" in ctx
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "config or api_key or system_context"
```
预期：全部 FAILED

- [ ] **Step 3: 实现配置加载、API key、环境快照**

追加到 `claw.py`（execute_tool 之后）：

```python
# ── 配置加载

def load_config(workspace: str) -> dict:
    defaults = {
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "active_skills": [],
    }
    config_path = os.path.join(workspace, "claw.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            defaults.update(json.load(f))
    return defaults


def get_api_key(provider: str) -> str:
    env_var = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
    key = os.environ.get(env_var)
    if not key:
        raise ValueError(f"未找到 API key：请设置环境变量 {env_var}")
    return key


# ── 环境快照

def get_system_context() -> str:
    cwd = os.getcwd()
    try:
        entries = []
        for name in sorted(os.listdir(cwd))[:50]:
            full = os.path.join(cwd, name)
            if os.path.isdir(full):
                entries.append(f"  {name}/ [目录]")
            else:
                size = os.path.getsize(full)
                size_str = f"{size // 1024}KB" if size >= 1024 else f"{size}B"
                entries.append(f"  {name} ({size_str})")
        dir_listing = "\n".join(entries) or "  (空目录)"
    except Exception:
        dir_listing = "  (无法读取目录)"

    return (
        f"## 当前环境\n"
        f"- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 系统: {platform.system()} {platform.release()} ({platform.machine()})\n"
        f"- Python: {sys.version.split()[0]}\n"
        f"- Shell: {os.environ.get('SHELL', 'unknown')}\n"
        f"- 用户: {os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))}\n"
        f"- 工作目录: {cwd}\n"
        f"- 目录内容:\n{dir_listing}"
    )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "config or api_key or system_context"
```
预期：全部 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add config loading, api key resolution, env snapshot"
```

---

## Task 4: System Prompt 组装（agent.md + memory.md + skills懒加载 + 环境快照）

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`
- Modify: `/Users/moka/project/work/mini_claw/tests/test_claw.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_claw.py

def test_parse_skill_meta_with_frontmatter():
    import claw
    content = """---
name: github
description: "Interact with GitHub using gh CLI"
---
# GitHub Skill
full content..."""
    name, desc = claw._parse_skill_meta(content, "fallback")
    assert name == "github"
    assert "GitHub" in desc

def test_parse_skill_meta_fallback():
    import claw
    name, desc = claw._parse_skill_meta("no frontmatter", "myskill")
    assert name == "myskill"
    assert desc == ""

def test_load_system_prompt_includes_agent_md(tmp_path):
    import claw
    (tmp_path / "agent.md").write_text("你是专业助手")
    prompt = claw.load_system_prompt(str(tmp_path), {"active_skills": []}, "## 环境\n...")
    assert "你是专业助手" in prompt

def test_load_system_prompt_default_when_no_agent_md(tmp_path):
    import claw
    prompt = claw.load_system_prompt(str(tmp_path), {"active_skills": []}, "")
    assert len(prompt) > 0

def test_load_system_prompt_includes_memory(tmp_path):
    import claw
    (tmp_path / "memory.md").write_text("用户喜欢简洁风格")
    prompt = claw.load_system_prompt(str(tmp_path), {"active_skills": []}, "")
    assert "用户喜欢简洁风格" in prompt
    assert "记忆" in prompt

def test_load_system_prompt_skills_lazy(tmp_path):
    import claw
    skill_dir = tmp_path / "skills" / "github"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("""---
name: github
description: "Interact with GitHub"
---
# Full content that should NOT appear
""")
    prompt = claw.load_system_prompt(
        str(tmp_path), {"active_skills": ["github"]}, ""
    )
    assert "github" in prompt
    assert "Interact with GitHub" in prompt
    assert "Full content that should NOT appear" not in prompt
    assert "skill.md" in prompt

def test_load_system_prompt_missing_skill_warns(tmp_path, capsys):
    import claw
    claw.load_system_prompt(str(tmp_path), {"active_skills": ["nonexistent"]}, "")
    captured = capsys.readouterr()
    assert "警告" in captured.err
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "system_prompt or skill_meta"
```
预期：全部 FAILED

- [ ] **Step 3: 实现 system prompt 组装**

追加到 `claw.py`（get_system_context 之后）：

```python
# ── 默认 agent 指令
DEFAULT_AGENT_MD = """你是一个智能助手 Claw。你擅长使用工具解决复杂问题。
遇到需要信息时，主动使用工具获取，而不是等用户提供。
需要使用某个 skill 时，先用 read_file 读取对应的 skill.md 获取完整指南，然后再执行。"""


def _parse_skill_meta(content: str, fallback_name: str) -> tuple[str, str]:
    """从 skill.md YAML frontmatter 中提取 name 和 description。"""
    name, description = fallback_name, ""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            for line in content[3:end].splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')
    return name, description


def load_system_prompt(workspace: str, config: dict, system_context: str) -> str:
    parts = []

    # 1. agent.md
    agent_path = os.path.join(workspace, "agent.md")
    if os.path.exists(agent_path):
        parts.append(open(agent_path, "r", encoding="utf-8").read())
    else:
        parts.append(DEFAULT_AGENT_MD)

    # 2. memory.md
    memory_path = os.path.join(workspace, "memory.md")
    if os.path.exists(memory_path):
        memory_content = open(memory_path, "r", encoding="utf-8").read().strip()
        if memory_content:
            parts.append(f"## 记忆\n{memory_content}")

    # 3. Skills 懒加载（只注入 name + description + 路径）
    active_skills = config.get("active_skills", [])
    if active_skills:
        skill_lines = []
        for skill_name in active_skills:
            skill_path = os.path.join(workspace, "skills", skill_name, "skill.md")
            if not os.path.exists(skill_path):
                print(f"[警告] Skill 未找到: {skill_path}", file=sys.stderr)
                continue
            content = open(skill_path, "r", encoding="utf-8").read()
            name, desc = _parse_skill_meta(content, skill_name)
            skill_lines.append(
                f"  - name: {name}\n"
                f"    description: {desc}\n"
                f"    file: skills/{skill_name}/skill.md"
            )
        if skill_lines:
            parts.append(
                "## Skills\n"
                "以下 skills 可用。需要时先用 read_file 读取对应 file 获取完整指南。\n"
                "```yaml\nskills:\n" + "\n".join(skill_lines) + "\n```"
            )

    # 4. 环境快照
    if system_context:
        parts.append(system_context)

    return "\n\n".join(parts)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "system_prompt or skill_meta"
```
预期：全部 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add system prompt assembly with lazy skill loading"
```

---

## Task 5: Agent 执行循环（流式 LLM + 工具循环）

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`

注意：`run_agent_loop` 需要真实 LLM，不写单元测试，在 Task 7 冒烟测试时人工验证。

- [ ] **Step 1: 实现 run_agent_loop**

追加到 `claw.py`（load_system_prompt 之后）：

```python
# ── Agent 执行循环

def run_agent_loop(client: "OpenAI", model: str, messages: list) -> str:
    """流式 LLM 调用 + 工具执行循环。返回最终文字回复。"""
    for _ in range(MAX_TOOL_ITERATIONS):
        collected_content = ""
        collected_tool_calls: list[dict] = []
        finish_reason = None

        with client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_SCHEMA,
            stream=True,
        ) as stream:
            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                delta = choice.delta

                if delta.content:
                    print(delta.content, end="", flush=True)
                    collected_content += delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        while tc.index >= len(collected_tool_calls):
                            collected_tool_calls.append(
                                {"id": "", "type": "function",
                                 "function": {"name": "", "arguments": ""}}
                            )
                        ctc = collected_tool_calls[tc.index]
                        if tc.id:
                            ctc["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                ctc["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                ctc["function"]["arguments"] += tc.function.arguments

        if collected_content:
            print()

        # 无工具调用 → 本轮结束
        if not collected_tool_calls:
            messages.append({"role": "assistant", "content": collected_content})
            return collected_content

        # 追加 assistant 消息（含 tool_calls）
        messages.append({
            "role": "assistant",
            "content": collected_content or None,
            "tool_calls": collected_tool_calls,
        })

        # 执行所有工具，追加结果
        for tc in collected_tool_calls:
            tool_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            args_preview = json.dumps(args, ensure_ascii=False)
            if len(args_preview) > 80:
                args_preview = args_preview[:80] + "..."
            print(f"\n[🔧 {tool_name}: {args_preview}]")

            result = execute_tool(tool_name, args)

            result_preview = result[:200].replace("\n", " ")
            print(f"→ {result_preview}{'...' if len(result) > 200 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    return "[达到最大工具调用次数]"
```

- [ ] **Step 2: 语法检查**

```bash
cd /Users/moka/project/work/mini_claw && python -c "import claw; print('OK')"
```
预期：`OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add streaming agent loop with tool execution"
```

---

## Task 6: Memory 自动总结

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`
- Modify: `/Users/moka/project/work/mini_claw/tests/test_claw.py`

注意：使用 mock client 测试，不需要真实 LLM。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_claw.py

def test_summarize_memory_writes_file(tmp_path):
    import claw

    class FakeMessage:
        content = "提炼后的记忆内容"
    class FakeChoice:
        message = FakeMessage()
    class FakeResponse:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        chat = FakeChat()

    (tmp_path / "memory.md").write_text("旧记忆")
    session_history = [
        {"role": "user", "content": "帮我分析数据"},
        {"role": "assistant", "content": "分析完成"},
    ]
    claw.summarize_memory(FakeClient(), "test-model", str(tmp_path), session_history)
    assert (tmp_path / "memory.md").read_text() == "提炼后的记忆内容"

def test_summarize_memory_creates_if_missing(tmp_path):
    import claw

    class FakeMessage:
        content = "新记忆"
    class FakeChoice:
        message = FakeMessage()
    class FakeResponse:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        chat = FakeChat()

    claw.summarize_memory(FakeClient(), "m", str(tmp_path), [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    assert (tmp_path / "memory.md").read_text() == "新记忆"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "memory"
```
预期：FAILED（AttributeError: module 'claw' has no attribute 'summarize_memory'）

- [ ] **Step 3: 实现 summarize_memory**

追加到 `claw.py`（run_agent_loop 之后）：

```python
# ── Memory 自动总结

def summarize_memory(client: "OpenAI", model: str, workspace: str, session_history: list) -> None:
    """提炼本次对话关键信息，写回 memory.md。"""
    memory_path = os.path.join(workspace, "memory.md")
    current_memory = ""
    if os.path.exists(memory_path):
        current_memory = open(memory_path, "r", encoding="utf-8").read()

    conv_parts = []
    for msg in session_history:
        role, content = msg.get("role", ""), msg.get("content", "")
        if role == "user" and content:
            conv_parts.append(f"用户: {content}")
        elif role == "assistant" and content:
            conv_parts.append(f"助手: {str(content)[:500]}")

    prompt = (
        "你是一个记忆管理助手。根据以下对话历史，提炼出值得长期记住的关键信息"
        "（用户偏好、项目背景、重要事实），合并到现有 memory.md 内容中。"
        "忽略本次任务的临时操作细节。直接输出更新后的 memory.md 全文，不要任何额外说明。\n\n"
        f"现有 memory.md:\n{current_memory or '(空)'}\n\n"
        f"本次对话历史:\n{chr(10).join(conv_parts)}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        new_memory = response.choices[0].message.content.strip()
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(new_memory)
    except Exception as e:
        print(f"[警告] 记忆更新失败: {e}", file=sys.stderr)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v -k "memory"
```
预期：2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add memory auto-summarization on exit"
```

---

## Task 7: main() REPL 主循环 + CLI 入口 + 全量测试

**Files:**
- Modify: `/Users/moka/project/work/mini_claw/claw.py`
- Create: `/Users/moka/project/work/mini_claw/agent.md`（示例）
- Create: `/Users/moka/project/work/mini_claw/claw.json`（示例）

- [ ] **Step 1: 实现 main() 和 CLI 入口**

追加到 `claw.py` 末尾：

```python
# ── 主循环

def main() -> None:
    parser = argparse.ArgumentParser(description="Claw — 单文件 AI Agent")
    parser.add_argument("--workspace", default=os.getcwd(),
                        help="Workspace 目录（默认：当前目录）")
    parser.add_argument("--model", help="模型名称（覆盖 claw.json）")
    parser.add_argument("--base-url", dest="base_url",
                        help="API base URL（覆盖 claw.json）")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace)
    config = load_config(workspace)
    if args.model:
        config["model"] = args.model
    if args.base_url:
        config["base_url"] = args.base_url

    try:
        api_key = get_api_key(config["provider"])
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=config["base_url"])
    model = config["model"]

    # 确保 memory.md 存在
    memory_path = os.path.join(workspace, "memory.md")
    if not os.path.exists(memory_path):
        open(memory_path, "w").close()

    system_context = get_system_context()
    system_prompt = load_system_prompt(workspace, config, system_context)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    session_history: list[dict] = []

    skills_info = (
        f"Skills: {', '.join(config['active_skills'])}"
        if config["active_skills"] else "Skills: 无"
    )
    print(f"\n🤖 Claw Agent 就绪 ({model})")
    print(skills_info)
    print("输入 exit 或 Ctrl+C 退出")
    print("─" * 40)

    try:
        while True:
            try:
                user_input = input("\n你: ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "退出"):
                break

            messages.append({"role": "user", "content": user_input})
            session_history.append({"role": "user", "content": user_input})

            print("\n助手: ", end="", flush=True)
            try:
                response = run_agent_loop(client, model, messages)
                session_history.append({"role": "assistant", "content": response})
            except KeyboardInterrupt:
                print("\n[中断]")
                break
            except Exception as e:
                print(f"\n[错误: {e}]")

    except KeyboardInterrupt:
        pass

    # 退出时触发 memory 总结（至少1轮完整对话）
    if len(session_history) >= 2:
        print("\n💾 正在更新记忆...")
        summarize_memory(client, model, workspace, session_history)
    print("再见！")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建示例 agent.md**

写入 `/Users/moka/project/work/mini_claw/agent.md`：

```markdown
# Claw Agent

你是一个高效的命令行助手。你的特点：
- 主动使用工具获取信息，不依赖用户描述
- 遇到代码/文件任务，直接读取文件再操作
- 遇到网络信息需求，直接用 web_search 或 web_fetch 获取
- 操作前先理解当前环境（目录结构、文件内容）
- 回答简洁，优先给出可执行的结果
```

- [ ] **Step 3: 创建示例 claw.json**

写入 `/Users/moka/project/work/mini_claw/claw.json`：

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com/v1",
  "active_skills": []
}
```

- [ ] **Step 4: 语法全量检查**

```bash
cd /Users/moka/project/work/mini_claw && python -c "import claw; print('导入成功')"
```
预期：`导入成功`

- [ ] **Step 5: 运行全量测试**

```bash
cd /Users/moka/project/work/mini_claw && python -m pytest tests/test_claw.py -v
```
预期：全部 passed

- [ ] **Step 6: --help 冒烟测试**

```bash
cd /Users/moka/project/work/mini_claw && python claw.py --help
```
预期输出包含：`--workspace`, `--model`, `--base-url`

- [ ] **Step 7: Commit**

```bash
cd /Users/moka/project/work/mini_claw && git add . && git commit -m "feat(claw): add main REPL loop, CLI entry, example config files"
```

---

## 自检结果

| 设计需求 | 对应 Task | 测试覆盖 |
|---------|----------|---------|
| 单文件 claw.py | Task 1-7 | 导入检查 |
| OpenAI-compatible + provider→env映射 | Task 1, 3 | test_get_api_key_* |
| exec/read_file/write_file | Task 2 | 单元测试 |
| web_fetch/web_search | Task 2 | 仅 schema 结构测试（需网络，跳过实现测试） |
| Skills 懒加载（yaml摘要，按需读全文） | Task 4 | test_load_system_prompt_skills_lazy |
| Memory 自动总结退出时触发 | Task 6 | mock client 测试 |
| 环境快照注入 system prompt | Task 3, 4 | test_get_system_context_* |
| 流式输出 + 工具执行打印 | Task 5 | 无（需真实LLM） |
| claw.json + agent.md + memory.md + skills/ | Task 3, 4, 7 | 配置测试 |
| console REPL 交互 | Task 7 | --help 冒烟测试 |
