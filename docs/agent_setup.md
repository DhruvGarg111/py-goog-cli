### Prerequisites
Ensure you have `pygog` installed on your system. If you haven't installed it yet, you can do so via pip:
`pip install pygog`
*(Note: Refer to the main repository README for full installation instructions).*
# Getting Started with the `pygog ask` AI Agent

The `ask` agent is a powerful natural-language feature within pygog. This guide covers how to configure your environment, secure your API keys, and start running prompts.

## 1. Get Your API Keys
To use the agent, you need an API key from a supported provider. You only need one to get started:
* **OpenAI:** [Get your key here](https://platform.openai.com/api-keys)
* **Anthropic:** [Get your key here](https://console.anthropic.com/settings/keys)
* **Gemini (Google):** [Get your key here](https://aistudio.google.com/app/apikey)
* **DeepSeek:** [Get your key here](https://platform.deepseek.com/)
* **OpenRouter:** [Get your key here](https://openrouter.ai/keys)

## 2. Environment Configuration
You must export your API key as an environment variable so `pygog` can access it securely.

**For Bash / Zsh (Mac & Linux):**
```bash
export OPENAI_API_KEY="your-api-key-here"
# Or for other providers:
# export ANTHROPIC_API_KEY="your-api-key-here"
# export GEMINI_API_KEY="your-api-key-here"
# export DEEPSEEK_API_KEY="your-api-key-here"
# export OPENROUTER_API_KEY="your-api-key-here"
```

**For PowerShell (Windows):**
```bash
$env:OPENAI_API_KEY="your-api-key-here"
# Or for other providers:
# $env:ANTHROPIC_API_KEY="your-api-key-here"
# $env:GEMINI_API_KEY="your-api-key-here"
# $env:DEEPSEEK_API_KEY="your-api-key-here"
# $env:OPENROUTER_API_KEY="your-api-key-here"
```

## 3. Basic Usage Examples
Once your environment is configured, you can use the ask command directly in your terminal.
```bash
pygog ask "Draft an email to my manager about the deployment"
pygog ask "Create a calendar event for tomorrow at 3 PM"
```

## 4. Model Selection
By default, pygog ask uses a default model. You can specify exactly which model to use by passing the --model flag.
```bash
pygog ask --model gemini/gemini-2.5-flash-lite "Draft an email to my manager about the deployment"
pygog ask --model deepseek/deepseek-chat "Write a polite email declining a job offer"
pygog ask --model openai/gpt-4o "Summarise the report on latest iphone present in my Gdrive"
pygog ask --model anthropic/claude-3-opus-20240229 "What is silver price currently in Bengaluru?"
pygog ask --model openrouter/anthropic/claude-3-opus "Explain the theory of relativity"