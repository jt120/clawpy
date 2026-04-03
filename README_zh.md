# Claw - 单文件 AI Agent

<div align="center">

[English](README.md) | [中文](README_zh.md)

</div>


一个极简的单文件 Python AI Agent，支持工具调用、Skills 和持久记忆，通过控制台交互。

## 🚀 特性

- **单文件设计**：仅一个 `claw.py` 文件，零框架依赖
- **开箱即用**：复制到任意目录，`python claw.py` 即可启动
- **工具调用**：内置文件操作、命令执行、网页抓取和搜索
- **Skills 系统**：支持加载自定义技能指南
- **持久记忆**：自动总结对话并保存到 `memory.md`
- **多模型支持**：OpenAI、DeepSeek、Anthropic、百度、智谱等
- **流式输出**：实时显示 AI 回复和工具调用过程

## 📁 项目结构

```
<workspace>/
├── claw.py            # 主程序（单文件）
├── agent.md           # agent 角色指令（可选）
├── memory.md          # 持久记忆（自动创建）
├── claw.json          # 主配置文件
├── .env               # API 密钥（可选）
└── skills/            # skills 目录（可选）
    ├── github/
    │   └── skill.md
    ├── weather/
    │   └── skill.md
    └── <任意>/
        └── skill.md
```

## 🛠️ 快速开始

### 1. 安装依赖

```bash
pip install openai requests
```

### 2. 设置 API 密钥

```bash
# 设置环境变量（以 DeepSeek 为例）
export DEEPSEEK_API_KEY=your_api_key_here

# 或使用 .env 文件
echo "DEEPSEEK_API_KEY=your_api_key_here" > .env
```

### 3. 运行

```bash
# 最简启动（当前目录作为 workspace）
python claw.py

# 指定 workspace
python claw.py --workspace ~/my-project

# 命令行覆盖模型配置
python claw.py --model gpt-4o --base-url https://api.openai.com/v1

# 非交互式模式：直接输入查询，执行完自动退出
python claw.py "查看当前目录的文件"
```

### 4. 设置别名（推荐）

添加到 shell 配置文件（~/.zshrc 或 ~/.bashrc），可以在任意路径快速调用：

```bash
# 替换为你的 claw.py 实际路径
alias claw='python /path/to/claw.py'
```

重新加载配置后即可使用：
```bash
# 任意路径下直接使用
claw "查看当前目录结构"
```

## ⚙️ 配置

### 配置文件 (claw.json)

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com/v1",
  "active_skills": ["github", "weather"]
}
```

### 支持的 Provider

| Provider | 环境变量 | 备注 |
|----------|----------|------|
| `openai` | `OPENAI_API_KEY` | OpenAI 兼容 API |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude 模型 |
| `deepseek` | `DEEPSEEK_API_KEY` | DeepSeek 模型 |
| `qwen` | `DASHSCOPE_API_KEY` | 通义千问 |
| `moonshot` | `MOONSHOT_API_KEY` | 月之暗面 |
| `zhipu` | `ZHIPUAI_API_KEY` | 智谱 AI |
| `baidu` | `QIANFAN_API_KEY` | 百度千帆 |

未在列表中的 provider，环境变量规则为 `{PROVIDER}_API_KEY`（大写）。

## 🛠️ 内置工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `exec` | 执行 shell 命令 | `command: str` |
| `read_file` | 读取文件内容 | `path: str` |
| `write_file` | 写入/覆盖文件 | `path: str, content: str` |
| `web_fetch` | 抓取网页内容 | `url: str` |
| `web_search` | 搜索网页 | `query: str` |

**安全策略**：工具不做路径限制或命令黑名单（单文件工具场景，信任本地用户）。

## 📚 Skills 系统

Skills 是预定义的技能指南，存储在 `skills/<name>/skill.md` 文件中。

### 创建 Skill

```bash
mkdir -p skills/github
cat > skills/github/skill.md << 'EOF'
---
name: github
description: "使用 gh CLI 与 GitHub 交互"
---
# GitHub Skill

## 功能
- 查看仓库信息
- 创建 Issue
- 管理 Pull Request

## 示例
```bash
gh repo view
gh issue create --title "Bug" --body "Description"
```
EOF
```

### 激活 Skill

在 `claw.json` 中添加 skill 名称到 `active_skills` 列表：

```json
{
  "active_skills": ["github", "weather"]
}
```

## 💾 持久记忆

Agent 会在退出时自动总结对话，将关键信息保存到 `memory.md`。

**触发条件**：用户输入 `exit` 或按 `Ctrl+C` 退出，且本次会话对话轮数 > 1。

记忆内容包括：
- 用户偏好
- 项目背景
- 重要事实
- 长期配置

## 🤖 Agent 指令

默认 agent 指令存储在 `agent.md` 中，如果不存在则使用内置默认模板：

```markdown
# Claw Agent

你是一个高效的命令行助手。你的特点：
- 主动使用工具获取信息，不依赖用户描述
- 遇到代码/文件任务，直接读取文件再操作
- 遇到网络信息需求，直接用 web_search 或 web_fetch 获取
- 操作前先理解当前环境（目录结构、文件内容）
- 回答简洁，优先给出可执行的结果
```

## 🎯 使用示例

### 启动 Agent

```bash
$ python claw.py

🤖 Claw Agent 就绪 (deepseek-chat)
Skills: github, weather
输入 exit 或 Ctrl+C 退出
──────────────────────────────────────
```

### 交互示例

```
User: 查看当前目录的文件

助手: 我来查看当前目录的内容...
[🔧 exec: ls -la]
total 48
drwxr-xr-x  14 user  staff   448 Apr  3 11:31 .
drwxr-xr-x   5 user  staff   160 Apr  3 10:58 ..
-rw-r--r--   1 user  staff   369 Apr  3 11:25 agent.md
-rw-r--r--   1 user  staff   125 Apr  3 11:25 claw.json
-rw-r--r--   1 user  staff 18000 Apr  3 11:25 claw.py
drwxr-xr-x   3 user  staff    96 Apr  3 11:25 docs
...

User: 帮我创建一个 Python 脚本

助手: 我来创建一个 Python 脚本...
[🔧 write_file: hello.py]
已写入 hello.py
[🔧 read_file: hello.py]
文件为空，我来添加一些内容...
[🔧 write_file: hello.py]
已写入 hello.py

User: exit
💾 正在更新记忆...
再见！
```

### 技能使用示例

使用 prompt-optimizer 技能优化 prompt：

```bash
# 直接在命令行中执行任务，自动加载相关技能
claw "优化prompt，job_profile_4.0.3.txt，如果存在job_profile，则直接生成，不要从jd中提取"

// 自动加载技能，用技能优化prompt 
我已经优化了 prompt，创建了 `job_profile_4.0.4.txt`。主要优化点包括：
```

## 🧪 测试

项目包含完整的单元测试：

```bash
# 运行测试
python -m pytest tests/

# 查看测试覆盖率
python -m pytest --cov=claw tests/
```

## 📋 设计理念

Claw 遵循 "一行经理" 模式：
- **单文件**：复制一个文件即可使用
- **零配置**：默认配置开箱即用
- **可扩展**：通过 Skills 系统添加功能
- **可读性**：约 400 行代码，易于理解和修改

## 🔧 开发

### 代码结构

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
```

### 添加新工具

1. 在 `TOOLS_SCHEMA` 中添加工具定义
2. 实现对应的工具函数
3. 在 `execute_tool` 函数中添加分发逻辑

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📚 相关文档

- [设计文档](docs/superpowers/specs/2026-04-02-claw-single-file-agent-design.md) - 详细的设计说明
- [测试用例](tests/test_claw.py) - 完整的单元测试

## 🚀 下一步计划

- [ ] 支持更多工具（数据库、API 调用等）
- [ ] 添加插件系统
- [ ] 支持会话持久化
- [ ] 添加 Web UI 界面
- [ ] 支持多 agent 协作

---

**Claw** - 让 AI 助手变得简单、可移植、强大！