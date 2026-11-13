## MODIFIED Requirements

### Requirement: The Service runs the step as the row fix_plan in its mode
The model lane SHALL hold the row `fix_plan` after `retitle`. The row SHALL need a clone and be due on a first run. The setting `roadmap.fix_plan.mode` SHALL be `off`, `plan` or `on`, with `plan` as the default. Mode `off` SHALL send no request. Mode `plan` SHALL select and log the pull request, and SHALL make no model call and no write. Mode `on` SHALL run the attempt.

#### Scenario: The place of the row
- **WHEN** a test reads the rows of the model lane
- **THEN** `fix_plan` follows `retitle`, needs a clone and is due on a first run

#### Scenario: Mode plan
- **WHEN** the row runs in mode `plan` and a plan pull request qualifies
- **THEN** the row makes no model call and no write
