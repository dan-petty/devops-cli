# roadmap-stage/premise Specification

## Purpose
The premise probes that the stage job runs at the staging commit, and the Feasibility section that quotes them: bare names, cited fields and the preconditions of a called function.

## Requirements

### Requirement: The job probes the premise at the staging commit
Before the model call, the stage job SHALL probe each path and each identifier that the issue cites at the staging commit, and SHALL put the probe text in the model input under the key `probes`. The job SHALL take the cited items from the same extraction as the context of the model. A missing path SHALL be probed for the commit that deleted or renamed it, and an identifier with no definition for the commit that last added or removed its text.

#### Scenario: Probe output is in the model input
- **WHEN** the job plans an issue that cites a file of the staging commit and a function that the commit defines
- **THEN** the model input holds `probes` with a line that says the file is present and a line that names the definition of the function

#### Scenario: A removed identifier names its removal commit
- **WHEN** the issue cites `validate_url`, which a commit removed from the history before the staging commit
- **THEN** `probes` says that the identifier has no definition and names that commit

#### Scenario: A removed path names its removal commit
- **WHEN** the issue cites a path that a commit deleted
- **THEN** `probes` says that the path is missing and names the commit that deleted it

#### Scenario: A thing that never existed
- **WHEN** the issue cites a path that no commit ever held
- **THEN** `probes` says that the path is missing and that no commit in the history deleted or renamed it

#### Scenario: A backtick text that is no path and no identifier
- **WHEN** the issue holds the backtick texts `git log -S x`, `owner/repo` and the number 0.41
- **THEN** `probes` holds no line for any of them

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

### Requirement: The prompt asks feasibility to quote the probes
The prompt of the stage job SHALL tell the model that `probes` holds the result of read-only commands at the staging commit, SHALL ask `feasibility` to quote the lines of `probes` that confirm the premise, and SHALL tell the model that the reply has no key to report a false premise: when the issue cannot be built as written, `feasibility` says so with the evidence and the plan holds no code that compensates for it.

#### Scenario: The prompt names the probes
- **WHEN** the stage prompt loads
- **THEN** it names `probes`, asks `feasibility` to quote the probes, and does not name `premise_failed` as a key to set

### Requirement: Feasibility quotes a probe line
When `probes` is not empty, the stage job SHALL refuse a `feasibility` list that holds no line of `probes` word for word.

#### Scenario: No quoted probe
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns a problem that names `feasibility` and the quote rule.

#### Scenario: Exact probe quote
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The probe shows def f(): pass.`
- **THEN** `check_proposal` returns no quote problem.

#### Scenario: A job that read no probe is not judged
- **WHEN** `probes` is empty and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns no quote problem.

### Requirement: The probe names the files of a cited bare name
When a cited path is no file at the root of the staging commit and the staged tree holds files with the same name under a folder, the stage probe SHALL name those files and give the existing file as the candidate.

#### Scenario: Cited bare name with a file under a folder
- **WHEN** The issue cites `stage_specs.py`, the staging commit holds no root `stage_specs.py`, and `src/devops_cli/roadmap/stage/stage_specs.py` is a file of the commit.
- **THEN** The probe line for `stage_specs.py` says the path is no file at the root of the staging commit, names `src/devops_cli/roadmap/stage/stage_specs.py` as the candidate, and lists `stage_specs.py` in `missing`.

#### Scenario: Cited root file lists no same-name file
- **WHEN** The issue cites `README.md` and the staging commit holds `README.md` at the root.
- **THEN** The probe reports `README.md` as a file of the staging commit and lists no other file.

#### Scenario: Missing path with no same-name file keeps its line
- **WHEN** The issue cites `src/devops_cli/never.py`, the staging commit holds no such file, and no file of the commit has the name `never.py`.
- **THEN** The probe reports the path as no file of the staging commit and names no candidate.

#### Scenario: Same-name files stay bounded
- **WHEN** Six files of the staged tree carry the name of the cited path and the root holds none of them.
- **THEN** The probe names at most five of them, in sorted order.

### Requirement: The stage prompt names a sample file by a bare name
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL tell the planner to write a sample file that a test writes at run time, and that no group creates, as a bare name with no folder.

#### Scenario: The prompt holds the bare-name rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text names `test_sample.py` as a bare name and says that a name with a folder is read as a path of the repository

### Requirement: The prompt asks for the preconditions of a called function
The stage prompt SHALL ask for one `feasibility` line for each called function whose arguments need a checkout, a client or a network.

#### Scenario: The stage prompt loads
- **WHEN** The stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text names a checkout, a client and a network as preconditions to state in `feasibility`.

### Requirement: A cited class field is probed at the staging commit
The premise probe SHALL read a cited `Class.field` reference as a class field when the staging
commit defines the class, and SHALL name the file and line of the field when the class defines it.

#### Scenario: A class that defines the cited field
- **WHEN** The issue body cites `PullStatus.labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The probe text says that `PullStatus` defines `labels` at its file and line, and the reference is not in the probe's missing list

#### Scenario: A class without the cited field
- **WHEN** The issue body cites `PullStatus.unknown_field` and `PullStatus` at the staging commit defines no `unknown_field`
- **THEN** The probe text says that `PullStatus` defines no `unknown_field`, and the reference is in the probe's missing list

#### Scenario: The cited dotted reference names a class
- **WHEN** The issue body cites `PullStatus.labels` and the staging commit defines the class `PullStatus`
- **THEN** The probe text holds no line that says the path `PullStatus.labels` is no file of the staging commit

### Requirement: Bounded read-only field probe
The field probe MUST count each git command against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` and
MUST leave the checkout unchanged.

#### Scenario: A probe of cited fields
- **WHEN** The probe reads a cited class field at the staging commit
- **THEN** The probe reports its command count against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`, and `git status --porcelain` of the checkout stays empty
