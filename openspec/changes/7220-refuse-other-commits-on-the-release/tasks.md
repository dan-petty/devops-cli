# Tasks

## 1. Run the release file guard as a command

Kind: behavior. Reads: `src/devops_cli/release/merge_candidate.py`, `src/devops_cli/release/__init__.py`, `src/devops_cli/github/session.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/output/console.py`, `tests/release/test_release_merge_guards.py`, `tests/release/test_release_merge_pick.py`, `tests/support/fakes/github.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/release/merge_candidate.py`, `src/devops_cli/release/release_files.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/release/test_release_files.py` (new).
Adds: `release_file_refusals`, `check_release_files`

- [ ] 1.1 `tests/release/test_release_files.py::test_the_check_refuses_a_source_file` drives `check_release_files` over the fake GitHub API of `tests/support/fakes/github.py` with a compare that holds `src/devops_cli/main.py` and `CHANGELOG.md`, and `tests/release/test_release_files.py::test_a_clean_release_pull_request_is_allowed` with only the four release files
  - Verification: `$ uv run devops ci test tests/release/test_release_files.py tests/release/test_release_merge_guards.py tests/release/test_release_merge_pick.py` fails on the base
- [ ] 1.2 In `src/devops_cli/release/merge_candidate.py`, change `_file_refusals` to `_file_refusals(number: int, files: Sequence[PullRequestFile]) -> list[str]` and add `release_file_refusals(session, repository, number)`, which reads the pull request with `ReleasePull.model_validate` and its files with `_changed_files`; `refusals` passes `facts.pull.number` and `facts.files`. Add `src/devops_cli/release/release_files.py` with `check_release_files(argv)`: it takes `--repo` and `--pull`, calls `release_file_refusals`, writes each refusal to standard error and exits 1, exits 0 with one line for a clean pull request, and exits 1 with the read error when GitHub cannot be read. Add `usage_pull` and `files_allowed` to `ReleaseMessages` in `src/devops_cli/lang/en/messages.py`. Write `tests/release/test_release_files.py` over `tests/support/fakes/github.py` for the refused path, the clean pull request and the failed read
  - Verification: `$ uv run devops ci test tests/release/test_release_files.py tests/release/test_release_merge_guards.py tests/release/test_release_merge_pick.py` passes

## 2. Run the guard in the job Tests on Main

Kind: other. Reads: `.github/workflows/ci.yml`, `.github/actions/setup-toolchain/action.yml`, `.github/workflows/release-merge.yml`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/ci.yml`.

- [ ] 2.1 In `main-tests` of `.github/workflows/ci.yml`, add `contents: read` and `pull-requests: read` to the job permissions. Add a step that checks out `${{ github.event.pull_request.base.sha }}` with `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` and `persist-credentials: false`, a step that runs `.github/actions/setup-toolchain/action.yml` with `save-uv-cache: "false"` and `compile-bytecode: "false"`, and a step that runs `uv run --locked --no-dev python -m devops_cli.release.release_files --repo "$REPOSITORY" --pull "$PULL"` with `GH_TOKEN`, `REPOSITORY` and `PULL` in `env:`. Place the step before the step `Read Tests & Coverage of Main`, give it `timeout-minutes: 5`, and extend the comment of the job
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## 3. Document the release file guard in the release cycle

Kind: other. Reads: `RELEASE_CYCLE.md`, `.github/workflows/ci.yml`. Changes: `RELEASE_CYCLE.md`.

- [ ] 3.1 Edit step 4 of `RELEASE_CYCLE.md` and the Files row of its guard table: the job `Tests on Main` runs the release file guard from the base commit of the pull request and fails when the release pull request changes a path that release-please does not write, and a clean release pull request keeps its automatic merge
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `RELEASE_CYCLE.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
