## MODIFIED Requirements

### Requirement: The probes are bounded and read-only
The probes of one item SHALL run at most 10 git commands. When the issue cites more items than the bound allows, the probe SHALL stop at the bound and list the items it did not probe. The probe SHALL list an identifier as not probed when its definition lookup is undecided, as when only files of other languages name it and one command is left. Every probe command SHALL be `git cat-file`, `git grep` or `git log`, and no probe SHALL change the checkout.

#### Scenario: The bound stops the probes
- **WHEN** the issue cites 12 paths that the commit holds
- **THEN** the probe runs 10 commands and `probes` lists 2 paths as not probed

#### Scenario: The bound leaves a Rust function undecided
- **WHEN** the issue cites 9 paths that the commit holds and then a function that only a Rust file of the commit defines
- **THEN** the probe runs 10 commands, lists the function as not probed, and does not say that it has no definition

#### Scenario: A cut read leaves a Rust function undecided
- **WHEN** 21 Rust files call `shared_helper`, and only `src/z_util.rs`, which is after them in path order, defines it
- **THEN** the probe lists `shared_helper` as not probed and does not say that it has no definition

#### Scenario: Only reading commands
- **WHEN** the probe runs for an issue that cites a missing path, a missing identifier and a present path
- **THEN** every command it ran is `cat-file`, `grep` or `log`, and `git status --porcelain` of the checkout is empty
