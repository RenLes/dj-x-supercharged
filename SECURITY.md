# Security policy

## Supported versions

This is a `0.x` alpha. Only the most recent commit on `main` is supported.

## What we care about

This project handles **OAuth tokens** for Spotify and X. Any vulnerability around token handling, leakage, or storage is treated as high severity. Specifically:

- Tokens are written to `~/.djx/tokens.json` with `chmod 0600`.
- Tokens never leave your machine except in outbound `Authorization: Bearer` headers to Spotify, X, and (optionally) xAI.
- The OAuth loopback server binds to `127.0.0.1` only and is one-shot (shuts down after capturing the code).

## Reporting a vulnerability

**Do not open a public issue.**

Instead, email the maintainers at the address listed in the GitHub repository's profile, or open a [private security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on GitHub.

Please include:
- Affected version / commit
- Reproduction steps
- Impact assessment

We aim to acknowledge within 7 days and patch within 30 days for high-severity issues.

## Out of scope

- Vulnerabilities in upstream libraries (please report to them directly)
- Issues that require an attacker to already have local access to your machine
- Rate-limit or quota issues — these are tier limitations, not vulnerabilities
