## MODIFIED Requirements

### Requirement: The model proposes rejected and the job confirms it

The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or
`partly` verdict. The job SHALL give `rejected` when the ADRs that the model saw hold that ADR, an
option of its `Considered Options` list names the tool, and no chosen or adopted option names it.
The check SHALL record the tool URL. The comment SHALL keep the tool line with the URL and name the
ADR as four digits. The block SHALL name the ADR too.

#### Scenario: Temporal and ADR 0008

- **WHEN** ADR 0008 holds the options line "Temporal and Hatchet: rejected." in strong emphasis, and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, its comment holds the tool URL and `ADR 0008`, and its block names `ADR 0008`

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

- **WHEN** the test reads ADR 0018 for gVisor and bubblewrap, ADR 0008 for APScheduler and ADR 0005
  for `github/codeql`
- **THEN** each ADR rejects its tool

#### Scenario: A deferred option

- **WHEN** ADR 0018 names `kubernetes-sigs/agent-sandbox` only in an option that it does not measure
- **THEN** ADR 0018 rejects `kubernetes-sigs/agent-sandbox`

## ADDED Requirements

### Requirement: A chosen option wins over a not-chosen phrase

A chosen or adopted option that names the tool SHALL win over a `not chosen` or `not adopted`
phrase in the same option, so the ADR rejects no tool that it adopted.

#### Scenario: An option holds both markers

- **WHEN** an option names a tool and holds both `chosen` and `not chosen`
- **THEN** the job confirms no rejection of that tool
