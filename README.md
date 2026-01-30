# 🧭 pygog

**Google in your terminal — done right.**

`pygog` is a fast, powerful, and script-friendly CLI for Google services. Built with Python for performance and reliability, it provides an intuitive interface for Gmail, Calendar, Drive, and Tasks.

---

## ✨ Features

- 📧 **Gmail** - Search threads, send emails with HTML support, manage labels and drafts.
- 📂 **Drive** - List, search, upload, and download files. Built-in export for Google Workspace docs (PDF/Docx/Xlsx).
- 🗓️ **Calendar** - Manage events, check free/busy status, and RSVP to invitations.
- ✅ **Tasks** - Full management of task lists and individual tasks.
- 🤖 **Natural Language Agent** - Ask `pygog` to do things in plain English. Supports DeepSeek, OpenAI, Gemini, & Anthropic.
- 🌐 **Web Search** - Real-time access to news, prices, and weather via the agent.
- 🔑 **Secure** - Built-in OS-level keyring support for storing sensitive tokens.
- 💻 **Developer Friendly** - JSON output for everything. Perfect for automation scripts.
- 👥 **Multi-Account** - Manage multiple Google accounts with easy aliasing.

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/pygog/pygog.git
cd pygog

# Install in editable mode
pip install -e .
```

---

## 🛠️ Setup & Authentication

### 1. Create Google Cloud Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create a Project and enable the Gmail, Drive, Calendar, and Tasks APIs.
3. Create an **OAuth Client ID** (Application type: *Desktop App*).
4. Download the JSON credentials file.

### 2. Register Credentials
```bash
pygog auth credentials path/to/credentials.json
```

### 3. Add Your Account
```bash
# This will open your browser for authentication
pygog auth add your.email@gmail.com --services gmail,drive,calendar,tasks
```

---

## 📖 Command Examples

### 📧 Gmail
```bash
# Search for recent emails
pygog gmail search "from:boss newer_than:1d" --max 5

# Send a quick email
pygog gmail send --to "friend@example.com" --subject "Hello" --body "Sent from pygog!"

# List your labels
pygog gmail labels list
```

### 📂 Google Drive
```bash
# List files in your root directory
pygog drive ls --max 10

# Download a file and export a Google Doc as PDF
pygog drive download <FILE_ID> --format pdf --out report.pdf

# Upload a local file
pygog drive upload ./backup.zip --name "Weekly Backup"
```

### 🗓️ Calendar
```bash
# See what's happening today
pygog calendar events --today

# Create a new event
pygog calendar create --summary "Team Meeting" --from "2026-02-01T10:00:00" --to "2026-02-01T11:00:00"

# Check free/busy for your team
pygog calendar freebusy --calendars "user1@org.com,user2@org.com" --from "today" --to "tomorrow"
```

### ✅ Google Tasks
```bash
# List all your task lists
pygog tasks lists

# View tasks in a specific list
pygog tasks list <TASKLIST_ID>

# Add a new task
```

### 🧠 Natural Language Agent (`ask`)
Interact with your Google Workspace and the Web using natural language.

1. **Set your API Key** (choose one):
   ```bash
   $env:DEEPSEEK_API_KEY = "sk-..." 
   $env:OPENAI_API_KEY = "sk-..."
   $env:GEMINI_API_KEY = "AIza..."
   $env:ANTHROPIC_API_KEY = "sk-ant..."
   $env:OPENROUTER_API_KEY = "sk-or..."
   ```

2. **Ask away**:
   ```bash
   # Email & Drive
   pygog ask "Find the Q4 report PDF and email it to my boss"
   
   # Calendar & Tasks
   pygog ask "What meetings do I have this week?"
   pygog ask "Remind me to call John tomorrow at 2pm"
   
   # Web Search
   pygog ask "What is the gold price in Delhi today?"
   pygog ask "Latest tech news"
   ```

3. **Select Model** (optional):
   ```bash
   pygog ask "Summarize my emails" --model gpt-4o
   ```

---

## ⚙️ Advanced Usage

### Scripting with JSON
Use the `--json` flag to get raw data for pipes and scripts:
```bash
pygog --json drive ls | jq '.[0].id'
```

### Account Aliases
Tired of typing long emails? Set an alias:
```bash
pygog auth alias set work "primary.work.account@company.com"

# Now use the alias
pygog --account work gmail search "urgent"
```

### Default Account
Set your main account to avoid the `--account` flag:
```bash
pygog config set default_account your.email@gmail.com
```

---

### Output Formats
- **Tables (Default)**: Beautiful, human-readable terminal tables via `rich`.
- **JSON (`--json`)**: Machine-readable output for integration with tools like `jq`.
- **Plain (`--plain`)**: Simple TSV-style output for quick grepping/parsing.

---

## 🔒 Security
`pygog` uses your system's secure keyring (macOS Keychain, Windows Credential Manager, or Secret Service) to store OAuth2 refresh tokens. Tokens are never stored in plain text.

---
