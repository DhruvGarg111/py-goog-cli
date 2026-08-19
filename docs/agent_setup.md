# Getting Started with the `pygog ask` AI Agent

## Prerequisites

Install from the repository; a public PyPI release is not assumed:

```bash
uv sync --extra agent
# or, from an editable checkout:
pip install -e '.[agent]'
```

The agent supports LiteLLM-compatible providers including OpenAI, Anthropic,
Gemini, DeepSeek, and OpenRouter. Set one provider key in the environment.

## 1. Get an API key

- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- Gemini: https://aistudio.google.com/app/apikey
- DeepSeek: https://platform.deepseek.com/
- OpenRouter: https://openrouter.ai/keys

## 2. Configure the environment

Bash/Zsh:

```bash
export OPENAI_API_KEY="your-api-key-here"
# Or: ANTHROPIC_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

Never commit provider keys or paste them into prompts. pygog redacts
secret-shaped diagnostic values, but the provider receives the query and any
selected tool results needed to answer it.

## 3. Basic usage

```bash
pygog ask "What meetings do I have today?"
pygog ask --model deepseek/deepseek-chat "Summarize my unread emails"
```

## 4. Write safety and tool allowlists

Agent mode is read-only by default. Write-capable tools are not exposed unless
the local user explicitly passes `--allow-write`, and every write still asks
for a local confirmation. Retrieved Gmail, Drive, and web content is untrusted
data; instructions found in retrieved content cannot grant write permission.

Use `--tools` to restrict the run to an exact comma-separated tool allowlist:

```bash
pygog ask --tools gmail_search,drive_search "Find the Q4 report"
pygog ask --allow-write --tools gmail_send "Send this exact message to ..."
```

The legacy `--yes` flag is deprecated and cannot bypass local confirmation.

## 5. Model selection

```bash
pygog ask --model gemini/gemini-2.5-flash-lite "Explain this calendar"
pygog ask --model openai/gpt-4o "Summarize my Drive files"
pygog ask --model anthropic/claude-3-opus-20240229 "Summarize my inbox"
pygog ask --model openrouter/anthropic/claude-3-opus "Search the web"
```

For JSON/TSV scripting, see `docs/json_scripting.md`. The agent requires the
optional `agent` dependency extra; the base CLI remains usable without it.
