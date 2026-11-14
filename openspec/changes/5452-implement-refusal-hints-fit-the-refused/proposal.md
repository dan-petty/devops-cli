# Proposal

## Why

The implement step answers every refused shell form with one text, so `uv run python -c` with a `;` and `git status && git log` read the same advice, and the advice about the file comes last. The prompt and that text send the model to `.data/agent/scratch/`, which a fresh checkout does not have, and the prompt tells it to make a directory with `uv run python -c`, a form that the shell refuses. The model sends the same form again, or it stops after three refusals in a row. #5452

## What Changes

- Select the refusal hint from the whole refused command in `src/devops_cli/roadmap/implement/implement_shell_refusal.py:def refusal_hint`, so Python code with a separator gets the `write_file` text first and a chain of allowed programs gets two calls.
- Rewrite `implement_refusal_operator` in `src/devops_cli/lang/en/messages.py` to the two-call text, and add `implement_refusal_python_code` for the script file under the scratch directory.
- Name `read_file` with `offset` and `limit` in the refusal of a pipe to a program that the shell does not allow.
- Add `SHELL_REFUSALS` rows for `openspec` and a bare `devops`, render them in `docs/ROADMAP_WORKFLOW.md`, and compare the refusal table with the shell programs in its test.
- Offer the tool `create_directory` in the implement step, and make `.data/agent/scratch/` in the job before the first step.
- Replace the `python -c` mkdir text of `src/devops_cli/ai/tasks/roadmap_implement_step.md` with `create_directory`.
- Name `create_directory` and the scratch directory in the shell section of `docs/ROADMAP_WORKFLOW.md`, hold that text under a test in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, and run `uv run devops ci fail-to-pass --base origin/main` in the same step.
- Carry the spec delta of `roadmap-implement-step/shell` and `roadmap-implement-step/inputs`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/shell`: A chain of allowed programs names two calls, The pipe refusal names read_file, The refusal table names openspec and devops, The step offers create_directory, The python -c refusal names the write_file call first
- `roadmap-implement-step/inputs`: The job makes the scratch directory before the first step, The prompt names create_directory for a new directory

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_directory.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/implement/test_roadmap_implement_read_pipe.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_directory.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`

## Feasibility

- The probes confirm each cited path at the staging commit, word for word: The path `src/devops_cli/roadmap/implement/implement_shell_refusal.py` is a file of the staging commit.
- The probes place the prompt under the package, word for word: The path `roadmap_implement_step.md` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/tasks/roadmap_implement_step.md`. No commit in the history deleted or renamed it.
- read_file of `src/devops_cli/roadmap/implement/implement_shell_refusal.py` 45-70 and 95-112 shows the first-word selection: `src/devops_cli/roadmap/implement/implement_shell_refusal.py:52:def refusal_hint(word: str) -> str:`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py:59:if word in IMPLEMENT_SHELL_PROGRAMS:` and the one call site `src/devops_cli/roadmap/implement/implement_shell_refusal.py:105:return self._refused(ctx, f"{shown} {refusal_hint(word)}")`.
- read_file of `src/devops_cli/lang/en/messages.py` 3225-3250 shows one text for every operator: `src/devops_cli/lang/en/messages.py:3235:implement_refusal_operator: str = (` and one pipe text: `src/devops_cli/lang/en/messages.py:3242:implement_refusal_pipe: str = (`. The issue cites lines 3223-3229 of 0.129.1; the symbol exists at the staging commit and moved.
- read_file of `src/devops_cli/roadmap/implement/implement_step.py` 636-670 shows the tool names and the agent: `src/devops_cli/roadmap/implement/implement_step.py:648:IMPLEMENT_LOCAL_TOOL_NAMES: Final[frozenset[str]] = frozenset(` holds `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `IMPLEMENT_SHELL_TOOL` and no `create_directory`, and `src/devops_cli/roadmap/implement/implement_step.py:653:def build_agent(` builds the agent.
- search_code for `create_directory` found no match in the commit, so the tool is new and no existing code is copied.
- read_file of `src/devops_cli/ai/tasks/roadmap_implement_step.md` 30-65 shows the mkdir text: `src/devops_cli/ai/tasks/roadmap_implement_step.md:40:Make the directory with ` and `src/devops_cli/ai/tasks/roadmap_implement_step.md:59:The tool `write_file` does not create a directory. To create one, run `, so the 14 mkdir calls follow the prompt.
- read_file of `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` 28-64 shows that the locked harness has no directory tool: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:34:gives an agent six tools` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:59:does not create a directory. A shell command creates it.`, so the issue's `create_directory` of the harness is no tool of 0.59.0 and the plan builds the small tool instead.
- read_file of `src/devops_cli/roadmap/implement/implement_shell_policy.py` 150-230 shows the table and the two sets that the new rows meet: `src/devops_cli/roadmap/implement/implement_shell_policy.py:199:SHELL_REFUSALS: tuple[ShellRefusal, ...] = (`, `src/devops_cli/roadmap/implement/implement_shell_policy.py:212:IMPLEMENT_ALLOWED_PROGRAMS: tuple[str, ...] = (*IMPLEMENT_SHELL_PROGRAMS, *VERIFICATION_PROGRAMS)` and `src/devops_cli/roadmap/implement/implement_shell_policy.py:197:VERIFICATION_PROGRAMS: tuple[str, ...] = (BIN_OPENSPEC, BIN_DEVOPS)`; no row names `openspec` or `devops`.
- read_file of `tests/roadmap/implement/test_roadmap_implement_shell_policy.py` 100-120 and 468-495 shows the test that the two rows contradict: `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:108:def test_a_refused_program_is_not_an_allowed_program() -> None:` and `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:109:assert set(IMPLEMENT_SHELL_REPLACEMENTS).isdisjoint(IMPLEMENT_ALLOWED_PROGRAMS)`. Group 3 edits that assertion and keeps the test and its name.
- read_file of `tests/roadmap/implement/test_roadmap_implement_shell_policy.py` 475-482 shows the test that reads the document and that the last group's verify runs: `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:475:def test_the_document_of_the_workflow_holds_the_same_tables() -> None:` and `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:476:text = (REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md").read_text(encoding="utf-8")`.
- read_file of `tests/invariants/test_roadmap_workflow_doc.py` 189-195 shows the second test that reads the same document: `tests/invariants/test_roadmap_workflow_doc.py:194:assert workflow_problems(_document()) == []`. The text that the last group adds names no label, no record key, no step and no gate, so that test still passes.
- read_file of `docs/ROADMAP_WORKFLOW.md` 255-330 shows the shell section and the refusal table: `docs/ROADMAP_WORKFLOW.md:286:## The shell of a step` and `docs/ROADMAP_WORKFLOW.md:314:The programs that the shell refuses, and what to run instead:`.
- read_file of `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` 140-200 and 375-400 shows the two tests that group 1 updates: `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py:145:def test_the_refusal_of_an_operator_states_the_rule_of_one_command_in_each_call(` and `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py:161:def test_the_refusal_of_python_code_names_the_operator_in_the_code_and_a_script_file(`, and the replacement test at `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py:383:def test_each_replacement_names_an_allowed_program_or_a_tool_that_the_agent_has(`, which the two new rows still pass because each replacement starts with `uv`.
- read_file of `src/devops_cli/roadmap/implement/implement_run.py` 460-500 shows where the job makes the checkout: `src/devops_cli/roadmap/implement/implement_run.py:471:def _worktree(source: Path, target: ImplementTarget, url: str) -> Iterator[Path]:`, which the job opens before the first step.
- search_code for `.data/agent/scratch` shows the path is already the scratch place: `AGENTS.md:18:12. **Keep your own files out of git.** Put agent files under `.data/agent/` and scratch scripts under `.data/agent/scratch/`.`; read_file of `.gitignore` 70-76 shows the ignore rule at `.gitignore:73:.data/*`, so a file there reaches no commit.
- list_files of `tests/roadmap/implement` shows the suites that the changed modules keep: `tests/roadmap/implement/test_roadmap_implement_job.py` for `implement_run`, `tests/roadmap/implement/test_roadmap_implement_command.py` for `implement_step`, `tests/roadmap/implement/test_roadmap_implement_prompt.py` for the prompt, and `tests/roadmap/implement/test_roadmap_implement_read_pipe.py` for the pipe.
- read_file of `src/devops_cli/ci/fail_to_pass.py` 700-745 and 374-400 shows the replay of the last group: `src/devops_cli/ci/fail_to_pass.py:706:def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:`, `src/devops_cli/ci/fail_to_pass.py:379:_verify_commit(root, base)`, `src/devops_cli/ci/fail_to_pass.py:374:def changed_tests(root: Path, base: str, head: str = "HEAD") -> ChangedTests:` and `src/devops_cli/ci/fail_to_pass.py:715:with tempfile.TemporaryDirectory() as tmp:`. The replay runs the changed test files on the base tree only, so it proves a new test fails on the base and proves nothing about the text of a document on the head.
- The review finding is answered: the last group's `verify` is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, which runs `test_the_document_of_the_workflow_holds_the_same_tables` and the new assertion `test_the_shell_section_of_the_document_names_the_directory_tool_and_the_scratch_directory` on the text that the same group adds to `docs/ROADMAP_WORKFLOW.md`, so a command checks the document change.
- The replay is no longer the last group's `verify`: that group runs `uv run devops ci fail-to-pass --base origin/main` in its implementation after the document edit, and the pull request runs it too, as `.github/workflows/fail-to-pass.yml:65:uv run devops ci fail-to-pass --base "origin/${BASE_REF}"` shows.
- Precondition of the call `run_fail_to_pass(root, base="origin/main")` in the last group: it needs a checkout of the repository, and it needs the commit that `origin/main` names, because `_verify_commit` refuses a revision that the checkout does not hold; a fetch of that revision needs a network.
- The replay reads the changed test files of the merge base to the head, so it sees the earlier groups' work in the `wip:` commits that the job makes for each passing group, and it sees a new test file that is untracked.
- The commands of the groups are `uv run devops ci test` and `uv run devops ci fail-to-pass`, the `devops` program of the runner image; they run `git` and `pytest` from the image and write their base worktree in a temporary directory, so no tool is `NOT_IN_RUNNER`. The pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`, and the temporary directory is the writable one of the pod.
- The failure class of the last group is `test` when the replay finds no new test that fails on the base, and its action is `repair`; the failure class of each other group whose test fails is `test` too.
- Preconditions of the other calls: `run_step` in the new tests needs a checkout of the repository, which the `implement_checkout` fixture gives, and a scripted model, so no client and no network; `create_directory(checkout)` needs a checkout only; `add_worktree` reads `origin` through `OriginGit`, so a real run needs a network and the new job test doubles the process; `git check-ignore` in the new job test needs a checkout and reaches no network.
- The first check of the change is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`; the last group then runs `uv run devops ci fail-to-pass --base origin/main`.
- The post-release telemetry criterion reads Loki 7 days after the release, so no offline test and no group delivers it, and it is `pending-person`.

## Existing Tool Considered

No open tool covers this need: the locked pydantic-ai-harness 0.59.0 gives `Coder` six tools, and `write_file` creates no directory. The change builds a small `create_directory` tool and the hint texts in `_RefusingToolset`: about 50 lines of code and about 180 lines of tests, 150k tokens and 3 hours to build, and one tool and one hint per refused form to keep.

## Dependencies

- #5528 also changes `src/devops_cli/lang/en/messages.py`; it touches the decision texts and this change touches the refusal texts, so the later pull request rebases on the earlier.
- #5547 also changes `src/devops_cli/lang/en/messages.py`; it touches the test-worker texts, and the two sets of lines do not meet.
- #5575 also changes `src/devops_cli/lang/en/messages.py`; it touches the golden-base texts, and the two sets of lines do not meet.
