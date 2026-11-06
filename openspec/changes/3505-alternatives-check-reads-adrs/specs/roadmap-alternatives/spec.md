## ADDED Requirements

### Requirement: The check reads the ADRs of the repository
The check SHALL list the files of `docs/adr/` on the default branch, once for a run. It SHALL do so only when the run checks an item that is no skip class. It SHALL read each file named with four digits, a hyphen and a name that ends with `.md`. From each file it SHALL keep the number, the title, the status paragraphs and the `Considered Options` section. A failed read SHALL stop the run, but a missing directory SHALL NOT.

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

### Requirement: The check leaves out an ADR that a later ADR supersedes
The check SHALL leave out an ADR that a later ADR supersedes in whole. Either ADR can say so in its status. The older one says "ADR 0012 supersedes this ADR." The newer one says "ADR 0012 supersedes ADR 0011." An ADR that a later ADR amends, or supersedes in part, SHALL stay with its status lines.

#### Scenario: The older ADR says so
- **WHEN** ADR 0011 says "ADR 0012 supersedes this ADR." and ADR 0012 holds no such sentence
- **THEN** the check keeps ADR 0012 and leaves out ADR 0011

#### Scenario: The newer ADR says so
- **WHEN** ADR 0013 says "ADR 0013 supersedes ADR 0012." and ADR 0012 holds no such sentence
- **THEN** the check leaves out ADR 0012

#### Scenario: An ADR that a later ADR amends or supersedes in part
- **WHEN** ADR 0003 says that ADR 0017 supersedes its webhook clause, and ADR 0004 says that ADR 0014 amends it
- **THEN** the check keeps both ADRs with their status lines

### Requirement: The request holds the decisions of the ADRs
The request of an item SHALL hold the key `decisions`. For each ADR in force it SHALL hold the number as four digits, the title, the status lines and the options, the highest number first. The text SHALL hold at most `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. The cut SHALL take whole entries, and the job SHALL log a warning that names each ADR that the cut leaves out. A repository with no `docs/adr/` SHALL send no `decisions` key.

#### Scenario: Two ADRs
- **WHEN** the repository holds ADR 0006, ADR 0007, and ADR 0008 that supersedes ADR 0007 and amends ADR 0006
- **THEN** `decisions` holds the entry of ADR 0008, then the entry of ADR 0006, and no entry of ADR 0007
- **AND** the entry of ADR 0008 holds its status lines and its options

#### Scenario: The decisions are cut to the cap
- **WHEN** the entries of the ADRs hold more tokens than `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`
- **THEN** `decisions` holds whole entries only, starts with the ADR of the highest number, and holds no more tokens than the cap
- **AND** a warning names each ADR that the cut leaves out

#### Scenario: A repository with no ADR directory
- **WHEN** the repository has no `docs/adr/`
- **THEN** the request holds no `decisions` key, and the verdict is the one that the reply gives

### Requirement: A text names a tool in a form that says so
A text SHALL name a tool when it holds the full `owner/name` of the repository. It SHALL also name the tool when it holds a name of two words or more as a whole word. A name of one word SHALL name the tool only inside a code span, a link or strong emphasis. The job SHALL test the last segment of the repository or package name, and the `tool_name` of the reply. The test SHALL ignore case, and SHALL take a space, `-`, `_` and `.` as one separator.

#### Scenario: A name of two words
- **WHEN** a text says "the Argo Workflows controller" and the tool is `argoproj/argo-workflows`
- **THEN** the text names the tool

#### Scenario: A name of one word in a form that marks it
- **WHEN** a text says "Run `just` for the build." and the tool is `casey/just`
- **THEN** the text names the tool

#### Scenario: A common word in prose
- **WHEN** a text says "just add it" and the tool is `casey/just`
- **THEN** the text does not name the tool

#### Scenario: The owner and the name
- **WHEN** a text says "Run example/scanner now." and the tool is `example/scanner`
- **THEN** the text names the tool

#### Scenario: The display name of the reply
- **WHEN** a text says "DBOS Transact in-process", the tool is `dbos-inc/dbos-transact-py` and `tool_name` is "DBOS Transact"
- **THEN** the text names the tool

#### Scenario: A longer name
- **WHEN** a text says "add pytest-cov" and the tool is `pytest-dev/pytest`
- **THEN** the text does not name the tool

### Requirement: The model proposes rejected and the job confirms it
The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or `partly` verdict. The job SHALL give the check the verdict `rejected` when two things hold. The ADRs that the model saw hold that ADR. Its title or its options name the tool. The check SHALL record the tool URL. The comment SHALL keep the tool line with the URL and name the ADR as four digits. The block SHALL name the ADR too.

#### Scenario: Temporal and ADR 0008
- **WHEN** ADR 0008 holds the options line "Temporal and Hatchet: rejected." in strong emphasis, and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, its comment holds the tool URL and `ADR 0008`, and its block names `ADR 0008`

#### Scenario: The record
- **WHEN** a run with `--confirm` writes that check
- **THEN** the job record holds the verdict `rejected` and the tool URL
- **AND** the counter `devops_cli_roadmap_alternatives_total` has a point with the `verdict` `rejected`

#### Scenario: The display name of the tool
- **WHEN** ADR 0008 says "DBOS Transact in-process: rejected for now.", the tool is `dbos-inc/dbos-transact-py`, and the reply gives `tool_name` "DBOS Transact" and `adr` 8
- **THEN** the check has the verdict `rejected`

#### Scenario: A rejected tool that the item names
- **WHEN** the job confirms `adr` 8 and the body of the item names the tool too
- **THEN** the check has the verdict `rejected`

### Requirement: The job drops a rejection that it cannot confirm
If the job cannot confirm the ADR of a reply, it SHALL drop the number, keep the verdict of the reply and write the check. It SHALL NOT refuse the reply for that reason. A reply with a verdict that names no tool SHALL keep its verdict.

#### Scenario: An ADR that the repository does not hold
- **WHEN** the reply gives `covers` with `adr` 99 and the repository holds no ADR 0099
- **THEN** the check has the verdict `covers` and no ADR, and refine asks its question

#### Scenario: An ADR that does not name the tool
- **WHEN** the reply gives `adr` 7 for a tool that the title and the options of ADR 0007 do not name
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR that a later ADR supersedes
- **WHEN** the reply gives `adr` 4, and ADR 0005 supersedes ADR 0004
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR that the cut left out
- **WHEN** the cut of `decisions` left out ADR 0008 and the reply gives `adr` 8
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR with a verdict of no tool
- **WHEN** the reply gives the verdict `none` and `adr` 8
- **THEN** the check has the verdict `none`

### Requirement: The model proposes in-use and the job confirms it
The reply MAY hold the key `in_use`. The job SHALL give the check the verdict `in-use` when four things hold. The reply has `in_use` true. Its verdict is `covers` or `partly`. No ADR gave `rejected`. The title or the body of the item names the tool. The job SHALL read the body outside the block of the check and outside the refine section. The check SHALL hold the tool and a line that says that the item already names it.

#### Scenario: The body names the tool
- **WHEN** the reply gives `covers` for `https://github.com/example/scanner` with `in_use` true, and the body says "Run example/scanner on each file."
- **THEN** the check has the verdict `in-use` and records the tool URL

#### Scenario: A partly verdict
- **WHEN** the reply gives `partly` for a tool that the item names, with `in_use` true
- **THEN** the check has the verdict `in-use`

#### Scenario: Only the block of the check names the tool
- **WHEN** the title and the body outside the block name no tool, and the block of an earlier check names `example/scanner`
- **THEN** the check keeps the verdict `covers`

#### Scenario: Only the refine section names the tool
- **WHEN** the body outside the refine section names no tool, and the refine section holds an open question that names the tool
- **THEN** the check keeps the verdict `covers`

#### Scenario: A common word for a name
- **WHEN** the body says "Just add the file." and the tool is `casey/just`
- **THEN** the check keeps the verdict `covers`
- **AND** a body that says "Run `just` for the build." gives the verdict `in-use`

### Requirement: The job drops an in-use flag that the text does not back
The job SHALL NOT give the verdict `in-use` when `in_use` is false. If `in_use` is true and the title and the body name no tool of the reply, the job SHALL drop the flag. It SHALL keep the verdict of the reply and write the check.

#### Scenario: The model gives no flag
- **WHEN** the body names the tool and the reply holds no `in_use`
- **THEN** the check keeps the verdict `covers`

#### Scenario: The text does not name the tool
- **WHEN** the reply holds `in_use` true and the title and the body name no tool of the reply
- **THEN** the check keeps the verdict `covers`, and refine asks its question

### Requirement: The model cannot give a verdict that the job sets
The job SHALL give a reply with the verdict `rejected`, `in-use` or `not-applicable` one more turn. The message SHALL say that the job sets the verdict, and name the keys `adr` and `in_use`. The job SHALL refuse a second reply with one of these verdicts. A refused reply SHALL skip its item with a named reason and write no check for it.

#### Scenario: A natural reply with in-use
- **WHEN** the model first gives the verdict `in-use`, and then gives `covers` with `in_use` true
- **THEN** the check is written with the verdict `in-use`, and the item is not skipped

#### Scenario: A second reply with a verdict of the job
- **WHEN** the model gives the verdict `rejected` twice
- **THEN** the item is skipped with the reason that the job sets that verdict, and no check is written for it
