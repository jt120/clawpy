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


def test_load_config_defaults(tmp_path):
    import claw

    config = claw.load_config(str(tmp_path))
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o"
    assert config["active_skills"] == []


def test_load_config_from_file(tmp_path):
    import claw, json

    (tmp_path / "claw.json").write_text(
        json.dumps(
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com/v1",
                "active_skills": ["github"],
            }
        )
    )
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
    prompt = claw.load_system_prompt(
        str(tmp_path), {"active_skills": []}, "## 环境\n..."
    )
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
    prompt = claw.load_system_prompt(str(tmp_path), {"active_skills": ["github"]}, "")
    assert "github" in prompt
    assert "Interact with GitHub" in prompt
    assert "Full content that should NOT appear" not in prompt
    assert "skill.md" in prompt


def test_load_system_prompt_missing_skill_warns(tmp_path, capsys):
    import claw

    claw.load_system_prompt(str(tmp_path), {"active_skills": ["nonexistent"]}, "")
    captured = capsys.readouterr()
    assert "警告" in captured.err


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

    claw.summarize_memory(
        FakeClient(),
        "m",
        str(tmp_path),
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    )
    assert (tmp_path / "memory.md").read_text() == "新记忆"



