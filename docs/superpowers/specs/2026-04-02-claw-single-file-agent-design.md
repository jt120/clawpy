# Claw 单文件 Agent 设计文档

**日期**: 2026-04-02  
**状态**: 已批准  
**目标**: 实现一个单文件极简 Python Agent，支持工具调用、Skills、持久记忆，通过 console 交互

---

## 1. 定位与目标

**使用场景**："一行经理"模式——复制一个 `claw.py` 文件到任意目录，`python claw.py` 启动，即可运行一个能调用工具、拥有记忆、读取技能指南的智能 agent。解决单个 prompt 无法完成的复杂任务。

**设计原则**：
- 单文件，零框架依赖（仅 `openai` + `requests`）
- 约 400 行代码，可读性优先
- 不支持：多 channel、cron、多 agent、session 持久化
- 支持：流式输出、工具调用循环、Skills 加载、Memory 自动总结

---

## 2. 文件结构

```
<workspace>/
├── claw.py            # 主程序（单文件）
├── agent.md           # agent 角色指令（不存在则使用内置默认模板）
├── memory.md          # 持久记忆（不存在则自动创建为空文件）
├── claw.json          # 主配置（模型、激活的 skills）
└── skills/            # skills 目录（可选）
    ├── github/
    │   └── skill.md
    ├── weather/
    │   └── skill.md
    └── <任意>/
        └── skill.md
```

---

## 3. 配置文件（claw.json）

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com/v1",
  "active_skills": ["github", "weather"]
}
```

**字段说明**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `provider` | 是 | LLM 提供商，决定从哪个环境变量读取 API key |
| `model` | 是 | 模型名称（传给 OpenAI-compatible 接口） |
| `base_url` | 是 | OpenAI-compatible API 地址 |
| `active_skills` | 否 | 激活的 skill 目录名列表，默认空列表 |

**Provider → 环境变量映射**（内置）：

| provider | 环境变量 |
|----------|----------|
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `qwen` | `DASHSCOPE_API_KEY` |
| `moonshot` | `MOONSHOT_API_KEY` |
| `zhipu` | `ZHIPUAI_API_KEY` |
| `baidu` | `QIANFAN_API_KEY` |

未在列表中的 provider，环境变量规则为 `{PROVIDER}_API_KEY`（大写）。

---

## 4. CLI 入口

```bash
# 最简启动（当前目录作为 workspace）
python claw.py

# 指定 workspace
python claw.py --workspace ~/my-project

# 命令行覆盖模型配置
python claw.py --model gpt-4o --base-url https://api.openai.com/v1
```

配置优先级：**命令行参数 > claw.json > 内置默认值**

---

## 5. System Prompt 组装

每次调用 LLM 前，system prompt 按以下顺序拼接：

```
1. agent.md 内容（角色指令）
2. memory.md 内容（持久记忆，标注为 ## 记忆）
3. 各 active_skills 对应 skill.md 内容（标注为 ## Skills，只加载skill的name和description，yaml文件格式，当用到这个skill时，在read对应的skill.md文件）
4. 当前环境快照（标注为 ## 当前环境）
```

**当前环境快照内容**（启动时采集一次，复用于整个会话）：

```
## 当前环境
- 时间: 2026-04-02 14:32:11 CST
- 系统: macOS 14.5 (arm64)
- Python: 3.11.8
- Shell: zsh
- 用户: moka
- 工作目录: /Users/moka/project/my-task
- 目录内容:
  data.csv (12KB)
  report.py
  README.md
  output/ [目录]
```

工具 schema 通过 `openai` SDK 的 `tools` 参数传递，无需手写在 system prompt 中。

---

## 6. Agent 执行循环

```
用户输入
    │
    ▼
构建 messages（system + history + 用户输入）
    │
    ▼
┌─────────────────────────────────────────┐
│          LLM 工具调用循环（最多 40 轮）    │
│                                         │
│  流式调用 LLM                            │
│      │                                  │
│      ├─ 文字 delta → 实时打印            │
│      │                                  │
│      └─ tool_calls                      │
│              │                          │
│              ▼                          │
│    打印 [🔧 tool_name: args_preview]     │
│              │                          │
│              ▼                          │
│    执行工具，打印结果摘要（首 200 字符）   │
│              │                          │
│              ▼                          │
│    追加 tool_result → messages           │
│              │                          │
│              ▼                          │
│    继续下一轮 LLM 调用 ──────────────────┤
│                                         │
│  finish_reason == "stop" → 退出循环      │
└─────────────────────────────────────────┘
    │
    ▼
追加本轮对话到 session history（内存，不持久化）
    │
    ▼
等待下一个用户输入
```

**History 管理**：
- 仅保留当前会话 messages 列表（内存中）
- 不做 token 截断（信任用户控制对话长度）
- 退出时丢弃（记忆通过 memory.md 持久化）

---

## 7. 内置工具

| 工具名 | 参数 | 说明 |
|--------|------|------|
| `exec` | `command: str` | 执行 shell 命令，timeout 60s，输出截断 8000 字符 |
| `read_file` | `path: str` | 读取文件内容 |
| `write_file` | `path: str, content: str` | 写入/覆盖文件 |
| `web_fetch` | `url: str` | 抓取网页，返回纯文本正文 |
| `web_search` | `query: str` | 搜索网页，优先用 `BRAVE_API_KEY`，无则 DuckDuckGo |

**安全策略**：工具不做路径限制或命令黑名单（单文件工具场景，信任本地用户）。

---

## 8. Skills 加载

1. 读取 `claw.json` 中的 `active_skills` 列表
2. 对每个 skill 名，加载 `<workspace>/skills/<name>/skill.md`
3. 若文件不存在，打印警告并跳过
4. 将所有 skill.md 内容拼接，注入 system prompt 的 `## Skills` 区块

Skill 文件格式遵循 nanobot 的 skill.md 规范（可直接复用 nanobot 的 built-in skills）。

---

## 9. Memory 自动总结

**触发条件**：用户输入 `exit` 或按 `Ctrl+C` 退出，且本次会话对话轮数 > 1。

**总结流程**：
1. 读取当前 `memory.md` 内容
2. 组合会话历史 + 现有 memory，发起一次独立 LLM 调用
3. Prompt 指示 LLM：提炼持久性事实，合并到 memory.md，忽略临时任务细节
4. 将返回内容直接写回 `memory.md`
5. 打印 `💾 记忆已更新` 后退出

**总结 Prompt 模板**：
```
你是一个记忆管理助手。根据以下对话历史，
提炼出值得长期记住的关键信息（用户偏好、项目背景、重要事实），
合并到现有 memory.md 内容中。
忽略本次任务的临时操作细节。
直接输出更新后的 memory.md 全文，不要任何额外说明。

现有 memory.md:
{current_memory}

本次对话历史:
{session_history}
```

---

## 10. Console 交互体验

```
$ python claw.py

🤖 Claw Agent 就绪 (deepseek-chat)
Skills: github, weather
输入 exit 或 Ctrl+C 退出
──────────────────────────────────────
你: 分析当前目录的 data.csv，生成摘要报告

助手: 我来读取并分析这个文件...
[🔧 read_file: data.csv]
[🔧 exec: python -c "import csv..."]
数据共 1,243 行，包含以下字段：name, age, score...

你: exit
💾 正在更新记忆...
再见！
```

---

## 11. 代码结构（单文件内部分区）

```python
# ── 1. 标准库 + 第三方导入（openai, requests）
# ── 2. 常量与配置（MAX_TOOL_ITERATIONS=40, EXEC_TIMEOUT=60, ...）
# ── 3. PROVIDER_ENV_KEYS 映射表
# ── 4. 工具函数（exec_tool, read_file, write_file, web_fetch, web_search）
# ── 5. TOOLS_SCHEMA（OpenAI tools 格式定义）
# ── 6. execute_tool(name, args) 分发函数
# ── 7. load_config(workspace) → dict
# ── 8. load_system_prompt(workspace, config) → str
# ── 9. get_system_context() → str（环境快照）
# ── 10. run_agent_loop(client, model, messages, tools) → str（流式）
# ── 11. summarize_memory(client, model, workspace, history)
# ── 12. main() → REPL 主循环
# ── 13. if __name__ == "__main__": main()
```

---

## 12. 依赖

```
openai>=1.0.0     # OpenAI-compatible SDK（流式支持）
requests>=2.28.0  # web_fetch / web_search
```

安装：`pip install openai requests`
