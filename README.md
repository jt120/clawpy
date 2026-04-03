# Claw - Single-File AI Agent

<div align="center">

[English] | [中文](README_zh.md)

</div>

A minimalist single-file Python AI Agent with tool calling, Skills, persistent memory, and console interaction.

## 🚀 Features

- **Single-file design**: Just one `claw.py` file, zero framework dependencies
- **Out-of-the-box**: Copy to any directory, run `python claw.py` to start
- **Tool calling**: Built-in file operations, command execution, web scraping and search
- **Skills system**: Load custom skill guides
- **Persistent memory**: Automatically summarize conversations and save to `memory.md`
- **Multi-model support**: OpenAI, DeepSeek, Anthropic, Baidu, Zhipu, and more
- **Streaming output**: Real-time AI responses and tool call visualization

## 📁 Project Structure

```
<workspace>/
├── claw.py            # Main program (single file)
├── agent.md           # Agent role instructions (optional)
├── memory.md          # Persistent memory (auto-created)
├── claw.json          # Main configuration file
├── .env               # API keys (optional)
└── skills/            # Skills directory (optional)
    ├── github/
    │   └── skill.md
    ├── weather/
    │   └── skill.md
    └── <any>/
        └── skill.md
```

## 🛠️ Quick Start

### 1. Install Dependencies

```bash
pip install openai requests
```

### 2. Set API Key

```bash
# Set environment variable (DeepSeek example)
export DEEPSEEK_API_KEY=your_api_key_here

# Or use .env file
echo "DEEPSEEK_API_KEY=your_api_key_here" > .env
```

### 3. Run

```bash
# Simplest start (current directory as workspace)
python claw.py

# Specify workspace
python claw.py --workspace ~/my-project

# Override model configuration via command line
python claw.py --model gpt-4o --base-url https://api.openai.com/v1
```

## ⚙️ Configuration

### Configuration File (claw.json)

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com/v1",
  "active_skills": ["github", "weather"]
}
```

### Supported Providers

| Provider | Environment Variable | Notes |
|----------|----------------------|-------|
| `openai` | `OPENAI_API_KEY` | OpenAI-compatible API |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude models |
| `deepseek` | `DEEPSEEK_API_KEY` | DeepSeek models |
| `qwen` | `DASHSCOPE_API_KEY` | Qwen models |
| `moonshot` | `MOONSHOT_API_KEY` | Moonshot AI |
| `zhipu` | `ZHIPUAI_API_KEY` | Zhipu AI |
| `baidu` | `QIANFAN_API_KEY` | Baidu Qianfan |

For providers not in the list, environment variable follows `{PROVIDER}_API_KEY` (uppercase).

## 🛠️ Built-in Tools

| Tool Name | Function | Parameters |
|-----------|----------|------------|
| `exec` | Execute shell command | `command: str` |
| `read_file` | Read file content | `path: str` |
| `write_file` | Write/overwrite file | `path: str, content: str` |
| `web_fetch` | Fetch web page content | `url: str` |
| `web_search` | Search the web | `query: str` |

**Security policy**: No path restrictions or command blacklists (trust local users in single-file tool scenario).

## 📚 Skills System

Skills are predefined skill guides stored in `skills/<name>/skill.md` files.

### Create a Skill

```bash
mkdir -p skills/github
cat > skills/github/skill.md << 'EOF'
---
name: github
description: "Interact with GitHub using gh CLI"
---
# GitHub Skill

## Features
- View repository information
- Create Issues
- Manage Pull Requests

## Examples
```bash
gh repo view
gh issue create --title "Bug" --body "Description"
```
EOF
```

### Activate Skill

Add skill names to the `active_skills` list in `claw.json`:

```json
{
  "active_skills": ["github", "weather"]
}
```

## 💾 Persistent Memory

Agent automatically summarizes conversations when exiting and saves key information to `memory.md`.

**Trigger condition**: User inputs `exit` or presses `Ctrl+C`, and the session has more than 1 conversation round.

Memory includes:
- User preferences
- Project context
- Important facts
- Long-term configurations

## 🤖 Agent Instructions

Default agent instructions are stored in `agent.md`. If not present, built-in default template is used:

```markdown
# Claw Agent

You are an efficient command-line assistant. Your characteristics:
- Actively use tools to obtain information, don't rely on user descriptions
- For code/file tasks, read files first then operate
- For web information needs, use web_search or web_fetch directly
- Understand current environment (directory structure, file content) before operations
- Provide concise answers, prioritize actionable results
```

## 🎯 Usage Examples

### Start Agent

```bash
$ python claw.py

🤖 Claw Agent ready (deepseek-chat)
Skills: github, weather
Type exit or Ctrl+C to quit
──────────────────────────────────────
```

### Interaction Example

```
User: List files in current directory

Assistant: I'll check the current directory contents...
[🔧 exec: ls -la]
total 48
drwxr-xr-x  14 user  staff   448 Apr  3 11:31 .
drwxr-xr-x   5 user  staff   160 Apr  3 10:58 ..
-rw-r--r--   1 user  staff   369 Apr  3 11:25 agent.md
-rw-r--r--   1 user  staff   125 Apr  3 11:25 claw.json
-rw-r--r--   1 user  staff 18000 Apr  3 11:25 claw.py
drwxr-xr-x   3 user  staff    96 Apr  3 11:25 docs
...

User: Help me create a Python script

Assistant: I'll create a Python script...
[🔧 write_file: hello.py]
Written to hello.py
[🔧 read_file: hello.py]
File is empty, I'll add some content...
[🔧 write_file: hello.py]
Written to hello.py

User: exit
💾 Updating memory...
Goodbye!
```

### Skill Usage Example

Using prompt-optimizer skill to optimize prompts:

```bash
# Execute task directly in command line, automatically load relevant skills
claw "Optimize prompt, job_profile_4.0.3.txt, if job_profile exists, generate directly, do not extract from jd"

// Automatically load skill, optimize prompt using skill
I have optimized the prompt and created `job_profile_4.0.4.txt`. Main optimizations include:
```

## 🧪 Testing

The project includes comprehensive unit tests:

```bash
# Run tests
python -m pytest tests/

# Check test coverage
python -m pytest --cov=claw tests/
```

## 📋 Design Philosophy

Claw follows the "One-Line Manager" pattern:
- **Single file**: Copy one file and use it anywhere
- **Zero configuration**: Default settings work out of the box
- **Extensible**: Add functionality through Skills system
- **Readable**: ~400 lines of code, easy to understand and modify

## 🔧 Development

### Code Structure

```python
# ── 1. Standard library + third-party imports (openai, requests)
# ── 2. Constants & configuration (MAX_TOOL_ITERATIONS=40, EXEC_TIMEOUT=60, ...)
# ── 3. PROVIDER_ENV_KEYS mapping table
# ── 4. Tool functions (exec_tool, read_file, write_file, web_fetch, web_search)
# ── 5. TOOLS_SCHEMA (OpenAI tools format definition)
# ── 6. execute_tool(name, args) dispatch function
# ── 7. load_config(workspace) → dict
# ── 8. load_system_prompt(workspace, config) → str
# ── 9. get_system_context() → str (environment snapshot)
# ── 10. run_agent_loop(client, model, messages, tools) → str (streaming)
# ── 11. summarize_memory(client, model, workspace, history)
# ── 12. main() → REPL main loop
```

### Adding New Tools

1. Add tool definition to `TOOLS_SCHEMA`
2. Implement corresponding tool function
3. Add dispatch logic in `execute_tool` function

## 📄 License

MIT License

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📚 Related Documentation

- [Design Document](docs/superpowers/specs/2026-04-02-claw-single-file-agent-design.md) - Detailed design specifications
- [Test Cases](tests/test_claw.py) - Comprehensive unit tests

## 🚀 Roadmap

- [ ] Support more tools (database, API calls, etc.)
- [ ] Add plugin system
- [ ] Support session persistence
- [ ] Add Web UI interface
- [ ] Support multi-agent collaboration

---

**Claw** - Making AI assistants simple, portable, and powerful!