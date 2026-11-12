# roadmap-stage/paths-gate Specification

## Purpose
The path gate of a plan: each path that a plan names exists at the staged commit or a group creates it, and the checks of the negative searches, the moved paths, the move groups and the callers that a task changes.

## Requirements

### Requirement: The plan names files that exist at the staged commit
The job SHALL check each path of the reply against the tracked files of the staged commit: the paths of `reads` and `changes`, the paths in the code spans of the tasks, and the paths in `verify`. A path SHALL pass when the commit holds it, or when `creates` of its group or of an earlier group lists it. A missing path SHALL go back to the model with the files of the commit of the same name. A missing path after the last return SHALL stop the item with no draft pull request.

#### Scenario: A test file that moved
- **WHEN** a group changes `tests/test_scanner_tool_executor.py` and the commit holds `tests/security/test_scanner_tool_executor.py`
- **THEN** the job asks the model again, and the problem names the missing path and lists `tests/security/test_scanner_tool_executor.py`

#### Scenario: The second reply has a missing path
- **WHEN** the second reply and each later reply still name `tests/test_scanner_tool_executor.py`
- **THEN** the job stops the item with the problem after the last return, pushes no branch and opens no draft pull request

#### Scenario: A path in a task or in a verify command
- **WHEN** a code span of a task or the `verify` command of a group names a file that the commit lacks and no group up to it creates
- **THEN** the problem names that file

#### Scenario: A created path
- **WHEN** a group changes `tests/test_new.py`, lists it in `creates`, and a later group reads it
- **THEN** the job finds no missing path
- **AND** when only a later group lists it in `creates`, the earlier group names a missing path

#### Scenario: A word that is no path
- **WHEN** a code span holds `status/blocked`, `--strict` or `uv run devops ci docs`
- **THEN** the job finds no missing path

#### Scenario: A name with no folder
- **WHEN** a code span of a task or the `verify` command holds `ruff.toml` or `grep step_files.py`
- **THEN** the job finds no missing path
- **AND** a path of `reads` or `changes` with no folder is still checked

### Requirement: A problem names the group that creates a missing path
When a later group lists a missing path in `creates`, the problem SHALL name the group that names the path and the first later group that creates it, and SHALL tell the model to move the creating group before the reading group. A path that no group creates SHALL keep the problem without a creating group.

#### Scenario: A path that only a later group creates
- **WHEN** group 1 reads `tests/test_new.py` and only group 3 lists it in `creates`
- **THEN** the problem names group 1 and group 3, and tells the model to move group 3 before group 1

#### Scenario: A path that no group creates
- **WHEN** group 1 reads `tests/test_new.py` and no group lists it in `creates`
- **THEN** the problem names group 1 and names no creating group

### Requirement: The paths of a negative search are checked against the staged commit
`check_proposal` SHALL read the paths of a `verify` command that is a negative search from the reader of the step, and SHALL refuse a path that is no file or folder of the staged commit and that no group up to its own creates. A path that ends in `/` SHALL be a folder. The path `.` SHALL not be judged. A glob SHALL be judged by the files that it matches.

#### Scenario: A folder that is not in the commit
- **WHEN** a group gives the `verify` command `! git grep -n hello scr/ testz/` and the commit has `src/` and `tests/` only
- **THEN** `check_proposal` returns a problem for `scr` and one for `testz`

#### Scenario: Folders of the commit and a folder that the plan creates
- **WHEN** a group gives the `verify` command `! git grep -n old_name src/ tests/`, `! git grep -n x -- .` or `! git grep -n x -- tests/newdir`, and the plan creates `tests/newdir/test_new.py`
- **THEN** `check_proposal` returns no problem about the paths

#### Scenario: A file with a trailing slash
- **WHEN** a group gives the `verify` command `! git grep -n devops README.md/` and `README.md` is a file of the commit
- **THEN** `check_proposal` returns a problem for `README.md`

### Requirement: A move group names every module of its prefix
The stage plan check SHALL refuse a group that moves a top-level Python module by name prefix and leaves another module of that prefix for no later group. A top-level module is a `.py` file directly under the folder. A file whose name starts with `test_`, and `conftest.py`, is no module of a job prefix.

#### Scenario: A move group omits a module of its prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/stage/stage_verify.py`, and one group lists `src/devops_cli/roadmap/stage/stage_ready.py` in `changes` and `src/devops_cli/roadmap/stage/ready.py` in `creates`, with no later group.
- **THEN** `check_proposal` returns a problem that names `src/devops_cli/roadmap/stage/stage_verify.py`.

#### Scenario: A later group moves the missing module
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/stage/stage_verify.py`, the first group moves `stage_ready.py` into `stage/`, and a later group moves `stage_verify.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for either module.

#### Scenario: A move group leaves a module of another prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/status.py`, and a group moves `stage_ready.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for `src/devops_cli/roadmap/status.py`.

#### Scenario: A move group leaves a test module
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `tests/roadmap/stage/test_roadmap_stage_ready.py`, and a group moves `stage_ready.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for `tests/roadmap/stage/test_roadmap_stage_ready.py`.

### Requirement: A move group verifies the whole prefix
The stage plan check SHALL refuse a move group whose `! git grep` verify literal equals the import path of one top-level module of the moved prefix, the bare prefix included.

#### Scenario: A move group verifies one sampled import
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage.stage_ready src/ tests/`.
- **THEN** `check_proposal` returns a problem that says the verify command must cover the prefix.

#### Scenario: A move group verifies the bare prefix
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage.stage src/ tests/`.
- **THEN** `check_proposal` returns a problem, because the literal names `stage.py` and matches the new `stage/` package.

#### Scenario: A move group verifies the dotted prefix
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage_ src/ tests/`.
- **THEN** `check_proposal` returns no problem about the verify command.

### Requirement: The stage prompt asks for every module of a prefix
The stage prompt SHALL tell the planner to list every module of a moved name prefix in the group `changes` and to give a `verify` command that covers the prefix, with the layout invariant test or with a `! git grep` literal that names no single module.

#### Scenario: The stage prompt describes a prefix move
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text tells the planner to name every module of the prefix, not the entry module only, and to verify the prefix.

### Requirement: The stage check names the message file a task needs
The stage check SHALL return a problem that names `src/devops_cli/lang/en/messages.py` when a rendered task text of a group names `MESSAGES.roadmap` and no group lists that file in `changes`.

#### Scenario: A task text names a message without the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a message with the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and a group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns no problem about `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a dotted message entry
- **WHEN** A plan has a task text that names `MESSAGES.roadmap.some_entry` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

### Requirement: The stage job records the hits of a negative search
The stage job SHALL run the literal of each negative-search verify command on the staged tree with git grep and SHALL record the matching paths before it judges the reply.

#### Scenario: A negative search has staged hits
- **WHEN** The plan gives a negative-search verify command whose literal matches paths of the staged tree.
- **THEN** The job records each matching path under the literal and passes the record to check_proposal.

### Requirement: A negative search with no staged hit is refused
check_proposal MUST refuse a negative-search literal that the recorded evidence gives with no matching path.

#### Scenario: The literal finds nothing before the change
- **WHEN** The recorded evidence for a negative-search literal holds no matching path.
- **THEN** check_proposal returns a problem that says the search already passes before the change and proves nothing.

### Requirement: A negative search that a created module keeps is refused
check_proposal MUST refuse a negative-search literal when a source path that the plan creates has an import path that contains the literal.

#### Scenario: A created module matches the literal
- **WHEN** A group creates a source path under src/devops_cli/ whose import path contains the negative-search literal.
- **THEN** check_proposal returns a problem that says the search can never pass on the produced tree.

### Requirement: A negative search with a surviving hit is accepted
check_proposal MUST accept a negative-search literal when the recorded evidence holds a matching path and no created source path has an import path that contains the literal.

#### Scenario: A staged hit survives the change
- **WHEN** The recorded evidence holds a matching path and no created source path has an import path that contains the literal.
- **THEN** check_proposal returns no problem for that literal.

### Requirement: The stage prompt asks for the hit count of a negative search
The stage prompt MUST ask the planner to call search_code with the literal of each negative-search verify command and to quote the hit count in feasibility.

#### Scenario: The planner reads the prompt
- **WHEN** The stage job plans an item whose plan gives a negative-search verify command.
- **THEN** The prompt tells the planner to call search_code with the literal and to quote the hit count in feasibility.

### Requirement: Refuse a What Changes path that no group lists
The proposal check SHALL return a problem when a repository path in a code span of a What Changes item is in neither the changes nor the creates list of any task group, and the path is not under the living spec folder.

#### Scenario: What Changes names a path that no group lists
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/lang/en/messages.py`, and no group lists that path in `changes` or `creates`
- **THEN** `check_proposal` returns a problem that names the unlisted path

#### Scenario: What Changes names a path that a group changes
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/stage/stage_change.py`, and a group lists that path in `changes`
- **THEN** `check_proposal` returns no problem for that path

#### Scenario: What Changes names a path that a group creates
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/new_check.py`, and a group lists that path in `creates`
- **THEN** `check_proposal` returns no problem for that path

### Requirement: Ignore a What Changes item with no unlisted path
The proposal check SHALL accept a What Changes item when it holds no repository path in a code span, when each code span that is a repository path is listed by a task group, or when the path is under the living spec folder that `openspec archive` writes.

#### Scenario: What Changes item describes behaviour only
- **WHEN** A proposal has a What Changes item with no code span that is a repository path
- **THEN** `check_proposal` returns no problem for that item

#### Scenario: What Changes names a command in a code span
- **WHEN** A proposal has a What Changes item with the code span `uv run devops ci test`
- **THEN** `check_proposal` returns no problem for that code span

#### Scenario: What Changes names a path that openspec archive writes
- **WHEN** A proposal has a What Changes item with the code span `openspec/specs/roadmap-stage/spec.md`, and no group lists that path
- **THEN** `check_proposal` returns no problem for that path

#### Scenario: The replay runs the What Changes check without git
- **WHEN** The replay calls `check_proposal` with a proposal and the `StagedTree` of its facts, and no checkout
- **THEN** The replay returns the unlisted-path problem and makes no git call

### Requirement: The stage check refuses an overlapping create path
The stage check SHALL refuse a plan that lists a path in `creates` that another open plan also creates. The problem SHALL name the path and the open item. The reply SHALL go back to the model as a refused reply.

#### Scenario: Two open plans create the same module
- **WHEN** open item #3308's `tasks.md` marks `src/devops_cli/roadmap/stage_constants.py` with `(new)`, and the reply of the item lists the same path in `creates`
- **THEN** the check returns a problem that names the path and #3308

### Requirement: The missing-path message names both forms
The message of a path that the staged tree lacks SHALL name the `creates` list of a stage reply and the ` (new)` mark of the `Changes:` line of `tasks.md`.

#### Scenario: A group names a missing file
- **WHEN** `path_problems` judges a group that names `src/devops_cli/new_module.py` and no group creates it
- **THEN** the problem holds `creates`, ` (new)` and `Changes:`

#### Scenario: A plan omits the mark
- **WHEN** the plan check reads a change folder whose group 3 `Changes:` line names four new case files with no ` (new)` mark
- **THEN** each of the four problems holds ` (new)` and `Changes:`

### Requirement: The missing-path message keeps its hint
The missing-path message SHALL end with the hint that names the tracked files of the same name, or that states that no file has the name.

#### Scenario: A tracked file has the same name
- **WHEN** the tree holds `src/devops_cli/roadmap/stage/stage.py` and a group names `src/devops_cli/new/stage.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `stage.py`

#### Scenario: A later group creates the path
- **WHEN** group 1 names `src/devops_cli/new_module.py` and group 3 lists it in `creates`
- **THEN** the problem names group 3 and holds neither `creates` nor ` (new)`

### Requirement: The module docstring names both readers
The module docstring of `stage_paths.py` SHALL state that `path_problems` judges both the stage reply and the change folder.

#### Scenario: A reader opens the module
- **WHEN** a test reads the module docstring of `src/devops_cli/roadmap/stage/stage_paths.py`
- **THEN** the docstring holds `change folder` and `reply`

### Requirement: The stage job checks each literal of a negative search
The stage job SHALL record the staged hits of each `-e` literal of a negative-search verify command, and check_proposal SHALL apply the rules of the negative search to each literal, the rule of the staged hit and the rule of the created module alike.

#### Scenario: One literal has no staged hit
- **WHEN** A group gives the verify command `! git grep -n -e old_name -e gone_name -- src/ tests/`, and the staged tree holds `old_name` but no `gone_name`.
- **THEN** check_proposal returns one problem that names the literal `gone_name` and says that the search already passes before the change.

#### Scenario: A move group names a module with a second literal
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -e devops_cli.roadmap.stage.stage_ready -e devops_cli.roadmap.stage.stage -- src/ tests/`.
- **THEN** check_proposal returns two problems: the problem of the move and the problem of the created module, and each names the literal `devops_cli.roadmap.stage.stage`.

### Requirement: The comment lists the named paths that moved
The stage job SHALL list each path that a group of the plan names under `reads` or `changes` and that a commit on the default branch changed after the plan's base.

#### Scenario: A named plan path changes on main
- **WHEN** The plan names `src/devops_cli/roadmap/stage/stage_change.py` under `reads` and a later commit on the default branch changes that file.
- **THEN** The comment of the staged item names `src/devops_cli/roadmap/stage/stage_change.py` and the commit that changed it.

#### Scenario: An unnamed path changes on main
- **WHEN** A commit after the base changes a file that no group of the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item does not name that file.

### Requirement: A moved path gives its commits in log order
The stage job SHALL give the short hash and the subject of each commit that changed a listed path, in log order.

#### Scenario: Two commits change one named path
- **WHEN** Two commits after the base change a path that the plan names under `changes`.
- **THEN** The comment lists the two short hashes and subjects under that path in log order.

#### Scenario: No commit changes a named path
- **WHEN** No commit after the base changes a path that the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item has no moved-file section.

### Requirement: The comparison reads the latest default branch
The stage job MUST fetch the default branch before it compares the plan's base with the default branch.

#### Scenario: The remote default branch advances
- **WHEN** A remote commit changes a named path after the stage job fetched the base.
- **THEN** The comment of the staged item lists that path and commit.

### Requirement: The path gate names every caller of a function that a task changes
The path gate SHALL refuse a plan whose task clause adds a parameter, an argument or a keyword to a function, or adds one code span in parameter shape, and that leaves out a file under `src/` that calls the function. A clause ends at a `.`, a `:` or a `;` outside a code span. A decorator, an option or a constant in capitals is no parameter. A name that no module under `src/` defines with `def` is no function, and a call is a call of the name itself, as `ast` reads it.

#### Scenario: A task adds a parameter to a function
- **WHEN** A task text of a group holds the words Add a probes parameter to `check_proposal`
- **THEN** The caller check reads the function name `check_proposal`

#### Scenario: A task adds an argument to two functions
- **WHEN** A task text holds the words add the keyword-only argument `base_scenarios` to `check_gates` and `check_proposal`
- **THEN** The caller check reads the function names `check_gates` and `check_proposal`

#### Scenario: A task adds one code span in parameter shape
- **WHEN** A task text holds the words Add `known` to `build_import_graph`, or add `sampling: CallSampling | None = None` to `_build_anthropic_kwargs` and `_claude_messages`
- **THEN** The caller check reads `build_import_graph` from the first text, and `_build_anthropic_kwargs` and `_claude_messages` from the second

#### Scenario: A decorator or an option is no parameter
- **WHEN** A task text holds the words Add `@dry_run_class("request-plan")` to `run_benchmark`, or Add `--take-ownership` to `_build_helm_upgrade_cmd`
- **THEN** The caller check reads no function name

#### Scenario: A field of a model has no caller
- **WHEN** A task text holds the words add `constant_claims` to `StageProposal`, `StageProposal` is a class, and a file under `src/` calls `StageProposal()`
- **THEN** `path_problems` returns no problem about a caller of `StageProposal`

#### Scenario: A task adds a member to a class
- **WHEN** A task text holds the words Add `REVIEW = "review"` to `FailureClass`, or Add the property `added_names` to `TaskGroup`
- **THEN** The caller check reads no function name

#### Scenario: A name in the next clause
- **WHEN** A task text holds the words Add the method `_repair_scope` to the run: it takes the folder, and pass the same log to `_fix`
- **THEN** The caller check reads no function name

#### Scenario: Two files call the function
- **WHEN** The checkout holds `src/a.py` and `src/b.py`, each calls `check_proposal`, and a module defines it with `def`
- **THEN** The caller search returns `src/a.py` and `src/b.py`

#### Scenario: A longer name and a string are no call
- **WHEN** A file holds `scan_fix(log)` and a docstring that holds `_fix(log)`
- **THEN** The caller search for `_fix` does not return that file

#### Scenario: A class has no caller
- **WHEN** The function name is the name of a class, as `TaskGroup` is, and a file calls `asyncio.TaskGroup()`
- **THEN** The caller search returns no file

#### Scenario: The plan omits a caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold `src/devops_cli/roadmap/stage_eval_gates.py` and no `src/devops_cli/roadmap/stage.py`
- **THEN** `path_problems` returns a problem that names `check_proposal` and `src/devops_cli/roadmap/stage.py`

#### Scenario: The plan lists every caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold every file that the caller search returns
- **THEN** `path_problems` returns no problem about a caller of `check_proposal`

#### Scenario: The tree holds no checkout
- **WHEN** The path gate runs on a tree of a replay case, which holds no checkout
- **THEN** `path_problems` returns no problem about a caller

### Requirement: The plan check refuses a path of its own change folder
`check_proposal` SHALL refuse a path under `openspec/changes/<change>/` in a group `changes` or in a code span of a task when `change` is the plan's own change folder.

#### Scenario: A group lists the plan proposal
- **WHEN** A behavior group lists `openspec/changes/3321-plan-check/proposal.md` in `changes`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the path and the own change folder.

#### Scenario: A task names the plan tasks file
- **WHEN** A behavior group's `implementation` names `openspec/changes/3321-plan-check/tasks.md` in a code span, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the group and the path.

#### Scenario: A group names another change folder
- **WHEN** A behavior group changes `openspec/changes/3307-other/proposal.md`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns no own-change problem.

### Requirement: A move needs the module in another place
The stage job SHALL treat a Python module as moved only when a task group lists it in `changes` and creates, in `creates`, a module of the same name or a module under the sub-package that the name prefix of the module gives. A group that creates only a test, a document or a module of another name SHALL move no module, and the job SHALL probe no reference for it.

#### Scenario: A group edits a module and creates a test
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `tests/roadmap/test_stage_probe.py`.
- **THEN** the group moves no module.

#### Scenario: A group moves a module into a sub-package
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `src/devops_cli/roadmap/stage/probe.py`.
- **THEN** the group moves `src/devops_cli/roadmap/stage_probe.py`, with the dotted name `devops_cli.roadmap.stage_probe`.
