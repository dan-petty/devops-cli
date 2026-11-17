# Proposal: #6204

## Why
The `audit` row of Static Analysis fails on main. `npm audit` of the OpenSpec lockfile reports GHSA-fc5q-39xc-vjpf (picomatch ReDoS, high), and no released picomatch holds the fix. SECURITY.md "A Finding with No Fix" asks for a time-limited ignore entry in the ignore file of the scanner, but `npm audit` reads no ignore file and `devops ci audit` read none. Closes #6204.

## What Changes
- `devops ci audit` and the gate's `audit` row read `.npm-audit-ignore.yaml`, in the form of `.trivyignore.yaml`: `id`, `paths`, `statement` and `expired_at`.
- An `npm audit` report of findings passes only when an entry for its lockfile, before its `expired_at` day, covers each advisory of the report. An entry names one advisory, each lockfile and the tracking issue; a wildcard is refused.
- The audit names each entry that it used and each that expired.
- One entry: GHSA-fc5q-39xc-vjpf on `src/devops_cli/tools_lock/openspec/package-lock.json`, until 2026-11-20, tracked by #6202.

## Capabilities
- New: `ci-dependency-audit`.

## Impact
- Main and every pull request pass the `audit` row again until 2026-11-20. On that day the row fails again unless a picomatch release fixes the advisory or the entry is renewed with new proof.
- An audit that could not run never passes through an entry.

## Feasibility
- Read 2026-11-17: the advisory names no patched version and covers picomatch `<= 4.0.7`; picomatch 4.0.7 is the newest release; OpenSpec 2.1.0 depends on `picomatch ^4.0.4` and `tinyglobby ^0.2.17`. The report is recorded in `tests/fixtures/npm_audit/picomatch_redos.json`.

## Existing Tool Considered
- npm has no ignore option for `npm audit` (no `--ignore` flag, no config key).
- `better-npm-audit` and `audit-ci` wrap `npm audit` with an allow list, but they add a new Node tool to the tools lock for one list. `osv-scanner` reads ignores with a date, but it would replace `npm audit`, and SECURITY.md forbids turning off a scanner.
- Cost to build: about 120 lines in `dependency_audit.py` and `ci.py` and 12 tests, under 1 hour. The entry form copies `.trivyignore.yaml`, so the repository has one ignore form.
