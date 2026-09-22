# Task 349: Review Feedback Loop Calibration & Verified Session Finding Remediation

**Issue**: [#349](https://github.com/dan-petty/devops-cli/issues/349)
**PR**: [#350](https://github.com/dan-petty/devops-cli/pull/350)
**Status**: In Review
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/fix`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Hand-verification of review session `20260920-124350` (55 findings: 2 CRITICAL, 4 HIGH, 24 MEDIUM, 25 LOW) found 4 real defects and 2 false positives in the CRITICAL/HIGH tier, alongside substantial symptom fan-out. Investigating why the loop produced that mix surfaced two defects in the self-improvement machinery itself that silently degrade review quality without changing review output.

### Key Deliverables Completed:

- [x] **Verified Defect Remediation**:
  - `src/devops_cli/k8s/informer.py`: publish the active `watch.Watch()` to `self._watcher` for the stream's lifetime and clear it on exit, so `stop()` interrupts the blocking stream instead of leaving the worker thread alive until the next server-side resync; `stop()` now also joins the worker under a bounded timeout (`DEFAULT_K8S_INFORMER_STOP_TIMEOUT_SECONDS`).
  - `src/devops_cli/k8s/informer.py`: bound the resource cache with an `OrderedDict` and FIFO eviction at `DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES`.
  - `src/devops_cli/k8s/service.py`: `_set_cached` honours its `ttl` argument by storing an absolute expiry deadline; short negative caches (a failed reachability probe asking for ~2s) are no longer pinned for the full cache TTL.
  - `src/devops_cli/commands/k8s/cluster_context.py`: replace `except Exception: pass` with a typed, logged warning so client-realignment failures stay diagnosable without failing the command.
  - `src/devops_cli/github/client.py`: wrap `get_repo_overview` GraphQL transport failures in an annotated `GitHubOperationError` instead of letting raw exceptions crash the CLI.
- [x] **Suppression Catalog Safety (`src/devops_cli/ai/review/common_hallucinations.py`)**:
  - Auto-learning synthesizes a **co-occurrence** signature requiring two distinctive keywords, or emits no signature and relies on the already-guarded compound keyword match. Previously a single keyword became a whole signature.
  - Bare prose-word signatures are rejected **at match time**, neutralizing **104 poisoned patterns** already written to disk (`unvalidated`, `traversal`, `insecure`, `unbounded`, `server`, `command`, …) without a data migration. Bare *code identifiers* (`DEFAULT_HTTP_BROKER`, `FastMCP`) remain valid signatures.
  - An invalid signature regex is skipped rather than degraded into a broad substring match.
- [x] **Calibration Integrity**:
  - The builtin catalog was loading **zero of 27 entries** because one malformed record aborted the whole list comprehension inside a single `try`, with the failure logged only at debug level — leaving verification to run on auto-learned entries alone. Entries are now validated individually, malformed records are skipped with a warning naming their id, and a missing or unreadable baseline warns rather than failing silently.
  - Both confirmed false positives registered as catalog patterns (`HALLUCINATION-SERVER-CONSTRUCTOR-NO-AUTH`, `HALLUCINATION-DECLARATION-WITHOUT-CONSUMER`).
- [x] **Duplicate Consolidation (`src/devops_cli/ai/review_schema.py`)**:
  - Merge findings naming the same distinctive code symbol over overlapping lines, and merge near-identical titles in one file even when the cited line ranges differ (personas routinely cite different, and often both wrong, ranges for one defect).
  - Deliberately conservative: findings that merely share an enclosing function are never merged, because dropping a real defect is costlier than leaving a duplicate.
  - Matching signals centralized in `constants.py` (`REVIEW_GENERIC_SYMBOL_STOPWORDS`, `REVIEW_STRONG_SYMBOL_MIN_LENGTH`, `REVIEW_DESCRIPTION_SIMILARITY_THRESHOLD`).
- [x] **Prompt Mandates** (`code_review_prompt.md`, `review_output_instruction.md`, `personas/devsecops/prompt.md`):
  - One finding per root cause, with downstream consequences enumerated in that finding's description.
  - Segment-boundary honesty: never assert a control is absent when the code establishing it lies outside the provided segment; never declare a symbol unused without locating its consumer.
  - A server object's constructor is not its security boundary — transport, bind address, and loopback enforcement live at the launch site.
  - Narrowest true location, and a mandatory non-empty `fix`.
- [x] **Documentation (`docs/SELF_IMPROVEMENT.md`)**:
  - New §5 *Loop Failure Modes & Calibration Guardrails* covering symptom fan-out, segment-boundary false positives, suppression catalog poisoning, silent baseline loss, unactionable findings, and the calibration metrics worth tracking.
  - Session `20260920-124350` case study recorded under §6.
- [x] **Test Coverage**:
  - `tests/test_review_loop_calibration.py` (15 tests) pinning consolidation behaviour and catalog safety, including the over-merge guard.
  - Informer shutdown, cache bounding, and per-entry TTL regressions in `tests/test_k8s_service.py`.
  - GraphQL error wrapping in `tests/test_github_client.py`; realignment logging in `tests/test_k8s_context.py`.
- [x] **Test Runner Configuration**: `pyproject.toml` pytest `addopts` set to `-n logical`.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (3649 tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- Applying the corrected consolidation to session `20260920-124350` reduces 55 findings to 50 with no distinct defect merged.
- 104 degenerate suppression signatures neutralized; builtin catalog loads 27 of 27 entries.

## Follow-Up Observation

Switching pytest `addopts` from `-n auto --maxprocesses=8` to `-n logical` raised the test and coverage gate from **2m07s to 2m53s** on a 16-logical-core host. The previous `--maxprocesses=8` cap appears to have been deliberate: worker oversubscription under coverage instrumentation costs more than the added parallelism returns. Worth revisiting if CI wall-clock matters.
