# Proposal

## Why

Issue #1538: the security row of `devops ci` runs Bandit over `src/` and `tests/` at medium severity and above, so nobody reviews a low-severity finding in `src/`. The owner decided on 2026-10-10 that Bandit covers both targets at medium and above through one shared `.bandit`, and that the low findings in `src/` get this item. The item asks for three things:

- A production `assert` becomes an explicit check, because Python drops `assert` under `-O`.
- A process that starts by a bare program name goes through the process seam.
- Each password-like or `random` literal is fixed or carries a reviewed `# nosec` with its rule and a reason. Then a new low finding in `src/` fails the gate.

## What Changes

- **The gate.** The security row runs Bandit two times with the shared `.bandit`: over `src/` at low severity and above, then over `tests/` at medium and above. Each file is scanned once, as before. `devops ci security --severity` sets the threshold of the `tests/` run; `src/` is always scanned at low.
- **The shared config.** `.bandit` skips four low-severity rules, each with its reason: B404 (importing `subprocess`) and B603 (a list-form call without a shell), which a CLI that runs tools has by design; B110 and B112 (swallowed exceptions), which the swallowed-failures ratchet counts with Ruff's S110 and S112. All four are low severity, so the medium run over `tests/` does not change. The three `# nosec B603` markers in `src/` go, because the config skips the rule.
- **Asserts.** In `ai/benchmark/runner.py` the loop branches on `client is None`, which is a dry run, so the `assert` goes. In `roadmap/intake.py` four asserts become `RoadmapIntakeError`. `_apply_placement` makes its two checks before any write, so a failed check leaves no label on the issue.
- **Processes.** `ai/rag/drift.py` and `github/metrics.py` run `git` through `run_subprocess` as local reads. Each keeps its fallback, and the log line gives the runner's error, which names the program when it is missing.
- **Literals.**
  - `vulnerability_lookup.py` takes `token or None` in place of `token if token != "" else None`.
  - `sanitizer.py` masks a URL password with one `_URL_MASK` constant in place of two `"***"` literals.
  - Nine names, enum values, secret names and path defaults that only look like credentials carry `# nosec B105`, `B106` or `B107` with a reason.
  - Five `random` uses carry `# nosec B311` with a reason. Two are seeded samples that must repeat, and three are retry jitter and chaos fault rates that guard nothing.
- **Markers.** Every `# nosec` in `src/` names its rule and gives a reason after a second `#`. A test in `tests/test_architectural_invariants.py` refuses a bare marker. The existing markers get their reasons.
- **The suppression ceiling.** `src nosec` in `DEFAULT_SUPPRESSION_CEILINGS` rises from 13 to 23: 13 new markers, less the 3 B603 markers that go.
- The gate is a behavior that a consumer observes, so the change carries a spec delta: the new capability `ci-security-gate`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ci-security-gate`: what the security row of `devops ci` scans, at which severity, which rules the shared `.bandit` skips, and the form of a `# nosec` marker in `src/`.

## Impact

- `.bandit`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`.
- `src/devops_cli/ai/benchmark/runner.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/security/sanitizer.py`, and the files that get a `# nosec` marker or lose one.
- `tests/test_ci.py`, `tests/test_security_bandit.py`, `tests/test_architectural_invariants.py`, `tests/test_github_metrics.py`, `tests/test_rag_drift.py`, `tests/test_roadmap_intake_checks.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

Measured on origin/main d156ce7e with the locked Bandit 1.9.4 (`uv run bandit -r src -f json`): 124 findings in `src/`, all low severity.

| Rule | Count | Handling |
| :--- | ---: | :--- |
| B101 `assert_used` | 5 | Fixed: `ai/benchmark/runner.py:389`, `roadmap/intake.py:568`, `:1121`, `:1122`, `:1217`. |
| B105 hardcoded password string | 6 | 1 fixed (`security/vulnerability_lookup.py:489`); 5 marked. |
| B106 hardcoded password argument | 2 | 1 fixed (`security/sanitizer.py:399`); 1 marked (`k8s/credentials.py:219`). |
| B107 hardcoded password default | 2 | 2 marked (`security/vault_lease.py:188`, `:202`). |
| B311 `random` | 5 | 5 marked. |
| B607 partial path | 3 | Fixed: `ai/rag/drift.py:61`, `github/metrics.py:172`, `:215`. |
| B603 subprocess without shell | 7 | Skipped in `.bandit`; 4 of them are the three calls above and `github/metrics.py:229`, which now go through the seam. |
| B404 import subprocess | 40 | Skipped in `.bandit`. |
| B110 / B112 swallowed exception | 43 / 11 | Skipped in `.bandit`; the swallowed-failures ratchet counts them. |

The issue counted 184 at 5c5df79; later work removed 60, among them the asserts of `ai/durable.py` and `valkey/client.py`.

Bandit 1.9.4 checked in a scratch tree:

- A `# nosec B107` on a `def` line and a `# nosec B106` on the first line of a call over several lines both hold.
- `# nosec B105 # reason` gives no warning: the second `#` ends the rule list.
- `skips` in the INI file holds.
- A target on the command line replaces the targets of `--ini` ("Using command line arg for selected targets").

Timing on this host: Bandit over `src/` took 29.6 s and over `tests/` 35.6 s at medium. Two runs over the two targets scan each file once, as one run over both did.

## Existing Tool Considered

Bandit, already locked and already the gate, does the work. Its INI `skips` and its `# nosec` markers hold the decisions, so no baseline file and no new ceiling table is added. Ruff's flake8-bandit rules were measured as the other way: `ruff check src --select S105` reports 69 strings against Bandit's 6, so it would need dozens of markers on constants that only look like credentials. The change deletes three `# nosec B603` markers and two direct `subprocess.run` imports of `git`.
