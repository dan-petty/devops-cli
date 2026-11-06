# Design

## Decisions

### The verifier is an agent with the planner's read tools

The verifier answers the `Verification` schema through the same `ToolboxClient` that answers the `StageProposal` schema. The run gets the read tools of `StageTools` and a fresh `RunTrace`. The request holds the system prompt of the pass, the issue, the plan and the cited files. It holds no planner message, because the run starts with a new message list. The eval builds the same client, with the OpenSpec tool too, so its score measures the pass of the job.

- Chosen: one `ToolboxClient` class answers both schemas. The project keeps one tool set and one run loop.
- Rejected: a separate verifier tool set. It is a second tool set to keep and fix, and it can drift from the planner tools.
- Rejected: a verifier that reads the files in code before the call. The model then cannot ask for the file that its claim needs, and the gates already show what the code can check.

### The verifier model comes from the task slot `verification`

The job passes the verifier as a `ToolboxModel` of the task `verification`, as it passes the planner model as a `ToolboxModel` of the task `stage`. The inner client of that runner answers any other schema with no tool.

### The request fits the window with the planner reserve

The window is `task_window("verification")`, because the model of that task serves the run, and the tasks `stage` and `verification` can resolve to different windows. The run hook offers no tool at `tool_stop(window)`, which is the window less its share for the reply. The first request, counted as the hook counts it and with its instructions, stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below that point, so the verifier has room to read. When the cited files do not fit, the request keeps the files in plan order and drops the rest. The verifier can still read a dropped file with `read_file`, and a quote of that read counts.

- Rejected: no limit on the request. A large plan then overflows the window and the run fails.
- Rejected: cut the JSON text of the request. It breaks the structure that the prompt describes.

### Two repair rounds

A finding of a return type with a quote in the input or in a tool answer returns the plan to the planner. The planner gets each open finding of the round, so a `spec_delta_wrong` finding also gets its repair. The job repeats this at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times, which is two. The last review judges the last plan, so its open findings, and no earlier ones, keep the draft with the label `plan/needs-fix`. The comment lists every finding of each round.

- Chosen: a round count. It is bounded and easy to test.
- Rejected: one round. The planner then gets one chance for mechanical findings.
- Rejected: a token budget. It is harder to enforce and to debug than a count.

### Return types

`TASK_ORDER` and `VERIFY_FORM` join `RETURN_TYPES`. They then join `OPEN_TYPES` too, because `OPEN_TYPES` holds every return type.

- Rejected: keep the two types as advice. Then the checks gate nothing, and the plans still need correction commits.

### Evidence from a tool answer

The tools exist so that the verifier reads past the capped input. A quote that had to be in the capped input would make those reads gate nothing. So `VerificationInput.contains` also reads the tool answers of the run, as the tool gave them and with no line numbers. A placeholder finding still needs a quote in the request, because a placeholder in another file of the repository is no defect of the plan.

- Rejected: the full text of each cited file. It misses a file that `search_code` found.

### The review of refine keeps its behavior

`refine_judge.py` sends the same pass with a plain client. The rules that are true only for an agent run (the tools, the quote from a tool answer and the repair rounds) go to `roadmap_stage_verify_tools.md`, and only an agent run loads that prompt. A proposal of refine holds no task group and no verify command, so `JUDGE_OPEN_TYPES` leaves out `task_order` and `verify_form`.

- Rejected: give that review a `ToolboxClient`. It is a new cost for each item of a bot, and no criterion of this item asks for it.
- Rejected: let the two types refuse an item. The findings could only be about tasks that the proposal does not have.

### Trace

Each verifier run appends its `RunTrace` to the traces of its runner. The planner combines the traces of the planner runner and the verifier runner. The item comment reads the combined trace, so each read appears as a tool call with its path.

- Rejected: a separate verify log. It is a second format, and it adds no information.

### Recall floor

The floor is 90% of the defects of the severities `blocker` and `major`. It is the floor that `docs/ROADMAP_WORKFLOW.md` states, and it is the floor that #3207 names. The constant `CONST_ROADMAP_VERIFY_RECALL_FLOOR` holds the number, and the report prints it.

- Rejected: 80% of all defects. The best model that was tested found 56% of the labeled defects and 68% of the major ones, so 80% of all is out of reach now. The project would also hold two floors.
- Rejected: no floor. The eval then can neither pass nor fail.

### Plan that stays open

Commit `#3264` keeps a plan with an open finding in draft, with the label `plan/needs-fix`. The issue body asked that no pull request opens. This change follows the code, which the module docstring of `stage_verify.py` already states.

## Open questions decided here

- The body cites D1 for the round count. The design block of the issue sets two repair rounds. This change uses two.
- The body asks for findings in the PR comment. The job posts the comment on the staged item, so this change keeps that place.
- The read tools are in `stage_tools.py`, not in `stage_toolbox.py`. The change names the right file.
- The score of criterion 2 needs a spend above the limit of the agent, so a person allows that run.
