# Design

## Decisions

- **Return each open finding, the placeholder finding too.**: A finding that keeps the plan in draft is a defect that the planner can fix in the plan. A placeholder finding quotes a text of the request, and `criterion_dropped` and `spec_delta_wrong` name a group or a requirement of the plan. One set (`OPEN_TYPES`) and one function (`open_findings`) now decide both the return and the label, so the two can not drift apart again.
- **Reverse the choice of #3448 to keep `criterion_dropped` from the planner.**: That choice saved one planner call for each false finding. Because no job revisits a draft with `plan/needs-fix`, the saving left 5 of 7 plans of one day without a repair. A false finding now costs at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` repair rounds, as a false `missing_path` finding already does.
- **Tell the planner how to fix the two types in the planner prompt.**: The `problem` text (`stage_verify_return`) asks the planner to fix each finding or to show that it is no defect. The planner prompt explained `problem` only as a failed check. It now names the model review, and gives the fix of a `criterion_dropped` finding and of a `spec_delta_wrong` finding with the words of the verifier prompt.
- **Keep the fields of the line `stage review round:`.**: `k8s/README.md` documents the line, and log queries read `returned` and `open`. The two fields are now equal.
- **Add a requirement and do not modify "An evidence-backed finding returns the plan at most twice".**: The new requirement states the open types that return the plan, and does not contradict the five types of the old one. #4851 can then change the count of repair rounds in the old requirement with no second change of the same requirement.

## Rejected alternatives

- **Add only `spec_delta_wrong` and `criterion_dropped` to `RETURN_TYPES`.**: A placeholder finding would still keep the plan in draft with no repair round, and two sets would still decide the return and the label.
- **Return the plan only when a repair round remains, and log `returned=0` on the last round.**: It changes the meaning of a logged field for no gain in this change. #4851 changes the round count and can log an extension.
- **A later job that repairs a draft with `plan/needs-fix`.**: It does not replace this change: a plan should get its repair before the draft opens. #5061 files the step for a plan that is still open after the last round.
