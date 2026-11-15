## MODIFIED Requirements

### Requirement: A retry and a return to New clear the counted spend
The job SHALL clear `implement.spend_counted` in the same write that clears `implement.spend`, at the start of a retry. A return to New SHALL write `implement.spend` with the spend of every step of the item, and SHALL leave `implement.spend_counted` as it is. The roadmap Service report of a Job whose result is `returned` SHALL count the tokens of `implement.spend` less `implement.spend_counted` in the result line, the attempt line and the token counter. It SHALL then clear `implement.spend` and `implement.spend_counted` in the write that records the state of the Job, so the next plan of the item starts with no spend.

#### Scenario: A retry starts the count from zero
- **WHEN** A person retries an item whose record holds `implement.spend_counted`, and the new Job starts.
- **THEN** the record holds no `implement.spend_counted`.

#### Scenario: A return to New keeps the spend for the report
- **WHEN** group 1 of a Staged item passes, the record holds `100` in `implement.spend_counted`, and the step of group 2 ends with a `premise` request and evidence
- **THEN** the record holds `implement.result` equal to `returned`, `implement.spend` with the 3 model requests of the run, and `100` in `implement.spend_counted`

#### Scenario: A return to New clears the count
- **WHEN** the Service reports a Job that returned the item to New, and its record holds 1,000 tokens in `implement.spend` and `400` in `implement.spend_counted`
- **THEN** the result line holds `result=returned` and `tokens=600`, and the record holds no `implement.spend` and no `implement.spend_counted`
