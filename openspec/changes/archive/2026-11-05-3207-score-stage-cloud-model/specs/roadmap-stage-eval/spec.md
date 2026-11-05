# Spec Delta

## MODIFIED Requirements

### Requirement: The live run scores the first reply of the model
`devops roadmap eval stage` SHALL plan each case with the stage planner, the model of the `stage` task or `--model`, and a checkout of the commit of the case. It SHALL judge the first reply with the gates, and print for each scored defect type the cases that have it, how many the model avoided, how many a gate caught, and the rate, with a total. It SHALL show no rate for a type that no gate judges, nor for the gate `kind`. It SHALL store the report as JSON under the data directory.

#### Scenario: A reply with a missing path
- **WHEN** the first reply of the model names a file that the checkout lacks, and the second reply is right
- **THEN** the case is `staged`, the first reply counts as caught by `paths` and not as avoided, and the report file holds the model name and the rows

#### Scenario: A reply that passes
- **WHEN** the first reply of the model passes both gates
- **THEN** the case counts as avoided for each type of its known defects that the live run scores

#### Scenario: The kind gate
- **WHEN** the score is printed
- **THEN** the `kind` row shows its count and no rate, since the client sends a reply that breaks the schema back unseen

#### Scenario: The model breaks the schema twice
- **WHEN** the model breaks the schema of the reply on both tries
- **THEN** the case ends `failed` and counts as neither avoided nor caught

#### Scenario: A model call fails
- **WHEN** the model call fails for a case
- **THEN** the case ends `failed`, counts as not avoided, and the command exits 1 after the other cases

## ADDED Requirements

### Requirement: The live report states the tokens and the spend of the run
The JSON report and the printed score of a live run SHALL state the input tokens and the output tokens of the model calls of the run, and the spend in USD at the hosted price of the model. The spend SHALL be null in the report, and the printed score SHALL say that no price is known, when the price registry holds no price for the model.

#### Scenario: A priced model
- **WHEN** a live run of `claude-sonnet-5-5` ends
- **THEN** the report holds `usage` with the input tokens, the output tokens and a spend equal to the hosted price of those tokens, and the printed score has the line `Tokens: <in> in, <out> out.`

#### Scenario: A model with no price
- **WHEN** a live run of a model that has no price ends
- **THEN** the `spend_usd` of the report is null and the printed score says `Spend: no price for the model.`

### Requirement: The workflow document defines an acceptable stage score and the baseline
`docs/ROADMAP_WORKFLOW.md` SHALL define an acceptable stage score with a recall threshold of the blocker and major defects, a rule of no finding on the good plans and a share of live plans, and SHALL record the commands of the baseline run, the setting `ai.tasks.stage.model` and the work that waits for the baseline.

#### Scenario: The workflow document states the threshold
- **WHEN** a test reads the stage measurement section of `docs/ROADMAP_WORKFLOW.md`
- **THEN** it holds the recall threshold, the rule for the 3 good plans and the share of live plans

#### Scenario: The workflow document names the baseline procedure
- **WHEN** a test reads the stage measurement section
- **THEN** it names `eval stage` with `--no-toolbox`, `eval verify`, `ai.tasks.stage.model` and the parked items #3066 and #3060
