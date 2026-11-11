## ADDED Requirements

### Requirement: A left-out item counts and logs its reason
A stage round SHALL count a skipped item in `devops_cli_roadmap_stage_total` with the label `reason`, a bounded kind of the rule that left it out, such as `title_type`, `held`, `returned` or `rejected`, and `none` for another result. The Service SHALL log the kind and the text of the reason of a left-out item once, and again only when its kind changes.

#### Scenario: Each result carries a reason label
- **WHEN** a round leaves one item out for its title type, stages one, returns one and finds one rejected
- **THEN** the counter has one point each for `title_type`, `returned` and `rejected` under `skipped`, and one for `none` under `staged`

#### Scenario: A reason logs once until it changes
- **WHEN** three rounds leave one item out, the first two for its title type and the third for the label `needs-split`
- **THEN** each round counts the item, and two log lines name the item, one with `title_type` and one with `needs_split`
