# Task 322: Cryptography Pure-Python Asymmetric Key Management & Hardware Token Authentication Research

**Issue**: [#322](https://github.com/dan-petty/devops-cli/issues/322)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

Most of what this issue describes was already done: `src/devops_cli/crypto/` generates
Ed25519 keys and X.509 certificates through the `cryptography` package with no OpenSSL
subprocess, and the `ssh/` and `tls/` packages the issue names do not exist. The remaining
subprocess cryptography was SSH host key handling in `src/devops_cli/git/operations.py` —
and examining it turned up a security defect rather than a portability one.

`_ensure_known_host` ran `ssh-keyscan` and appended whatever came back to
`~/.ssh/known_hosts` unconditionally. `ssh-keyscan` performs no verification; it reports the
key the network hands it. The result was that anyone able to intercept the first SSH
connection to a host had their key pinned permanently and silently, and it ran automatically
on every SSH clone. Reproduced before fixing:

```
known_hosts now contains:
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIATTACKERKEY...
```

Membership was tested with `ssh-keygen -F`, which additionally required the OpenSSH client
to be installed and cost a process spawn per check.

### Key Deliverables Completed:

- [x] **Pure-Python `known_hosts` (`src/devops_cli/crypto/known_hosts.py`)**:
  - Replaces `ssh-keygen -F` with in-process parsing and matching: comma-separated alias
    lists, `[host]:port` bracketed forms, `*`/`?` wildcards, `!` negations, `@revoked` and
    `@cert-authority` markers, and hashed hostnames recomputed via HMAC-SHA1.
  - A host whose only entries are `@revoked` is **not** trusted. Treating a revocation as
    evidence of trust would skip verification entirely and leave the withdrawn key in place.
  - A single malformed line is skipped rather than discarding the file, which would lose a
    `@revoked` marker recorded further down.
- [x] **Host Key Verification (`src/devops_cli/crypto/host_keys.py`)**:
  - Computes the SHA256 fingerprint in the exact form OpenSSH prints — unpadded standard
    base64 — because a padded or hex rendering would never compare equal to the value a user
    reads from the operator's documentation.
  - Verifies against fingerprints GitHub publishes at `https://api.github.com/meta`, so
    trust in the SSH host key derives from TLS PKI rather than from assuming the first
    answer received is honest.
  - Rejects unsupported key types and undecodable key material at parse time: writing an
    unusable entry into `known_hosts` silently breaks every later connection to that host.
- [x] **Fail-Closed Trust**: an unverifiable key for a pinned host is refused and nothing is
  written. `allow_unverified` restores trust-on-first-use for hosts publishing no
  fingerprints, and is **refused for hosts that do** — letting the flag override verification
  would reintroduce the defect behind an option.
- [x] **Hostname Provenance**: the entry is recorded under the hostname that was requested,
  not the one the scan response claimed, so a response naming other hosts cannot pin a key
  under those names.
- [x] **Centralized Constants**: `known_hosts` markers and hash prefix, accepted host key
  algorithms, the fingerprint prefix, GitHub's published fingerprints and meta URL.
- [x] **Automated Tests & Quality Gates**:
  - 66 tests in `tests/test_ssh_host_keys.py` using structural tuple equality assertions.
  - `host_keys.py` **100%**, `known_hosts.py` **100%**, `git/operations.py` **100%**.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all new modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy
  strict, audit, security, actionlint, docs, uv check, lockfile).
- The fingerprint implementation was validated against GitHub's live API: computing
  fingerprints from the raw keys in `ssh_keys` independently reproduces every value in
  `ssh_key_fingerprints`. If this disagreed with OpenSSH's rendering, every comparison
  against a published fingerprint would fail and the verification would be useless.
- The attack was re-run after the fix: a hostile key is refused with nothing written, and
  the genuine key is accepted.

## A Second Defect Found While Building This

Host pattern matching initially used `fnmatch`, which honours `[...]` as a character class.
OpenSSH writes a non-default port as the literal `[host]:port`, so under `fnmatch` such an
entry never matches itself — the host would be rescanned and re-added on every connection,
accumulating duplicates and re-running verification needlessly. OpenSSH's own matcher
supports only `*` and `?`, so patterns are now compiled accordingly. Pinned by a test.

## Design Constraint: Verification That Cannot Fail Is Not Verification

The previous code had the shape of a trust decision without making one. The fix is only
meaningful if it can refuse, so it fails closed: a key that cannot be checked is not
written, and a legitimate key rotation surfaces as an explicit refusal naming the
fingerprint that was offered, which the operator resolves deliberately. That is a worse
experience than silent acceptance exactly once per rotation, and a better one every other
time.

## Scope Note

**A pure-Python `ssh-keyscan` replacement was not implemented.** Retrieving a host key
without the OpenSSH client means implementing the SSH transport protocol — version exchange,
`KEXINIT` negotiation, and key exchange — and the value on offer is removing one subprocess
from a path that runs once per host. A hand-rolled partial protocol implementation in a
security-sensitive path is a poor trade against that, and the defect worth fixing was never
the retrieval: it was that nothing verified what the retrieval returned. `ssh-keyscan` is
retained for the network fetch and its output is now verified.

**FIDO2 / PKCS#11 hardware token inspection was not implemented.** It cannot be exercised
without physical tokens in CI, and shipping an unverifiable code path into the
authentication surface is the opposite of the auditability this task is about. **Native SSH
agent client integration** was likewise left out: nothing in the codebase currently consumes
an agent, so it would be an unexercised path.
