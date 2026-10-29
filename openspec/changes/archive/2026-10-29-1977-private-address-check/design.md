# Design

## Scope

The rule holds for every tracked text file outside three groups:

- **Test code** (`tests/**/*.py`, `.ast-grep/rule-tests/`). The egress and reference classifiers have RFC 1918 behavior of their own, so their tests must send RFC 1918 addresses. Test fixtures, snapshots and other data under `tests/` stay in scope, because a recording from a live system is the likely way a real address gets into the tree.
- **Archived OpenSpec changes.** They record merged work. The living specs, which the archive writes, stay in scope.
- **`CHANGELOG.md`.** Release-please writes it from merged titles and bodies.

## What passes

- A range in CIDR form with a prefix shorter than 32. A `/32` is a host and fails.
- Three upstream values, each named in the test with its source. They are an upstream project's default or example, not a machine of this project.
- RFC 5737 addresses, loopback, `example.com`, `localhost`, a bare `.lan`, `*.lan` and `<role>.lan`.

## Rejected alternatives

- **Every tracked file, as the issue says.** 98 addresses in 27 test files would need a marker or a rewrite, and the classifier tests cannot use RFC 5737 space for RFC 1918 behavior.
- **`ipaddress.is_private`.** Python 3.14 reads the RFC 5737 blocks and loopback as private, which SECURITY.md allows.
- **A Gitleaks custom rule.** Regular expressions only, no CI step runs Gitleaks today, and the issue rules out an octet pattern.
- **A per-line marker that allows one address.** It is an escape, which the owner rule of 2026-10-20 rules out.
- **A list of allowed files.** A file list hides the next address in the same file.
- **`.local` hosts.** SECURITY.md names them, but `svc.cluster.local` is Kubernetes service DNS in many manifests. The issue scopes the check to `.lan`.
