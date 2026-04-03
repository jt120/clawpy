#!/usr/bin/env python3
"""Claw — 单文件 AI Agent"""

# ── 标准库
import argparse
import json
import os
import platform
import subprocess
import sys
import traceback
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
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "zhipu": "ZHIPUAI_API_KEY",
    "baidu": "QIANFAN_API_KEY",
}

# ── 工具函数


def exec_tool(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=EXEC_TIMEOUT
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
        lines = [
            f"**{r['title']}**\n{r['url']}\n{r.get('description', '')}" for r in results
        ]
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
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"}
                },
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
                "properties": {
                    "url": {"type": "string", "description": "要抓取的 URL"}
                },
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
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
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


# ── 配置加载


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    # 验证必填字段
    required_fields = ["provider", "model", "base_url"]
    for field in required_fields:
        if field not in config:
            print(f"❌ 配置文件缺少必填字段: {field}")
            sys.exit(1)
    return config


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


def load_system_prompt(workspace: str, script_dir: str, config: dict, system_context: str) -> str:
    parts = []

    # 1. agent.md: workspace -> script_dir -> default
    agent_path = os.path.join(workspace, "agent.md")
    if not os.path.exists(agent_path):
        agent_path = os.path.join(script_dir, "agent.md")
    
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
            # Skills only load from script directory
            skill_paths = [
                os.path.join(script_dir, "skills", skill_name, "skill.md"),
                os.path.join(script_dir, "skills", skill_name, "SKILL.md"),
            ]
            
            skill_path = None
            for path in skill_paths:
                if os.path.exists(path):
                    skill_path = path
                    break
            
            if not skill_path:
                print(f"[警告] Skill 未找到: {skill_name}", file=sys.stderr)
                continue
            
            content = open(skill_path, "r", encoding="utf-8").read()
            name, desc = _parse_skill_meta(content, skill_name)
            # Use relative path for file reference based on where it was found
            if "skills" in skill_path[len(workspace):]:
                file_path = f"skills/{skill_name}/{os.path.basename(skill_path)}"
            else:
                file_path = f"skills/{skill_name}/{os.path.basename(skill_path)}"
            
            skill_lines.append(
                f"  - name: {name}\n"
                f"    description: {desc}\n"
                f"    file: {file_path}"
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
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
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
        messages.append(
            {
                "role": "assistant",
                "content": collected_content or None,
                "tool_calls": collected_tool_calls,
            }
        )

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

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
            )

    return "[达到最大工具调用次数]"


# ── Memory 自动总结


def summarize_memory(
    client: "OpenAI", model: str, workspace: str, session_history: list
) -> None:
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


# ── 主循环


def main() -> None:
    parser = argparse.ArgumentParser(description="Claw — 单文件 AI Agent")
    parser.add_argument(
        "--workspace", help="Workspace 目录（默认：当前目录）"
    )
    parser.add_argument("--model", help="模型名称（覆盖 claw.json）")
    parser.add_argument(
        "--base-url", dest="base_url", help="API base URL（覆盖 claw.json）"
    )
    parser.add_argument("query", nargs="*", help="查询内容（非交互式模式）")
    args = parser.parse_args()

    # Determine workspace: if not specified, use current directory, fall back to script directory for config
    current_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace = os.path.abspath(args.workspace) if args.workspace else current_dir
    config_path = os.path.join(workspace, "claw.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(script_dir, "claw.json")
        if not os.path.exists(config_path):
            print(f"❌ 配置文件不存在: {config_path}")
            print("请先在当前目录创建 claw.json 配置文件")
            sys.exit(1)
            
    config = load_config(config_path)
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

    # memory.md: workspace -> script_dir, create empty if none exists
    memory_path = os.path.join(workspace, "memory.md")
    if not os.path.exists(memory_path):
        script_memory_path = os.path.join(script_dir, "memory.md")
        if os.path.exists(script_memory_path):
            # Copy default memory from script directory to workspace
            with open(script_memory_path, "r", encoding="utf-8") as src_f:
                memory_content = src_f.read()
            with open(memory_path, "w", encoding="utf-8") as dst_f:
                dst_f.write(memory_content)
        else:
            # Create empty memory file if no default exists
            open(memory_path, "w").close()

    system_context = get_system_context()
    system_prompt = load_system_prompt(workspace, script_dir, config, system_context)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    session_history: list[dict] = []

    # Non-REPL mode: if query is provided, execute once and exit
    if args.query:
        user_input = " ".join(args.query)
        messages.append({"role": "user", "content": user_input})
        session_history.append({"role": "user", "content": user_input})
        
        print("助手: ", end="", flush=True)
        try:
            response = run_agent_loop(client, model, messages)
            session_history.append({"role": "assistant", "content": response})
        except Exception as e:
            print(f"\n[错误: {e}]")
            print("详细错误信息:")
            traceback.print_exc()
    
    # REPL mode
    else:
        skills_info = (
            f"Skills: {', '.join(config['active_skills'])}"
            if config["active_skills"]
            else "Skills: 无"
        )
        print(f"\n🤖 Claw Agent 就绪 ({model})")
        print(skills_info)
        print("输入 exit 或 Ctrl+C 退出")
        print("─" * 40)

        try:
            while True:
                try:
                    user_input = input("\nUser: ").strip()
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
                    print("详细错误信息:")
                    traceback.print_exc()

        except KeyboardInterrupt:
            pass

    # 退出时触发 memory 总结（至少1轮完整对话）
    if len(session_history) >= 2:
        print("\n💾 正在更新记忆...")
        summarize_memory(client, model, workspace, session_history)
    print("再见！")


if __name__ == "__main__":
    main()
