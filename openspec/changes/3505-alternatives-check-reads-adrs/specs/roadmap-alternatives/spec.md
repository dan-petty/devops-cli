## ADDED Requirements

### Requirement: The check reads the ADRs of the repository
Once for a run, and only when the run checks an item that is no skip class, the check SHALL list the files of `docs/adr/` on the default branch and read each file whose name is four digits, a hyphen and a name that ends with `.md`. From each file it SHALL keep the number, the title of its first level-1 heading and the text of its `Considered Options` section. A failed read other than a missing directory SHALL stop the run with its error and write no check.

#### Scenario: A file that is no ADR
- **WHEN** `docs/adr/` holds `README.md` and `0009-third.md`
- **THEN** the check keeps the third ADR only

#### Scenario: An ADR with no options
- **WHEN** an ADR has a title and no `Considered Options` section
- **THEN** the check keeps its number and its title and no options text

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads no file of `docs/adr/`

#### Scenario: A failed read
- **WHEN** GitHub fails the read of `docs/adr/` with a server error
- **THEN** the run stops with that error and writes no check

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the read of `docs/adr` and the read of each file of it, with the `gh` command of each

### Requirement: The request holds the decisions of the ADRs
The request of an item SHALL hold the key `decisions`: for each ADR its number as four digits, its title and its options, the ADR with the highest number first, cut to `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. When the repository has no `docs/adr/`, the request SHALL hold no `decisions` key.

#### Scenario: Two ADRs
- **WHEN** the repository holds `docs/adr/0007-first.md` and `docs/adr/0008-second.md`, each with a title and a `Considered Options` section, and an item is checked
- **THEN** `decisions` holds `ADR 0008:` and the title of the second ADR with its options, then `ADR 0007:` and the title of the first ADR with its options, in that order

#### Scenario: The decisions are cut to the cap
- **WHEN** the options of the ADRs hold more tokens than `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`
- **THEN** `decisions` holds no more tokens than the cap and starts with the ADR of the highest number

#### Scenario: A repository with no ADR directory
- **WHEN** the repository has no `docs/adr/`
- **THEN** the request holds no `decisions` key, and the verdict is the one that the reply gives

### Requirement: A text names a tool by its name as a whole word
A text SHALL name a tool when it holds the last segment of the tool's name as a whole word: the part after `owner/` for a repository, or the package name for a PyPI package. The test SHALL ignore case, SHALL take a space, `-`, `_` and `.` as one separator, and SHALL NOT take a letter, a digit, `_` or `-` next to the name as the end of a word.

#### Scenario: A name in prose
- **WHEN** a text says "The dashboard shows Grafana panels" and the tool is `grafana/grafana`
- **THEN** the text names the tool

#### Scenario: A name with a hyphen written as words
- **WHEN** a text says "the Argo Workflows controller" and the tool is `argoproj/argo-workflows`
- **THEN** the text names the tool

#### Scenario: A longer name
- **WHEN** a text says "add pytest-cov" and the tool is `pytest-dev/pytest`
- **THEN** the text does not name the tool

#### Scenario: A part of a word
- **WHEN** a text says "the scanners run" and the tool is `example/scanner`
- **THEN** the text does not name the tool

### Requirement: An ADR that rejected the tool gives the verdict rejected
The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or `partly` verdict. When the repository holds that ADR and its title or its options name the tool, the job SHALL give the check the verdict `rejected` and record the tool URL. The comment SHALL keep the tool line with the URL and name the ADR as four digits, and the block SHALL name it too. A reply with a verdict that names no tool SHALL keep its verdict.

#### Scenario: Temporal and ADR 0008
- **WHEN** the repository holds ADR 0008 with the options line "Temporal and Hatchet: rejected." and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, its comment holds the tool URL and `ADR 0008`, and its block names `ADR 0008`

#### Scenario: The record
- **WHEN** a run with `--confirm` writes that check
- **THEN** the job record holds the verdict `rejected` and the tool URL, and the counter `devops_cli_roadmap_alternatives_total` has a point with the `verdict` `rejected`

#### Scenario: An ADR with a verdict of no tool
- **WHEN** the reply gives the verdict `none` and `adr` 8
- **THEN** the check has the verdict `none`

### Requirement: The job refuses a rejection that it cannot confirm
The job SHALL refuse a reply whose `adr` is no ADR of the repository, and a reply whose ADR does not name the tool in its title or its options. The job SHALL refuse the verdicts `rejected` and `in-use` from the model, since only the job sets them. A refused reply SHALL skip its item with a named reason and write no check for it.

#### Scenario: An ADR that the repository does not hold
- **WHEN** the reply gives `adr` 99 and the repository holds no ADR 0099
- **THEN** the item is skipped with a named reason and no check is written for it

#### Scenario: An ADR that does not name the tool
- **WHEN** the reply gives `adr` 7 for a tool that the title and the options of ADR 0007 do not name
- **THEN** the item is skipped with a named reason and no check is written for it

#### Scenario: A verdict that only the job sets
- **WHEN** the reply gives the verdict `rejected` or `in-use`
- **THEN** the item is skipped with the reason that the job sets that verdict, and no check is written for it

### Requirement: An item that names the tool gives the verdict in-use
When the verdict of a reply is `covers` or `partly`, no ADR rejected the tool, and the title or the body of the item names the tool, the job SHALL give the check the verdict `in-use`, with the tool in the record, the comment and the block, and a line that says that the item already names the tool. The job SHALL read the body outside the block of the check and outside the refine section. An item that names no tool of the reply, and that no ADR rejected, SHALL keep the verdict of the reply.

#### Scenario: The body names the tool
- **WHEN** the reply gives `covers` for `https://github.com/example/scanner` and the body of the item says "Run example/scanner on each file."
- **THEN** the check has the verdict `in-use` and records the tool URL

#### Scenario: Only the block of the check names the tool
- **WHEN** the title and the body outside the block name no tool, and the block of an earlier check names `scanner`
- **THEN** the check keeps the verdict `covers`

#### Scenario: Only the refine section names the tool
- **WHEN** the body outside the refine section names no tool, and the refine section holds an open question that names `scanner`
- **THEN** the check keeps the verdict `covers`

#### Scenario: Nothing names the tool
- **WHEN** no ADR rejected the tool and the item names no tool of the reply
- **THEN** the check keeps the verdict `covers`

#### Scenario: A rejected tool that the item names
- **WHEN** the reply gives `adr` 8 that names the tool, and the body of the item names it too
- **THEN** the check has the verdict `rejected`

#### Scenario: A partly verdict
- **WHEN** the reply gives `partly` for a tool that the item names
- **THEN** the check has the verdict `in-use`
