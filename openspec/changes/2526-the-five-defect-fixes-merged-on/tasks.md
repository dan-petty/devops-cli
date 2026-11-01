# Tasks

## 1. Add four guardrails to SECURITY.md

Reads: none. Changes: `SECURITY.md`.

- [ ] 1.1 A grep for each of the four guardrail phrases in SECURITY.md fails before the change and passes after: `grep -q 'frozen lockfile' SECURITY.md && grep -q 'userinfo' SECURITY.md && grep -q 'one time, through the egress check' SECURITY.md && grep -q 'automountServiceAccountToken' SECURITY.md`, and verify that `grep -q 'frozen lockfile' SECURITY.md && grep -q 'userinfo' SECURITY.md && grep -q 'one time, through the egress check' SECURITY.md && grep -q 'automountServiceAccountToken' SECURITY.md` fails on the base
- [ ] 1.2 Add a sentence to item 7 (Review Tool Execution) stating that a scan command that runs a tool adapter MUST use the frozen lockfile (`--frozen`) so the audit is reproducible and not affected by lockfile drift. Add a sentence to item 1 (Zero Secret Leakage) stating that a display string that names a server MUST use only the origin (scheme, host, port) of the URL it called and MUST never include the userinfo component. Add a sentence to item 2 (Strict Egress and SSRF Protection) stating that a NetworkPolicy or scrape target that names a host MUST resolve it one time, through the egress check, at connect time and MUST NOT cache the resolution. Add a sentence to item 5 (Least Privilege Runtime) stating that a pod that does not call the Kubernetes API MUST set `automountServiceAccountToken: false` so it holds no service account token, and verify that `grep -q 'frozen lockfile' SECURITY.md && grep -q 'userinfo' SECURITY.md && grep -q 'one time, through the egress check' SECURITY.md && grep -q 'automountServiceAccountToken' SECURITY.md` passes
- [ ] 1.3 SECURITY.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Add one guardrail to CONTRIBUTING.md

Reads: none. Changes: `CONTRIBUTING.md`.

- [ ] 2.1 A grep for the CVE-check guardrail phrase in CONTRIBUTING.md fails before the change and passes after: `grep -q 'known CVE' CONTRIBUTING.md`, and verify that `grep -q 'known CVE' CONTRIBUTING.md` fails on the base
- [ ] 2.2 Add a sentence to section 1 (Development Philosophy and Core Invariants) stating that a pull request that pins a Helm sub-chart version MUST check that version against known CVEs before merge, and MUST name the CVE identifier in the pull request body when a CVE is found and accepted, and verify that `grep -q 'known CVE' CONTRIBUTING.md` passes
- [ ] 2.3 CONTRIBUTING.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
