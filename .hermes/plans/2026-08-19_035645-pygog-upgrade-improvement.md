# pygog Upgrade and Improvement Implementation Plan

> **For Hermes:** Use the `subagent-driven-development` skill to implement this plan task-by-task. Do not commit or push unless the user explicitly authorizes it; if authorized, keep commits small and file-focused.

**Goal:** Turn the current alpha CLI into a reliable, secure, testable `0.2.0` release without expanding into new Google services prematurely.

**Architecture:** Preserve the existing Typer command → service wrapper → Google API layering, but make the boundaries explicit: a typed CLI context, a stable output/error layer, typed service results, and a constrained agent tool adapter. Stabilize existing Gmail, Calendar, Drive, Tasks, authentication, and agent behavior before adding roadmap services.

**Tech Stack:** Python 3.10+, Typer, Rich, Google API Python Client, google-auth, keyring, LiteLLM, pytest, pytest-cov, Ruff, mypy, Bandit, pip-audit, Hatchling, uv, GitHub Actions.

---

## 1. Current repository baseline

Repository synchronized from `origin/main` by fast-forward from `72964e2` to `3cafee6` (`Merge pull request #12 from DhruvGarg111/testing-improvement-config`).

### Structure and strengths

- 47 tracked files, 33 package modules, approximately 3,623 Python code lines.
- Clear layering:
  - Entry point and global state: `pygog/__main__.py`, `pygog/cli.py`
  - Typer commands: `pygog/commands/`
  - Google API wrappers: `pygog/services/`
  - OAuth/config storage: `pygog/auth/`, `pygog/config.py`
  - Agent registry/loop/adapters: `pygog/agent/`
  - JSON/TSV/Rich output: `pygog/output/`
- Wheel and source distribution build successfully with `uv build`.
- `python -m pygog --help` works in an isolated environment.
- pip-audit found no known vulnerable installed dependencies.
- Bandit found no medium/high-severity issue (three low-severity findings).
- All 39 tests pass under the existing Python 3.12 environment, and every test file passes in isolation.

### Reproducibility and quality baseline

- The full suite is environment/order-dependent: under a clean Python 3.14 environment, collection-time `sys.modules` replacement in `tests/test_drive_security.py` corrupts Rich and causes three dry-run tests to fail (`36 passed, 3 failed`).
- Measured coverage in that isolated run was 28%; agent code was 0% covered, and most command/service modules were below 40%.
- Ruff reports 423 violations. Most are mechanical (`W293`, `UP045`, `I001`), but the check is not currently clean.
- mypy reports 84 errors, including real agent/service contract bugs, plus `Any` leakage from the untyped Google client.
- There is no CI workflow, pytest configuration, coverage policy, lockfile, CONTRIBUTING guide, changelog, or security policy.
- Runtime dependencies are broad lower bounds; `typer[all]` emits a warning because current Typer has no `all` extra. `httpx` appears unused.

### Confirmed correctness/security defects to address first

1. `pygog/agent/tools.py:193-245` has broken Drive adapters:
   - `drive_list()` passes `folder_id=` to `DriveService.list_files()`, whose parameter is `parent_id`.
   - Both `drive_list()` and `drive_search()` iterate a response dictionary instead of `response["files"]`.
   - `drive_search()` turns a user term into a Drive query expression, while the service treats its input as a literal term and escapes it again.
2. `pygog/auth/client.py:153-204` does not persist or reconstruct token expiry. A reconstructed credential with no expiry can appear valid indefinitely, refresh failures are silently swallowed, and reauthorization can overwrite a valid stored refresh token with `None` when Google omits a new one.
3. OAuth account identity is not verified: the requested address is only a `login_hint`, but the returned token is stored under that requested label even if the user authenticated a different Google account.
4. `pygog/cli.py:25-34,108-117` always gives `state.client` a non-null default. Command factories pass it to `BaseService`, bypassing `Config.get_client_for_account()` and breaking account/domain client mappings.
5. Calendar commands create naive local datetimes (`pygog/commands/calendar.py:85-109,205-212`), while `CalendarService.list_events()` appends `Z` to naive values (`pygog/services/calendar.py:84-92`), mislabeling local time as UTC.
6. `ServiceAccountStorage` writes a full service-account key into ordinary `config.json` (`pygog/auth/keyring.py:114-137`), and `pygog config list` would display it. The feature has no provisioning command and is incomplete.
7. Drive download/export derives a local path directly from a remote filename and opens the final target with `wb`; path separators/traversal can escape the intended directory, and a failed transfer can leave an existing target truncated.
8. Several advertised controls are inert or inconsistent:
   - `--no-input` is stored but never enforced.
   - `--force-consent` is accepted but not passed into the OAuth authorization request.
   - `keyring_backend` is configurable but does not select a backend.
   - Configured color mode is not consistently applied.
9. Agent mode sends Google data and web/email content to an external LLM. `ask --yes` removes write confirmations, creating a prompt-injection path from untrusted content to Gmail sends, Drive shares, calendar creation, and task mutations.
10. JSON/TSV support and response envelopes differ by command; no public compatibility contract exists.

### Existing GitHub issues to incorporate

- #4: multi-account and alias workflow documentation.
- #5: JSON output schema examples and compatibility guarantees.
- #7: Calendar relative-date shortcuts. `calendar events` already has `--today/--tomorrow`, while `calendar search` still lacks complete `--tomorrow`, `--from`, and `--to` behavior.

---

## 2. Release strategy and priorities

### Release 0.1.1 — stabilization (P0)

Fix confirmed data/auth/agent bugs, make tests deterministic, and add CI. Do not add new Google services.

### Release 0.2.0 — safe automation contract (P1)

Centralize context, confirmation, output, errors, time handling, pagination, and agent permissions. Document stable scripting behavior.

### Later releases (P2)

Only after 0.2.0 is stable: Contacts/Meet/Keep/TUI work from the roadmap, guided by separate requirements and OAuth-scope review.

---

## 3. P0 implementation tasks — 0.1.1 stabilization

### Task 1: Make the test suite deterministic

**Objective:** Ensure one `pytest` invocation behaves identically across supported Python versions and test order.

**Files:**
- Modify: `tests/test_drive_security.py`
- Modify: `tests/output/test_plain_output.py`
- Modify: `tests/test_drive_dry_run.py`
- Create: `tests/conftest.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

**Steps:**

1. Replace global `sys.modules[...] = MagicMock()` assignments with targeted `patch()` fixtures or use the real installed dependencies.
2. Add shared fixtures that reset `pygog.cli.state` and the `pygog.config._config` singleton after every test.
3. Convert mixed `unittest.TestCase`/pytest tests to normal pytest functions unless a class provides real value.
4. Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, strict marker/config checks, and concise tracebacks.
5. Add coverage configuration with branch coverage and an initial achievable floor (recommend 30%, then raise per phase).
6. Ignore `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `dist/`, `build/`, `*.egg-info/`, and local virtual environments.

**Verification:**

```bash
uv sync --extra dev
uv run pytest -q
uv run pytest -q --random-order-bucket=global  # if pytest-random-order is adopted
uv run coverage run --branch -m pytest -q
uv run coverage report --show-missing
```

Expected: all 39 existing tests pass in one process on Python 3.10 through the newest claimed version.

### Task 2: Repair and cover the agent tool adapters

**Objective:** Restore Drive reads in natural-language mode and prevent future command/service contract drift.

**Files:**
- Modify: `pygog/agent/tools.py:193-245`
- Modify: `pygog/agent/registry.py`
- Create: `tests/agent/test_tools.py`
- Create: `tests/agent/test_registry.py`

**TDD cases:**

1. `drive_list(folder_id="x")` calls `DriveService.list_files(parent_id="x")`.
2. Drive adapters read `result.get("files", [])`, not the response dictionary iterator.
3. `drive_search("quarterly report")` passes a literal search term once; it does not build a second query language inside the adapter.
4. Empty/missing `files` responses return `[]`.
5. Every registered adapter is tested against a fake service and returns the documented JSON-serializable shape.
6. Registry tests cover `Optional`, `list[T]`, primitive defaults, required fields, and destructive metadata.
7. Invalid model arguments are rejected before the service call rather than becoming broad `TypeError` strings.

**Verification:**

```bash
uv run pytest tests/agent -q
uv run mypy pygog/agent
```

Expected: Drive list/search adapter tests pass; no agent-specific mypy errors remain.

### Task 3: Persist OAuth expiry and make refresh failures explicit

**Objective:** Ensure expired credentials are refreshed reliably and authentication failures cannot masquerade as valid sessions.

**Files:**
- Modify: `pygog/auth/client.py:116-204`
- Modify: `pygog/auth/keyring.py`
- Create: `tests/auth/test_client.py`
- Create: `tests/auth/test_keyring.py`

**TDD cases:**

1. Serialization stores `expiry` in an ISO/RFC3339-compatible form.
2. Reconstruction restores an aware expiry timestamp; prefer Google’s `Credentials.to_json()` / `Credentials.from_authorized_user_info()` contract over a hand-maintained subset.
3. Expired credentials with a refresh token call `refresh()` and persist the new token and expiry.
4. Refresh failure raises a typed authentication error with re-authentication guidance; it is never silently ignored.
5. `check_token()` and normal service use report the same validity semantics.
6. Keyring corrupt JSON/backend failures are distinguishable from “account not found.”
7. Reauthorization preserves the previously stored refresh token when Google returns no new refresh token.
8. Request `openid email`, resolve the authenticated canonical email, and refuse to store a token under a different requested account label without an explicit reconciliation flow.
9. Mutation previews include the verified account identity, not only the user-supplied alias/login hint.

**Verification:**

```bash
uv run pytest tests/auth/test_client.py tests/auth/test_keyring.py -q
```

Expected: expiry round-trip and refresh tests pass without a network call.

### Task 4: Restore multi-account OAuth client selection

**Objective:** Make explicit clients, per-account clients, domain clients, and the default client resolve in the documented precedence order.

**Files:**
- Modify: `pygog/cli.py:25-34,51-117`
- Modify: `pygog/services/base.py:20-35`
- Modify: command `get_service()` helpers in:
  - `pygog/commands/gmail.py`
  - `pygog/commands/calendar.py`
  - `pygog/commands/drive.py`
  - `pygog/commands/tasks.py`
- Extend: `tests/test_config.py`
- Create: `tests/test_cli_context.py`

**Required precedence:**

1. Explicit `--client` / `GOG_CLIENT` override.
2. Exact `account_clients[email]` mapping.
3. `client_domains[domain]` mapping.
4. Configured default client.
5. Literal `"default"` fallback.

**Implementation direction:** Store an optional explicit override in CLI context. Do not eagerly replace it with `"default"` before `BaseService` has evaluated account/domain mappings.

**Verification:**

```bash
uv run pytest tests/test_config.py tests/test_cli_context.py -q
```

Expected: aliases and client mappings work together for two fake accounts without touching the keyring/network.

### Task 5: Fix OAuth scope and consent behavior

**Objective:** Request only valid, implemented, least-privilege scopes and make CLI flags truthful.

**Files:**
- Modify: `pygog/auth/client.py:14-99,116-151`
- Modify: `pygog/commands/auth.py:79-128,249-260`
- Extend: `tests/auth/test_client.py`
- Update: `README.md`

**Steps:**

1. Change default services to the four implemented services: Gmail, Calendar, Drive, Tasks.
2. Reject unknown service names instead of silently producing an empty/incomplete scope set.
3. Complete read-only mappings; do not leave write scopes such as Gmail settings or Docs scopes in a “read-only” request without an explicit reason.
4. Pass `prompt="consent"` (or the supported equivalent) when `force_consent=True` and test the generated authorization kwargs.
5. Decide whether unsupported scopes (Contacts, Chat, Classroom, Keep, etc.) should be removed until commands exist.

**Verification:**

```bash
uv run pytest tests/auth/test_client.py -q
```

Expected: deterministic scopes for default, explicit, read-only, `all`, and invalid inputs.

### Task 6: Establish CI and a reproducible development environment

**Objective:** Prevent regressions from merging when tests, lint, types, or packaging fail.

**Files:**
- Modify: `pyproject.toml`
- Create: `uv.lock`
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`

**Steps:**

1. Replace `typer[all]` with the actual required Typer/Rich/Shellingham dependencies.
2. Remove `httpx` and `python-dateutil` if a final import audit confirms no runtime path uses them.
3. Move LiteLLM and DDGS into an optional `agent` extra so the normal Google CLI install remains smaller and has a reduced dependency surface.
4. Define a modern dev dependency group for pytest, coverage, Ruff, mypy, Bandit, pip-audit, and build verification.
5. Generate and commit a uv lockfile for reproducible development/CI while retaining appropriate package dependency ranges in `[project.dependencies]`.
6. Add CI jobs for:
   - pytest + coverage on Python 3.10, 3.11, 3.12, 3.13, and 3.14 if all dependencies support them;
   - at least one Windows smoke job because keyring/config paths are platform-sensitive;
   - Ruff check/format;
   - mypy;
   - Bandit and pip-audit;
   - `uv build` and clean-wheel installation/`pygog --help` smoke test.
7. Add CI badges only after the workflow is green.

**Verification:**

```bash
uv sync --extra dev --extra agent
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy pygog
uv run bandit -r pygog -q
uv run pip-audit
uv build --out-dir "$LOCALAPPDATA/Temp/pygog-build"
```

Expected: every command exits 0 in a clean checkout.

---

## 4. P1 implementation tasks — 0.2.0 safe automation contract

### Task 7: Make Calendar time handling timezone-correct and complete issue #7

**Objective:** Interpret relative and ISO dates consistently in the configured/local timezone and never label local wall time as UTC.

**Files:**
- Modify: `pygog/commands/calendar.py:68-116,197-220`
- Modify: `pygog/services/calendar.py:52-103,334-373`
- Create: `pygog/utils/datetime.py`
- Create: `tests/test_calendar_time.py`

**Steps:**

1. Add one parser/range builder that always returns timezone-aware datetimes.
2. Resolve timezone from explicit command option → `GOG_TIMEZONE`/config → system local timezone.
3. Never append `Z` to a naive datetime. Reject naive values at the service boundary or attach the explicitly resolved timezone first.
4. Add `--tomorrow`, `--from`, and `--to` to `calendar search`.
5. Validate mutually exclusive shortcuts and define documented precedence rather than silently ignoring inputs.
6. Test date ranges around midnight and DST boundaries with fixed clocks.

**Verification:**

```bash
uv run pytest tests/test_calendar_time.py -q
```

Expected: exact RFC3339 boundaries for UTC, Asia/Kolkata, and a DST-observing timezone.

### Task 8: Centralize interaction policy (`--force`, `--no-input`, dry-run)

**Objective:** Give every destructive operation one predictable confirmation policy suitable for terminals and automation.

**Files:**
- Modify: `pygog/cli.py`
- Create: `pygog/interaction.py`
- Modify destructive commands in `pygog/commands/auth.py`, `calendar.py`, `drive.py`, `gmail.py`, and `tasks.py`
- Create: `tests/test_interaction.py`
- Extend: `tests/test_drive_dry_run.py`

**Policy:**

- `--no-input` must never prompt. If confirmation is required and neither `--force` nor dry-run is present, exit nonzero with an actionable message.
- `--force` skips confirmation consistently, including `auth remove`.
- Dry-run must make no service/auth/network call.
- JSON dry-run and error responses remain valid JSON on stdout; diagnostics go to stderr.
- Add dry-run first to high-risk operations: Gmail send, Drive upload/share/unshare/copy/mkdir, Calendar create/update/delete/respond, and Tasks create/update/delete/clear.

**Verification:**

```bash
uv run pytest tests/test_interaction.py tests/test_drive_dry_run.py -q
```

Expected: a table-driven test covers interactive accept/decline, forced, no-input, and dry-run for every destructive command.

### Task 9: Constrain the LLM trust boundary

**Objective:** Prevent untrusted mailbox/web content from driving unreviewed writes and document data disclosure.

**Files:**
- Modify: `pygog/commands/ask.py`
- Modify: `pygog/agent/core.py`
- Modify: `pygog/agent/registry.py`
- Create: `pygog/agent/policy.py`
- Create: `tests/agent/test_policy.py`
- Update: `docs/agent_setup.md`
- Update: `README.md`

**Recommended policy:**

1. Agent mode is read-only by default.
2. Require explicit `--allow-write` to expose mutation tools at all.
3. Always show and confirm the final write action after arguments are resolved; remove or sharply restrict `ask --yes` because web/email/Drive content is untrusted.
4. Label tool results as untrusted data in the system/tool messages and prohibit instructions found inside that data from changing policy.
5. Allow an explicit tool allowlist (for example `--tools gmail_search,calendar_events`) rather than the unused `GOG_ENABLE_COMMANDS` variable.
6. Clearly disclose that prompts and selected Google data are sent to the chosen LiteLLM provider.
7. Redact OAuth tokens, client secrets, private keys, and sensitive exception payloads before logging or returning errors to the model.

**Verification:**

```bash
uv run pytest tests/agent/test_policy.py -q
```

Expected: injected instructions in fake email/web content cannot invoke a mutation without a local confirmation.

### Task 10: Define a typed CLI context and stable error boundary

**Objective:** Remove module-global ambiguity and produce consistent exit behavior without exposing raw provider errors.

**Files:**
- Modify: `pygog/cli.py`
- Modify: `pygog/__main__.py`
- Create: `pygog/context.py`
- Create: `pygog/errors.py`
- Modify: `pygog/services/base.py`
- Modify: command modules under `pygog/commands/`
- Create: `tests/test_errors.py`

**Steps:**

1. Replace the mutable module-global `State` with a typed dataclass passed through `typer.Context.obj` (or wrap migration behind one accessor to avoid a flag day).
2. Validate `--json` and `--plain` as mutually exclusive.
3. Honor configured color mode without setting private Rich attributes directly.
4. Add typed exceptions for configuration, authentication, permission, rate limit, validation, network, and not-found errors.
5. Map exceptions to stable exit codes and user messages at one top-level boundary.
6. In JSON mode, return a stable machine-readable error object; keep stdout clean and put human diagnostics on stderr.
7. Show tracebacks only with `--verbose`.

**Verification:**

```bash
uv run pytest tests/test_cli_context.py tests/test_errors.py -q
```

Expected: table-driven tests assert exit code, stdout, and stderr for each error class and output mode.

### Task 11: Standardize JSON/TSV output and complete issue #5

**Objective:** Make automation behavior documented, testable, and backward-compatible.

**Files:**
- Modify: `pygog/output/json_output.py`
- Modify: `pygog/output/plain_output.py`
- Modify: `pygog/output/table_output.py`
- Modify command modules under `pygog/commands/`
- Create: `tests/output/test_json_output.py`
- Create: `tests/output/test_table_output.py`
- Create: `tests/commands/` snapshot/contract tests
- Create: `docs/json_scripting.md`

**Steps:**

1. Inventory every command’s current JSON shape before changing it.
2. Define per-command schemas and a compatibility/versioning policy. Avoid a gratuitous universal envelope if it would break existing scripts.
3. Preserve pagination metadata (`nextPageToken`) consistently.
4. Make `--plain` available for all list/search commands with stable columns.
5. Normalize `None`, tabs, CR/LF, nested values, and Unicode behavior.
6. Add golden-output tests for Gmail search, Drive list/search, Calendar events/search, Tasks list, dry-run, and errors.
7. Publish realistic examples and optional/null field notes in `docs/json_scripting.md`.

**Verification:**

```bash
uv run pytest tests/output tests/commands -q
```

Expected: byte-for-byte stable output fixtures for JSON and TSV modes.

### Task 12: Harden config and secret handling

**Objective:** Prevent secret disclosure/corruption and remove settings that claim unsupported behavior.

**Files:**
- Modify: `pygog/config.py`
- Modify: `pygog/auth/credentials.py`
- Modify: `pygog/auth/keyring.py`
- Modify: `pygog/commands/config_cmd.py`
- Modify: `pygog/commands/auth.py`
- Extend: `tests/test_config.py`
- Extend: `tests/auth/test_keyring.py`

**Steps:**

1. Write config and OAuth client files atomically via a same-directory temporary file plus replace.
2. Use restrictive permissions where the platform supports them and document Windows Credential Manager behavior.
3. Validate loaded configuration types/schema; report malformed files instead of silently replacing them with an empty in-memory config.
4. Preserve or back up the malformed file, add same-process/inter-process write locking, and test concurrent writers rather than allowing a later `config set` to destroy recoverable state.
5. Redact sensitive keys from `config list/get` by default and block `service_account:*` through generic `config set`.
6. Recommended YAGNI choice: remove incomplete `ServiceAccountStorage` until a secure, scoped provisioning workflow is designed. If retained, store the key in OS keyring, never `config.json`, require explicit scopes, enumerate service-account-only identities, and make removal delete/verify the selected credential type instead of always reporting success.
7. Either implement real keyring backend selection or remove the inert `auth keyring` setter and related environment variables.
8. Test interrupted writes, malformed JSON5, concurrent writes, keyring unavailable/corrupt data, and secret redaction.

**Verification:**

```bash
uv run pytest tests/test_config.py tests/auth/test_keyring.py -q
```

Expected: simulated write failure leaves the previous valid config intact; no secret appears in command output.

### Task 13: Add pagination, retries, and safe file transfer

**Objective:** Make service commands reliable for large accounts and transient API failures.

**Files:**
- Modify: `pygog/services/base.py`
- Modify: `pygog/services/gmail.py`
- Modify: `pygog/services/calendar.py`
- Modify: `pygog/services/drive.py`
- Modify: `pygog/services/tasks.py`
- Modify corresponding command modules
- Create: `tests/services/`

**Steps:**

1. Add shared page iterators and expose `--page-token` plus an explicit `--all` mode; keep bounded defaults.
2. Retry only safe/idempotent calls for documented transient statuses with capped exponential backoff and jitter.
3. Add Drive shared-drive flags (`supportsAllDrives`, `includeItemsFromAllDrives`, appropriate corpora/drive ID) where required.
4. Apply explicit, bounded timeouts to OAuth refresh, Google API requests, LiteLLM, and DDGS calls.
5. Reduce a remote default filename to a validated basename; reject absolute paths, separators, reserved names, and traversal before creating a local target.
6. Download/export to a temporary sibling file, fsync/close, then atomically rename on success.
7. Add no-clobber by default and explicit overwrite behavior.
8. Validate upload paths and make error cleanup deterministic.
9. Unit-test pagination, 429/5xx retries, no retry for permanent 4xx, timeout handling, path traversal/reserved filenames, partial download cleanup, and shared-drive request parameters.

**Verification:**

```bash
uv run pytest tests/services -q
```

Expected: fake two-page APIs return all items; transient failures retry within the cap; failed transfers do not leave a final corrupt file.

### Task 14: Reduce command/service duplication after behavior is covered

**Objective:** Simplify maintenance without a risky pre-test rewrite.

**Files:**
- Modify command modules under `pygog/commands/`
- Modify output helpers under `pygog/output/`
- Remove or use: `pygog/utils/console.py`, unused output helpers, unused constants

**Steps:**

1. Only after command contract tests exist, extract common service acquisition, output-mode selection, list rendering, and confirmation logic.
2. Use typed payload aliases/TypedDicts for Google responses rather than leaking `Any` through every method.
3. Configure mypy to tolerate only the untyped Google API boundary, not the whole application.
4. Fix mypy errors by narrowing/casting once at that boundary.
5. Run Ruff format/check and eliminate all existing violations in a dedicated mechanical change, separate from functional fixes.
6. Remove or implement the unused Gmail `thread get --download/--out-dir` options; add a CLI test so options cannot remain decorative.
7. Generate the agent capability prompt and tool summaries from the registry, removing stale summaries for nonexistent `drive_upload`, `drive_delete`, and `calendar_delete` tools and the unused `DEFAULT_MODEL` constant.
8. Prove dead code before removing `safe_print`, unused output functions, unused environment constants, and unsupported service-account paths.

**Verification:**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy pygog
uv run pytest -q
```

Expected: zero Ruff/mypy errors and no output snapshot changes.

---

## 5. Documentation, packaging, and release tasks

### Task 15: Correct project metadata and onboarding

**Files:**
- Modify: `pyproject.toml:55-58`
- Modify: `README.md`
- Modify: `docs/agent_setup.md`
- Create: `docs/multi_account.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`

**Steps:**

1. Replace `https://github.com/pygog/pygog` URLs and clone commands with the actual repository URL or the intended canonical organization URL.
2. Verify whether `pip install pygog` is genuinely published; otherwise document installation from the repository until a release exists.
3. Complete GitHub issue #4 with tested multi-account, alias, client-mapping, and default-account workflows.
4. Complete issue #5 with generated JSON examples tied to output contract tests.
5. Document the optional `agent` extra, supported providers/models, privacy boundary, and write policy.
6. Generate or validate command reference snippets against Typer help so `possible-commands.md` cannot silently drift.
7. Correct existing drift explicitly: `config show` should be `config list`, `pygog time` should be `pygog time now` unless the callback is redesigned, and the reference must include `--color`, `--force`, and `--no-input`.
8. Add contributor setup and exact quality commands.
9. Add a responsible disclosure policy and token-redaction guidance.

**Verification:**

```bash
uv run pygog --help
uv run pygog auth --help
uv run pygog calendar search --help
uv run pygog drive delete --help
```

Expected: all copied commands match real CLI help and docs links resolve.

### Task 16: Prepare and validate the 0.2.0 release

**Files:**
- Modify version source (`pyproject.toml` and remove duplicate manual versioning in `pygog/__init__.py`, or adopt one dynamic source)
- Modify: `CHANGELOG.md`
- Create/update release workflow only after manual build/install is proven

**Steps:**

1. Establish one source of truth for version metadata via `importlib.metadata.version("pygog")` or Hatch dynamic versioning.
2. Build wheel/sdist in a clean environment.
3. Install the wheel into a fresh environment, not the editable source tree.
4. Smoke-test `pygog --version`, `pygog --help`, config path, and offline dry-runs.
5. Run the full quality/security pipeline.
6. Publish to TestPyPI first if packaging is intended, install from TestPyPI, then publish the exact validated artifacts to PyPI.
7. Tag and create a GitHub release only after explicit user authorization.

**Verification:**

```bash
uv build
uv venv "$LOCALAPPDATA/Temp/pygog-wheel-smoke"
uv pip install --python "$LOCALAPPDATA/Temp/pygog-wheel-smoke/Scripts/python.exe" dist/*.whl
"$LOCALAPPDATA/Temp/pygog-wheel-smoke/Scripts/pygog.exe" --version
"$LOCALAPPDATA/Temp/pygog-wheel-smoke/Scripts/pygog.exe" --help
"$LOCALAPPDATA/Temp/pygog-wheel-smoke/Scripts/pygog.exe" drive delete fake-id --dry-run --json
```

Expected: installation and offline smoke commands succeed without importing the working tree.

---

## 6. Definition of done for 0.2.0

- [ ] Agent Drive list/search work and all agent adapters have unit tests.
- [ ] OAuth expiry round-trips; refresh errors never fail silently.
- [ ] OAuth reauthorization preserves refresh capability and tokens are bound to the verified Google identity.
- [ ] Multi-account client mapping follows documented precedence.
- [ ] Default OAuth scopes cover only implemented services and read-only mode is truthful.
- [ ] Calendar filters are timezone-aware; issue #7 is complete.
- [ ] `--no-input`, `--force`, and dry-run have one tested policy.
- [ ] Agent writes are disabled by default and untrusted content cannot bypass local review.
- [ ] Config writes are atomic and secrets are redacted/not stored in ordinary config.
- [ ] JSON/TSV contracts are documented and snapshot-tested; issues #4 and #5 are complete.
- [ ] Pagination and transient retry behavior are tested.
- [ ] Full tests pass in one process on the supported Python matrix.
- [ ] Coverage is at least 70% overall, with critical auth/agent/interaction modules at least 85%.
- [ ] Ruff, Ruff format, mypy, Bandit, pip-audit, build, and wheel smoke tests pass in CI.
- [ ] README/project URLs, installation instructions, and version metadata are correct.
- [ ] Working tree contains no generated build/test artifacts.

---

## 7. Risks, tradeoffs, and decisions needed before implementation

1. **Agent auto-confirm:** Recommended: remove/restrict `ask --yes` and require read-only-by-default plus per-write confirmation. Keeping unrestricted auto-confirm is a material prompt-injection risk.
2. **Service accounts:** Recommended: remove the incomplete storage path for 0.1.1. A secure implementation needs keyring storage, explicit scopes, domain delegation documentation, and tests.
3. **JSON compatibility:** Inventory existing shapes before standardization. Fixing inconsistency must not silently break scripts.
4. **Python support:** Test 3.10–3.14 before adding classifiers. If dependencies fail on 3.14, publish an explicit temporary upper bound/support statement rather than claiming untested compatibility.
5. **Dependency split:** Moving LiteLLM/DDGS to an `agent` extra makes base installs smaller but changes installation instructions for current agent users; document it as a 0.2.0 change.
6. **Large formatting change:** Ruff reports hundreds of mostly mechanical issues. Keep formatting/import cleanup separate from behavior changes to preserve reviewable diffs.
7. **Coverage floor:** Raise incrementally (30% baseline → 50% after P0 → 70% for 0.2.0) so CI becomes useful immediately without encouraging low-value tests.

## Recommended implementation order

1. Task 1 — deterministic tests.
2. Task 2 — agent Drive correctness.
3. Tasks 3–5 — OAuth expiry, multi-account client resolution, least-privilege scopes.
4. Task 6 — CI and reproducible environment.
5. Tasks 7–9 — timezone, interaction policy, agent trust boundary.
6. Tasks 10–12 — context/errors, output contract, secret-safe config.
7. Tasks 13–14 — pagination/retries and cleanup/refactor.
8. Tasks 15–16 — documentation and release validation.
