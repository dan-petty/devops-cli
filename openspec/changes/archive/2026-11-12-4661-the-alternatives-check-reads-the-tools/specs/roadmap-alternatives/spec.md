## ADDED Requirements

### Requirement: The check reads the tools in use
Once for a run that checks an item of no skip class, the check SHALL read the SPDX SBOM that the dependency graph of the repository exports, with one request. When the run has a clone, the check SHALL also read the files under `roadmap.alternatives.inventory_paths` of the clone. A dependency graph that is off SHALL give an empty SBOM and no error.

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads no SBOM

#### Scenario: Two items
- **WHEN** the run checks two items of no skip class
- **THEN** it reads the SBOM once

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the `gh` command of the SBOM read and the URL of the deps.dev read, each with its condition

### Requirement: A tool in use gives in-use with no proposal
When no ADR gave `rejected`, the job SHALL give `in-use` to a check whose reply gives `covers` or `partly` for a tool that the inventory holds: the SBOM holds its repository or package, the deployed files name it as a whole word in any case, or the SBOM holds a package that deps.dev links to its GitHub project as the source. The job SHALL ask deps.dev only when the SBOM holds a package. The check SHALL say that the repository already uses the tool.

#### Scenario: A package of the SBOM
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0` and the reply gives `covers` for `https://pypi.org/project/MCP`
- **THEN** the check has the verdict `in-use`, and its comment and its block say "The repository already uses this tool."

#### Scenario: An action with a path
- **WHEN** the SBOM holds `pkg:githubactions/github/codeql-action/init` and the reply gives `covers` for `https://github.com/github/codeql-action`
- **THEN** the check has the verdict `in-use`

#### Scenario: A deployed service
- **WHEN** a file under `k8s` of the clone says `image: ghcr.io/berriai/LiteLLM:main`, a file under `docs` names Velero, and a file under `tf` says `trivyscan`
- **THEN** a reply for `https://github.com/BerriAI/litellm` gives `in-use`, and replies for `velero-io/velero` and `aquasecurity/trivy` keep `covers`

#### Scenario: A package that deps.dev links
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0`, deps.dev links the PyPI package `mcp` to `github.com/modelcontextprotocol/python-sdk`, and the reply gives `covers` for that repository
- **THEN** the check has the verdict `in-use` after one deps.dev read

#### Scenario: An empty SBOM
- **WHEN** the SBOM holds no package and the reply gives `covers` for a tool that the deployed files do not name
- **THEN** the check keeps `covers` and sends no deps.dev request

#### Scenario: The census
- **WHEN** a test replays the 97 `covers` and `partly` checks of the census of 2026-11-11 over the SBOM and the deployed words recorded at its commit
- **THEN** at least 55 of the 58 tools in use give `in-use`

### Requirement: A failed read of deps.dev skips the item
If the read of deps.dev for the tool of a reply fails, the job SHALL skip the item with a named reason, record the failure in its job record and write no check for it.

#### Scenario: deps.dev answers 502
- **WHEN** the SBOM holds a package, the tool of the reply is in no source, and deps.dev answers 502
- **THEN** the run writes no check for the item and records `alternatives.failed_error` `HTTPStatusError`

### Requirement: A check records the canonical id of its tool and the hash of its ADRs
A written check SHALL record `alternatives.tool_id` and `alternatives.adr_hash`. The id SHALL be `github.com/<owner>/<name>` in lower case for the GitHub project of the tool, which a PyPI tool takes from the source URL of its PyPI record, else `pkg:pypi/<name>` with the canonical name of `packaging`, else the tool URL. The hash SHALL cover the ADR entries that the model saw.

#### Scenario: A PyPI package with a source
- **WHEN** the PyPI record of `pydantic-ai-slim` names the `Source` `https://github.com/Pydantic/Pydantic-AI`
- **THEN** the id of the tool is `github.com/pydantic/pydantic-ai`

#### Scenario: A PyPI package with no GitHub source
- **WHEN** the tool is `https://pypi.org/project/Markdown_It.py` and its record names no GitHub project
- **THEN** the id of the tool is `pkg:pypi/markdown-it-py`

#### Scenario: The census
- **WHEN** a test maps the 88 tool strings of the 330 blocks of the census
- **THEN** they give at most 81 ids

#### Scenario: The record
- **WHEN** a run with `--confirm` writes a check of `https://pypi.org/project/gidgethub`, whose source is `gidgethub/gidgethub`
- **THEN** the job record holds the id `github.com/gidgethub/gidgethub` and the hash of the ADRs that the model saw

### Requirement: A change of the ADRs makes a check due
The check SHALL take an item of no skip class whose check is current when its recorded `alternatives.adr_hash` differs from the hash of the ADRs at HEAD, or when its check recorded none, in the order of the items whose check is old. It SHALL NOT take a skip-class item for that reason.

#### Scenario: Another ADR hash
- **WHEN** four items were checked 2 days ago with unchanged bodies: one with the hash at HEAD, one with another hash, one with no hash, and one skip-class item with no hash
- **THEN** the run takes the items with another hash and with no hash, and leaves the other two current

## MODIFIED Requirements

### Requirement: The check reads the ADRs of the repository
The check SHALL list the files of `docs/adr/` on the default branch once for a run, before it selects the items. It SHALL read each file named with four digits, a hyphen and a name that ends with `.md`. From each file it SHALL keep the number, the title, the status paragraphs and the `Considered Options` section. A failed read SHALL stop the run, but a missing directory SHALL NOT.

#### Scenario: A file that is no ADR
- **WHEN** `docs/adr/` holds `README.md` and `0009-third.md`
- **THEN** the check keeps the third ADR only

#### Scenario: An ADR with no options
- **WHEN** an ADR has a title and no `Considered Options` section
- **THEN** the check keeps its number and its title and no options text

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads `docs/adr/` once and makes no model call

#### Scenario: A failed read
- **WHEN** GitHub fails the read of `docs/adr/` with a server error
- **THEN** the run stops with that error and writes no check

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the read of `docs/adr` and the read of each file of it, with the `gh` command of each

### Requirement: The model proposes rejected and the job confirms it
The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or `partly` verdict. The job SHALL give `rejected` when the ADRs that the model saw hold that ADR and only its options that say `rejected` or `not chosen` name the tool. The check SHALL record the tool URL. The comment SHALL keep the tool line with the URL and name the ADR as four digits. The block SHALL name the ADR too.

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

### Requirement: The job drops an in-use flag that the text does not back
The job SHALL NOT give `in-use` from the text of the item when `in_use` is false. If `in_use` is true and the title and the body name no tool of the reply, the job SHALL drop the flag. It SHALL keep the verdict of the reply and write the check, unless the inventory holds the tool.

#### Scenario: The model gives no flag
- **WHEN** the body names the tool, the reply holds no `in_use`, and the inventory does not hold the tool
- **THEN** the check keeps the verdict `covers`

#### Scenario: The text does not name the tool
- **WHEN** the reply holds `in_use` true, the title and the body name no tool of the reply, and the inventory does not hold the tool
- **THEN** the check keeps the verdict `covers`, and refine asks its question
