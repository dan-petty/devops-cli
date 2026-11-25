# Design

## Decisions
1. **Single new prefix constant and shared dual-prefix matcher (`src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/stage/stage_change.py`):**
   - Set `PLAN_TITLE_PREFIX: Final = "docs(spec): plan #"` and `LEGACY_PLAN_TITLE_PREFIX: Final = "docs(openspec): plan #"` in `pr_verdict.py`, with a light helper `is_plan_title(title: str | None) -> bool` checking both prefixes (or `is_plan_title_prefix` without `#` for `implement_pull.kind_of`). Importing `pr_verdict.py` stays lightweight compared to `stage_change.py` (~1 s).
   - Set `STAGING_TYPE: Final[str] = "docs(spec)"` in `stage_change.py`, while `plan_summary()` checks both `docs(spec)` and legacy `docs(openspec)` so `implement` still extracts summaries from merged plan commits.
2. **Every plan-title reader accepts both prefixes:**
   - Update `pr_verdict.pull_kind`, `implement._pull_reason`, `implement_pull.kind_of`, `stage_overlap._open_pull` (`_PLAN_SCOPES = frozenset({"spec", "openspec"})`), `grounding.plan_issue`, `plan_check.is_plan`, `plan_drift`, and `.github/workflows/pr-title.yml` (`plan-check` `if:` expression) to recognize both `docs(spec)` and legacy `docs(openspec)` plan PRs.
   - Update `plan_check._TITLE` and `MESSAGES.roadmap.plan_check_title` to validate new plan PR titles against `docs(spec): plan #{number} <summary>`, while `is_plan` still recognizes open legacy plan PRs.
3. **New commit messages, labels, workflow scopes, persona rules, and docs use `spec`:**
   - Update `ARCHIVE_MESSAGE` (`rebase.py`), `implement_commit_split` (`messages.py`), `implement_run.py` (amend/split), `stage_job_phases.py` (`docs(spec): scaffold #{number}`), and `implement_eval_run.py` (`docs(spec): the plan of the fixture (#{number})`).
   - Update `.github/labels.yml` (`scope/spec`), `.github/workflows/pr-title.yml` (`spec` in `scopes`), `src/devops_cli/ai/personas/lens.toml` (`label.scope_spec`), `CONTRIBUTING.md`, prompts, docs, tests, and living specs. Regenerate docs via `devops docs generate`.

## Rejected alternatives
- **Drop `docs(openspec): plan #` from readers immediately:** Rejected because merged PRs in `git log`/GitHub keep `docs(openspec): plan #` titles (`eval grades`, `eval funnel`, `implement` `plan_summary`), and open legacy plan PRs keep their titles until #6314.
- **Execute live label rename and open PR retitle in this PR:** Rejected; deferred to #6314 after the release so existing readers and label sync on deployed versions do not break.
- **Rename `devops openspec` or `openspec/`:** Rejected; only the Conventional Commit scope changes (#6007).
