# Design

## Decisions

- **Put the rule in `_rejected_problems` beside `_security_problems` and call it from `content_problems`.**: The stage job and the replay both reach `content_problems` through `check_proposal`, so one rule set judges the job and the golden set.
- **Require a rejected alternative only when the plan holds a decision.**: A plan with no decision states no chosen design, so it has no alternative to reject, and every gate must accept each good plan of the golden set.
- **Accept a path and line, a quoted command output or a number as one fact.**: The issue records the HTTP 422 of #3171 as the fact that showed a wrong design, and a path and line does not carry that fact.
- **Keep the heading `## Rejected alternatives`.**: `_design_file` of `src/devops_cli/roadmap/stage/stage_change.py` writes that part from `proposal.rejected`, so a second name would judge no plan and change every rendered design.
- **Put the new tests in `tests/roadmap/stage/test_roadmap_stage_alternatives.py`.**: The folder mirrors `src/devops_cli/roadmap/stage/`, and `tests/roadmap/stage/test_roadmap_stage_security.py` holds the same shape for the security rule.
- **Add the new case to half A of `tests/fixtures/roadmap_eval/stage/split.json`.**: Half A holds 29 cases and half B holds 30 at the staged commit, so half A keeps the two halves even.
- **Record the case as a plan for #2877 with a decision and no rejected alternative, with the null commits.**: The tree holds no reply of the plan of pull request 3168 before its repair, and the #3247 case records a plan that no merge made as that plan.
- **Add no entry to `src/devops_cli/roadmap/stage/stage_finding_classes.json` for the two new messages.**: `tests/roadmap/stage/test_roadmap_stage_findings.py:207:assert finding_classes(_plans()) == load_finding_classes()` recomputes that seed from the saved refused replies, so a hand entry fails it.
- **Put the replay task in group 1, which changes the stage check.**: `STAGE_EVAL_TRIGGER_PATHS` holds `src/devops_cli/roadmap/stage/stage_change.py`, and one replay task in one group satisfies the rule for the whole plan.
- **Write the dependency entry as `Pull request #5489 changes ...` and not as `#5489: ...`.**: `issue_dependencies` reads a leading `#<number>:` as an issue that must be delivered first and would read pull request 5489 on GitHub, and the entry holds the number and the shared path where `_overlap_problems` looks.

## Rejected alternatives

- **Accept any non-empty sentence as the evidence of an alternative.**: The plan fixes of 2026-11-02 found 3 plans whose alternatives gave no fact, so an opinion passes today and the defect of #3257 stays.
- **Accept only a path and line as a fact.**: The issue records the HTTP 422 of page 300 in #3171, which is a number and no path, so the rule would refuse a true fact.
- **Require a rejected alternative for every plan, even one with no decision.**: `tests/fixtures/roadmap_eval/stage/good-2739-the-subprocess-environment-guard-accepts-gh` is a good case of the golden set, and every gate must accept a good plan.
- **Rename the part to `## Alternatives`.**: `_design_file` of `src/devops_cli/roadmap/stage/stage_change.py` writes `## Rejected alternatives`, so a rename would change every rendered design and judge no plan.
- **Add the two new messages to `src/devops_cli/roadmap/stage/stage_finding_classes.json` by hand.**: `tests/roadmap/stage/test_roadmap_stage_findings.py:207:assert finding_classes(_plans()) == load_finding_classes()` holds the seed to the saved refused replies, so a hand entry fails the test.
- **Start the dependency entry with `#5489:` so that the overlap is named first.**: `issue_dependencies` matches `^#(?P<number>[0-9]+):` and returns the number, so `plan_check` would read pull request 5489 as an open issue dependency and report a problem.
