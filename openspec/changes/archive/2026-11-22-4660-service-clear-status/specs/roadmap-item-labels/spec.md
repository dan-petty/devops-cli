## MODIFIED Requirements

### Requirement: A closed issue holds no Status and no Owner label
Each round of the row `implement` of the Service SHALL remove every `status/*` label and every `owner/*` label of each closed issue of its repository, with one label removal request for each label, and SHALL remove no other label. The trigger of an `issues.closed` delivery SHALL make the row due. The row SHALL read the issue again before it removes a label, and SHALL keep the labels of an issue that is open at that read. No file in the repository SHALL be needed for the removal.

#### Scenario: An issues.closed delivery
- **WHEN** the row `implement` succeeded 1 minute ago, and a round runs for the trigger `("webhook", "issues", "closed")` of a closed issue that holds `status/ready`
- **THEN** the row runs, and it sends exactly one label removal request, for `status/ready`

#### Scenario: A merge closes an issue
- **WHEN** a round runs with a closed issue that holds `status/in-review`, `owner/agent` and `type/bug`
- **THEN** the round sends one label removal request for `status/in-review` and one for `owner/agent`, and the issue keeps `type/bug`

#### Scenario: A closed issue with two status labels
- **WHEN** a round runs with a closed issue that holds `status/ready`, `status/in-review` and `priority/p2-medium`
- **THEN** the round sends exactly two label removal requests, for `status/ready` and `status/in-review`

#### Scenario: A closed issue with no managed label
- **WHEN** a round runs with a closed issue that holds only `priority/p2-medium`
- **THEN** the round sends no label removal request

#### Scenario: A label that no delivery removed
- **WHEN** a round runs with no trigger, and a closed issue holds `owner/agent`
- **THEN** the issue loses `owner/agent`, and the next round sends no label removal request

#### Scenario: A person reopens the issue after the listing
- **WHEN** the listing of the round shows a closed issue with `status/ready`, and a person reopens the issue before the removal
- **THEN** the issue keeps `status/ready`
