# Proposal

## Why

The stage planner reads files and runs no command, so a plan can rest on a premise that only a run shows, and the read-only-looking command of #3218 deleted a config key. ADR 0018 gives the planner a run tool in a sandbox, and its second follow-up is this allow-list: the table of command paths that may run, and the refusal of every other path or parameter with one reason word. It plans #4004.

## What Changes

- Add `src/devops_cli/roadmap/stage/stage_run_allowlist.py`, which builds the allow-list from the read-only rows of the exposure table and narrows each restricted command to its allowed options.
- A command leaves the allow-list when a permitted parameter holds a path: a parameter that Typer types as a path, or a parameter that the path confinement table names, such as the text option `scan_sast.config`.
- A positional argument counts as a permitted parameter, so a command such as `scan sast`, whose target is a path argument, stays out.
- `check_command` returns a refusal that holds the command path and one reason word: `unknown command`, `not read-only`, `path option` or `option not permitted`, with the option name for the last one.
- The help form of a command path that the Click tree resolves is permitted, so the planner learns the options of a write command without running it.
- The allow-list keeps `vault get`, whose permitted parameters hold no file path and whose `show` option is withheld, so the command prints no credential.
- Add `tests/roadmap/stage/test_stage_run_allowlist.py` with one case for each scenario, a case for a text path option, and a census of the 144 rows of the exposure table.
- Add `stage_run_allowlist` to the module list of the `stage/` row in `docs/roadmap/package-layout.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The allow-list holds the read-only rows of the exposure table, A path parameter keeps its command out of the allow-list, A restricted command permits only its allowed options, The help form of a command path is permitted, A refused run names the path and one reason

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_run_allowlist.py`
- Documents: `docs/roadmap/package-layout.md`
- Tests: `tests/roadmap/stage/test_stage_run_allowlist.py`

## Feasibility

- The premise is that the staged commit holds the decision record and the tables that the issue names. The probe says, word for word: The path `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` is a file of the staging commit.
- The probe says, word for word: The path `src/devops_cli/config/constants.py` is a file of the staging commit. The read of lines 280 to 440 shows the table opening at `src/devops_cli/config/constants.py:285:CONST_MCP_EXPOSURE_TABLE: Final[tuple[tuple[tuple[str, ...], float, bool, bool], ...]] = (` and its last row at `src/devops_cli/config/constants.py:434: (("vault", "sync"), 60.0, False, False),`.
- The read counts 144 rows. The table runs from line 286 to line 434, which is 149 lines, and five of those lines are comments: 319, 361, 371, 397 and 399. The earlier count of 149 was the line count and not the row count; this plan states 144.
- The first group's census test walks every row of the table, decides each one, and stops when the count differs from 144, so a row that a later commit adds or removes fails the test.
- The probe says, word for word: The path `src/devops_cli/ai/mcp/generator.py` is a file of the staging commit. The read shows `src/devops_cli/ai/mcp/generator.py:37:_PATH_PARAM_RESTRICTIONS: dict[tuple[str, ...], dict[str, Any]] = {` and `src/devops_cli/ai/mcp/generator.py:193:def resolve_click_command(path: tuple[str, ...]) -> Any:`.
- The probe says, word for word: The path `tests/ai/mcp/test_path_confinement.py` is a file of the staging commit. The read shows the two path types at `tests/ai/mcp/test_path_confinement.py:20:from typer._click.types import File as TyperFile` and `tests/ai/mcp/test_path_confinement.py:21:from typer.models import TyperPath`.
- The probe says, word for word: The path `typer.models.TyperPath` is no file of the staging commit. No commit in the history deleted or renamed it. The read shows it is the class of the installed package that the audit imports at `tests/ai/mcp/test_path_confinement.py:21:from typer.models import TyperPath`, so the issue names no deleted file.
- The review's evidence line is `tests/ai/mcp/test_path_confinement.py:38:_TEXT_PATH_OPTIONS: Mapping[str, frozenset[str]] = {"scan_sast": frozenset({"config"})}`, and the read confirms it: it is the record of a text option that holds a path and that no type shows.
- The review's example is not exact. `src/devops_cli/commands/scan.py:376: target: Annotated[` and `src/devops_cli/commands/scan.py:377: Path,` show that `scan sast` also takes a positional target typed as a path, so the type check alone already leaves the row `src/devops_cli/config/constants.py:410: (("scan", "sast"), 300.0, True, False),` out of the table.
- The class of defect is real. `src/devops_cli/commands/scan.py:381: str,` shows that `config` is a text option, and `src/devops_cli/ai/mcp/path_confinement.py:65: "scan_sast": frozenset({"target", "config"}),` is the tested record that it holds a path, so a type check alone misses it.
- The corrected rule: the builder leaves a command out when a permitted parameter is typed as a path or is named by `PATH_CONFINEMENTS`, and the first group's test proves the second clause with a command whose only path parameter is a text option.
- `src/devops_cli/ai/mcp/path_confinement.py:23:PATH_CONFINEMENTS: Final[Mapping[str, frozenset[str]]] = {` holds the published path parameter of each tool, and `tests/ai/mcp/test_path_confinement.py:245: assert _undecided(_published_path_parameters()) == []` fails when a published path parameter is in neither table, so the builder reads one complete record.
- `src/devops_cli/ai/mcp/path_confinement.py:95: "vault_get": {` and `src/devops_cli/ai/mcp/path_confinement.py:96: "path": "A Vault secret path selects a secret from Vault, and the server opens no file.",` show that `vault get` publishes no file path, so its row `src/devops_cli/config/constants.py:432: (("vault", "get"), 60.0, True, False),` stays.
- `src/devops_cli/ai/mcp/generator.py:21:_IGNORED_PARAM_NAMES: frozenset[str] = frozenset({"help", "install_completion", "show_completion"})` and `src/devops_cli/ai/mcp/generator.py:296: if restrictions and p.name not in restrictions["allowed"]:` give the permitted set that the builder applies.
- `resolve_click_command(path)` needs a checkout of the repository, because it loads the module of the first path segment; it needs no client and no network.
- `build_allowlist()` calls `resolve_click_command` once for each of the 144 rows, so it needs the checkout that holds the command modules, no client and no network.
- `check_command(path, options)` calls `resolve_click_command` for the help form, so it needs the same checkout, no client and no network.
- A failure of `uv run devops ci test tests/roadmap/stage/test_stage_run_allowlist.py` is the failure class `test`, action `repair`; the image holds `uv`, `python`, `pytest` and `devops`, the plan introduces no program, and `NOT_IN_RUNNER` names nothing for it.
- A failure of `uv run devops ci docs` is the failure class `test`, action `repair`; the pod settings `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true` and `seccompProfile: RuntimeDefault` apply to both verifies.
- The module list of the `stage/` row in `docs/roadmap/package-layout.md` names `stage_request`, and the second group adds `stage_run_allowlist` beside it.
- The census decides each row from its own data: a row whose flag is false is removed with `not read-only`, a read-only row whose permitted parameter is a path is removed with `path option`, a row whose command the Click tree does not resolve is removed with `unknown command`, and every other read-only row is allowlisted.
- The review's finding is answered: the plan now states the 144 rows of the table, and the census test stops when the count differs, so the test passes on the base tree.

## Existing Tool Considered

Click and Typer give the command tree and the option types, and `CONST_MCP_EXPOSURE_TABLE`, `_PATH_PARAM_RESTRICTIONS` and `PATH_CONFINEMENTS` give the policy. No open, maintained library builds an allow-list of read-only Click commands from a project's exposure table, so the comparison logic is written here at 10k tokens to build, keep and fix, and 4 hours of elapsed work.

## Dependencies

None.
