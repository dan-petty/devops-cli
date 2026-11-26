# Proposal

## Why

The item #3770 asks for an onboarding step that checks OpenSpec in the target repository and sets it up through one pull request. The stage job plans each item as an OpenSpec change and reads the rules of the config file, so a managed repository without that file learns of the missing setup one failed plan at a time. This change adds the OpenSpec row to `devops repos onboard`, so one run reports the state before a plan fails, and it adds the project-neutral config file and the specs placeholder to the one template pull request that the command already opens.

## What Changes

- Add row 16 `openspec` to `devops repos onboard` in `src/devops_cli/github/onboard/run.py` and `src/devops_cli/github/onboard/routes.py`: it reads the config file and the entries under the specs folder at the default branch and prints `present`, `missing`, `invalid` or `waiting`.
- Add `MISSING` and `INVALID` to `src/devops_cli/github/onboard/model.py` and count both as failing, so a repository without a valid OpenSpec setup makes the command exit 1.
- Add `openspec_row` in `src/devops_cli/github/onboard/openspec_row.py` and `folder_entries_at` in `src/devops_cli/github/client.py`, because `get_file_at` gives None for a folder and the specs path holds a file.
- Ship the project-neutral config at `src/devops_cli/templates/openspec/config.yaml`, with a marked context line and the proposal, specs, design and tasks rules, and merge it with the specs placeholder into the template pull request of row 9 in `src/devops_cli/github/onboard/template_pr.py`, so one pull request carries the label rule of #3742 and the OpenSpec files.
- Teach the fake repository in `tests/support/github_repository.py` to answer a folder path with the listing of its entries, so the row reads the specs folder.
- Prove the merged tree with a live test that runs the real pinned `openspec validate --specs --strict` over the merged files of a scratch repository, and prove the four row states, the one pull request and the second confirm with row tests.
- Describe row 16, its states, the shipped template and the specs placeholder in `docs/repos/onboard.md`, the document of the command.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: The OpenSpec row reads present, The OpenSpec row reads missing, The OpenSpec row reads invalid, The OpenSpec row reads waiting on the template pull request, The shipped OpenSpec config is project-neutral, The OpenSpec files reach the repository in one pull request, The merged tree passes the strict OpenSpec validation, The onboard document describes the OpenSpec row, One row for each step

## Impact

- Code: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/openspec_row.py`, `src/devops_cli/github/client.py`, `src/devops_cli/templates/openspec/config.yaml`, `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py`, `tests/github/onboard/test_onboard_rows.py`

## Feasibility

- `probes` says "The path `openspec/config.yaml` is a file of the staging commit." This run then read that file: `openspec/config.yaml:1:schema: spec-driven`, `openspec/config.yaml:7:devops-cli is pre-1.0 alpha software` and `openspec/config.yaml:12:rules:` show a file of this project with the schema and the rules, so the file of devops-cli cannot serve another repository and the shipped template replaces it.
- `probes` says "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.", and that module holds the statement `CREATED_LINE_TOKENS: Final[int] = 32`, so the rules of the config file are applied at `src/devops_cli/roadmap/stage/stage_change.py`.
- `probes` says "The path `stage_validate.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_validate.py`. No commit in the history deleted or renamed it.", and the strict run of a plan is `src/devops_cli/roadmap/stage/stage_validate.py:134:def validate_change(`, whose body runs `run = tool.run(["validate", change, "--strict", "--json"], root)`.
- The issue names an onboard command of the roadmap group, and this tree has none: `src/devops_cli/commands/repos.py:1063:@app.command("onboard", help=HELP.repos.onboard)` registers the command under `repos`, and `docs/repos/onboard.md:44:| Row | Name | What it does |` is its row table, so the plan changes `docs/repos/onboard.md` and not the `docs/roadmap/onboard.md` of the issue.
- `src/devops_cli/github/onboard/run.py:62:ROW_NAMES: Final[dict[int, str]] = {` holds rows 0 to 15, and `src/devops_cli/github/onboard/run.py:246: run.put(15, lambda: rag_row(writer, ctx, settings))` is the last row of a run, so row 16 is new.
- `src/devops_cli/github/onboard/model.py:14:class RowState(StrEnum):` holds no `missing` and no `invalid`, `src/devops_cli/github/onboard/model.py:17:PRESENT = "present"` shows that a state prints its own value, and `src/devops_cli/github/onboard/model.py:30:_FAILING_STATES: Final[frozenset[RowState]] = frozenset(` holds the states that make the command exit 1.
- `src/devops_cli/github/client.py:650: def get_file_at(self, repo: str, path: str, ref: str) -> str | None:` answers None for a directory at `src/devops_cli/github/client.py:662: if isinstance(answer, list):`, and `src/devops_cli/github/client.py:677: def folder_names_at(self, repo: str, path: str, ref: str) -> tuple[str, ...]:` lists folders only, so the row needs one read of every entry of the specs folder, which group 1 adds as `folder_entries_at`.
- `src/devops_cli/github/onboard/template_pr.py:73:def _file_states(` adds only the files that the revision lacks, `src/devops_cli/github/onboard/template_pr.py:216:def template_row(` compares `src/devops_cli/github/onboard/template_pr.py:226: missing, kept = _file_states(session, repo, baseline.files, ctx.default_branch)` and records the open pull request in `ctx.template_head`, so the one pull request, the no-overwrite rule and the second-confirm no-op need no new write code.
- `tests/support/github_repository.py:343: def merge_template_pull(self) -> None:` merges the template pull request in a scratch repository, and `tests/support/github_repository.py:530: def _contents(self, files: dict[str, str] | None, path: str) -> httpx2.Response:` answers `tests/support/github_repository.py:531: if files is None or path not in files:` with 404 for a folder, so group 1 teaches the fake to answer a folder path with the listing of its entries.
- `src/devops_cli/config/constants.py:5969:CONST_OPENSPEC_CONFIG_PATH: Final[str] = f"{CONST_OPENSPEC_DIR}/{CONST_OPENSPEC_CONFIG_FILENAME}"` is the config path and `src/devops_cli/config/constants.py:5974:CONST_OPENSPEC_SPECS_DIR: Final[str] = f"{CONST_OPENSPEC_DIR}/specs"` is the specs folder, so the row and the template name no second copy of either.
- `src/devops_cli/openspec/tool.py:165:def isolated_openspec(root: Path | None = None) -> Iterator[OpenSpecTool]:` gives the pinned binary, and `tests/openspec/test_openspec_contract.py:56:@pytest.mark.live("openspec")` is the mark of a test that starts it, so group 3 runs the real validator over the merged tree.
- `src/devops_cli/github/onboard/routes.py:344:READS: Final[tuple[tuple[int, str], ...]] = (` ends at `src/devops_cli/github/onboard/routes.py:377: (15, "Qdrant count and scroll of the points of the repository"),`, so group 4 adds the two reads of row 16 there.
- The comment of 2026-11-11 puts the generic template in the project kit of #3753 and the config read in the helper of #4629. This plan ships the template that criterion 3 of #3770 names, because #3753 is no dependency of the body, and it reads the config at the default branch with `get_file_at`, because `src/devops_cli/openspec/project.py:26:def uses_openspec(source: Path, ref: str, *, operation: str) -> bool:` takes a checkout and the onboard run has none.
- Precondition: `openspec_row(session, ctx)` needs a client of the GitHub API, for the config file and for the entries under the specs folder.
- Precondition: `get_file_at(repo, path, ref)` and `folder_entries_at(repo, path, ref)` need a client of the GitHub API.
- Precondition: `onboard_repository(options, *, session, settings)` needs a client of the GitHub API, which sends every request of the run.
- Precondition: `template_row(session, writer, ctx, baseline, template)` needs a client of the GitHub API and a checkout of the template that the renderer reads; the test gives both through the fakes of `tests/support/`.
- Precondition: `isolated_openspec(root)` needs a checkout of the scratch tree and no network, because it starts the pinned binary in that directory.
- The verify commands `uv run devops ci test tests/github/onboard/test_onboard_openspec.py`, `uv run devops ci test tests/github/onboard/test_onboard_rows.py` and `uv run devops ci docs` need the failure classes `test`, `lint` and `types`. The one program the plan starts is the `openspec` binary, which the runner image holds, so no program of the plan is `NOT_IN_RUNNER`, and the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`.
- The first check against the real system is `uv run devops repos onboard <owner>/<name> --plan --only 16` on a repository whose default branch holds no `openspec/config.yaml`, which must print row 16 as `missing` and exit 1.
- The second live check is `uv run devops repos onboard <owner>/<name> --confirm` on that repository, which must open one draft template pull request that holds the OpenSpec config file and the specs placeholder, and a second `--confirm` must create no commit and no second pull request.
- `src/devops_cli/roadmap/stage/stage_change.py:143:CREATED_LINE_TOKENS: Final[int] = 32` and `src/devops_cli/roadmap/stage/stage_change.py:145:MAX_GROUP_CHANGES: Final[int] = 5` bound each group, and group 1 holds 5 files with 200 estimated new lines, which counts 6400 tokens of its step.

## Existing Tool Considered

Fission-AI/OpenSpec (MIT, maintained) is the open tool in use: `openspec init` writes the folder, the config file and the skills, and `openspec validate --specs --strict` validates the specs, and this repository runs the pinned binary under an isolated configuration. The tool gives no project-neutral context line, no rules for proposal, specs, design and tasks, no present, missing or invalid row, and no pull request with the no-overwrite and second-confirm behavior, so this change adds only those parts. Written cost of the row, the shipped template and their tests: about 300,000 tokens to build, keep and fix, and about 2 hours. The change deletes no internal code.

## Dependencies

- #3742: it delivers the label file through the template pull request of row 9, and this change adds the OpenSpec files to that same pull request, so it blocks no group here.
- #3767: it changes the pull request form check for a repository without OpenSpec, and this plan adds no pull request code, so no group waits on it.
