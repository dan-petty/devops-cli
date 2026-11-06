# Design

## Decisions

- **Reuse the type `criterion_dropped` and add it to `OPEN_TYPES`.**: The enum, the prompt, the schema and the golden set already hold the type, so the change adds no ninth or tenth type.
- **Keep the quote rule of `open_findings`.**: A `criterion_dropped` finding is open only when `VerificationInput.contains` finds its quote in the input. A finding with no such quote stays advice, as the rule of #3264 says for every type.
- **Do not add `criterion_dropped` to `RETURN_TYPES`.**: The finding keeps the plan in draft and sends nothing back to the planner, so a false finding costs one label and no second planner call.
- **Remove `criterion_dropped` from the open types of the review of refine.**: `JUDGE_OPEN_TYPES` is `OPEN_TYPES` without the types about task groups. A proposal of refine holds no task group, so a `criterion_dropped` finding on it stays advice, as it does today. The living spec of `roadmap-refine` already lists the open types of that review without it.
- **Judge a test-only group in the prompt, not in code.**: Whether a group delivers its criterion depends on the groups before it, and a model reads that with the plan. The prompt says that a test-only group delivers its criterion when an earlier group changes the code that it needs.
- **Write a MODIFIED requirement for the open finding.**: The requirement "An open finding keeps the plan in draft" exists in `openspec/specs/roadmap-stage/spec.md`, and the change of #3039 that rewrote it is archived. The delta holds the full text of the requirement with `criterion_dropped` in its type list, so that the living spec names no second rule for the same finding.
- **Hold the pair in the golden set as one reviewed case and its good twin.**: The good case is the merged plan of #3410. The reviewed case is the same plan without group 3, so the two plans differ by the one group that gives the group of the case its code.
- **Remove the counts of the good plans and of the cases from the workflow document.**: A count was wrong after each new case. The invariant test reads the words and not the number, and the cost of a run is the cost of one case times the number of cases.

## Rejected alternatives

- **Report the finding as `spec_delta_wrong`.**: A correct spec delta can sit beside a group that delivers nothing. The spec delta of the plan of #3410 is correct, and the type would send the planner to the wrong part.
- **Add a new blocking type.**: A new type changes the schema, the prompt, the spec, the nine-type test and the golden set, and it duplicates `criterion_dropped`.
- **Flag each group that changes only test files in code.**: The group that adds the case of a move of the stage modules in the plan of #3410 changes only fixture files and a test file, and it delivers its criterion. A code rule refuses the good case that this change keeps good.
- **Open a finding with no quote.**: A finding with no quote shows no text of the input, so a person cannot check it. The rule of #3264 keeps it as advice.
- **Use the example of the issue as the bad case.**: The merged plan of #3410 is correct, and its recorded case has the field that the replay needs. The bad case removes the group that adds the field.
