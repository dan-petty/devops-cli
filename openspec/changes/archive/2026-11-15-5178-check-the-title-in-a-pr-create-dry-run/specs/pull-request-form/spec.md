## ADDED Requirements

### Requirement: A dry run checks the scope against the checkout labels
`devops pr create --dry-run` SHALL read `.github/labels.yml` of the checkout when `--repo` names no other repository, and SHALL refuse a title whose scope has no label as the real run refuses it. A dry run with `--repo` names the labels read in its plan and opens nothing. Its heading SHALL say that it would open the pull request.

#### Scenario: A scope with no label in the checkout
- **WHEN** the checkout labels file declares no `scope/devops` and the title is `feat(devops): a change`
- **THEN** the dry run exits 1 and prints the same refusal as the real run

#### Scenario: The heading
- **WHEN** the dry run passes
- **THEN** the output holds "Would open a draft pull request" and no "Opened a draft pull request"

#### Scenario: Another repository
- **WHEN** the command runs with `--repo owner/repo`
- **THEN** the plan lists the request that reads `.github/labels.yml`, and the dry run opens nothing
