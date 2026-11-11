## MODIFIED Requirements

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
