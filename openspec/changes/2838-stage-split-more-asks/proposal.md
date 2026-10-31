# Proposal

## Why
Issue #2838: `devops roadmap stage --plan` leaves out four P1 bugs (#2735, #2739, #2147, #2747) because one task group of each measures 41179 to 48286 tokens, over the budget of 40000. The issue asks for more split asks and for a check of the shared part (the item and the change folder, which every group pays).

The numbers show a different cause. The measure of a group packs each file it names to at most the budget (`limit=self._budget`, 40000 tokens). The implement step packs each file to at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` (3000 tokens), in `implement_step._packed`. So the stage job charges `src/devops_cli/config/constants.py` 38159 tokens, and the step that does the work reads 1847. A group that names this file is over the budget whatever the model splits. Another ask cannot fix that.

## What Changes
- The measure of a group packs each file the way the implement step does: one function, `packed_file`, in the new module `roadmap/step_files.py`, used by `implement_step` and by `stage_change`. A file counts at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`.
- `measure_groups` loses its `limit` argument. `Planner._build` stops passing the budget as a file limit.
- The requirement "The job measures each task group" changes: it names the cap per file. This is an observable change, so it has a spec delta.
- The number of split asks stays one. The acceptance criteria that ask for a second ask are not built (see Feasibility).
- The module text of `stage.py` and the tests of the measure change with the code.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `roadmap-stage`: the measure of a task group counts each file as the step reads it.

## Impact
The groups of the four items measure about 5000 to 8000 tokens, and the job stages them with no person. Every item that names a large file stops less often. The step budget of 40000 does not change.

The change fits one pull request: one new module of about 20 lines, two edited functions, and tests.

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

Files, which make the rest of each group:

| Group | Group total | Shared | Group text | Files at the budget | Files as the step reads them |
| :--- | ---: | ---: | ---: | ---: | ---: |
| #2735 "Add LESS to refused env patterns" | 41479 | 3029 | 291 | 38159 | 1847 |
| #2739 "Add data-egress constant and extend the guard" | 45013 | 3642 | 231 | 41140 | 4828 |
| #2147 "Remove the exemption sentence from the README" | 43076 | 3157 | 186 | 39733 | 3000 |
| #2747 "Add PYTEST_ADDOPTS to the env guard" | 41732 | 3347 | 226 | 38159 | 1847 |

One file makes the difference each time: `src/devops_cli/config/constants.py` is 61452 tokens raw, 38159 packed by the stage measure and 1847 as the step reads it. `k8s/README.md` is 41011 raw and counts 39733 in the stage measure, 3000 in the step. After a split, every new group that names `constants.py` was still over the budget (41598, 42242, 41906, 42003), because the file alone is 38159. A split moves files between groups. It cannot make one file smaller. A second ask, with the measured tokens, would see the same file in the same group and could only drop it, but the group needs the file. This matches the real flow: the step reads 1847 tokens of it and opens the rest with its tools.

The groups with the corrected measure: #2735 about 5200, #2739 about 8800 (`constants.py` and `core/process.py` in one group; the model may keep one group), #2147 about 6600, #2747 about 5400. All are far under 40000.

Command output: `uv run devops roadmap stage --plan` on 2026-10-31 lists the four items under "Left out". The scratch run that gave these numbers wraps `Planner._build` and records the replies.

## Existing Tool Considered
- The context packer of the repository (`ContextPacker`) and `truncate_to_token_limit` already pack a file to a cap. The implement step uses them in `_packed`. The change moves that function to a shared module and calls it from the stage measure. It builds no new packer and no new counter.
- tiktoken counts the tokens (`count_tokens`), as before.
- The change deletes `implement_step._packed` and `stage_change._packed_tokens` as they are, and the `limit` argument of `measure_groups`.
