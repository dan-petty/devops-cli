# roadmap-stage/claims Specification

## Purpose
The claims of a plan that the stage job checks against the staged tree: constants, commands, options, MCP keys, model attributes, registry and ratchet places, and the programs of the Job and of a verify command.

## Requirements

### Requirement: The plan lists the registry and ratchet places that its changes need
The stage job SHALL build the registry and ratchet table from the module-level `REGISTRY_COUNTS` declarations of the test modules, and MUST NOT read a hand-copied table. The plan context SHALL list each matching entry with its `path:line`, and `check_proposal` MUST refuse a plan that adds a counted item and has no task whose text names the declared path.

#### Scenario: A new declaration appears in the table
- **WHEN** A test module adds a `REGISTRY_COUNTS` entry for a counted prefix, enum or table name.
- **THEN** The table builder returns that entry with its test path and line, and no hand-written table changes.

#### Scenario: New roadmap limit without a ratchet task
- **WHEN** A plan adds `DEFAULT_ROADMAP_EXAMPLE_LIMIT` and has no task for `tests/roadmap/test_roadmap_limit_classes.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_limit_classes.py` and `check_proposal` returns a missing-path problem for it.

#### Scenario: New job write without one registry task
- **WHEN** A plan adds a write method and has no task for `tests/support/fakes/roadmap_store.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_dry_runs.py`, the `WRITES` table in `tests/support/fakes/roadmap_store.py`, `tests/roadmap/test_roadmap_store_contract.py` and `src/devops_cli/roadmap/request_plan.py`, and `check_proposal` returns a problem for the fault-test path.

#### Scenario: A plan that names every listed place passes
- **WHEN** A plan adds a counted item and holds a task whose text names each declared path.
- **THEN** `check_proposal` returns no registry problem for that plan.

### Requirement: A plan number beside a constant matches the staged value
The plan check SHALL refuse a plan when a sentence names one known module-level integer constant of the staged tree, holds one candidate decimal number, and that number differs from the value of the constant.

#### Scenario: Summary bound mismatch
- **WHEN** A spec scenario says `SUMMARY_MAX_CHARS` is 40, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns one problem that names `SUMMARY_MAX_CHARS`, 40 and 60.

#### Scenario: Summary bound match
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 60, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A bound after the constant name
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` holds 60 characters, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A note reference beside the constant
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` is 60 (#2714), and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Two numbers in one sentence
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 40, while the staged tree sets it to 60.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the sentence is ambiguous.

### Requirement: A constant that the staged tree does not define is ignored
The plan check MUST skip a constant name that the staged tree does not define as a module-level integer assignment.

#### Scenario: New plan constant
- **WHEN** A design decision names `PLAN_SUMMARY_MAX_CHARS = 47`, and the staged tree does not define `PLAN_SUMMARY_MAX_CHARS`.
- **THEN** The check returns no problem about `PLAN_SUMMARY_MAX_CHARS`.

#### Scenario: Non-literal assignment
- **WHEN** A staged module sets `SUMMARY_MAX_CHARS` from a call, and the plan says `SUMMARY_MAX_CHARS` is 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Ambiguous definition
- **WHEN** Two staged modules set `SUMMARY_MAX_CHARS` to different integers, and the plan says `SUMMARY_MAX_CHARS` is 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the tree holds no one value.

### Requirement: The check reads constants without running staged code
The plan check MUST read the constant values with the Python `ast` module and MUST NOT import or execute a staged file.

#### Scenario: A staged module with a side effect
- **WHEN** A staged Python module writes a file at import, and the plan says `SUMMARY_MAX_CHARS` is 60.
- **THEN** The check writes no file and returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: An alias to another constant
- **WHEN** A staged module sets `BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` and another staged module sets `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS = 1000`, and the plan says `BODY_MAX_CHARS` is 1000.
- **THEN** The check returns no problem about `BODY_MAX_CHARS`.

### Requirement: The task commands carry no constant claim
The plan check MUST NOT compare a number in `tasks.md` with a constant.

#### Scenario: Task command number
- **WHEN** `tasks.md` holds `SUMMARY_MAX_CHARS` and 40 in one command, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

### Requirement: The replay passes recorded constants
The stage eval replay MUST pass the constants of a case to the plan check and MUST read no git.

#### Scenario: Recorded constants
- **WHEN** A case records `SUMMARY_MAX_CHARS` as 60, and its spec scenario says 40.
- **THEN** The replay refuses the plan with the problem that names the constant, 40 and 60.

#### Scenario: A case with no constants
- **WHEN** A case records no constants.
- **THEN** The replay runs the check with an empty mapping and keeps the result it gives today.

### Requirement: The prompt asks for the staged value of a constant
The plan stage prompt SHALL tell the model to cite the staged value of each constant that the plan relies on, and to give no new name to the bound of a constant that the staged tree defines.

#### Scenario: Prompt rule
- **WHEN** The prompt rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The text holds an instruction to cite the staged value of each constant that the plan relies on.

### Requirement: A read of a model attribute that the model lacks is refused
The stage proposal check SHALL refuse a plan that names an attribute that the Pydantic model of the staged commit does not define, and SHALL name the reference and the module of the model in the problem.

#### Scenario: PullStatus lacks labels
- **WHEN** A plan names `PullStatus.labels`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines no `labels` field.
- **THEN** `check_proposal` returns a problem that names `PullStatus.labels` and `src/devops_cli/github/client.py`.

#### Scenario: A model field that exists passes
- **WHEN** A plan names `PullStatus.state`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines `state`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A name that is no model class is left alone
- **WHEN** A plan names `stage_ready.item`, and no Pydantic model class of the staged commit is named `stage_ready`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A caller gives no model map
- **WHEN** `check_proposal` runs with no `models` argument on a plan that names `PullStatus.labels`.
- **THEN** `check_proposal` returns no problem for that reference.

### Requirement: The module of a model that a plan extends is in changes
The stage proposal check SHALL return a problem that names the module of a model when a plan reads an attribute that the model lacks and no group lists that module in `changes`, and SHALL return no such problem when a group lists it.

#### Scenario: The plan omits the model module
- **WHEN** A plan reads `PullStatus.labels` and no group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns a problem that tells the model to add `src/devops_cli/github/client.py` to a group's `changes`.

#### Scenario: The plan lists the model module
- **WHEN** A plan reads `PullStatus.labels` and a group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns no problem for the model attribute.

#### Scenario: A second reply with the same gap stops the item
- **WHEN** The first, the second and each later reply read `PullStatus.labels` and omit `src/devops_cli/github/client.py` from `changes`.
- **THEN** The stage job records a failure of the item with `RoadmapStageError`, and the plan holds no ready change.

### Requirement: Resolve cited command spans
The plan check SHALL resolve every `devops` command span in the Feasibility text and the task text against the real command tree.

#### Scenario: Unknown subcommand is refused
- **WHEN** A plan cites `uv run devops ai ast-graph --help`.
- **THEN** The check returns a problem that names `ai ast-graph` and refuses the plan.

### Requirement: Accept a resolved command span
The plan check SHALL accept a `devops` command span that resolves to a leaf command with valid options.

#### Scenario: Known subcommand is accepted
- **WHEN** A plan cites `uv run devops ai ast graph --help`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited option flags
The plan check SHALL resolve each option flag in a cited `devops` command span against that command.

#### Scenario: Unknown option is refused
- **WHEN** A plan cites `uv run devops gh pages verify --root_dir .`.
- **THEN** The check returns a problem that names `--root_dir` and refuses the plan.

#### Scenario: Known option is accepted
- **WHEN** A plan cites `uv run devops gh pages verify --dir .`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited MCP exposure keys
The plan check SHALL resolve each quoted tuple key that a plan cites against `CONST_MCP_EXPOSURE_TABLE`. It SHALL read a quoted tuple as a cited key only when the sentence that holds the tuple names `CONST_MCP_EXPOSURE_TABLE` or the words "exposure table".

#### Scenario: Unknown MCP exposure key is refused
- **WHEN** A plan cites the exposure table key `("ai", "ast-graph")`.
- **THEN** The check returns a problem that names `("ai", "ast-graph")` and refuses the plan.

#### Scenario: Known MCP exposure key is accepted
- **WHEN** A plan cites the exposure table key `("ai", "ast", "graph")`.
- **THEN** The check returns no MCP exposure problem for that key.

#### Scenario: A quoted tuple of another table is no key
- **WHEN** A plan says that the fixture table of `tests/conftest.py` lists `("reset_logfire_bridge",)`.
- **THEN** The check returns no MCP exposure problem.

#### Scenario: The sentence of the tuple decides
- **WHEN** A plan names the exposure table in one sentence and quotes the tuple `("ai", "ast-graph")` in the next sentence.
- **THEN** The check returns no MCP exposure problem.

### Requirement: Gate refuses unsupported Job command
The staging gate SHALL refuse a plan that adds a command to the Job when its `## Feasibility` section names no runner capability for that command.

#### Scenario: Unsupported Job command is refused
- **WHEN** A plan adds `devops review` to the Job and its Feasibility section names no review tool from `NOT_IN_RUNNER`.
- **THEN** The gate returns a refusal that names `devops review` and the missing runner capability.

### Requirement: Gate refuses unsupported verify program
The staging gate SHALL refuse a plan whose task verify runs a `NOT_IN_RUNNER` program without a `## Feasibility` line that names its runner capability.

#### Scenario: Helm verify is refused
- **WHEN** A plan has a task verify that runs `helm template` and its Feasibility section names no runner capability for `helm`.
- **THEN** The gate returns a refusal that names `helm` and the missing runner capability.

### Requirement: Docker verify is refused
The staging gate SHALL refuse a medium-effort plan whose task verify runs `docker` without a `## Feasibility` line that names its runner capability.

#### Scenario: Medium-effort Docker verify is refused
- **WHEN** A medium-effort plan has a task verify that runs `docker build` and its Feasibility section names no runner capability for `docker`.
- **THEN** The gate returns a refusal that names `docker` and the missing runner capability.

### Requirement: The table builder parses only the modules that name the registry
The table builder SHALL read the text of each test module, and MUST NOT parse a module whose text does not hold `REGISTRY_COUNTS`. A module that holds the name only outside a module-level assignment, such as in a comment, SHALL give no entry.

#### Scenario: A module with no declaration is not parsed
- **WHEN** `counts_in` reads a test module whose text does not hold `REGISTRY_COUNTS`.
- **THEN** It returns no entry, and `ast.parse` gets no call for the text of that module.

#### Scenario: The name in a comment gives no entry
- **WHEN** `counts_in` reads a test module that holds `REGISTRY_COUNTS` only in a comment.
- **THEN** It returns no entry.
