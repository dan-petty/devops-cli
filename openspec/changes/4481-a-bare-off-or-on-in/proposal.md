# Proposal

## Why

A bare `off` or `on` as the value of `roadmap.intake.jev` stops the settings load. PyYAML follows YAML 1.1 and reads that value as `false` or `true`, and the mode fields accept only `off`, `shadow` and `on`. `devops config set` writes exactly that bare value through the ruamel.yaml writer, so a written mode fails the next load. `roadmap.decisions` has the same gap (#4481).

## What Changes

- Give the mode type in `src/devops_cli/config/defaults.py` a `BeforeValidator`, so a YAML 1.1 `false` reads as `off` and `true` reads as `on` for `JevMode` and `DecisionMode`.
- Add `tests/config/test_mode_yaml_booleans.py`: a bare `off` and `on` in a config file load as `off` and `on`, `TypeAdapter(DecisionMode)` reads `False` and `True` as `off` and `on`, a mapping that `round_trip.edit` writes reloads through `RoadmapIntakeConfig`, and `devops config set roadmap.intake.jev off` loads as `off`.
- Replace `test_the_setting_is_off_by_default_and_refuses_the_old_bool` in `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`, because a bool is now the mode it names.
- State in `docs/roadmap/intake.md` that `roadmap.intake.jev` takes a bare `off` and `on`.
- Leave the reader `yaml.safe_load` and the writer `round_trip.edit` as they are, and change no manifest.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: A mode setting reads a bare YAML 1.1 off or on

## Impact

- Code: `src/devops_cli/config/defaults.py`
- Documents: `docs/roadmap/intake.md`
- Tests: `tests/config/test_mode_yaml_booleans.py`, `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`

## Feasibility

- The probe confirms the file that the issue names, word for word: The path `src/devops_cli/config/settings.py` is a file of the staging commit.
- The probe read the other names of the issue as paths, and each is an identifier of the code: The path `yaml.safe_load` is no file of the staging commit. No commit in the history deleted or renamed it.
- The same holds for the setting of the issue: The path `roadmap.intake.jev` is no file of the staging commit. No commit in the history deleted or renamed it.
- The probe says the same of the writer call: The path `round_trip.edit` is no file of the staging commit. No commit in the history deleted or renamed it.
- The `read_file` call on `src/devops_cli/config/defaults.py` lines 920 to 960 showed `src/devops_cli/config/defaults.py:936:JevMode = Literal["off", "shadow", "on"]` and `src/devops_cli/config/defaults.py:939:DecisionMode = Literal["off", "shadow", "on"]`, the two types that refuse a bool.
- The same call showed the staged default that the plan relies on: `src/devops_cli/config/defaults.py:937:DEFAULT_ROADMAP_INTAKE_JEV: JevMode = "off"`.
- The `read_file` call on `src/devops_cli/config/settings.py` lines 1318 to 1370 showed `src/devops_cli/config/settings.py:1327:jev: Annotated[JevMode, Variable()] = Field(` and `src/devops_cli/config/settings.py:1356:decisions: Annotated[dict[str, DecisionMode], Variable()] = Field(`, so one shared type covers both settings of the issue.
- The `search_code` call with `safe_load(path.read_text` showed the reader in `src/devops_cli/config/settings.py:def _read_config_file`: `lambda: yaml.safe_load(path.read_text(encoding="utf-8")) or {},`.
- The `file_symbols` call on `src/devops_cli/config/round_trip.py` showed `def edit(` at line 99, and the `read_file` call on lines 99 to 118 showed `src/devops_cli/config/round_trip.py:110:yaml = YAML(typ="rt")`, the YAML 1.2 writer that leaves a string `off` unquoted.
- The `read_file` call on `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py` lines 300 to 345 showed `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py:322:RoadmapIntakeConfig(jev=True)` inside `test_the_setting_is_off_by_default_and_refuses_the_old_bool`, the existing assertion that the change replaces; the file ends at line 324, and its `ValidationError` import stays in use through the replacement test.
- The `read_file` call on `tests/ai/ast/test_ai_ast_cli.py` line 9 showed `tests/ai/ast/test_ai_ast_cli.py:9:from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES`, the existing test of `src/devops_cli/config/defaults.py` that group 1 reads, which answers the second fault of the problem.
- The `list_files` call on `tests/config` showed `tests/config/test_loki_url.py` and no `tests/config/test_mode_yaml_booleans.py`, so the new module goes in that folder, which mirrors `src/devops_cli/config/`.
- The `search_code` call with `cli("config", "set"` showed `tests/config/test_loki_url.py:28:result = cli("config", "set", "loki.url", "http://example.com:3100")`, the model of the written-mode test.
- The `read_file` call on `docs/roadmap/intake.md` lines 30 to 70 showed `docs/roadmap/intake.md:44:has three values (ADR 0019)`, the section where the docs group adds the bare values.
- The `read_spec` call on `config-commands` listed its requirements, and none of them covers a YAML 1.1 boolean, so the change adds one requirement to that capability.
- The `read_issue` calls showed #4397 closed and #4453 merged, so the field `roadmap.decisions` exists at the staged commit, and the `find_issues` call with `roadmap.intake.jev` listed #4481, #4450 and #4446; neither other open item changes the mode type, so the plan takes no dependency.
- The plan calls no function whose arguments need a checkout of the repository, a client of a service or a network: `round_trip.edit` takes a text and a mapping, `yaml.safe_load` takes a text, and `TypeAdapter` and `load_settings` read memory and local files.
- The plan introduces no command and no verify program: both verifies are existing commands, `uv run devops ci test`, whose failure class is `test`, and `uv run devops ci docs`, whose failure class is `test`. Both run in the runner image, which holds `uv` and `pytest`, so no tool of the plan is `NOT_IN_RUNNER` and the pod settings `readOnlyRootFilesystem` and `runAsNonRoot` stay as they are.
- First check against the real system: `uv run devops ci test tests/config/test_mode_yaml_booleans.py` fails on a bare `off` before the change and passes after it.
- Second check against the real system: `uv run devops ci test tests/commands/test_cli_startup_imports.py`, because `src/devops_cli/config/defaults.py` gains a `pydantic` import and the row counts the modules that a command imports.
- Third check against the real system: `uv run devops ci docs` shows the intake page in step with the settings.
- The third fault of the problem is answered: the `what_changes` list names no manifest path now, so the plan names no security trigger and `security` stays empty.

## Existing Tool Considered

Pydantic is the open, maintained library that the change uses: `BeforeValidator` runs the normalization before the `Literal` check, and pydantic has no built-in coercion from a YAML 1.1 boolean to a `Literal`, so the change writes one validator, at about 1k tokens and 10 minutes to build, keep and fix.

## Dependencies

None.
