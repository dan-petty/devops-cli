## ADDED Requirements

### Requirement: A labelled set holds the cases of the Jev completeness check
The folder `tests/fixtures/roadmap_eval/completeness/` SHALL hold at least 30 cases with at least 10 of each label, `complete` and `incomplete`. A case SHALL hold `case.json` (label, kind, criteria, source) and `draft.diff`. An incomplete case SHALL be a plan with a dropped criterion, or a complete diff from which one hunk is removed and named in `removed`.

#### Scenario: The set loads
- **WHEN** the committed set is loaded
- **THEN** it holds at least 30 cases with at least 10 of each label, and the diff of each case fits `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`

#### Scenario: A removed-hunk case
- **WHEN** a case names a removed hunk
- **THEN** the diff of its complete twin holds the hunk and the diff of the case does not

### Requirement: The command scores the check and decides on the switch
`devops roadmap eval completeness` SHALL send one request to Jev for each case and print the recall of the incomplete drafts, the false holds, and the spend. It SHALL store a JSON report with the probability of each criterion. It SHALL say that the switch stays off when the false holds exceed `CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE` or the set is too small. With `--dry-run` it SHALL send no request.

#### Scenario: A run
- **WHEN** the command runs on a set with Jev answering
- **THEN** it sends one request for each case, prints the recall and the false holds, and stores the report

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it lists the requests and sends none
