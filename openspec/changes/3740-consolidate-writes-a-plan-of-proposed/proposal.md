# Proposal: #3740

## Why
The consolidation job (#1127) builds shortlists of open items that may share a root cause (`src/devops_cli/roadmap/consolidate_shortlist.py`), but no code calls them. A person cannot run `devops roadmap consolidate` or read a plan of proposed groups. This change is the model stage of the job: a proposal and a refutation of each shortlist, a check of the answers in code, and a plan file. Apply (#3743) and the MCP mirror with the weekly row (#3745) are other items. Closes #3740.

## What Changes
- `src/devops_cli/roadmap/consolidate.py`: the plan models (`Plan`, `Group`, `GroupMember`, `Failure`), the rules in code, the run, the decline, the render and the dry run.
- `src/devops_cli/roadmap/consolidate_judge.py`: the judge seam, `ShortlistJudge`, one function that takes a case (a shortlist with its item texts) and returns a `Judgement` with a verdict for each member. `GatewayShortlistJudge` is the one implementation: two tool-less `chat_structured` calls with the client of `ai.for_task("analysis")`, a proposal and a refutation. Another judge can replace it with no change to the rules in code.
- `src/devops_cli/ai/tasks/roadmap_consolidate_propose.md` and `roadmap_consolidate_refute.md`: the prompts. A member text is data in the user message and never an instruction.
- `src/devops_cli/commands/roadmap.py`: `devops roadmap consolidate` with `--repo`/`-R`, `--ref`, `--limit`, `--dry-run`, `--confirm` and `--decline <group-id>`. `--limit` caps the shortlists that one run judges; the plan holds the rest as unjudged and a rerun judges them.
- `src/devops_cli/roadmap/stores/store.py`: the job record key `consolidate.declined`, in `ConsolidateRecordKey`.
- `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`: the dry-run requests, the step name `judge`, the help and the output text.
- `docs/roadmap/consolidate.md` and the generated command documents.
- The change adds a command, so it carries a spec delta (`roadmap-consolidate-plan`).

It fits one pull request.

## Capabilities
- `roadmap-consolidate-plan`: new.
- `roadmap-command-help`: not modified. Its requirement names six commands; the help of the new command follows the same rule and `roadmap-consolidate-plan` states it.

## Impact
- A person can run `devops roadmap consolidate` and read `.data/roadmap/consolidate/<date>.json`. The only GitHub write is `--decline <group-id> --confirm`: one write of the job record of the anchor.
- A run costs two model requests for each judged shortlist. The plan keeps the model output, so a rerun over a shortlist with the same hash costs none.
- No new dependency and no new setting. The token cap and the wait limit of the model stage follow the bounds of the other model steps when they exist (#3566); until then the client defaults apply.

## Feasibility
Premise checked on 2026-11-10 against the code and command output.

1. The command is absent: `uv run devops roadmap consolidate --help` answers `No such command 'consolidate'`. `git grep -n "consolidation_groups" -- src` finds no caller outside `consolidate_shortlist.py`. The shortlists (`consolidation_groups`, `Shortlist`, `Member`, `Evidence`) and their tests exist.
2. Two tool-less structured calls: `LLMClient.chat_structured(system, prompt, schema)` of `src/devops_cli/ai/client/structured.py` takes a schema and no tools, and `get_llm_client(task="analysis", ...)` builds the client of `ai.for_task("analysis")` (the refine job uses it the same way). No task key is needed. `GatewayRetitleModel` shows the error rule: a call that cannot reach the gateway raises `ModelGatewayUnreachableError`, which names the gateway.
3. A person's milestone: no job writes the milestone of an issue. `RoadmapStore` has no method that sets it (`git grep -n "milestone" src/devops_cli/roadmap/stores/store.py` shows only the read of the title and the edit of a milestone itself), and intake "sets no milestone". So every milestone on an item is a person's, and the job record (ADR 0002) needs no mark to tell them apart. If a job ever writes a milestone, it must record a mark, and the rule reads it.
4. Status labels: `CONST_ROADMAP_STATUS_IN_PROGRESS` and `CONST_ROADMAP_STATUS_IN_REVIEW` exist, and `Item.status` reads them from the labels (ADR 0016).
5. A reopened member: `RoadmapStore.closures(number)` returns the close and reopen events of an issue, with `duplicate_of` for a close as a duplicate. A member closed as a duplicate of the anchor and reopened later is readable.
6. A cited `path:line`: `git show <sha>:<path>` through `devops_cli.roadmap.clone_git.git` reads the file at the recorded commit; the line is in range or it is not. A cited `#N` is checked against `store.issues()`.
7. The decline: `RoadmapStore.set_marks(item, marks)` writes a mark in the job record of an Item in one write. `consolidate.declined` is a new key; `_JOB_RECORD_KEYS` lists the keys this version reads, so the key is added there.
8. The issue lists a flag `--confirm` and says a run writes no GitHub change. The only GitHub write in this change is the decline, so `--confirm` applies to `--decline`. `--confirm` without `--decline` is refused with a message, not ignored.
9. Not verified here: the quality of the verdicts of a model on the whole board. The live run in the pull request comment judges a small shortlist only.

## Existing Tool Considered
The alternatives check of #1127 (2026-10-30) and of this issue (2026-11-08) found no open, maintained tool that groups open issues by root cause with these rules. The change reuses `chat_structured`, `ai.for_task("analysis")`, the shortlists of `consolidate_shortlist.py`, the `RoadmapStore`, `resolve_data_path`, `write_json_file` and Pydantic. It adds no dependency and no home-grown similarity or graph code: the embeddings and the grouping are the existing code. The judge is built, not bought: about 700 lines and 12 tests. The cost is the tokens to write them once (about 150 000), the upkeep of two prompts, and the model requests of a run. The code deletes nothing; `consolidate_shortlist.py` gets its first caller.
