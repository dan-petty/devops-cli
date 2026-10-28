# Tasks

## 1. The security row scans src at low

- [x] Add failing tests: the security row starts Bandit over `src` at low and over `tests` at medium; `--severity high` changes only the `tests` run; the row's targets equal the targets of `.bandit`; `.bandit` skips B404, B603, B110 and B112
  - Verification: `uv run devops ci test tests/test_ci.py`
- [x] Run the two Bandit runs in the security row and in `devops ci security`, and skip the four rules in `.bandit` with their reasons
  - Verification: `uv run devops ci test tests/test_ci.py`
- [x] Describe the gate in `docs/ROUTINE_TASKS.md`, `docs/SDLC.md` and the help of `--severity`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Asserts become checks

- [x] Add failing tests: `_Entry.neighbour` without a number, `_apply_placement` without an item or a priority (and no write before the error), and `_decision_lines` for a placement with no placement raise `RoadmapIntakeError`
  - Verification: `uv run pytest tests/test_roadmap_intake_checks.py -n 0`
- [x] Replace the four asserts of `roadmap/intake.py` with checks, and branch on `client is None` in `ai/benchmark/runner.py`
  - Verification: `uv run pytest tests/test_roadmap_intake_checks.py tests/test_ai_benchmark.py -n 0`

## 3. git through the process seam

- [x] Add failing tests over `process_fake`: the drift head commit, the tag list and the commit count read `git` as local reads, and a missing `git` gives the fallback with a log line that names `git`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_rag_drift.py`
- [x] Run `git` through `run_subprocess` in `ai/rag/drift.py` and `github/metrics.py`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_rag_drift.py`

## 4. Literals and markers

- [x] Add a failing test: every `# nosec` in `src/` names a rule and a reason
  - Verification: `uv run pytest tests/test_architectural_invariants.py -n 0`
- [x] Fix the two literals, add the reviewed markers, give the existing markers their reasons, delete the three `# nosec B603` markers, and set `src nosec` to 23
  - Verification: `uv run devops ci security`

## 5. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1538-bandit-low-findings`
- Pending a person: approve the `src nosec` suppression ceiling of 23 (it was 13) by merging.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
