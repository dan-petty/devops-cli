# Design: #5019 Fix-Conflict Step

## Architectural Context
The `fix-conflict` step settles merge conflicts between an item's topic branch and the default branch. It resides in `src/devops_cli/roadmap/steps/fix_conflict.py` and is accessible via CLI (`devops roadmap step fix-conflict --pull N`) and programmatic execution inside the runner job (`src/devops_cli/roadmap/implement/implement_run.py`).

## Core Components

### 1. Step Pipeline (`src/devops_cli/roadmap/steps/fix_conflict.py`)
1. **Safety Bounds & Admission**:
   - Refuse pull requests authored by humans or containing commits by humans after the last bot push.
   - Refuse items with `owner/*` labels (e.g. `owner/human`, `owner/agent`) or claimed by a human/agent.
   - Verify that the target head SHA matches the expected judged head.
   - Enforce caps: maximum 2 rounds by default (soft cap). Allow one additional round if the count of conflicted files decreases. Never exceed 4 rounds (hard cap). Enforce at most one model round per `<base>:<head>`.
2. **Tier 1 (Deterministic Conflict Resolution)**:
   - Identify conflicted files via `git diff --name-only --diff-filter=U`.
   - Release path guard: If any conflict occurs in `CHANGELOG.md`, manifests (`.release-please-manifest.json`, `release-please-config.json`), or version definitions, abort and stop with failure class `conflict`.
   - Archive conflicts: When conflicts only affect `openspec/specs/**` or `openspec/changes/archive/**`, drop the archive commit from the branch, rebase the preceding commits onto `origin/<default>`, and re-run the archive finish step (`devops openspec archive <change>`).
   - Generated docs: For conflicts in generated documentation, resolve using the base branch version (`checkout --ours/--theirs`) and re-run `devops docs generate`.
   - Lockfile: For conflicts in `uv.lock`, checkout the base branch version and run `uv lock`.
3. **Tier 2 (Model Conflict Resolution)**:
   - If non-trivial conflicts remain:
     - In mode `plan` without `--confirm`, log remaining conflicted files and pause without calling the model.
     - In mode `on` (or with `--confirm`), prompt the model with the conflicted files, both conflict hunks, and the item's task specification.
4. **Verification & Push**:
   - Validate specifications with `openspec validate --specs --strict`.
   - Execute scoped quality checks.
   - Push rebased and resolved branch with lease.
   - Record `fix_conflict.key` (`<base>:<head>`), `fix_conflict.rounds`, `fix_conflict.files`, and `fix_conflict.result`.

### 2. Runner Job Integration (`src/devops_cli/roadmap/implement/implement_run.py`)
- When `_sync()` or `_rebased_copy()` encounters a rebase conflict (`GitOperationError`), invoke `fix_conflict` instead of immediately stopping with `FailureAction.WAIT`.
- If `fix_conflict` resolves the conflict, proceed with the implementation run.
- If `fix_conflict` cannot resolve the conflict or halts on bounds/release paths, stop with failure class `conflict` and record that 1 fix round was executed (`repair_rounds = 1`).

### 3. Settings & Failure Actions
- In `src/devops_cli/roadmap/failure.py`, map `FailureClass.CONFLICT` to `FailureAction.REPAIR`.
- In `src/devops_cli/config/settings.py` and `defaults.py`, register `RoadmapFixConflictConfig` with tier 1 mode defaulting to `on` and tier 2 mode defaulting to `plan`.
- In `docs/ROADMAP_WORKFLOW.md`, document `repair` as the default action for `conflict`.
