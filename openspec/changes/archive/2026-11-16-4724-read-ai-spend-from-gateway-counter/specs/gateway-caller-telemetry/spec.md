## MODIFIED Requirements

### Requirement: The dashboard shows the gateway's attempts, callers and coverage
The AI spend dashboard SHALL hold Gateway Attempts by Status (the gateway's chat and embedding requests by `status_code`), Gateway Requests and Tokens by Caller (its replied requests and its tokens by `end_user`), and Spend Coverage: devops-cli of gateway (devops-cli's gateway spend over the gateway's total spend, as a stat in percent).

#### Scenario: The gateway row
- **WHEN** the three panels are read
- **THEN** the attempts group by `status_code` and match no status, the caller panel's two queries group by `end_user`, and the coverage stat divides devops-cli's `provider="gateway"` spend by the gateway's spend, in `percentunit`
