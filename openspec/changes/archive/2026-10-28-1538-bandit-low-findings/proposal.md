# Proposal

## Why

Issue #1538: the security row of `devops ci` runs Bandit over `src/` and `tests/` at medium severity and above, so nobody reviews a low-severity finding in `src/`. The owner decided on 2026-10-10 that Bandit covers both targets at medium and above through one shared `.bandit`, and that the low findings in `src/` get this item. The item asks for three things:

- A production `assert` becomes an explicit check, because Python drops `assert` under `-O`.
- A process that starts by a bare program name goes through the process seam.
- Each password-like or `random` literal is fixed or carries a reviewed `# nosec` with its rule and a reason. Then a new low finding in `src/` fails the gate.

The owner decided on 2026-10-28 that each of these findings is fixed in code, with no new `# nosec` marker and no higher suppression ceiling.

## What Changes

- **The gate.** The security row runs Bandit two times with the shared `.bandit`: over `src/` at low severity and above, then over `tests/` at medium and above. Each file is scanned once, as before. `devops ci security --severity` sets the threshold of the `tests/` run; `src/` is always scanned at low.
- **The shared config.** `.bandit` skips four low-severity rules, each with its reason: B404 (importing `subprocess`) and B603 (a list-form call without a shell), which a CLI that runs tools has by design; B110 and B112 (swallowed exceptions), which the swallowed-failures ratchet counts with Ruff's S110 and S112. All four are low severity, so the medium run over `tests/` does not change. The three `# nosec B603` markers in `src/` go, because the config skips the rule.
- **Asserts.** In `ai/benchmark/runner.py` the loop branches on `client is None`, which is a dry run, so the `assert` goes. In `roadmap/intake.py` four asserts become `RoadmapIntakeError`. `_apply_placement` makes its two checks before any write, so a failed check leaves no label on the issue.
- **Processes.** `ai/rag/drift.py` and `github/metrics.py` run `git` through `run_subprocess` as local reads. Each keeps its fallback, and the log line gives the runner's error, which names the program when it is missing.
- **Literals and draws, fixed in code.** No finding gets a new `# nosec` marker, and `.bandit` skips none of B105, B106, B107 or B311.
  - `vulnerability_lookup.py` takes `token or None` in place of `token if token != "" else None`.
  - `sanitizer.py` masks a URL password with one `_URL_MASK` constant in place of two `"***"` literals.
  - `STATUS_PASS`, `STATUS_FAIL` and `STATUS_NOT_RUN` of the template sweep become the `SweepStatus` `StrEnum`, whose `auto()` gives the member name, so a run record still stores `PASS`, `FAIL` and `NOT_RUN`. `ProbeStatus` and `DefectClass` take `auto()`, which gives the lower-case member name that each value already was.
  - `CONST_GH_TOKEN_ENV` becomes `CONST_GH_AUTH_ENV_VAR`, and `CONST_RUNS_INDEX_SECRET` becomes `CONST_RUNS_INDEX_AUTH_OBJECT`: each name says what its value is, a variable name or a Kubernetes object name.
  - The Argo CD admin call in `k8s/credentials.py` and the two path defaults in `security/vault_lease.py` take named module constants.
  - The retry jitter in `ai/rag/embeddings.py` and the fault rate in `ai/chaos/injector.py` draw from one `secrets.SystemRandom()` for each module. Bandit 1.9.4's B311 list does not name it.
  - The seeded benchmark sample in `ai/benchmark/document_chunker.py` and the seeded defect draw in `ai/review/defects.py` use `core/draws.py`, which orders the items by the SHA-256 of the seed and each position. The same seed still gives the same draw on every host.
- **Markers.** Every `# nosec` in `src/` names its rule and gives a reason after a second `#`. A test in `tests/test_architectural_invariants.py` refuses a bare marker. The existing markers get their reasons.
- **The suppression ceiling.** `src nosec` in `DEFAULT_SUPPRESSION_CEILINGS` falls from 13 to 10, because the three `# nosec B603` markers go.
- The gate is a behavior that a consumer observes, so the change carries a spec delta: the new capability `ci-security-gate`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ci-security-gate`: what the security row of `devops ci` scans, at which severity, which rules the shared `.bandit` skips, and the form of a `# nosec` marker in `src/`.

## Impact

- `.bandit`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`.
- `src/devops_cli/ai/benchmark/runner.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/security/vault_lease.py`, `src/devops_cli/k8s/credentials.py`, `src/devops_cli/ai/review/template_sweep.py`, `src/devops_cli/ai/review_schema.py`, `src/devops_cli/sandbox/models.py`, `src/devops_cli/config/constants.py` and its users, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/chaos/injector.py`, `src/devops_cli/ai/benchmark/document_chunker.py`, `src/devops_cli/ai/review/defects.py`, the new `src/devops_cli/core/draws.py`, and the files whose markers get a reason or go.
- `tests/test_ci.py`, `tests/test_security_bandit.py`, `tests/test_architectural_invariants.py`, `tests/test_github_metrics.py`, `tests/test_rag_drift.py`, `tests/test_roadmap_intake_checks.py`, `tests/core/test_draws.py`, `tests/test_review_template_sweep.py`, `tests/test_sandbox_probe.py`, `tests/test_review_taxonomy_and_severity.py`, `tests/test_docs.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

Measured on origin/main d156ce7e with the locked Bandit 1.9.4 (`uv run bandit -r src -f json`): 124 findings in `src/`, all low severity.

| Rule | Count | Handling |
| :--- | ---: | :--- |
| B101 `assert_used` | 5 | Fixed: `ai/benchmark/runner.py:389`, `roadmap/intake.py:568`, `:1121`, `:1122`, `:1217`. |
| B105 hardcoded password string | 6 | Fixed: a `token or None`, three enums with `auto()`, and two constants renamed. |
| B106 hardcoded password argument | 2 | Fixed: `_URL_MASK` (`security/sanitizer.py:399`) and a named constant (`k8s/credentials.py:219`). |
| B107 hardcoded password default | 2 | Fixed: named constants (`security/vault_lease.py:188`, `:202`). |
| B311 `random` | 5 | Fixed: `secrets.SystemRandom()` for the jitter and the fault rate (3); `core/draws.py` for the two seeded draws. |
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

Bandit, already locked and already the gate, does the work: its INI `skips` hold the four rules that need no decision, so no baseline file and no new ceiling table is added. Each other finding is fixed in code with the standard library: `enum.auto`, `secrets.SystemRandom` and `hashlib.sha256`. NumPy's seeded generator would also pass Bandit, but NumPy is not a direct dependency. Ruff's flake8-bandit rules were measured as the other way: `ruff check src --select S105` reports 69 strings against Bandit's 6.

`core/draws.py` is built: 2 functions in 25 lines, about 5k tokens to build and close to none to keep, since it only calls `hashlib` and `sorted`. The change deletes three `# nosec B603` markers, two direct `subprocess.run` calls of `git`, and the `random` imports of four modules.
