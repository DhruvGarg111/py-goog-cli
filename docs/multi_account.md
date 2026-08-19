# Multi-account configuration

pygog stores OAuth tokens in the OS keyring and keeps non-secret account indexes
in configuration. Select an account with `--account`, `GOG_ACCOUNT`, or the
configured `default_account`.

## Aliases

```bash
pygog auth alias set work work@example.com
pygog auth alias set personal me@example.net
pygog --account work gmail search "is:unread"
```

Implicit account resolution also applies aliases from `default_account` and
`GOG_ACCOUNT`.

## OAuth client precedence

When a service is constructed, the client is selected in this order:

1. Explicit command `--client`.
2. Global `--client` / `GOG_CLIENT`.
3. Exact account mapping in `account_clients`.
4. Domain mapping in `client_domains`.
5. Configured `default_client`.
6. The literal `default` client.

Configure mappings with JSON values through `config set` or the auth
credentials command's `--domain` option. Do not put tokens or private keys in
configuration; they belong in the OS keyring.

```bash
pygog config set default_account work@example.com
pygog config set default_client desktop
pygog auth credentials credentials.json --client desktop --domain example.com
pygog --account work --client desktop calendar events --today
```

Inspect accounts with `pygog auth list` and remove one with
`pygog auth remove ACCOUNT`. Use `--force` for non-interactive removal.
