## MODIFIED Requirements

### Requirement: The check reads the ADRs of the repository
The check SHALL list the files of `docs/adr/` on the default branch once for a run, before it selects the items. It SHALL read each file named with four digits, a hyphen and a name that ends with `.md`, and keep its number, its title, its front matter and its `Considered Options` section. It SHALL read the status from the front matter, never from prose. A failed read or a front matter that does not validate SHALL stop the run, but a missing directory SHALL NOT.

#### Scenario: A file that is no ADR
- **WHEN** `docs/adr/` holds `README.md` and `0009-third.md`
- **THEN** the check keeps the third ADR only

#### Scenario: An ADR with no options
- **WHEN** an ADR has a title and no `Considered Options` section
- **THEN** the check keeps its number and its title and no options text

#### Scenario: A front matter that is not valid
- **WHEN** the front matter of `docs/adr/0011-old.md` holds an unknown key, an unknown status, or a record number that is not a quoted string of four digits
- **THEN** the read stops with an error that names `docs/adr/0011-old.md`

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads `docs/adr/` once and makes no model call

#### Scenario: A failed read
- **WHEN** GitHub fails the read of `docs/adr/` with a server error
- **THEN** the run stops with that error and writes no check

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the read of `docs/adr` and the read of each file of it, with the `gh` command of each

### Requirement: The check leaves out an ADR that a later ADR supersedes
The check SHALL keep only the ADRs in force: an ADR whose `status` is `accepted`, or that has no status, whose `superseded-by` is empty and whose number no `supersedes` of another ADR names. Either ADR of a supersession can say so in its front matter. An ADR that another ADR amends SHALL stay.

#### Scenario: The older ADR says so
- **WHEN** ADR 0001 has `superseded-by: ["0002"]` and ADR 0002 has no `supersedes`
- **THEN** the check keeps ADR 0002 and leaves out ADR 0001

#### Scenario: The newer ADR says so
- **WHEN** ADR 0005 has `supersedes: ["0004"]` and ADR 0004 has no `superseded-by`
- **THEN** the check leaves out ADR 0004

#### Scenario: An ADR that is not accepted
- **WHEN** ADRs have the status `proposed`, `rejected`, `deprecated` and `superseded`, an ADR has `status: accepted` and an ADR has no front matter
- **THEN** the check keeps the accepted ADR and the ADR with no front matter only

#### Scenario: An ADR that a later ADR amends or supersedes in part
- **WHEN** ADR 0004 has `amended-by: ["0014"]`, the link of an amendment or of a supersession in part, and ADR 0014 has `amends: ["0004"]`
- **THEN** the check keeps both ADRs, and the entry of ADR 0004 names ADR 0014

### Requirement: The request holds the decisions of the ADRs
The request of an item SHALL hold the key `decisions`. For each ADR in force it SHALL hold the number as four digits, the title, a line `Amended by` with each ADR of its `amended-by`, and the options, the highest number first. The text SHALL hold at most `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. The cut SHALL take whole entries, and the job SHALL log a warning that names each ADR that the cut leaves out. A repository with no `docs/adr/` SHALL send no `decisions` key.

#### Scenario: Two ADRs
- **WHEN** the repository holds ADR 0006 with `amended-by: ["0008"]`, ADR 0007, and ADR 0008 with `supersedes: ["0007"]` and `amends: ["0006"]`
- **THEN** `decisions` holds the entry of ADR 0008, then the entry of ADR 0006, and no entry of ADR 0007
- **AND** the entry of ADR 0006 holds the line `Amended by ADR 0008.` and its options

#### Scenario: The decisions are cut to the cap
- **WHEN** the entries of the ADRs hold more tokens than `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`
- **THEN** `decisions` holds whole entries only, starts with the ADR of the highest number, and holds no more tokens than the cap
- **AND** a warning names each ADR that the cut leaves out

#### Scenario: A repository with no ADR directory
- **WHEN** the repository has no `docs/adr/`
- **THEN** the request holds no `decisions` key, and the verdict is the one that the reply gives
