# Proposal

## Why

The spec delta gate of the stage job and `devops openspec check` compare requirement titles as exact strings, so a planner adds a requirement that repeats one of the base spec or of another active change under a new title and the rule of ADR 0010 does not hold (#4133). A person measured each text signal on 132 merged change folders and 391 added requirements: the signals that catch both copies of the incident refuse merged plans that hold no duplicate, and ADR 0005 keeps a finding from a model out of a gate. The plan gives the planner the scenarios and the active changes before it writes a requirement, and names the active change as a blocker.

## What Changes

- Add `ActiveRequirement` and `read_active_requirements` to `src/devops_cli/roadmap/stage/stage_specs.py`, which read the added and the modified requirements of each active change for one capability.
- List the scenario of each requirement and the requirements of the active changes in the `read_spec` answer of `src/devops_cli/roadmap/stage/stage_tools.py`.
- State the rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `docs/roadmap/stage.md`: read the requirements of a capability before adding one, modify the requirement that holds the behavior, and name the active change as a blocker.
- Add the two requirements to `roadmap-stage/toolbox` and `roadmap-stage/spec-delta`.
- Keep the plan review as the judge of a paraphrase and add no gate that compares requirement text, because ADR 0005 keeps a finding from a model out of a gate and the measurement of 2026-11-13 shows that each text rule either misses the incident or refuses merged plans.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/toolbox`: The tool read_spec lists the scenario of each requirement
- `roadmap-stage/spec-delta`: The stage prompt names the active change as a blocker

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage_tools.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise of the issue holds at the staged commit, and the probe line reads, word for word: The path `src/devops_cli/roadmap/stage/stage_specs.py` is a file of the staging commit. That module gives the model the names only, because its entry builder holds `return {"name": name, "purpose": self.purpose, "requirements": list(self.requirements)}`.
- The spec delta gate that the issue cites is in the file that the probe names: The path `src/devops_cli/roadmap/stage/stage_change.py` is a file of the staging commit, and its gate member holds `SPEC_DELTA = "spec-delta"`.
- The issue cannot be built as written as a gate on the text of a requirement, and this plan compensates for none of it. The comment of 2026-11-13 by dan-petty measured each text signal on 132 merged change folders and 391 added requirements and reports "| Equal normalized WHEN and THEN text of one scenario (the design) | No | 0 |" and "| Equal scenario name and equal WHEN text on one scenario | Yes, 2 of 2 | 4, in 2 plans |", so the rule of the proposed design catches neither copy of the incident, and each signal that catches both refuses merged plans that hold no duplicate.
- The same comment names the alternative: "#3246 adds the requirement text to the stage context. With the scenarios of the active changes in that context, the planner can see the requirement to modify before it writes a new one, and the model review keeps the semantic check." This plan gives the planner the scenarios and the active changes, and keeps the semantic check in the plan review.
- The tool answer holds requirement names only: `src/devops_cli/roadmap/stage/stage_tools.py:366:listed = [*([f"Purpose: {purpose}"] if purpose else []), *found]`, while the OpenSpec JSON already holds the scenarios, as `src/devops_cli/roadmap/stage/stage_tools.py:496:for scenario in entry["scenarios"]:` shows.
- The document that states the answer today is `docs/roadmap/stage.md:94:| Capabilities | The names only. `read_spec` gives the purpose and the requirements of one capability on demand. |` and the change updates it.
- The set that the reader walks is the active change folders: the tool `list_files` on `openspec/changes` gave 46 folders besides archive, so the reader reads at most 46 delta files for one capability. Each member is restricted to a change that holds a delta file for the named capability, and no member is allowlisted or removed; the count is 46.
- The reader reuses the patterns that the module already defines: `src/devops_cli/roadmap/stage/stage_specs.py:24:_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement:[ \t]*(.+?)[ \t]*$", re.M)` and `_SCENARIO_NAME: Final[re.Pattern[str]] = re.compile(r"^#### Scenario:[ \t]*(.+?)[ \t]*$", re.M)`, so the change adds no new name for a bound that the staged tree defines.
- Precondition of `read_active_requirements`, which the plan adds to the module at `src/devops_cli/roadmap/stage/stage_specs.py:79:def read_base_specs(source: Path, tool: OpenSpecTool | None) -> dict[str, BaseSpec]:`: a checkout of the repository, because it reads the delta file of each active change, and no network.
- Precondition of `read_spec` at `src/devops_cli/roadmap/stage/stage_tools.py:343:def read_spec(self, capability: str = "", requirement: str = "") -> ToolReturn:`: a checkout of the staged commit and a client of OpenSpec, and no network.
- Precondition of `uv run devops roadmap eval stage --limit 5`: a network, because it calls a model provider.
- The first checks that the implementation runs against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then the live score `uv run devops roadmap eval stage --limit 5`.
- The failure classes and the runner capabilities: `uv run devops ci test` gives `test`, `lint` and `types` with the action `repair`, and the live score gives `provider` and `timeout` with the action `retry`. Every program is in the image (`uv`, `devops`, `git`, `pytest`, `openspec`), and none is `NOT_IN_RUNNER`.
- Each command runs in the runner pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The plan changes no check of the stage job, so it gives no replay of the golden set: the prompt change gives the live score, which a replay cannot move because the replay calls no model. It adds no copy rule and no check in `devops openspec check`, because the measurement above shows that such a rule refuses no copy of the incident.

## Existing Tool Considered

OpenSpec (Fission-AI/OpenSpec, MIT, maintained) holds the requirement and scenario text of the capabilities and of the active change deltas, and its checks refuse an exact duplicate ADDED requirement at the archive; no check compares a scenario with a base requirement or with a requirement of another active change, and no problem names both titles. The change therefore reads the delta file of each active change itself: about 12000 tokens to build and test, about 2000 tokens a year to keep and fix, and about half a day. It deletes no module.

## Dependencies

- #3246: it adds the requirement text to the stage context and moves the purpose and the requirement names of a capability into the `read_spec` answer, so its text lands before this change extends the same module and the same prompt paragraph.
