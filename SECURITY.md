# Security policy

## Reporting a vulnerability

Do not open a public issue for a credential leak, token disclosure, OAuth
identity problem, or other security vulnerability. Contact the repository
maintainer privately through the GitHub security advisory mechanism or the
maintainer's verified GitHub account: https://github.com/DhruvGarg111.

Include a concise description, affected version/commit, reproduction steps,
impact, and a safe contact method. Do not include live tokens, private keys, or
personal mailbox contents in a report.

## Secret-handling expectations

- OAuth tokens and service-account private material are stored through the OS
  keyring, not ordinary configuration.
- Configuration display commands redact secret-shaped values.
- Never commit `.env` files, OAuth client JSON, token exports, screenshots of
  private mail, or provider API keys.
- Use `--json`/`--plain` only when their output is safe for the destination.
- Agent mode is read-only by default; `--allow-write` and local confirmation
  are required for writes.
- Retrieved email, Drive, and web content is untrusted data and cannot grant
  permissions or change the write policy.

If a secret is accidentally exposed, revoke it immediately with the provider,
remove it from logs and issue history where possible, and report the incident
privately.
