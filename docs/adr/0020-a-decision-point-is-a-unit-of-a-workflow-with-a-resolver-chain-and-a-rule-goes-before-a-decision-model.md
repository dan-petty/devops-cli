# A decision point is a unit of a workflow with a resolver chain, and a rule goes before a decision model

TypeSafe Jev (`typesafe/jev-1.14`) is a System One decision model. ADR 0019 says how a step uses it: short closed questions about evidence that tools extract. The pilots that followed put Jev on top of steps that a generation model still runs. This record changes the unit of design. A workflow has named **decision points**. A point has a resolver chain: a deterministic rule first, a decision model second and the current behavior of the generation workflow last. This record builds no code. The registry and the first point on it are the next two items.

## Status

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md` names the merge commit.

This record **amends ADR 0019** in three places and no other. The seven rules of ADR 0019 stay in force. (1) The table of ranked decision points and the section of the pilots in ADR 0019 are replaced by the catalogue below. (2) Rule 6 of ADR 0019 says that a switch is off by default. This record says where the switch is: the mode of the point in `roadmap.decisions`, and the setting `ai.decision_model` that names the model. (3) The text of pilot 2 in ADR 0019 is replaced by its measured result (see the catalogue).

## Context

The owner asked on 2026-11-10: are we using decision-model functions as they are built, or are we using Jev in a workflow built for a generation model? The answer has two parts.

- The client is right. `src/devops_cli/ai/jev.py` uses the `DecisionModel` of pydantic_ai with typed `Choice`, `Noul` and `Score` questions, and `decide_with_jev` sends one request. The first pilot follows ADR 0019.
- The workflows are not. Every pilot is a gate or a judge on a step that a generation model runs. The cookbook functions of `jev.py` (`route_with_jev`, `gate_tool_call_with_jev`, `select_skill_with_jev`, the `auto` mode) have no caller in a workflow. No workflow has a named decision point. Each pilot has its own setting, its own metric and its own log line.

The owner decided: build the workflows as decision-model workflows when a decision model is configured and enabled.

What the pilots measured (2026-11-10):

| Step | Result | What it shows |
| :--- | :--- | :--- |
| The screen before the verify step (#4282) | The reviewer alone found no serious defect in 9 of 48 cases (19%). No screen can skip more with no loss. On the held-out halves, the best shared cut skipped 4% and lost nothing. | Jev works for closed questions about a digest that tools make, with cuts fitted on labelled data. The data limits the saving. |
| The completeness check of a draft (#4308) | 28% false holds, 43% recall. The probability moved 0.02 or less when one hunk left a long diff that was given as state. | Jev does not read a long diff. |
| The labels of an intake proposal (#4298) | Type: a tie with the triage model (17 of 25 each). Priority 10 against 15, Value 12 against 16, Effort 15 against 17. True duplicates: 0 of 3 against 1 of 3. | Jev is no drop-in for a structured answer of a generation model. |
| The class of a failure when no rule matches (pilot 2) | 8 stops in 8 days, 4 of them one pattern. A typed class fixes that pattern (#4390). | A rule beats a model on a small tail. |
| The extension of the implement budget (pilot 3, #4394) | 33 labelled checkpoints from 28 items, 16 of them right to extend. A rule on the last 20 tool calls (one successful edit, fewer than 4 refused commands) has no error on them. | A rule beats a model when a count decides. |

So the design cannot assume that a decision model is better. A point asks a rule first. It asks the decision model second, and only where the model has been measured to add something to the rule. It falls back to the behavior of today.

## Decision

### 1. The decision point

A **decision point** is a named place in a workflow where the workflow picks one outcome of a closed set. It is a first-class unit. The registry holds one entry for each point, with these parts.

| Part | What it is |
| :--- | :--- |
| Name | `<area>.<what>`, such as `stage.verify_screen`. The name is a key of the setting `roadmap.decisions`, a label of the metric and a key of the records. |
| Question schema | The typed questions: `Noul` (yes/no with a probability), `Choice` (one option of a list) and `Score` (a level of a rubric). The set is fixed in code. No question text comes from the input. |
| Evidence builder | Code that makes the digest from the input of the point. A tool extracts each fact (a count, a path check, a test name, a criterion). The digest is short. Where the repository is private, the digest holds counts only. A digest that holds a secret raises, and the point falls back. |
| Resolver chain | Section 2. |
| Cuts | Section 3. The cuts are data in the repository. |
| Action bands | `continue`, `review` and `flag`. The point says what each band does. |
| Fail-back | An error, a timeout, a missing answer, a confidence under the floor, or no model configured: the current behavior runs. |
| Mode | `off`, `shadow` or `on`, in `roadmap.decisions`. |
| Outcome join | Section 6. |

A point returns a band and never a text. The generation model still writes every plan, every code edit and every finding.

### 2. The resolver chain

The registry resolves a point in this order and stops at the first resolver that answers.

1. **The rule.** A deterministic function of the digest, with its parameters as data. A point has a rule only when a rule is proven good on labelled data: it meets the bar of the point on the half that was not fitted. Where a rule meets the bar, the point gets no model resolver. A model is added to a point only when it is measured to add to the best rule: it meets a bar that the rule misses, on the half that was not fitted.
2. **The decision model.** It runs when `ai.decision_model` is set and the mode of the point is `shadow` or `on`. The questions go in one request. The cuts give the band.
3. **The current behavior.** The workflow does what it does today. This is the fail-back, and it is the only resolver of a point whose mode is `off`.

The mode sets what the answer does. With `off` the chain does not run. With `shadow` the chain runs, the registry records the answer, and the workflow acts as with `off`. With `on` the band acts. The registry refuses the mode `on` for a point that has no fitted cuts in the repository, and the check runs when the settings load.

With `ai.decision_model` empty, no request goes to any model and no model metric series appears. A point that has a rule still runs the rule, because the rule needs no model. A point that has no rule behaves as it does today.

### 3. Cuts are data, and the model resolver needs a fit

A cut is data in the repository with the model, the date, the cases, the split and the numbers that gave it (`Thresholds` in `decision_step.py`). The fit follows rule 4 of ADR 0019: two fixed halves, a fit on one and a report on the other, repeated with the halves swapped, a cut for each question and one shared cut, and the report gives both. The record of the split is a file in the repository. A cut in a constant is a guess, and a test refuses it. The parameters of a rule are data in the same way.

### 4. Action bands

| Band | What the workflow does |
| :--- | :--- |
| `continue` | The cheap path, or the path of today. |
| `review` | The costly path runs. |
| `flag` | The costly path runs, and the log names the question for a person. |

Each point defines the three bands in terms of its own action. The catalogue gives them. A case that no resolver answers has no band: the metric labels it `none`.

### 5. Shadow first

A new point starts in `shadow`. Its record is the evidence for a later `on`. A person turns a point on after reading the record and the fit report. The default of every mode is `off`.

### 6. The outcome join

Each decision gets an identifier: the point, the subject (the item or the run) and a sequence number. The registry writes one **decision record** as one structured log line: the identifier, the mode, the resolver, the band, the model, the date of the cuts, the answers, and the digest. The digest is in the record only when it holds counts. A digest of text is in the record as a hash. The workflow writes one **outcome record** with the same identifier when the real result is known: the reviewer found an open defect, the run stopped, the gate refused. A later analysis joins the two by identifier. The join gives labelled cases (`FitCase` of `decision_fit.py`), so the next fit uses real outcomes and the shadow log is the data of the fit. The join is a pure function of two lists of records, so a test runs it offline.

### 7. Observability

One counter, `devops_cli_decision_point_total`, with the labels `point`, `resolver` (`rule`, `model` or `fallback`), `band` (`continue`, `review`, `flag` or `none`) and `mode` (`shadow` or `on`). A point with mode `off` writes nothing. A `fallback` result has the band `none`. A point writes only the resolvers that it has. The possible series of a point are 4 for each mode when it has two resolvers (3 bands, plus `none`), so at most 8 for each point. The catalogue below has 6 points built or planned, so it has at most **48 series**. Only the series of points that run exist. The pilot of the screen alone is 8 series.

This counter replaces `devops_cli_roadmap_decision_step_total` and `devops_cli_roadmap_decision_step_review_total`. The false-clear rate of the screen is no longer a live series: it comes from the join of the decision records with the outcome records. The shadow record of a point is the log line of section 6.

### 8. The benefit is measured for each point

A decision model is not better by nature. A point enters `on` only when its bar is met, and the bar is set before the data. The bar names the loss that is allowed, the saving that must follow, and the cases that give both. It is checked against the oracle: the most that any resolver can save with no loss on the labelled data. A bar above the oracle is not set.

## Configuration

- `ai.decision_model`: the name of the decision model, such as `typesafe/jev-1.14`. Empty (the default) means that no decision model is configured. The model follows the conventions of the other models of `ai`: the gateway serves it by name, and `resolve_pydantic_ai_model` builds it. A name that is not a System One model is refused when the settings load. The setting has a variable, `DEVOPS_CLI_AI_DECISION_MODEL`.
- `roadmap.decisions`: a mapping from a point name to a mode (`off`, `shadow` or `on`). A point that is not in the mapping is `off`. A key that is not the name of a registered point is refused when the settings load, as the ladder refuses a step class that does not exist. The mapping has a variable, `DEVOPS_CLI_ROADMAP_DECISIONS`, which holds a JSON object.

The settings of the pilots go: `roadmap.stage.jev_screen` (the first migration), `roadmap.intake.jev` and `roadmap.stage.jev_completeness` (their migrations). The project is alpha and keeps no shim. `AIConfig` refuses unknown keys, and `RoadmapConfig` ignores them. So the new key `ai.decision_model` must wait for the image that knows it, and the keys `roadmap.decisions` and the old `roadmap.stage.jev_screen` are safe in the live ConfigMap in any order. The pull request that removes a pilot setting states the ConfigMap change and its order.

## The catalogue

Each point has its question set, evidence, baseline rule, label source and success bar written here **before** it is built. The bar of each point is checked against the oracle of its data.

| Point | Resolver chain | Mode now | Status |
| :--- | :--- | :--- | :--- |
| `stage.verify_screen` | model, fallback | `shadow` (live) | Migrates onto the registry first. |
| `intake.proposal` | rule (the type prefix of the title), model, fallback | `shadow` after #4395 | Migrates after #4395 merges. `on` is not allowed: the bar is not met. |
| `implement.extension` | rule, fallback | `on` when #4394 merges | Registered after #4394 merges. No model resolver. |
| `stage_ready.completeness` | model, fallback | `off` | Measured no-go. It stays `off` until its evidence builder is redone. |
| `stage.explore_stop` | model, fallback (a rule is fitted first) | `shadow` only | New. Built in the third item of this design. |
| `stage.tier_route` | rule (the Effort label), model, fallback | `shadow` only | New (#4284). Built later. |
| `defect.route` | not designed | none | Waits for the defect inventory. |

The owner's note named `stage.tier_route` as `implement.tier_route`. Issue #4284 puts the choice before the first plan call of the stage planner, so the name here follows the place.

The new points are ranked by volume, ambiguity and labels.

| Rank | Point | Volume | Ambiguity | Labels |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `stage.explore_stop` | About 7,000 `search_code` calls each week. A plan run makes 33 calls in the middle and 113 at the most. | High. Runs from 40 to 113 calls fill the window of 256,000 tokens. | A tool computes them from the trace and the final plan. |
| 2 | `stage.tier_route` | One for each plan run. | Medium. | The run records give the result of the tier that ran. Only one tier ran for each item, so a label is partial. |
| 3 | `defect.route` | Unknown. | Unknown. | The defect inventory decides. |

### `stage.verify_screen`

- **Questions.** Nine `Noul` questions, one for each type of defect of the verify step (`missing_path`, `false_premise`, `spec_delta_wrong`, `verify_form`, `task_order`, `criterion_dropped`, `ignores_existing_code`, `contrived_test`, `other`).
- **Evidence.** The digest of `stage_jev_screen.digest`: the criteria, the groups, the paths that the repository does not hold, and whether the verify command names a test file of the group.
- **Baseline.** The reviewer always runs. No rule is proven. The tool facts (a missing path) are already in the gates.
- **Bands.** `continue` skips the reviewer. `review` runs it. `flag` runs it and logs the question.
- **Labels.** The golden set (56 cases, 317 labelled defects) for the fit. In the live Service, the outcome record holds the open findings of the reviewer.
- **Bar for `on`.** The oracle of the golden set is 9 of 48 cases (19%), so the bar of ADR 0019 (30% skipped) cannot be met. The new bar: in the live record, at least 30 reviews in the band `continue` with no open serious finding, and the band `continue` holds at least 10% of all reviews. Zero losses in 30 cases means a loss rate under 10% with 95% confidence (the rule of three). A serious finding in the band `continue` sets the count to zero again and the cuts are fitted again.

### `intake.proposal`

- **Questions.** The questions of `intake_jev.py`: `Choice` for the type (asked only when the title gives none) and for the priority, `Score` for Value and Effort, and a `Noul` for each nearest item (a duplicate flag).
- **Evidence.** The title and a cut of the body, and the nearest items by the embedding search. The search is the tool. Jev flags a pair and does not search.
- **Baseline.** The type comes from the title prefix when the title gives one (this rule exists today). The triage model gives the rest.
- **Bands.** `continue` takes the field from Jev. `review` leaves the field to the triage model. `flag` names a possible duplicate for a person.
- **Labels.** The final labels of closed issues, after a person edited them (25 closed issues and 16 duplicate cases are in the repository today).
- **Bar for `on`, for a field.** On the closed items of the shadow record, at least 100 of them, Jev is as accurate as the triage model on that field, and it flags no false duplicate. Today no field except the type meets it. The oracle is the agreement of the triage model with the final labels.

### `implement.extension`

- **Question.** One `Choice`: `extend` or `stop`, asked when the run reaches `step_token_budget`.
- **Evidence.** Counts only: in the last 20 tool calls, the successful edits and the refused commands, the tokens used and the absolute ceiling.
- **Baseline and rule.** Today the run stops at the limit. The rule: extend once by a share of the limit when the last 20 calls hold a successful edit and fewer than 4 refused commands. The numbers belong to #4394.
- **Model.** None. The rule has no error on the 33 labelled checkpoints, so a model has nothing to add.
- **Labels.** Runs that stopped with `limit_reached`, and whether the branch ended in a merged pull request. 16 of the 20 stops of 14 days did.
- **Bar.** The one in #4394. This record only registers the point.

### `stage_ready.completeness`

- **Questions.** One `Noul` for each acceptance criterion: does the change deliver the criterion.
- **Evidence.** Today a long diff is the state, and that is why it failed. The redone builder gives each criterion a short digest from tools: the changed paths, the names of the tests that the diff adds, and the hunks that a tool matched to the criterion.
- **Baseline.** The checks of the pull request, and a person.
- **Bands.** `continue` marks the draft ready. `review` keeps it a draft with one note. `flag` adds the criterion to the note.
- **Labels.** Closed pull requests with the criteria that a person found missing at review.
- **Bar.** At most 10% false holds and a recall of a missing criterion of at least 80%, on at least 30 cases with at least 10 of each label. Today it is 28% and 43%.
- **Status.** The mode stays `off`. The registry refuses `on`. Even `shadow` waits for the redone builder (#4317).

### `stage.explore_stop`

- **Question.** One `Choice` between `explore` and `write`. Two `Noul` questions go with it and are only recorded: `enough_read` and `going_in_circles`.
- **Where.** The stage planner, at fixed checkpoints of the tool-call count: 10, 20, 30, 40, 60, 80 and 100.
- **Evidence.** Counts only, made by the toolbox: the calls so far; the calls since the last new file was read; the files read; the files read twice or more; the searches and the empty searches; the criteria of the issue; the criteria whose key words appear in a file that was read; the paths that the issue names, and how many exist and were read; the share of the window that the context fills and the tokens that remain.
- **Baseline.** The call budget of #4346: the prompt says that the run needs about 30 calls, and from call 40 each tool answer ends with a notice to give the reply. A review run has 40 and 60.
- **Rule first.** The fit tries rules of the digest before the model: the length of a stall, and the coverage of the criteria. If a rule meets the bar, the point gets the rule and no model.
- **Bands.** `continue` keeps exploring (today). `review` adds the notice to write the plan now. `flag` is a disagreement of the rule and the model, and is logged.
- **Label.** At a checkpoint, a run is *settled* when every path of its final plan (the paths that the groups read, change or create) was read already. A call after a settled checkpoint added no path that the plan uses. A tool computes the label from the trace and the final plan. It is a proxy: it does not prove that the plan would have been the same.
- **Bar.** Set before the data. Offline: on the half that was not fitted, at least 90% of the checkpoints that the point sends to `write` are settled, and they would have cut at least 20% of the calls. Live, for `on`: over at least 40 runs with the point on and the 40 runs before, the stage produces no more gate refusals for each plan, and the median of tool calls falls.
- **Data.** The traces that are stored today hold only the token and call count at each request (two traces of #3387). They do not hold the tool, the path or the order. The shadow record is the data. A fit needs at least 100 plan runs with at least 4 checkpoints each, which is about 2 to 3 weeks of the present volume.

### `stage.tier_route`

- **Questions.** The questions of `route_with_jev`: `Choice` between the tiers, `Score` for complexity (0 to 3), `Noul` for high risk, and `Noul` for "the item names concrete files and criteria".
- **Evidence.** Counts and facts: the Effort and Value labels, the criteria count, the paths that the body names and that exist, the scope, the stops of the item before. The body is not the state.
- **Baseline and rule.** The tier of today (one tier for all). The rule: the Effort label.
- **Bands.** `continue` the cheap tier. `review` the strong tier. `flag` a high-risk item, logged.
- **Labels.** The run record: the steps, the repairs, the stop class and the tokens, for the tier that ran. Only one tier runs for each item, so a label says whether the tier that ran was enough, and never whether the other would have been.
- **Bar for `on`.** On at least 100 runs, the cost for each merged item falls by at least 15% with no more stops than the baseline. Shadow only until then.

## What stays generation

- The plan: the summary, the groups, the tasks, the spec delta and every other prose.
- Code edits and repairs, and the tool calls that make them.
- The reasoning and the quotes of a review with tools, and the findings that cite them.
- The text of a pull request, a comment, an issue or a commit.
- The tool-call choices of an agent inside a run, except the one question at a checkpoint (`stage.explore_stop`).

## Migration

Each step is its own item and its own pull request. Each moves one pilot onto the registry, removes the old setting and the old metric, and states the ConfigMap change and its order.

1. The registry and the migration of `stage.verify_screen`.
2. `stage.explore_stop` in shadow, which is new.
3. `intake.proposal`, after the shadow pull request of #4395 merges.
4. `implement.extension`, after #4394 merges.
5. `stage_ready.completeness`, with the redone builder (#4317).
6. `stage.tier_route` (#4284).
7. `defect.route`, only if the defect inventory shows an ambiguity that a rule does not fix.

## Considered Options

- **Leave each pilot as it is.** Rejected. Each has its own setting, metric and log, none has an outcome join, and none keeps a rule ahead of the model.
- **Put the decision model first and the rule as a check.** Rejected. Two pilots (the failure tail and the budget extension) show a rule with no error on the labelled data. A model call costs a request and adds a failure mode.
- **One setting for each pilot.** Rejected. The mapping `roadmap.decisions` adds a point with no new setting, and it validates the names.
- **A metric for each pilot.** Rejected. One counter with a bounded `point` label is 48 series at most.
- **Turn a model on for all points when `ai.decision_model` is set.** Rejected. The benefit is measured for each point. The model name says only that a model exists.
- **Wait for a better Jev.** Rejected, for the reason in ADR 0019.

## Consequences

- A new decision point is one entry of the registry, a fit, a data file and a test. It needs no new setting and no new metric.
- With `ai.decision_model` empty, the Service behaves as it does today.
- A point whose rule meets the bar has no model and costs no request.
- The shadow records are the data of the next fit. A point cannot be turned on without them.
- A point that does not meet its bar stays in `shadow` or `off`, and the record says why. This record does not promise a saving.
