# Proposal

## Why

The item #3770 asks for an onboarding step that checks OpenSpec in the target repository and sets it up through one pull request. The stage job plans each item as an OpenSpec change and reads the rules of the config file, so a managed repository without that file learns of the missing setup one failed plan at a time. Since the infra move, the generic `openspec/config.yaml` is a file of the repository template of dan-petty/infra (`templates/repository/openspec/config.yaml`), and the template pull request of row 9 already adds each template file that a repository lacks. This change adds the OpenSpec row to `devops repos onboard`, so one run reports the state before a plan fails, and it proves that the one template pull request carries the OpenSpec files of the template.

## What Changes

- Add row 16 `openspec` to `devops repos onboard` in `src/devops_cli/github/onboard/run.py` and `src/devops_cli/github/onboard/routes.py`: it reads the config file and the specs folder at the default branch and prints `present`, `missing`, `invalid` or `waiting`.
- Add `MISSING` and `INVALID` to `src/devops_cli/github/onboard/model.py` and count both as failing, so a repository without a valid OpenSpec setup makes the command exit 1, and count both as drift in `src/devops_cli/github/onboard/drift.py`.
- Take the row numbers of `--only` from the row table in `src/devops_cli/commands/repos.py` and `src/devops_cli/lang/en/messages.py`, so `--only 16` is accepted.
- Add `openspec_row` in `src/devops_cli/github/onboard/openspec_row.py` and `folder_exists_at` in `src/devops_cli/github/client.py`, because `get_file_at` gives None both for a folder and for a path that does not exist.
- Write no OpenSpec template in devops-cli. The config file and the specs placeholder come from the render of the template of dan-petty/infra, through the existing file comparison of row 9, so one pull request carries the label file and the OpenSpec files, no file is overwritten, and a second confirm adds nothing.
- Add the OpenSpec config file and the specs placeholder to the fake render of the template in `tests/support/github_repository.py`, as the template of dan-petty/infra renders them, and teach the fake repository to answer a folder path with the listing of its entries.
- Prove the merged tree with a live test that runs the real pinned `openspec validate --specs --strict`, under the real process runner, over the merged files of a scratch repository, and prove the four row states, the one pull request and the second confirm with row tests.
- Describe row 16, its states and the OpenSpec files of the template in `docs/repos/onboard.md`, the document of the command.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: The OpenSpec row reads present, The OpenSpec row reads missing, The OpenSpec row reads invalid, The OpenSpec row reads waiting on the template pull request, The OpenSpec config comes from the repository template, The OpenSpec files reach the repository in one pull request, The merged tree passes the strict OpenSpec validation, The onboard document describes the OpenSpec row, One row for each step

## Impact

- Code: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/openspec_row.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/drift.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/commands/test_repos_onboard.py`

## Feasibility

- The issue body of 2026-11-26 says: "The generic `openspec/config.yaml` is in dan-petty/infra (`templates/repository/`), and the template pull request (row 9) adds it. Do not add a template under `src/`." The tree of dan-petty/infra on `main` holds `templates/repository/openspec/config.yaml`: after five comment lines it names `schema: spec-driven`, and it has a context line `Product: <one line: what this repository makes, for whom, and its main constraints>.` for a person to fill in, and has `rules` for proposal, specs, design and tasks.
- `src/devops_cli/github/onboard/baseline.py:1:"""The baseline of a repository: the Copier template of the template repository at one ref.` renders that template with the `copier` program, and `src/devops_cli/github/onboard/template_pr.py:216:def template_row(` compares each rendered file with the default branch through `_file_states`, adds only the files that the repository lacks to the branch `ci/repository-template`, and keeps a file that the repository holds with other text. So the one pull request, the no-overwrite rule and the second-confirm no-op need no new write code.
- The template of dan-petty/infra holds no `openspec/specs/` folder, and Git keeps no empty folder. `openspec init` of the pinned OpenSpec 2.2.0 writes `openspec/specs/.gitkeep` and `openspec/changes/archive/.gitkeep`; the item of dan-petty/infra under Dependencies adds both to the template. dan-petty/devtools holds `openspec/config.yaml` and no path under `openspec/specs/` today, so the row reads `invalid` there until that template change reaches it.
- The pinned `openspec validate --specs --strict` (OpenSpec 2.2.0) printed `No items found to validate.` and exited 0 in a folder that holds only the config file of the template, with and without an empty `openspec/specs/`, so the merged tree of a new repository passes the strict validation.
- `src/devops_cli/github/onboard/run.py:62:ROW_NAMES: Final[dict[int, str]] = {` holds rows 0 to 15, and `src/devops_cli/github/onboard/run.py:246: run.put(15, lambda: rag_row(writer, ctx, settings))` is the last row of a run, so row 16 is new.
- `src/devops_cli/github/onboard/model.py:14:class RowState(StrEnum):` holds no `missing` and no `invalid`, and `src/devops_cli/github/onboard/model.py:30:_FAILING_STATES: Final[frozenset[RowState]] = frozenset(` holds the states that make the command exit 1.
- `src/devops_cli/github/client.py:687: def get_file_at(self, repo: str, path: str, ref: str) -> str | None:` answers None for a folder at `src/devops_cli/github/client.py:699: if isinstance(answer, list):`, and `src/devops_cli/github/client.py:714: def folder_names_at(self, repo: str, path: str, ref: str) -> tuple[str, ...]:` lists only the folders in a folder, so `openspec/specs/` that holds only `.gitkeep` gives no name. The row needs to know whether the contents answer of the specs path is a folder, which group 1 adds as `folder_exists_at`.
- `tests/support/github_repository.py:157:def render_template(argv: tuple[str, ...], *, extra: dict[str, Any] | None = None) -> None:` writes the files that the fake `copier copy` renders and holds no OpenSpec file, and `tests/support/github_repository.py:530: def _contents(self, files: dict[str, str] | None, path: str) -> httpx2.Response:` answers `tests/support/github_repository.py:531: if files is None or path not in files:` with 404 for a folder, so the fake needs the two OpenSpec files and a folder answer.
- `src/devops_cli/commands/repos.py:1033:_ONBOARD_ROWS = range(16)` and `src/devops_cli/lang/en/messages.py:747: onboard_only_invalid: str = "--only takes row numbers from 0 to 15, such as 2,3,8: {value}"` refuse `--only 16`, and the row tests build `OnboardOptions` directly, so group 5 takes the numbers from `ROW_NAMES` and tests the command line.
- `src/devops_cli/github/onboard/drift.py:20:# The states of a plan row that leave the repository off its baseline and are no failed read: the` documents `_DRIFT_STATES` as the states that make the command exit 1, so `missing` and `invalid` join it.
- `tests/support/fakes/process.py:9: Also fakes `shutil.which` for any tool not on the passthrough list (`git`, `bwrap`),` and the fake answers an unknown call with exit 0, so the live test of group 3 runs the validator under `set_process_runner(DefaultProcessRunner())` of `src/devops_cli/core/process.py:1082:def set_process_runner(runner: ProcessRunner | None) -> None:`.
- `src/devops_cli/config/constants.py:6023:CONST_OPENSPEC_CONFIG_PATH: Final[str] = f"{CONST_OPENSPEC_DIR}/{CONST_OPENSPEC_CONFIG_FILENAME}"` is the config path and `src/devops_cli/config/constants.py:6028:CONST_OPENSPEC_SPECS_DIR: Final[str] = f"{CONST_OPENSPEC_DIR}/specs"` is the specs folder, so the row names no second copy of either.
- `src/devops_cli/openspec/tool.py:165:def isolated_openspec(root: Path | None = None) -> Iterator[OpenSpecTool]:` gives the pinned binary, and `tests/openspec/test_openspec_contract.py:56:@pytest.mark.live("openspec")` is the mark of a test that starts it, so group 3 runs the real validator over the merged tree.
- `src/devops_cli/github/onboard/routes.py:344:READS: Final[tuple[tuple[int, str], ...]] = (` ends at `src/devops_cli/github/onboard/routes.py:377: (15, "Qdrant count and scroll of the points of the repository"),`, so group 4 adds the reads of row 16 there.
- The issue names `stage_change.py` and `stage_validate.py` at their old paths; they are `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/roadmap/stage/stage_validate.py` since #3897, and this change does not edit them.
- Precondition: `openspec_row(session, ctx)`, `get_file_at` and `folder_exists_at` need a client of the GitHub API; the tests give it through the fakes of `tests/support/`.
- Precondition: `isolated_openspec(root)` needs a checkout of the scratch tree and no network, because it starts the pinned binary in that directory.
- The verify commands `uv run devops ci test tests/github/onboard/test_onboard_openspec.py`, `uv run devops ci test tests/github/onboard/test_onboard_rows.py` and `uv run devops ci docs` need the failure classes `test`, `lint` and `types`. The one program the plan starts is the `openspec` binary, which the runner image holds.
- The first check against the real system is `uv run devops repos onboard dan-petty/devtools --plan --only 16`, which must print row 16 as `invalid` with `openspec/specs/` in its reason while the template of dan-petty/infra holds no specs placeholder.

## Existing Tool Considered

Fission-AI/OpenSpec (MIT, maintained) is the open tool in use: `openspec init` writes the folder, the config file and the placeholders, and `openspec validate --specs --strict` validates the specs; this repository runs the pinned binary under an isolated configuration. Copier, through the template of dan-petty/infra and row 9, already writes the config file to a repository. Neither gives a present, missing or invalid row, so this change adds only that row, its reads and its tests. Written cost: about 150,000 tokens to build, keep and fix, and about 1 hour. The change deletes no internal code.

## Dependencies

- dan-petty/infra#201: it adds `openspec/specs/.gitkeep` and `openspec/changes/archive/.gitkeep` to the repository template. No group here waits on it, because the tests render the fake template with the placeholder, but until a release of dan-petty/infra holds it, a repository that onboards reads row 16 `invalid` after its template pull request merges, with the `copier update` step in the reason. The Workflow follow-up names it.
- #3742: closed; the template file `.github/labels.yml.jinja` of dan-petty/infra delivers the label file through the template pull request of row 9, so the label file and the OpenSpec files share that one pull request.
- #3767: it changes the pull request form check for a repository without OpenSpec, and this plan adds no pull request code, so no group waits on it.
