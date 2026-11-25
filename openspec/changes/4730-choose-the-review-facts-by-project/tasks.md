# Tasks

## 1. List the sections and the conditions of each repository in a dry run

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/catalog.py`, `src/devops_cli/commands/roadmap_review.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_review.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/commands/roadmap_review.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_review.py`.
Adds: `planned_sections`

- [ ] 1.1 `tests/commands/test_roadmap_review.py::test_a_dry_run_with_no_window_lists_each_repository_of_service_repos` fails first: with `service.repos` naming 7 repositories and no `prometheus.url` value, `devops roadmap review run --dry-run` prints one block for each of the 7, each with the title of each section of `src/devops_cli/roadmap/project_review/catalog.yaml` and the id of each fact, the reason `The setting prometheus.url has no value.` on the line of each fact of the prometheus reader, the text `the base and the head commits hold openspec/specs` on the line of each fact of the openspec reader, and `process_fake.calls == []` with `refuse_requests == []`; a second case with `service.repos` naming 3 repositories prints 3 blocks
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py` fails on the base
- [ ] 1.2 Add `planned_sections(catalog: Catalog, settings: Settings) -> str` to `src/devops_cli/roadmap/project_review/dispatch.py`: for each repository of `settings.service.repos` a heading (or an empty-repos message when `settings.service.repos` is empty), then each section title of the catalog, then each fact of that section with the reason of the first `setting:` condition of `catalog.rules(fact).requires` that `_setting` finds unset, else the text of `_condition` of its conditions, else a text that says the fact has no condition; print it with `write_stdout` from `run_cmd` of `src/devops_cli/commands/roadmap_review.py` when `(dry_run or is_dry_run())` holds and no window option is given (`not any((version, since, until, week, last))`), before `parse_window` and `find_repo_root`; add the heading, section, fact, no-condition and empty-repos texts to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py` passes

## 2. Read the review tag pattern from the roadmap file

Kind: behavior. Reads: `src/devops_cli/roadmap/project_profile.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_project_profile.py`, `.devops/roadmap.toml`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/project_profile.py`, `tests/roadmap/test_roadmap_project_profile.py`.
Adds: `CONST_ROADMAP_REVIEW_TAG_PATTERN`, `_Review`, `review_tag_pattern`

- [ ] 2.1 `tests/roadmap/test_roadmap_project_profile.py::test_the_review_table_gives_the_tag_pattern_and_the_default_is_v_star` fails first: `review_tag_pattern` gives `release-*` from a checkout whose `.devops/roadmap.toml` holds the review table, gives `v*` from a checkout whose file holds none, raises `ConfigurationError` naming `.devops/roadmap.toml` on invalid TOML or unknown keys, and `resolve_profile` reads a commit whose file holds the review table with no error
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_project_profile.py` fails on the base
- [ ] 2.2 Add `CONST_ROADMAP_REVIEW_TAG_PATTERN` with the value `v*` to `src/devops_cli/config/constants.py` beside `CONST_ROADMAP_IMPLEMENT_STEPS_FILE`; add the model `_Review` with the field `tag_pattern` and the function `review_tag_pattern(source: Path) -> str` to `src/devops_cli/roadmap/project_profile.py`, which reads `source / CONST_ROADMAP_IMPLEMENT_STEPS_FILE` with `tomllib`, validates it through `_Declaration.model_validate` and raises `ConfigurationError` with `MESSAGES.roadmap.roadmap_toml_invalid` on a decode error or a validation error, and gives `CONST_ROADMAP_REVIEW_TAG_PATTERN` when the file, the table or the key is absent; add `review: _Review = _Review()` to `_Declaration` so `resolve_profile` accepts the table. `tests/roadmap/test_roadmap_limit_classes.py` counts the numeric limits of the `CONST_ROADMAP_` prefix, and this string constant takes no entry there
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_project_profile.py` passes

## 3. Refuse a version window when no tag matches the pattern

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_window.py`, `tests/roadmap/project_review/test_review_facts.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_window.py`.

- [ ] 3.1 `tests/roadmap/project_review/test_review_window.py::test_a_version_window_needs_a_tag_that_matches_the_tag_pattern` fails first: `resolve_window` refuses a version window over an empty tag list and the pattern `release-*` with an error that names `tag_pattern` and `release-*` before any git command, and a second case resolves the window of the recorded tags of `v*` through `read_tags` and keeps `v1.0.0..v1.1.1`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py` fails on the base
- [ ] 3.2 Give `tag_args` of `src/devops_cli/roadmap/project_review/git_read.py` the pattern, defaulted to `CONST_ROADMAP_REVIEW_TAG_PATTERN`, and build `refs/tags/<pattern>` in place of the constant `_RELEASE_TAGS`; give `read_tags` and `resolve_window` of `src/devops_cli/roadmap/project_review/window.py` that pattern with the same default, and make `resolve_window` refuse a version window over an empty tag list before its first git read; add the refusal text to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py` passes

## 4. Name the review tag pattern in the tag query and the run

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/review.py`, `src/devops_cli/roadmap/project_review/window.py`, `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_profile.py`, `tests/roadmap/project_review/test_review_facts.py`, `tests/fixtures/git/review_window.json`, `tests/ai/review/test_review.py`, `tests/commands/test_review.py`. Changes: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/review.py`, `tests/roadmap/project_review/test_review_facts.py`.

- [ ] 4.1 `tests/roadmap/project_review/test_review_facts.py::test_the_run_reads_the_tag_pattern_of_the_roadmap_file` fails first: `review_facts` given the pattern `release-*` gives a `git.releases` fact whose query holds `refs/tags/release-*`; `planned_review` in a checkout whose `.devops/roadmap.toml` sets `[review] tag_pattern = "release-*"` starts no git command and lists `refs/tags/release-*`; `run_review` in a checkout whose `.devops/roadmap.toml` sets `release-*` with `git_fake.answer` answering empty tags for `refs/tags/release-*` refuses a version window naming `tag_pattern` and `release-*`; and `run_review` in the checkout of the recorded `review_window` transcript, whose roadmap file holds no review table, still reads the tags of `v*` and keeps the window `v1.0.0..v1.1.1`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py` fails on the base
- [ ] 4.2 Give `git_facts` and `review_facts` of `src/devops_cli/roadmap/project_review/facts.py` the pattern, defaulted to `CONST_ROADMAP_REVIEW_TAG_PATTERN`, and build the tag query with `tag_args(pattern)`; read the pattern in `run_review` and `planned_review` of `src/devops_cli/roadmap/project_review/review.py` with `review_tag_pattern(checkout)` and pass it to `read_tags`, `resolve_window`, `review_facts` and `tag_args`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py` passes

## 5. Give the functional change from the CHANGELOG and the subjects

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/roadmap/project_review/git_read.py`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/lang/en/messages.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/functional.py` (new), `tests/roadmap/project_review/test_review_functional.py` (new), `src/devops_cli/lang/en/messages.py`.
Adds: `changelog_sections`, `functional_change`

- [ ] 5.1 `tests/roadmap/project_review/test_review_functional.py::test_the_changelog_gives_the_functional_change_then_the_subjects` fails first: `functional_change` gives the `functional.change` fact with `section="changes"` from the Features and Bug Fixes sections of a `CHANGELOG.md` of the checkout with the source `changelog`, then from the feat and fix subjects of the window with the source `subjects`, and gives a skipped fact with `source="functional"` and a reason when both are empty
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py` fails on the base
- [ ] 5.2 Add `src/devops_cli/roadmap/project_review/functional.py` with `changelog_sections(text: str) -> list[str]` for the bullets under the `### Features` and `### Bug Fixes` headings of the first release (`## ...`) of `CHANGELOG.md`, and `functional_change(checkout: Path, window: ReviewWindow) -> Fact`, which reads `CHANGELOG.md` of the checkout, then the commits of the window with `commits(run_git(checkout, log_args(...)))` and `commit_type` of `src/devops_cli/roadmap/commit_title.py`, and gives the `functional.change` fact with `section=SECTION` (`"changes"`), list value and `n=len(items)` and source `changelog` or `subjects`, else a skipped fact with `source="functional"` and a reason; add the definition of `functional.change` and the reasons to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py` passes

## 6. Give the functional change from the merged pull request titles

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/functional.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_catalog.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/functional.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_functional.py`.

- [ ] 6.1 `tests/roadmap/project_review/test_review_functional.py::test_the_changelog_gives_the_functional_change_then_the_subjects_then_the_pull_request_titles` fails first: `functional_change` given titles and an empty CHANGELOG and no feat or fix subject gives the fact with the source `pull_requests`, and `read_catalog` over `load_catalog()` evaluates `listing.merged_titles` to the merged titles (and `[]` with `n=0` and status `ok` when no pull request merged in the window)
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py` fails on the base
- [ ] 6.2 Give `functional_change` of `src/devops_cli/roadmap/project_review/functional.py` the argument `titles: Sequence[str] = ()`, and give the `functional.change` fact with the source `pull_requests` from the titles when the CHANGELOG and the subjects give none; add the `listing.merged_titles` fact to `src/devops_cli/roadmap/project_review/catalog.yaml` beside `listing.pulls_merged` (`query: repos/{repo}/issues?state=all`, `unit: pull requests`), returning a list of `.title` strings (`[]` when empty so status stays `ok` with `n` as `length`); add the definition and the reason to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_functional.py` passes

## 7. Record the functional change in the review

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/review.py`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/roadmap/project_review/functional.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `tests/commands/test_roadmap_review.py`, `tests/roadmap/project_review/test_review_facts.py`, `tests/ai/review/test_review.py`, `tests/commands/test_review.py`, `tests/roadmap/project_review/test_review_catalog.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/project_review/test_review_window.py`. Changes: `src/devops_cli/roadmap/project_review/review.py`, `src/devops_cli/roadmap/project_review/data.py`, `tests/commands/test_roadmap_review.py`.

- [ ] 7.1 `tests/commands/test_roadmap_review.py::test_a_run_records_the_functional_change_of_a_checkout_without_openspec` fails first: a run in the checkout of the recorded transcript with a `CHANGELOG.md` and no ok OpenSpec fact records the `functional.change` fact after `lizard.complexity` and before the catalog facts with the source `changelog`, `test_a_run_writes_data_json_under_the_data_directory_and_prints_it` holds `functional.change`, and a run with an ok `openspec.` fact omits `functional.change`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py` fails on the base
- [ ] 7.2 In `run_review` of `src/devops_cli/roadmap/project_review/review.py`, after `read_catalog`, add the fact of `functional_change(checkout, window, titles)` to the git facts before the catalog facts when the catalog result holds no ok fact whose id starts with `openspec.`, with the titles of the ok `listing.merged_titles` fact; in `src/devops_cli/roadmap/project_review/data.py`, add `functional`, `changelog`, `subjects` and `pull_requests` to the description of `Fact.source`, state in `Fact.id` that `functional.change` names its kind there and its fallback in `source`, and state in `ReviewData.facts` that the functional change fact sits between the git facts and the catalog facts when no OpenSpec fact is ok; add `functional.change` to the exact fact list of `tests/commands/test_roadmap_review.py` before the catalog facts
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py` passes

## 8. Skip the complexity rank when lizard reads no hot file

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_facts.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/facts.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_facts.py`.

- [ ] 8.1 `tests/roadmap/project_review/test_review_facts.py::test_a_shell_only_window_keeps_the_churn_rank_and_skips_the_complexity_rank` fails first: `complexity_fact` gives a skipped fact whose reason says that no hot file is one that lizard reads when `rows` holds a Shell file and lizard reads none of them (while empty `rows` stays `ok`), and `render_review` prints the skipped reason alongside `git.hotspots`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py` fails on the base
- [ ] 8.2 In `complexity_fact` of `src/devops_cli/roadmap/project_review/facts.py`, return a skipped fact with the new text when `rows` is non-empty and `read` is empty, so empty `rows` keeps `ok` `[]`, `git.hotspots` keeps the churn rank and `render_review` prints the reason; add the text to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py` passes

## 9. Document the review traits and the functional change fallback

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/project_review/catalog.yaml`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 9.1 Add the paragraph on the review traits to `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 9.2 Edit `docs/ROADMAP_WORKFLOW.md` to state the review tag pattern of the roadmap file of a repository with the default `v*`, the functional change from the OpenSpec facts then the CHANGELOG sections then the feat and fix subjects then the merged pull request titles, the churn-only hotspots of a repository that lizard cannot read, and the dry-run listing of each repository of `service.repos` with the reason of each unset setting and the condition of each other fact
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A fixture repository with no tags refuses a version window, with a message that names `tag_pattern`.
- Group 7: A repository with no `openspec/` takes its functional change from the CHANGELOG.
- Group 8: A Shell-only repository gets churn-only hotspots with a note.
- Group 1: `--dry-run` for each of the 7 `service.repos` lists the sections and the skipped reasons.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
