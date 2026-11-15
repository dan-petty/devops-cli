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

### Requirement: The stage job checks a stated CI job-time limit
Before it calls the planner, the stage job SHALL read the CI check name and the duration limit that the item body states, compare the limit with the mean of the check's last 20 runs on the default branch, and return the item to New with the evidence when the mean is over the limit. A mean equal to the limit SHALL pass. An item that states no limit SHALL make no job-time read.

#### Scenario: The body states a limit
- **WHEN** the body states that `Tests & Coverage` stays under 300 s
- **THEN** the parse returns the check `Tests & Coverage` and the limit 300 s

#### Scenario: The mean is over the limit
- **WHEN** the stated limit is 300 s and the last 20 runs average 328 s
- **THEN** the check reports the check, the mean, the sample size and the limit, and the item returns to New with no branch and no planner call

#### Scenario: The mean equals the limit
- **WHEN** the stated limit is 300 s and the mean is 300 s
- **THEN** the check reports no failure and the stage job stages the item

#### Scenario: The read fails twice
- **WHEN** the job-time read fails twice
- **THEN** the item stays Ready with the `ci_infra` failure and the job creates no branch and calls no planner

### Requirement: The probe names the test module of a cited function
The stage probe SHALL name, for each cited identifier that the staging commit defines, the test modules whose text holds the name as a word, and SHALL say that no test module names the identifier when none does. It SHALL read the test modules of all cited identifiers with one git command, and SHALL say so when its command bound leaves the listing out.

#### Scenario: A cited function has a test module
- **WHEN** the issue cites a function whose name a test module of the staging commit holds
- **THEN** the probes text holds a line that names that test module for the function

#### Scenario: A cited function has no test module
- **WHEN** no test module of the staging commit holds the name of a cited function
- **THEN** the probes text holds a line that says that no test module names the function

#### Scenario: The command bound leaves the listing out
- **WHEN** the probe has no git command left when it reads the test modules
- **THEN** the probes text holds a line that says that the bound left the test module listing out

### Requirement: The job probes a claimed missing check in a helper of its call site
After the model reply and before it writes a branch or a pull request, the stage job SHALL read the body of a call site that a plan text says runs no named check, and the body of each helper that the call site calls in its file. The job SHALL write one line that names the path and the line of a check that it finds there, and SHALL send no model request for the read. A claim that names no call site and no named check SHALL add no line.

#### Scenario: A helper of the call site holds the check
- **WHEN** a plan text says that the call site `_publish` runs no `title_problems` check, and `_publish` calls `_delivery_title`, whose body calls `title_problems`
- **THEN** the probe line names `title_problems` at the path and the line of its call in `_delivery_title`

#### Scenario: A claim with no cited call site
- **WHEN** a plan says that a check is missing but names no call site and no check
- **THEN** the probe adds no line and the stage job plans the item as before

#### Scenario: A claim is probed with no model call
- **WHEN** a plan claims a missing check and the stage job probes it
- **THEN** the stage job sends no model request for the read

### Requirement: The job searches the base tree for a claimed missing check
The stage job SHALL search the source files of the staging commit for a named check that a plan text says is missing, when the cited call site and its helpers do not hold it. The search SHALL use the git commands that the probe of the item has left, SHALL run only read-only commands at the staging commit, and SHALL list a claim as skipped when no command is left.

#### Scenario: A check that only another file holds
- **WHEN** a plan says that a call site runs no named check, and only another source file of the staging commit holds that check
- **THEN** the probe line names the path and the line of the check in that file

#### Scenario: The bound leaves a claim unprobed
- **WHEN** a plan claims more missing checks than the commands that are left
- **THEN** the probe lists the claim as skipped and runs no further command
