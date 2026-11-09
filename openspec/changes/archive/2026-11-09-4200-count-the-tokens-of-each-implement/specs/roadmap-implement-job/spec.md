## MODIFIED Requirements

### Requirement: Token counter
The roadmap Service SHALL increment `devops_cli_service_implement_tokens_total` with the labels `repo` and `item_class` by the tokens that the reported runner Job spent. The job record holds the spend of all Jobs of the item, so the Service SHALL keep the token total that it has counted in the job record key `implement.spend_counted`, SHALL add only the difference between the spend and that total, and SHALL write the new total in the same write that records the state of the Job. A spend below the counted total SHALL count whole once and become the counted total. A record with no `implement.spend_counted` SHALL count its whole spend once.

#### Scenario: Tokens add to the counter
- **WHEN** A reported runner Job for repository `owner/repo` and item class `feat` records 1,000 tokens.
- **THEN** The series `devops_cli_service_implement_tokens_total{repo="owner/repo",item_class="feat"}` increases by 1,000.

#### Scenario: A second Job counts only its own tokens
- **WHEN** The record of an item holds 1,500 tokens when its first Job is reported, and 4,000 tokens (the sum of both Jobs) when its second Job is reported.
- **THEN** The series increases by 1,500 at the first report and by 2,500 at the second, and `implement.spend_counted` holds `1500` and then `4000`.

#### Scenario: A spend below the counted total counts whole
- **WHEN** The record holds 900 tokens in `implement.spend` and `1500` in `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 900 and `implement.spend_counted` holds `900`.

#### Scenario: A record of an older version counts its spend once
- **WHEN** The record holds 1,500 tokens in `implement.spend` and no `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 1,500 and `implement.spend_counted` holds `1500`.

#### Scenario: A Job that spent nothing adds nothing
- **WHEN** The record holds 1,500 tokens in both `implement.spend` and `implement.spend_counted` when a Job is reported.
- **THEN** The series does not increase.

## ADDED Requirements

### Requirement: A retry and a return to New clear the counted spend
The job SHALL clear `implement.spend_counted` in the same write that clears `implement.spend`, at the start of a retry and at a return to New.

#### Scenario: A retry starts the count from zero
- **WHEN** A person retries an item whose record holds `implement.spend_counted`, and the new Job starts.
- **THEN** the record holds no `implement.spend_counted`.

#### Scenario: A return to New clears the count
- **WHEN** The job returns an item to New and its record holds `implement.spend_counted`.
- **THEN** the record holds no `implement.spend_counted`.
