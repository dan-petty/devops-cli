# Design

## Decisions

- Remove the ignore entry, because `npm audit` no longer reports GHSA-fc5q-39xc-vjpf after GitHub withdrew it on 2026-11-18.
- Keep `.npm-audit-ignore.yaml` with an empty `vulnerabilities` list. SECURITY.md "A Finding with No Fix" names the file as the place of the next entry, and its header tells the form.

## Rejected alternatives

- Bump picomatch: `npm view picomatch versions --json` shows 4.0.7 as the newest release, and the advisory names no first patched version.
- Add an `overrides` entry: no picomatch version outside the advisory range exists to override to.
- Renew the entry for 3 more days: the entry would ignore a finding that `npm audit` does not report, and its statement would be wrong.
- Delete `.npm-audit-ignore.yaml`: the next agent that must add an entry would lose the documented form of the file.
