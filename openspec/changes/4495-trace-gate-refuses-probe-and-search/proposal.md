# Proposal: #4495

## Why

The Feasibility trace gate of the stage job refuses sentences that make no claim about what the run read (#4495). `_uncalled_path` in `src/devops_cli/roadmap/stage/stage_change.py` takes each `read` or `reads` outside a negation as a claim that the run read the first path of the sentence. Only a code span, `it` or `which` before the word was exempt (#4314). So "This plan reads `x.py` in group 2", "the group that changes the catalog reads that test" and "a read-only root" were refused. The gate also judged the first path of the sentence, not the path that the read takes. The read set held only the `path`, `directory` and `paths` arguments of tool calls, so a line that the run saw in a `search_code` match counted as not seen. Each refusal costs one more plan run, and two refusals end the item. Closes #4495.

## What Changes

- The trace gate finds the subject of each read word in its clause. A read is a claim of the run when it is the tool `read_file`, a passive (`was read`), a read with no subject (`Read `x``, `Reading `x``, `the same read`), or a read whose subject names the run or its author (`I`, `we`, `the run`, `the planner`). A read whose subject is other words, such as `this plan`, `group 2`, `the probe` or `it`, is no claim.
- `read` before a hyphen, as in `read-only`, is no read word.
- The gate judges the path that the read takes: the first path after it in its clause, the subject of a passive, or the last path before it when no path follows (`read_file` of it). It judges each read claim of a sentence, not only the first path.
- `TraceFacts` holds the `path:line` of each match line that a `search_code` or `callers` answer showed. A citation of that line, `path:line` or `path:line:text`, counts as seen. A claim of the whole file or of a line range does not.
- The kept plan file holds the match lines that its Feasibility section cites, so a revision keeps them.
- A probe line is no read: the gate gives a probe path no support.
- The change carries a spec delta, because it changes which plans the stage job refuses. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The trace gate reads the subject and the object of a read word; a search match supports a citation of its line

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`, `tests/ai/client/test_roadmap_agent_run.py`
- Documents: `docs/roadmap/stage.md`
- Data: a kept plan file gets the field `facts.lines`. A file without it loads with no lines.

## Feasibility

- The premise is confirmed on the stored refusals. On 2026-11-11 the roadmap-service pod held 21 `<n>.refused.json` records (read with `kubectl exec ... cat`, no change). Their last replies hold 14 trace-path refusals of 9 items. A replay of the gate of `origin/main` 9087b39c (with #4463) over them, with a trace that holds every other path of the reply, still refuses 8 of 14:
  - 4 have a subject that is not the run: #4442 "This plan reads `tests/ai/client/test_ai_client_finish_reasons.py` in group 2", #3388 "so the group that changes the catalog reads that test", #3389 "so the new case reads the request context", #2530 "which keep the pulls files read".
  - 1 is `read-only`: #3049 "`k8s/devops/cronjob-runner.yaml` runs the pod as user 1000 with a read-only root".
  - 2 judge a path that the read does not take: #3453 "`read_file` of that prompt at lines 24 and 26 shows ..., and `search_code` with `Adds:` returned one unrelated hit in `src/devops_cli/commands/tf.py`", and #4472.
  - 1 is a true invented read: #3453 "`read_file` of `src/devops_cli/roadmap/plan_read.py` line 478 shows the reader", with no call for that path.
  - 3 of the 4 subject cases also cite a `search_code` match line (`runner.py:470`, `test_roadmap_implement_amend.py:5:...`, `test_roadmap_stage_plan.py:553:...`).
- The 5 probe refusals (#3423, #4442) pass on `origin/main`, because #4463 removes a quoted probe sentence. The subject parse also passes them.
- A search match is one line: `search_code` and `callers` answer `path:line:content` (`src/devops_cli/roadmap/refine/refine_investigation.py:def search_code`, `src/devops_cli/roadmap/stage/stage_tools.py:def callers`). So a citation of that line is a fact that the run saw, and the citation gate checks its text at the staged commit. A claim of the whole file is not: the eval case #3205 claims `read_file` of `src/devops_cli/commands/roadmap.py` from a line that the run did not read, and the replay counts it as a caught defect.
- A probe line is no read. It says only whether a path is a file. #3423 quotes "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit", so a probe path as a read would accept a read of a path that does not exist.
- After the change the replay of the 14 refusals refuses 1: the invented read of #3453.
- A corpus of 15,763 Feasibility sentences (the archived change proposals, the refused records, the eval cases and the kept plans), judged with a trace that holds every tool and no path: the gate of `origin/main` refuses 781, the change refuses 489. No sentence is newly refused. 17 refusals name another path, the object of the read.
- The 9 kept plan files with facts in the pod pass the gate of the change with their own facts.
- First check against the real system: `uv run devops roadmap eval stage --replay` on the base and on the change gives the same report: 81 of 318 defects caught by a gate, 0 missed, and 5 of 5 good plans accepted.

## Existing Tool Considered

A dependency parser such as spaCy finds the subject of a verb, but it needs a model download, adds a large dependency, and does not know the code spans and tool names of a plan. The gate needs the clause of one word and a short list of reader words. The change edits the gate and the trace facts and adds no component. Cost: about 60,000 tokens to build, 5,000 to keep and fix, and 3 hours. The change deletes the first-path rule of `_uncalled_path`.
