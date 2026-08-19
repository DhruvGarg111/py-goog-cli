# Pygog - All Possible Commands

A complete reference of all CLI commands available in Pygog.

---

## Global Options

```
--account, -a   Account email or alias to use
--client        OAuth client name
--json          Output in JSON format
--plain         Output in plain text format
--verbose, -v   Show verbose output
--version       Show version
--help          Show help
```

---

## Auth Commands

Manage authentication and accounts.

| Command | Description |
|---------|-------------|
| `pygog auth credentials <path>` | Store OAuth client credentials |
| `pygog auth add <email>` | Authorize a Google account via OAuth |
| `pygog auth list` | List authorized accounts |
| `pygog auth remove <email>` | Remove an authorized account |
| `pygog auth status` | Show authentication status for current account |
| `pygog auth services` | List available services and their OAuth scopes |
| `pygog auth keyring [backend]` | Show or set keyring backend |
| `pygog auth alias set <name> <email>` | Set an account alias |
| `pygog auth alias list` | List account aliases |
| `pygog auth alias unset <name>` | Remove an account alias |

---

## Config Commands

Manage configuration.

| Command | Description |
|---------|-------------|
| `pygog config list` | List current configuration |
| `pygog config set <key> <value>` | Set a config value |
| `pygog config unset <key>` | Remove a config value |
| `pygog config path` | Show config file path |

---

## Gmail Commands

Gmail operations.

| Command | Description |
|---------|-------------|
| `pygog gmail search <query>` | Search for threads |
| `pygog gmail messages search <query>` | Search for messages |
| `pygog gmail thread get <thread_id>` | Get a thread |
| `pygog gmail get <message_id>` | Get a message |
| `pygog gmail send` | Send an email |
| `pygog gmail url <thread_id>` | Get Gmail web URL for a thread |
| `pygog gmail thread modify <thread_id>` | Modify thread labels |
| `pygog gmail labels list` | List all labels |
| `pygog gmail labels get <label_id>` | Get label details |
| `pygog gmail labels create <name>` | Create a new label |
| `pygog gmail drafts list` | List drafts |
| `pygog gmail drafts create` | Create a draft |

### Gmail Send Options
```
--to        Recipient email(s), comma-separated (required)
--subject   Email subject (required)
--body      Plain text body (required)
--cc        CC recipients
--bcc       BCC recipients
```

---

## Calendar Commands

Calendar operations.

| Command | Description |
|---------|-------------|
| `pygog calendar calendars` | List all calendars |
| `pygog calendar events [calendar_id]` | List calendar events |
| `pygog calendar event <calendar_id> <event_id>` | Get event details |
| `pygog calendar get <calendar_id> <event_id>` | Get event details (alias) |
| `pygog calendar search <query>` | Search for events |
| `pygog calendar create` | Create a calendar event |
| `pygog calendar update <calendar_id> <event_id>` | Update a calendar event |
| `pygog calendar delete <calendar_id> <event_id>` | Delete a calendar event |
| `pygog calendar respond <calendar_id> <event_id>` | Respond to an event invitation |
| `pygog calendar freebusy` | Check free/busy status |

### Calendar Events Options
```
--today       Show today's events
--tomorrow    Show tomorrow's events
--week        Show this week's events
--days N      Show next N days
--from        Start time (ISO format)
--to          End time (ISO format)
```

---

## Drive Commands

Drive operations.

| Command | Description |
|---------|-------------|
| `pygog drive ls` | List files in Drive |
| `pygog drive search <query>` | Search for files |
| `pygog drive get <file_id>` | Get file metadata |
| `pygog drive download <file_id>` | Download or export a file |
| `pygog drive upload <file_path>` | Upload a file |
| `pygog drive mkdir <name>` | Create a folder |
| `pygog drive copy <file_id> <name>` | Copy a file |
| `pygog drive rename <file_id> <name>` | Rename a file |
| `pygog drive move <file_id>` | Move a file to a different folder |
| `pygog drive delete <file_id>` | Move a file to trash |
| `pygog drive permissions <file_id>` | List file permissions |
| `pygog drive share <file_id>` | Share a file with a user |
| `pygog drive unshare <file_id>` | Remove a permission from a file |
| `pygog drive drives` | List shared drives |
| `pygog drive url <file_id>` | Get Drive web URL for a file |

---

## Tasks Commands

Tasks operations.

| Command | Description |
|---------|-------------|
| `pygog tasks lists` | List all task lists |
| `pygog tasks create-list <title>` | Create a new task list |
| `pygog tasks list <tasklist_id>` | List tasks in a task list |
| `pygog tasks get <tasklist_id> <task_id>` | Get task details |
| `pygog tasks add <tasklist_id>` | Add a new task |
| `pygog tasks update <tasklist_id> <task_id>` | Update a task |
| `pygog tasks done <tasklist_id> <task_id>` | Mark a task as completed |
| `pygog tasks undo <tasklist_id> <task_id>` | Mark a task as not completed |
| `pygog tasks delete <tasklist_id> <task_id>` | Delete a task |
| `pygog tasks clear <tasklist_id>` | Clear all completed tasks from a list |

---

## Ask Command (Natural Language)

Use natural language to interact with Google services.

```bash
pygog ask "What are my unread emails?"
pygog ask "Send an email to john@example.com saying the meeting is confirmed"
pygog ask "Find the Q4 report and share it with finance@company.com"
pygog ask "What meetings do I have today?"
pygog ask "Create a task to call the client tomorrow"
```

### Ask Options
```
--yes, -y    Auto-confirm destructive actions
--model, -m  LLM model to use (e.g., deepseek/deepseek-chat, gpt-4o)
```

---

## Time Command

Show current time and timezone.

| Command | Description |
|---------|-------------|
| `pygog time now` | Show current time |
