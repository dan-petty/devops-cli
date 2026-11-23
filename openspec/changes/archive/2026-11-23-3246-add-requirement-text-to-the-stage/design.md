# Design

## Decisions

- **Select the requirement text in `stage_specs.py`, beside `read_spec`.**: The module already holds the base spec of each capability, so the planner, the review and its replay share one read and one selection.
- **Append the section to the context in `_Planner._request`, after the `### Registry places` section.**: `collect_context` is shared with the refine round, so a stage-only section stays out of the refine request.
- **Keep the two bounds as module constants with a docstring each, the count applied before the characters.**: The issue gives 12 requirements and 6000 characters, and a fixed count and then a fixed length are easy to assert offline.
- **Fill the `requirements` field of the review input in `VerificationInput.of` from the base specs of the checkout.**: The payload, `request_texts` and the quote check already decide what the review reads, and the stage job and the replay then compute the same text from the same specs.
- **Deliver the replay case of #3225 as a golden-set case that the review replays through `evaluate_cases`.**: `matched_defects` scores the findings of a case, and `open_findings` keeps a finding only when the request holds its quote, so the case shows the conflict offline once the requirement text is in the request.
- **Write every required field of the case defect: `type`, `severity`, `where`, `problem`, `evidence` and `gate`, with `reason` for the gate `none`.**: `Defect` forbids an extra key and requires `where` and `problem`, and `_read_case` raises on a case that omits one, so a short defect record would fail both the case test and the count test.
- **Run the replay test of group 6 on the sample repository, whose spec the test commits with `track`.**: No test of this repository checks out a commit of it, and `track` puts a spec at the head of the sample clone, so the replay reads a base spec offline.
- **Keep the case files in a `manifest` group and the pull registration in a separate `other` group.**: A `manifest` group verifies one case path of its own, and `EVALUATED_PULLS` lives in another test module, so one group cannot run both paths.
- **Keep `_duplicate_problems` on names.**: Its callers pass names, and a change to text would break the duplicate-name check and each caller.

## Rejected alternatives

- **Record only the pull, the commits and the defect in `case.json`.**: `src/devops_cli/roadmap/stage/stage_eval_cases.py:class StageCase` requires `title`, `change`, `scores` and `summary`, and `_read_case` refuses a case that lacks one.
- **Record the case defect with its type, severity, gate and evidence only.**: `src/devops_cli/roadmap/stage/stage_eval_cases.py:class Defect` also requires `where` and `problem`, and `_read_case` refuses a case whose defect lacks one.
- **Write a new module that parses the markdown of each spec.**: `src/devops_cli/roadmap/stage/stage_specs.py:def read_spec` already reads the purpose, the names and the statement of each requirement, and a second parse would copy it.
- **Bound the text by a token count.**: A character count needs no tokenizer and a test asserts it, while a token count changes with the tokenizer version.
- **Remove the read-spec tool and rely on the context.**: `docs/roadmap/stage.md` names the tool for the requirements outside the bound, and the bound leaves requirements out.
- **Replay the review of #3225 against GitHub instead of a golden-set case.**: That replay needs the network and the pull request of a closed item, while a golden-set case runs offline and gives the same answer on each run.
- **Change `_duplicate_problems` to compare requirement text.**: `src/devops_cli/roadmap/stage/stage_change.py:def _duplicate_problems` takes names from several callers, and a text comparison would break the duplicate-name check.
- **Give the `manifest` group of the case a verify that runs two test modules.**: A `manifest` group verifies one path of its own, so the count test of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` runs in the `other` group that registers the pull.
