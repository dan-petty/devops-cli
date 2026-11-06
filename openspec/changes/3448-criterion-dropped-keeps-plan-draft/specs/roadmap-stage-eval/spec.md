## ADDED Requirements

### Requirement: The golden set holds a test-only group that delivers its criterion and the same plan without the code
The golden set SHALL hold the merged plan of #3410 as a `good` case, and a reviewed case whose plan is the same plan without the group that adds the field of the case model. The reviewed case SHALL hold one `criterion_dropped` defect with the gate `none` and a `reason`. In both plans the group that adds the case of a move of the stage modules SHALL change only test files and fixture files.

#### Scenario: The replay lists the dropped criterion
- **WHEN** The stage eval replay runs the reviewed case of #3410.
- **THEN** The report lists one `criterion_dropped` defect with the gate `none`, and no gate refuses the plan.

#### Scenario: The good twin passes every gate
- **WHEN** The stage eval replay runs the good case of #3410.
- **THEN** Every gate accepts the plan, and the case is the twin of the reviewed case.

#### Scenario: The two plans differ by one group
- **WHEN** The groups of the two plans are compared.
- **THEN** The reviewed plan holds the groups of the good plan except the group that changes `src/devops_cli/roadmap/stage_eval_cases.py`.

## MODIFIED Requirements

### Requirement: The workflow document defines an acceptable stage score and the baseline
`docs/ROADMAP_WORKFLOW.md` SHALL define an acceptable stage score with a recall threshold of the blocker and major defects, a rule of no finding on the good plans and a share of live plans, and SHALL record the commands of the baseline run, the setting `ai.tasks.stage.model` and the work that waits for the baseline.

#### Scenario: The workflow document states the threshold
- **WHEN** a test reads the stage measurement section of `docs/ROADMAP_WORKFLOW.md`
- **THEN** it holds the recall threshold, the rule for the good plans of the golden set and the share of live plans

#### Scenario: The workflow document names the baseline procedure
- **WHEN** a test reads the stage measurement section
- **THEN** it names `eval stage` with `--no-toolbox`, `eval verify`, `ai.tasks.stage.model` and the parked items #3066 and #3060
