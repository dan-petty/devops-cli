# Delta for roadmap-alternatives

## MODIFIED Requirements

### Requirement: The model proposes rejected and the job confirms it

The reply MAY hold `adr` naming the ADR rejecting a `covers` or `partly` tool. Unless the tool is the item's own repository, the job SHALL give `rejected` before testing the inventory when an ADR in `decisions` has a non-chosen `Considered Options` title naming the tool as its subject, ignoring link targets, prepositions, methods, and qualifiers. The block SHALL name the ADR and keep the tool URL.

#### Scenario: Temporal and ADR 0008

- **WHEN** ADR 0008 holds the options line "Temporal and Hatchet: rejected." in strong emphasis, and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, and its block holds the tool URL and names `ADR 0008`

#### Scenario: The record

- **WHEN** a run with `--confirm` writes that check
- **THEN** the job record holds the verdict `rejected` and the tool URL
- **AND** the counter `devops_cli_roadmap_alternatives_total` has a point with the `verdict` `rejected`

#### Scenario: The display name of the tool

- **WHEN** ADR 0008 says "DBOS Transact in-process (runner-up): rejected for now.", the tool is `dbos-inc/dbos-transact-py`, and the reply gives `tool_name` "DBOS Transact" and `adr` 8
- **THEN** the check has the verdict `rejected`

#### Scenario: A rejected tool that the item names

- **WHEN** the job confirms `adr` 8 and the body of the item names the tool too
- **THEN** the check has the verdict `rejected`

#### Scenario: An ADR that adopts the tool

- **WHEN** ADR 0010 names OpenSpec in its chosen option and in two options that say "rejected", and the reply gives `covers` for `https://github.com/Fission-AI/OpenSpec` with `adr` 10
- **THEN** the check has the verdict `covers` and no ADR

#### Scenario: An unmarked rejected option

- **WHEN** ADR 0018 has an option that names `google/gvisor` and no chosen or adopted option names it
- **THEN** the check has the verdict `rejected` and names ADR 0018

#### Scenario: The census replay

- **WHEN** the test reads ADR 0018 for gVisor, bubblewrap, and agent-sandbox controller, ADR 0024 for IBM Carbon and GitHub Primer, and ADR 0008 for APScheduler 4
- **THEN** each ADR rejects its tool
- **AND** ADR 0005 gives `False` for `github/codeql`

#### Scenario: A deferred option

- **WHEN** ADR 0018 names `kubernetes-sigs/agent-sandbox` only in an option that it does not measure
- **THEN** ADR 0018 rejects `kubernetes-sigs/agent-sandbox`

## ADDED Requirements

### Requirement: ADR rejection ignores link targets
`rejects()` SHALL ignore Markdown link targets when matching a tool name in an ADR.

#### Scenario: A repository named only in an issue link
- **WHEN** `rejects()` inspects ADR 0014 with `<owner>/devops-cli` and `devops-cli`
- **THEN** `rejects()` returns `False`

### Requirement: Modifiers, prepositional objects, and methods do not reject
`rejects()` SHALL NOT match a bare tool name that only modifies a different head noun, follows a preposition such as `through`, or names the object of a packaging method such as `bundling`.

#### Scenario: A Kubernetes Lease qualifier
- **WHEN** `rejects()` inspects ADR 0021 with `kubernetes/kubernetes` and `kubernetes`
- **THEN** `rejects()` returns `False`

#### Scenario: An instrument after through and a CLI qualifier
- **WHEN** `rejects()` inspects ADR 0006 with `cli/cli` and `gh`
- **THEN** `rejects()` returns `False`

#### Scenario: Bundling CodeQL CLI is a method
- **WHEN** `rejects()` inspects ADR 0005 with `github/codeql` and `CodeQL`
- **THEN** `rejects()` returns `False`

### Requirement: Genuine path rejection precedes inventory while own repository gives in-use
The verdict check SHALL return `in-use` for the item's own repository first, SHALL confirm precise ADR rejections before testing the inventory, and SHALL then test the inventory.

#### Scenario: Own repository is in-use even when an ADR is cited
- **WHEN** `validate_reply` checks an item in `<owner>/devops-cli` with ADR 0014 cited for `https://github.com/<owner>/devops-cli`
- **THEN** the verdict is `in-use`

#### Scenario: Genuine ADR 0018 rejection stays ahead of inventory
- **WHEN** `validate_reply` checks an item with ADR 0018 cited for `bubblewrap` and an inventory containing `bubblewrap`
- **THEN** the verdict is `rejected`
