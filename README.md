# SmartBot

A flexible AI agent orchestration system with multi-platform LLM support, extensible toolchain, event-driven hooks, and a clean frontend abstraction.

## Features

- **Multi-Platform LLM**: DeepSeek, DashScope (Qwen), Ollama — add more via a simple adapter pattern
- **Streaming Native**: All LLM calls stream tokens, thinking, and tool calls incrementally
- **10 Built-in Tools**: File operations, shell execution, web search, browser automation (Playwright), and more
- **Permission System**: Fine-grained tool access control with multiple modes (ALLOW/CONFIRM/DENY)
- **Event-Driven Hooks**: Trigger bash scripts or HTTP calls on session/tool events
- **Frontend Agnostic**: Works with CLI or WebSocket — implement your own via the `ChatFrontend` protocol
- **Web Dashboard**: FastAPI-based web server with REST API for platform/settings/hook management
- **Skill System**: Load task-specific instructions from markdown files with YAML frontmatter
- **Tool Auto-Discovery**: Tools are automatically discovered and registered

## Quick Start

### Install

```bash
pip install smart-bot
```

Or in development mode:

```bash
git clone <repo-url>
cd smart-bot
pip install -e .
```

### Configure

Edit `~/.config/smart_bot/platforms.json` or use the web UI:

```json
{
  "my-deepseek": {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-xxx",
    "models": ["deepseek-chat"]
  }
}
```

### Run

```bash
# CLI mode
smart-bot

# Web mode (then open http://localhost:8765)
SMART_BOT_PORT=8765 python -m smart_bot.web
```

## Configuration

All config files live in `~/.config/smart_bot/`:

| File | Purpose |
|------|---------|
| `platforms.json` | LLM platform configurations |
| `settings.json` | Default platform, model, data directory |
| `hooks.json` | Event hook definitions |

## Project Structure

```
src/smart_bot/
├── main.py              # CLI entry point
├── web.py               # FastAPI web server
├── state.py             # Application state
├── config/              # Configuration management
├── interface/           # Core abstractions (LLM, Tool, Message)
├── platforms/           # LLM provider implementations
├── tools/               # 10 built-in tools
├── hook/                # Event hook system
├── pipeline/            # Chat orchestration
├── frontend/            # CLI / WebSocket frontends
├── event/               # Async event bus
├── skill/               # Skill loading
└── prompts/             # System prompts
```

## Supported Platforms

| Platform | Provider ID | SDK | Notes |
|----------|-------------|-----|-------|
| DeepSeek | `deepseek` | OpenAI-compatible | Supports reasoning, tool calls |
| DashScope | `dashscope` | OpenAI-compatible | Alibaba Cloud Qwen models |
| Ollama | `ollama` | Ollama SDK | Local models |

## Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `file_read` | ALLOW | Read text files |
| `file_write` | CONFIRM | Write/append text files |
| `file_edit` | CONFIRM | String-replacement edits |
| `file_glob` | ALLOW | Glob pattern search |
| `bash` | CONFIRM | Execute shell commands |
| `web_fetch` | ALLOW | Fetch & convert web pages |
| `duckduckgo_search` | ALLOW | Web search |
| `browser_control` | CONFIRM | Playwright browser automation |
| `skill` | ALLOW | Execute named skills |
| `ask_user` | ALLOW | Interactive user queries |

## Extending

- **Add a platform**: Create a class inheriting `LLM`, register it in `platforms/utils.py`
- **Add a tool**: Create a class inheriting `BaseTool`, decorate with `@ToolManager.register_tool`
- **Add a hook**: Configure `~/.config/smart_bot/hooks.json` with Bash or HTTP actions

## License

MIT
