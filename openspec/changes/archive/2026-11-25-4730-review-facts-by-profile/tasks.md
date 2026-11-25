# Tasks

## 1. List sections and conditions per repository in a dry run

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/catalog.py`, `src/devops_cli/commands/roadmap_review.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_review.py`. Changes: `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/commands/roadmap_review.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_review.py`.

- [x] 1.1 Add failing `tests/commands/test_roadmap_review.py::test_a_dry_run_with_no_window_lists_each_repository_of_service_repos` testing 7 `service.repos` (and a 3-repo case and empty `service.repos`) with unset `prometheus.url`, verifying every section title, fact ID, `The setting prometheus.url has no value.`, `the base and the head commits hold openspec/specs`, and zero calls on `process_fake` and `refuse_requests`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`
- [x] 1.2 Add `planned_sections(catalog: Catalog, settings: Settings) -> str` to `src/devops_cli/roadmap/project_review/dispatch.py`, wire no-window `--dry-run` in `src/devops_cli/commands/roadmap_review.py`, and add the message fields to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`

## 2. Read `[review] tag_pattern` from `.devops/roadmap.toml`

Kind: behavior. Reads: `src/devops_cli/roadmap/project_profile.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_project_profile.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/project_profile.py`, `tests/roadmap/test_roadmap_project_profile.py`.

- [x] 2.1 Add failing `tests/roadmap/test_roadmap_project_profile.py::test_the_review_table_gives_the_tag_pattern_and_the_default_is_v_star` covering `[review] tag_pattern`, missing file/table default `v*`, invalid TOML or unknown keys or unsafe pattern raising `ConfigurationError` naming `.devops/roadmap.toml`, and `resolve_profile` accepting `[review]`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_project_profile.py`
- [x] 2.2 Add `CONST_ROADMAP_REVIEW_TAG_PATTERN = "v*"` to `src/devops_cli/config/constants.py`, `_Review` and `review_tag_pattern` to `src/devops_cli/roadmap/project_profile.py`, and include `review: _Review = _Review()` on `_Declaration`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_project_profile.py`

## 3. Refuse a version window when no tag matches `tag_pattern`

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_window.py`. Changes: `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_window.py`.

- [x] 3.1 Add failing `tests/roadmap/project_review/test_review_window.py::test_a_version_window_needs_a_tag_that_matches_the_tag_pattern` asserting `resolve_window` raises `RoadmapReviewError` naming `tag_pattern` and `release-*` on empty `tags` with zero git calls and reads custom pattern in `read_tags`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py`
- [x] 3.2 Parameterize `tag_args`, `read_tags`, and `resolve_window` with `CONST_ROADMAP_REVIEW_TAG_PATTERN`, add empty-tag guard on `VersionRequest` in `resolve_window`, and add `review_no_matching_tags` to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py`

## 4. Propagate `tag_pattern` in review facts and dry-run plan

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/review.py`, `tests/roadmap/project_review/test_review_facts.py`. Changes: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/review.py`, `tests/roadmap/project_review/test_review_facts.py`.

- [x] 4.1 Add failing `tests/roadmap/project_review/test_review_facts.py::test_the_run_reads_the_tag_pattern_of_the_roadmap_file` checking custom `tag_pattern` in `review_facts`, `planned_review`, and `run_review`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`
- [x] 4.2 Add `tag_pattern: str = CONST_ROADMAP_REVIEW_TAG_PATTERN` to `git_facts` and `review_facts` in `src/devops_cli/roadmap/project_review/facts.py` and pass `review_tag_pattern(checkout)` in `run_review` and `planned_review` of `src/devops_cli/roadmap/project_review/review.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`

## 5. Build the functional change fallback from CHANGELOG, commit subjects, and merged PR titles

Kind: behavior. Reads: `src/devops_cli/roadmap/markdown.py`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/project_review/functional.py` (new), `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_functional.py` (new).

- [x] 5.1 Create failing `tests/roadmap/project_review/test_review_functional.py` covering `CHANGELOG.md` (`Features` and `Bug Fixes` in the first release) -> `feat`/`fix` commit subjects -> `listing.merged_titles` (including `[]` / `n=0` / `ok` when empty) -> `skipped` (`functional`), verifying `source` values (`changelog`, `subjects`, `pull_requests`, `functional`)
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py`
- [x] 5.2 Add `src/devops_cli/roadmap/project_review/functional.py` (`changelog_sections` using `commonmark_parser()`, `functional_change`), add `listing.merged_titles` to `src/devops_cli/roadmap/project_review/catalog.yaml`, and add `functional.change` definition and skip reason to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py`

## 6. Record `functional.change` in `run_review` when OpenSpec has no `ok` fact

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/review.py`, `src/devops_cli/roadmap/project_review/data.py`, `tests/commands/test_roadmap_review.py`, `tests/roadmap/project_review/test_review_facts.py`. Changes: `src/devops_cli/roadmap/project_review/review.py`, `src/devops_cli/roadmap/project_review/data.py`, `tests/commands/test_roadmap_review.py`, `tests/roadmap/project_review/test_review_facts.py`.

- [x] 6.1 Add failing `tests/commands/test_roadmap_review.py::test_a_run_records_the_functional_change_of_a_checkout_without_openspec` checking `functional.change` appears after `lizard.complexity` and before catalog facts when no `openspec.` fact is `ok`, and is omitted when an `openspec.` fact is `ok`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`
- [x] 6.2 Wire `functional_change` into `run_review` in `src/devops_cli/roadmap/project_review/review.py`, document the sources and ordering in `src/devops_cli/roadmap/project_review/data.py`, and update fact-list assertions in `tests/commands/test_roadmap_review.py` and `tests/roadmap/project_review/test_review_facts.py`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py tests/roadmap/project_review/test_review_facts.py`

## 7. Skip `lizard.complexity` when lizard reads no hot file

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_facts.py`. Changes: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_facts.py`.

- [x] 7.1 Add failing `tests/roadmap/project_review/test_review_facts.py::test_a_shell_only_window_keeps_the_churn_rank_and_skips_the_complexity_rank` asserting `complexity_fact` returns `skipped` for Shell-only hot files (while empty hot files stay `ok`) and `render_review` prints the skip reason
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`
- [x] 7.2 Update `complexity_fact` in `src/devops_cli/roadmap/project_review/facts.py` and add `review_lizard_unreadable` to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`

## 8. Document review traits and regenerate docs

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 8.1 Update `docs/ROADMAP_WORKFLOW.md` for `[review] tag_pattern`, the `functional.change` fallback chain, churn-only hotspots with skip note when lizard reads no hot file, and no-window `--dry-run`, and run `uv run devops docs generate` if CLI/message docs changed
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Tracked separately in #7042: route private repository review summaries to tracker issues.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
