# Proposal

## Why

Issue #3092: on 2026-11-01 the implement step stopped on a file that the agent wrote itself, in 4 of 13 stops. The prompt tells the agent to keep scratch files under `.data/agent/scratch/` (#3007), but the agent wrote them in the checkout root anyway:

- #2531: `ruff check` failed with `unused-import` in `tmp_test_telemetry.py`.
- #2524: `ruff check` failed with `unsorted-imports` in `tmp_test_ollama_no_url.py`.
- #2469: `ruff check` failed with an undefined name in `test_helm_commands.py`.
- #2175 (first attempt): `mypy --strict` failed on `test_get_ollama_semaphore.py`.

The step stages the whole checkout with `git add -A`, lists the staged files as "changed", and gives them all to `ruff` and `mypy`. So a scratch file is checked, committed, and can stop the step. A rule in a prompt does not hold.

## What Changes

- A new module `src/devops_cli/roadmap/implement_strays.py` holds `stray_files`. It takes the untracked files of the checkout and the group, and returns the ones that the group does not allow.
- A file is a stray file when it is untracked and git does not ignore it, and it is none of: a path that the group names in a code span (its `Changes:` line and its tasks), a file under the change folder of the item, or a new `test_*.py` file under `tests/` in the directory of a test file that the group names.
- Before the exit checks stage the checkout, the step lists the untracked files (`git ls-files --others --exclude-standard -z`) and deletes each stray file. It does the same after the extra turn, before it compares the checkout with the tree of the first turn. So `git add -A` stages only the allowed files, and `ruff` and `mypy` get only the changed tracked files and the files of the group.
- The names go to the log of the tool calls (one line in the Job log), to `StepOutcome.removed`, and to the message of the extra turn, which says why the step removed them. A fix step has no stray rule: its group names no file.
- The prompt keeps its rule and says that the step deletes a stray file.
- The eval of the job (`devops roadmap eval implement`) reads the diff, and the diff no longer holds a stray file. So the eval passes `StepOutcome.removed` to `diff_scope` and `no_scratch`, and they still fail on a scratch file that the agent wrote.
- Some tests of the step wrote a file that the group does not name and expected the step to keep or report it. They write a file that the group allows now.
- The table of the command shows the removed files. The help text of `devops roadmap implement` says the same.
- Observable behavior changes (a file is deleted, and a message and a table row appear), so the change carries a spec delta.
- The change fits one pull request.

The change does not build repair rounds (#3053) or a check of the mypy path (#3090).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: adds the requirement "A step removes the stray files of the agent".
- `roadmap-eval-implement`: adds the requirement "A run counts the stray files that the step removed".

## Impact

- Code: `src/devops_cli/roadmap/implement_strays.py` (new), `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Documents: `README.md` (generated), `openspec/specs/roadmap-implement-step/spec.md` and `openspec/specs/roadmap-eval-implement/spec.md` (by archive). `k8s/README.md` step 16 does not describe the checks of a step, so it stays.
- Tests: `tests/roadmap/test_roadmap_implement_strays.py` (new), `tests/roadmap/test_roadmap_implement_prompt.py`, `tests/roadmap/test_roadmap_implement_eval_properties.py`, `tests/roadmap/test_roadmap_implement_eval_run.py`, and the step tests whose setup wrote a file that the group does not name (`test_roadmap_implement_step.py`, `_step_repair.py`, `_step_format.py`, `_step_output_cap.py`, `test_roadmap_implement_job.py`).

## Feasibility

- `git grep -n '"add", "-A"' -- src/devops_cli/roadmap/implement_step.py` prints three lines: `_stage` (line 916), `_discarded_diff` and `_foreign_change`. `_exit_failure` calls `_stage` and gives its list of staged paths to `_format_failure` and `_static_failure`, which pass every `.py` path to `ruff` and `mypy`. So an untracked scratch file reaches both tools and the commit. The premise holds on `origin/main`.
- `git ls-files --others --exclude-standard -z` on a scratch repository (git 2.55.0) lists `tmp_test_x.py` and `sub/b.py`, and leaves out a file that `.gitignore` names. It lists files one by one, not whole directories. So git itself gives rule (d), and nothing parses `.gitignore`.
- `step_files.code_spans` reads the code spans of a text with the markdown-it parser. The `Changes:` line that the stage job writes (`stage_group_files`) holds the paths as code spans, a created path with the mark `(new)` after its span. The tasks of the group name the same paths. So the allowed paths come from a parser that the project already uses.
- The step reads no other source of the `creates` list: the plan holds it only as the `(new)` mark, and every created path is also in `Changes:`. So "in Changes" covers "in creates".

## Existing Tool Considered

The change uses `git ls-files --others --exclude-standard` for the list and the ignore rules, and the markdown-it parser of `step_files.py` (`code_spans`) for the paths of the group. `pathlib.PurePosixPath` of the standard library compares the paths. No library finds the stray files of an agent. The new code is one function of about 30 lines and one call site. The cost to build is about 40 000 tokens, to keep it about 3 000 tokens a year, and to fix it about 8 000 tokens. It takes half a working day. The change deletes no code.
