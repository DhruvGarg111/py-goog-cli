# JSON and TSV scripting contracts

`pygog` has two machine-readable output modes:

- `--json` writes one JSON document to stdout.
- `--plain` writes tab-separated values (TSV) to stdout, with a header row for
  the supported list/search commands.

Human-readable tables and progress messages are not part of either contract.
Use `--json` when the complete Google response is needed, and `--plain` when a
small, stable set of columns is more convenient for shell tools such as
`cut`, `awk`, or `column`.

## Common rules

- `--json` and `--plain` are mutually exclusive.
- JSON is UTF-8, pretty-printed with two-space indentation, and ends with a
  newline.
- JSON command output preserves the existing provider response shape. The CLI
  does not wrap list/search responses solely to make them look uniform.
- Provider fields that are optional remain optional in JSON. A missing field is
  not silently replaced by an empty string, and a provider JSON `null` remains
  JSON `null`.
- Pagination metadata is preserved when the service returns it. In particular,
  `nextPageToken` is optional: scripts must not assume it is present on every
  response.
- TSV has a header row followed by zero or more data rows. Missing display
  values and JSON `null` values are empty cells in the command adapters. Tabs
  and newlines in cell values are replaced with spaces so one record always
  occupies one line.
- TSV values are display values, not a second JSON encoding. Booleans and
  numbers are rendered as text; use JSON when their types matter.
- Diagnostics must not be parsed as successful data. At the CLI boundary,
  human diagnostics are written to stderr; JSON error payloads are written to
  stdout as described below.

## Read command JSON shapes

The following examples show the wrapper keys and representative provider
fields. Additional provider fields may be present and should be ignored by
forward-compatible scripts unless explicitly needed.

### Gmail

`pygog gmail search 'from:alice@example.com' --json` returns the Gmail list
response directly:

```json
{
  "threads": [
    {
      "id": "thread-1",
      "historyId": "42"
    }
  ],
  "nextPageToken": "next-thread-page"
}
```

`pygog gmail messages search 'is:unread' --json` likewise preserves the Gmail
message-list response:

```json
{
  "messages": [
    {
      "id": "message-1",
      "threadId": "thread-1"
    }
  ],
  "nextPageToken": "next-message-page"
}
```

Single-resource commands retain their existing wrappers:

```json
{"thread": {"id": "thread-1", "messages": []}}
{"message": {"id": "message-1", "threadId": "thread-1"}}
{"labels": [{"id": "INBOX", "name": "INBOX"}]}
```

### Drive

`pygog drive ls --json` and `pygog drive search report --json` return a Drive
list response. `files` is an array and `nextPageToken` is optional:

```json
{
  "files": [
    {
      "id": "file-1",
      "name": "report.txt",
      "mimeType": "text/plain",
      "size": "1024",
      "modifiedTime": "2026-08-19T12:00:00Z"
    }
  ],
  "nextPageToken": "next-file-page"
}
```

`pygog drive get file-1 --json` uses a resource wrapper:

```json
{
  "file": {
    "id": "file-1",
    "name": "report.txt",
    "mimeType": "text/plain",
    "size": "1024",
    "modifiedTime": "2026-08-19T12:00:00Z"
  }
}
```

### Calendar

`pygog calendar calendars --json` wraps the calendar list:

```json
{
  "calendars": [
    {"id": "primary", "summary": "Personal", "accessRole": "owner"}
  ]
}
```

`pygog calendar events --json` and `pygog calendar search planning --json`
preserve the Calendar events-list response, including optional pagination:

```json
{
  "items": [
    {
      "id": "event-1",
      "summary": "Planning",
      "start": {"dateTime": "2026-08-19T12:00:00+00:00"},
      "location": "Room 1"
    }
  ],
  "nextPageToken": "next-event-page"
}
```

`pygog calendar get primary event-1 --json` uses `{"event": {...}}`.
All-day events use `start.date`/`end.date` instead of `dateTime`; those fields
are optional by event type.

### Tasks

`pygog tasks lists --json` returns `{"tasklists": [...]}` and
`pygog tasks list LIST_ID --json` returns `{"tasks": [...]}`:

```json
{"tasklists": [{"id": "list-1", "title": "Personal"}]}
```

```json
{
  "tasks": [
    {
      "id": "task-1",
      "title": "Ship",
      "status": "needsAction",
      "due": "2026-08-20T00:00:00.000Z"
    }
  ]
}
```

The current Tasks service converts the provider's list response to these
arrays, so pagination metadata is not exposed by these two commands. Do not
infer that an absent `nextPageToken` means the same thing for every service.

## Stable TSV columns

The following columns are emitted in this exact order. Header names use the
JSON/command field spelling, not the title-cased labels used by Rich tables.

| Commands | Columns |
| --- | --- |
| `gmail search` | `id`, `subject`, `from`, `date` |
| `gmail messages search` | `id`, `thread_id`, `subject`, `from`, `date` |
| `gmail messages search --include-body` | the five columns above, then `body` |
| `drive ls`, `drive search`, `drive get` | `id`, `name`, `type`, `size`, `modified` |
| `calendar events`, `calendar search` | `id`, `summary`, `start`, `location` |
| `calendar calendars` | `id`, `summary` |
| `tasks lists` | `id`, `title` |
| `tasks list` | `id`, `title`, `status`, `due` |

Examples:

```text
$ pygog drive search report --plain
id	name	type	size	modified
file-1	report.txt	file	1.0 KB	2026-08-19
```

```text
$ pygog calendar search planning --plain
id	summary	start	location
event-1	Planning	2026-08-19	
```

When a supported list/search command has no rows, it still emits its header.
This makes pipelines safe to compose without a special empty-result branch.
For example, an empty Drive search emits:

```text
id	name	type	size	modified
```

Drive `type` is `folder` for Google Drive folders and `file` otherwise. Drive
`size` is a human-readable value such as `1.0 KB`, or `-` when no size is
available. Calendar `start` is `YYYY-MM-DD` for all-day events and
`YYYY-MM-DD HH:MM` for timed events.

## Mutation and dry-run responses

Machine-readable mutations have an intentional safety break from historical
interactive behavior: commands running with `--json` or `--plain` never prompt
for confirmation, because a prompt would corrupt the stdout contract. A script
must explicitly authorize the mutation with either the global `--force` option
(for example, `pygog --json --force gmail send ...`) or that mutation command's
local `--force` option. Alternatively, pass the command's `--dry-run` option to
preview the operation without calling the provider. Without `--force` or
`--dry-run`, the command exits nonzero with a `confirmation_required` error;
`--no-input` does not bypass this requirement.

Mutations keep their established wrapper or result keys rather than returning a
new generic envelope. Representative JSON shapes are:

```json
{"message": {"id": "message-1"}}
{"label": {"id": "label-1", "name": "Receipts"}}
{"file": {"id": "file-1", "name": "copy.txt"}}
{"folder": {"id": "folder-1", "name": "Archive"}}
{"permission": {"id": "permission-1", "role": "reader"}}
{"event": {"id": "event-1", "summary": "Planning"}}
{"task": {"id": "task-1", "title": "Ship"}}
{"deleted": true, "fileId": "file-1"}
{"deleted": true, "eventId": "event-1"}
{"deleted": true, "taskId": "task-1"}
```

A shared dry-run response is valid JSON and never calls the provider. For
example, `gmail send --dry-run --json` has this shape:

```json
{
  "dryRun": true,
  "status": "success",
  "action": "send email",
  "message": "DRY RUN, NO CHANGES MADE",
  "to": "person@example.com",
  "subject": "Subject",
  "cc": "",
  "bcc": ""
}
```

The older Drive `rename`, `move`, and `delete` dry-run paths retain their
existing action names and message (`"DRY RUN, NO FILES AFFECTED"`). Scripts
should branch on `dryRun == true`, not on a single message string.

Dry-run TSV uses the explicitly documented command fields, for example:

```text
dryRun	action	fileId	newName
True	rename Drive file	123	new_name.txt
```

## Errors and exit status

A JSON error has one top-level `error` object. `details` is optional:

```json
{
  "error": {
    "code": "validation_error",
    "message": "bad input"
  }
}
```

The stable typed CLI error codes and exit statuses are:

| Code | Exit status |
| --- | ---: |
| `configuration_error` | 2 |
| `authentication_error` | 3 |
| `permission_error` | 4 |
| `rate_limit_error` | 5 |
| `validation_error` | 6 |
| `network_error` | 7 |
| `not_found_error` | 8 |

Generic command/interaction failures use exit status `1`. In JSON mode, parse
stdout as an error document only when the process exits nonzero; always check
`$?` before accepting a response as successful data. Human diagnostics and
verbose tracebacks belong on stderr and must not be concatenated to JSON.

## Compatibility and versioning

The output contract is intentionally additive:

1. Existing top-level wrapper keys and provider pagination keys are preserved.
2. New optional provider fields may appear in JSON without constituting a
   breaking change.
3. Scripts should select known keys and tolerate unknown keys and absent
   optional keys.
4. TSV column order is stable for the command groups above. New columns will
   only be introduced with an explicit contract/versioning decision because
   positional TSV consumers are sensitive to order.
5. Use JSON for long-lived integrations that need provider types, optional
   fields, pagination, or forward compatibility. Use TSV for stable tabular
   extraction.
6. The project version (`pygog --version`) identifies the CLI release; this
   document describes the current contract for that release and should be
   checked when upgrading across releases.
