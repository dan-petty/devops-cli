# Proposal

## Why
Issue #2838: `devops roadmap stage --plan` leaves out four P1 bugs (#2735, #2739, #2147, #2747). One task group of each measures 41179 to 48286 tokens, over the budget of 40000. The issue asks for more split asks and a check of the shared part (the item and the change folder, which every group pays).

The numbers show a different cause. The delivered fix differs from the text of the issue, and the acceptance criteria that ask for a second split ask are replaced (see Feasibility). Two defects make a group cost more than its step reads:

- The measure packs each file to at most the budget (40000 tokens). The implement step packs each file to at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` (3000 tokens). The stage job charges `src/devops_cli/config/constants.py` 38159 tokens, and the step that does the work reads 1847.
- The measure counts the files of `reads` and `changes`. The step reads the files that the tasks of the group name in code spans. The `Reads:` line is no task, so the step never reads a file that only this line lists. A file in a task text that `reads` omits is read, but the measure skips it.

Another ask cannot fix a file that alone costs more than the budget.

## What Changes
- One module, `roadmap/step_files.py`, holds what a step reads: the parser of `tasks.md` (`parse_task_groups`), the choice of the files a group names (`named_files`) and the text of a file (`packed_file`). `implement_step` and `stage_change` both use it.
- `measure_groups` parses the text of each group as the step does, and counts the tokens of the files that the step reads, each packed as the step packs it. It loses its `limit` argument. `Planner._build` stops passing the budget.
- The stop record gets a second key, `stage.file_cap`: the file cap of the measure that made the stop. The job counts a `stage.needs_split` record only when `stage.file_cap` is the file cap of now. The four stopped items hold a record from the old measure, which no longer counts, so the default plan takes them without a person.
- The number of split asks stays one.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `roadmap-stage`: a task group is measured with the files its step reads, and a stop record counts only for the measure that made it.

## Impact
With the new measure the largest group of #2147, #2735 and #2739 measures 3083, 2833 and 3699 tokens. Every item that names a large file stops less often. The step budget of 40000 does not change.

The change fits one pull request: one new module that gathers code the step already has, two edited functions, one record key, and tests.

## Feasibility
The premise "a second ask fixes the groups" was tested against the real system. The four items were planned with the real model (`analysis` task through the gateway, the checkout at `origin/main`), and the measure of each group was split into its parts.

Shared part, which every group pays (item title and body, plus the five files of the change folder):

| Item | Item text | Change files | Shared |
| :--- | ---: | ---: | ---: |
| #2735 | 1825 | 1204 (first reply), 1414 (after the split) | 3029 / 3239 |
| #2739 | 1952 | 1690 / 1896 | 3642 / 3848 |
| #2147 | 1161 | 1996 / 2402 | 3157 / 3563 |
| #2747 | 1943 | 1404 / 1708 | 3347 / 3651 |

The shared part is 3000 to 3900 tokens: 8% to 10% of the budget. It is not what keeps the groups over. The refine block of #2735 is part of its 1825 tokens, and removing all of it would save less than 1800 tokens for each group.

Files, which make the rest of each group, with the old measure:

| Group | Group total | Shared | Group text | Files at the budget | Files as the step reads them |
| :--- | ---: | ---: | ---: | ---: | ---: |
| #2735 "Add LESS to refused env patterns" | 41479 | 3029 | 291 | 38159 | 1847 |
| #2739 "Add data-egress constant and extend the guard" | 45013 | 3642 | 231 | 41140 | 4507 |
| #2147 "Remove the exemption sentence from the README" | 43076 | 3157 | 186 | 39733 | 3000 |
| #2747 "Add PYTEST_ADDOPTS to the env guard" | 41732 | 3347 | 226 | 38159 | 1847 |

One file makes the difference each time: `src/devops_cli/config/constants.py` is 61452 tokens raw, 38159 packed by the old stage measure and 1847 as the step reads it. `k8s/README.md` is 41011 raw and counted 39733 in the old measure, 3000 in the step. After a split, every new group that named `constants.py` was still over the budget (41598, 42242, 41906, 42003), because the file alone is 38159. A split moves files between groups. It cannot make one file smaller. A second ask would see the same file in the same group and could only drop it, but the group needs the file.

Live check with the new code: `uv run devops roadmap stage --plan` on 2026-10-31 lists #2147, #2735 and #2739 under "To stage", with a largest group of 3083, 2833 and 3699 tokens. The setting `roadmap.stage.limit` is 3, so #2747 waits for the next round. Before the record key, the same command left out all four items because of the stale `stage.needs_split` records. A person who named one item with `--item` got it staged.

Command output: `uv run devops roadmap stage --plan` on 2026-10-31 before the change lists the four items under "Left out".

## Existing Tool Considered
- The context packer of the repository (`ContextPacker`) and `truncate_to_token_limit` already pack a file to a cap. The implement step uses them. The change moves that code, and the task parser of the step, to a shared module. It builds no new packer, parser or counter.
- markdown-it-py parses `tasks.md`, as before. tiktoken counts the tokens (`count_tokens`), as before.
- The change deletes `implement_step._packed`, `stage_change._packed_tokens` and the `limit` argument of `measure_groups`.
