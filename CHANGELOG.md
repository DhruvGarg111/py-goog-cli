# Changelog

All notable changes are recorded here. The project is not being published or
released by this working session.

## [1.1.0] — 2026-08-19

This release contains the upgrade work described below.

- Added deterministic test isolation, broader auth/agent/service coverage, and
  reproducible uv development dependencies.
- Hardened OAuth expiry, identity verification, refresh-token preservation,
  account/client routing, and least-privilege scopes.
- Added timezone-aware Calendar ranges with IANA timezone resolution.
- Added unified confirmation, `--force`, `--no-input`, and dry-run behavior for
  mutations.
- Made the natural-language agent read-only by default with explicit write
  capability, local confirmation, tool allowlists, and untrusted-result
  boundaries.
- Added typed CLI context/errors and stable JSON/TSV scripting documentation.
- Added atomic configuration writes, secret redaction, keyring-only
  service-account storage, pagination/retry helpers, and safer Drive transfers.

This entry is a work log for the unreleased branch, not a published release
claim. Version tagging, package publishing, and GitHub releases require an
explicit maintainer decision.
