# Proposal: #4730

## Why

The project review works for one repository only: it reads one fixed tag ref `refs/tags/v*`, takes the functional change only from the OpenSpec facts, and asks lizard to read a Shell file that lizard cannot read. #4730 makes the review read the traits of each managed repository, record the reason of each skipped fact, take the functional change from a fallback source, and list the sections and the conditions of each repository of `service.repos` in a dry run.

## What Changes

- Read the review tag pattern from `[review] tag_pattern` of `.devops/roadmap.toml` in the checkout, with default `v*` kept in `CONST_ROADMAP_REVIEW_TAG_PATTERN` beside `CONST_ROADMAP_IMPLEMENT_STEPS_FILE` in `src/devops_cli/config/constants.py`, in `src/devops_cli/roadmap/project_profile.py`.
- Accept the `review` table in `_Declaration` of `src/devops_cli/roadmap/project_profile.py` so `resolve_profile` validates `.devops/roadmap.toml` files that declare `[review]`.
- Pass the configured tag pattern through `git_read.py`, `window.py`, `facts.py`, and `review.py`, and refuse a version window when no tag matches `tag_pattern`, with an error that names `tag_pattern` and the pattern.
- Add `src/devops_cli/roadmap/project_review/functional.py` with `changelog_sections` (using `commonmark_parser()` from `src/devops_cli/roadmap/markdown.py`) and `functional_change`: take the functional change from the Features and Bug Fixes headings of the first release in `CHANGELOG.md` (`changelog`), then `feat` and `fix` commit subjects (`subjects`), then merged pull request titles (`pull_requests`), else `skipped` (`functional`).
- Add `listing.merged_titles` to `src/devops_cli/roadmap/project_review/catalog.yaml` beside `listing.pulls_merged` so the shared `listing` read yields merged pull request titles at zero extra GitHub requests.
- Insert `functional.change` in `run_review` (`src/devops_cli/roadmap/project_review/review.py`) right after `lizard.complexity` and before the catalog facts when no `openspec.` catalog fact is `ok`, and document `functional`, `changelog`, `subjects`, and `pull_requests` in `src/devops_cli/roadmap/project_review/data.py`.
- Skip `lizard.complexity` in `complexity_fact` (`src/devops_cli/roadmap/project_review/facts.py`) when hot files exist and lizard reads none of them, keeping churn order on `git.hotspots` with the reason shown.
- Add `planned_sections` in `src/devops_cli/roadmap/project_review/dispatch.py` and invoke it from `src/devops_cli/commands/roadmap_review.py` when `--dry-run` is given with no window option, listing each repository of `service.repos`, its catalog sections and fact IDs, unset `setting:` reasons, and other condition texts without running git or network requests.
- Update `docs/ROADMAP_WORKFLOW.md` and run `uv run devops docs generate` if CLI/message docs change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-project-review`: Add tag pattern selection and empty-tag version refusal, CHANGELOG/subject/merged-PR functional change fallback and ordering, skipped complexity rank when lizard reads no hot file, and no-window dry-run listing over `service.repos`.
- `toolchain-preset`: Allow `[review]` table in `.devops/roadmap.toml`.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap_review.py`, `src/devops_cli/roadmap/project_profile.py`, `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/functional.py` (new), `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/review.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/commands/test_roadmap_review.py`, `tests/roadmap/test_roadmap_project_profile.py`, `tests/roadmap/project_review/test_review_window.py`, `tests/roadmap/project_review/test_review_facts.py`, `tests/roadmap/project_review/test_review_functional.py`

## Feasibility

- Checked `openspec list --specs` and read `openspec/specs/roadmap-project-review/spec.md` and `openspec/specs/toolchain-preset/spec.md`: only those two specs apply, and existing requirements `The review writes the facts in a fixed order with the disagreements and the read counts` and `A dry run of the review starts no program` extend cleanly as `MODIFIED Requirements`.
- Confirmed `src/devops_cli/roadmap/project_profile.py` (`_Project`, `_Declaration`, `ProjectProfile`, `resolve_profile`): `resolve_profile` holds only `ToolchainPreset`, not `planning.system` or `languages`, and `_Declaration` sets `extra="forbid"`, so `[review]` must be declared on `_Declaration`.
- Confirmed `src/devops_cli/roadmap/project_review/dispatch.py` already evaluates `requires` conditions (`_setting`, `_missing_path`, `_unmet`) and records `FactStatus.SKIPPED` with `reason`.
- Confirmed `src/devops_cli/roadmap/project_review/facts.py:223` computes `read = [row for row in rows if lizard_languages.get_reader_for(row.path) is not None]`, which already determines whether lizard reads any hot file without adding a separate detector.
- Confirmed `src/devops_cli/roadmap/project_review/readers.py` and `dispatch.py` (`_ONE_READ`) share one `listing` read across listing facts, so `listing.merged_titles` collects merged PR titles with zero extra API requests.
- Confirmed private repository summary routing to tracker issues is deferred to separate issue `#7042`.
- Count of `service.repos` at runtime is configured per installation (`settings.service.repos` defaults to `[]`, declared under `ServiceConfig.repos` in `src/devops_cli/config/settings.py:1814`); the dry-run test census in `tests/commands/test_roadmap_review.py` exercises both a 7-repo set and a 3-repo set offline.

## Existing Tool Considered

No open tool covers the need: `git-cliff` generates a changelog from commits and `onefetch` summarizes repository languages and churn, and neither gates catalog `requires` conditions on settings and paths, records per-fact `skipped` reasons, falls back across `CHANGELOG.md` -> commit subjects -> merged PR titles, nor skips unreadable complexity rankings. Building this inside `src/devops_cli/roadmap/project_review/` is an issue-sized change (~100-200 lines plus tests, ~1 day elapsed) and deletes `_RELEASE_TAGS` fixed ref constant.
