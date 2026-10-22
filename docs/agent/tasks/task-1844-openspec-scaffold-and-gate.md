# Task: Scaffold OpenSpec and Gate Its Change Folders in devops ci (#1844)

**Issue**: [#1844](https://github.com/dan-petty/devops-cli/issues/1844)
**Scope**: type/feature
**Feasibility**: Checked on 2026-10-22 against OpenSpec 1.14.3 (the lock's pin, installed from the committed lockfile), Node 24.22.0 and git 2.55.0, in scratch directories under `/tmp` with a scratch `HOME` and `XDG_CONFIG_HOME` and the opt-outs set. `openspec init --tools claude,agents` under the isolated `custom` profile (telemetry off, delivery `skills`, four workflows) wrote the 12 files of 127,479 bytes the ADR lists: four `SKILL.md` in each tree, byte-identical and each `generatedBy: "1.14.3"`, `.agents/skills/.openspec-target`, `openspec/config.yaml` and two `.gitkeep`. `openspec update --force` left that tree as it was, in a copy holding only the skills and an empty `openspec/` as well, rewrote a hand-edited skill and removed a hand-made `openspec-archive-change` ("Removed: 1 skill directories (deselected workflows)"). It finds an agent by the skills it holds: in a tree with no skill it printed "No configured tools found" and wrote nothing, with one `openspec-*` skill in `.claude/skills/` or the `.agents` marker alone it wrote that agent's four skills, and with empty skill directories or only another skill it wrote nothing. With a global configuration of the `core` profile and delivery `both` in `XDG_CONFIG_HOME`, a bare `openspec update --force` rewrote six skill files, added the archive and sync skills in both trees and a `.claude/commands` tree, while `devops openspec check` and `regenerate` under the same environment left the tree as it was and reported a hand edit and an added archive skill. The ADR's configuration rendered through `openspec instructions` for the proposal, specs, design, tasks and apply operations with an empty standard error; a rule YAML reads as a mapping warned on all five, a rule under an unknown artifact on the first four, a 50.8 KB context on all five, each with exit 0, and an unknown top-level key said nothing. `validate --all --strict` listed a `MODIFIED` of a spec that does not exist as an `[INFO]` and passed it, while `archive` refused it with exit 1 and "No files were changed"; archiving a change without a Purpose wrote the placeholder, which `validate --specs --strict` then failed; a duplicate `ADDED` with other text was refused; an identical one archived as a no-op; two changes that `MODIFY` one requirement both archived. `openspec show <change> --json --deltas-only` names the requirement of a `MODIFIED` or `REMOVED` delta in `requirement.name` and of a `RENAMED` one in `rename.from`. A change with `skip_specs: true` and no delta validated and archived with `specsUpdated: false`. `validate --all --strict`, `--archived`, `--specs --strict` and `list --json` exit 0 on a tree with no spec and no change. `git log --topo-order --reverse --diff-filter=A --name-only` lists a renamed folder's `.openspec.yaml` only with `--no-renames`. The gate took 4.0 to 4.5 s on the repository (16 cores). `extra_allowed_env` keeps only a variable the parent already has, so the opt-outs are set through `env`. `devops gh api` resolved the tag v7.1.0 of `actions/setup-node` to the commit `949feb2413d6458794dcd2491c4babbbce0c15c1`. The harness refused an agent's edit of `.claude/settings.json`, Claude Code's own permission configuration, so those entries are a person's, and this item is delivered as a part (see the Acceptance Criteria).

## Description

The repository has somewhere to plan into and a gate that keeps a plan valid. OpenSpec's `validate`, `archive`, `instructions`, `update` and generated skills are used as shipped with the default `spec-driven` schema; the code is the glue [ADR 0010](../../adr/0010-openspec-is-the-spec-and-change-proposal-layer.md) names, and nothing is deleted.

- **The scaffold.** `openspec/config.yaml` is the ADR's file, every rule a folded scalar, with `openspec/specs/.gitkeep` and `openspec/changes/archive/.gitkeep`. The eight `SKILL.md` of the propose, explore, apply and update workflows sit in `.claude/skills/openspec-*/` and `.agents/skills/openspec-*/` beside `.agents/skills/.openspec-target`, as `openspec init` wrote them. `.gitignore` re-includes only `.claude/skills/openspec-*/`, so other skills, `settings.local.json` and worktrees stay ignored.
- **`devops openspec check`** (`src/devops_cli/commands/openspec.py`, `src/devops_cli/openspec/gate.py`) runs the pinned tool five ways and reports every problem with the check that found it: `validate --all --strict`; `validate --archived`; a regeneration of the skills in a scratch copy, compared with the tree (a changed file, one the regeneration adds, one it removes), and a finding for each glob of the generated files that matches no file, because `update` cannot write back a tree deleted whole; the instructions of a probe change for the proposal, specs, design, tasks and apply operations, with any output to standard error a finding; and the rehearsal of the cut, which archives every active change in a scratch copy of `openspec/`, in merge order, then runs `validate --specs --strict`, and ends with the overlap check. It passes a tree with no change and no spec, and fails first, naming `uv run devops install-tools --tool openspec --only-missing`, when `openspec` is not on PATH.
- **The child environment** (`src/devops_cli/openspec/tool.py`). Every run sets `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`, `OPEN_SPEC_INTERACTIVE=0` and an `XDG_CONFIG_HOME` that is a scratch directory holding the isolated configuration (`telemetry.enabled false`, `delivery skills`, `profile custom` and the four workflows, set with `openspec config set`), which goes when the run ends. The ADR names `extra_allowed_env`, which keeps only a variable the parent already has, so the values go through `env`.
- **`devops openspec regenerate`** (`src/devops_cli/openspec/skills.py`) runs `openspec update --force` in the checkout under that isolated configuration, and a bare `openspec update` is never run. Under `--dry-run` it starts nothing.
- **The archive function** (`src/devops_cli/openspec/archive.py`). `merge_order` orders folders by the commit that added each `.openspec.yaml` (`git log --topo-order --reverse --no-renames --diff-filter=A`), folders not yet committed last, ties by the issue read as a number. `archive_sequence` archives names in order with `openspec archive <name> --yes --json` and stops at the first refusal with `OpenSpecArchiveError`. `archive_complete_changes` is the cut's: it takes the changes `openspec list --json` calls `complete`, plans the sequence in a scratch copy first and only then runs it in the tree. The gate's rehearsal calls `archive_sequence`, so what it rehearses is what the cut runs; the cut itself calls the function in #1846. `scratch_copy` refuses a symbolic link under `openspec/`, which a copy would follow out of the folder, and the rehearsal reports it as the one finding. Cost, an estimate: about 150 lines and 11 test scenarios, some 30,000 tokens to write and test, some 15,000 more to fix until its order and its refusals matched the tool, near none to maintain while `archive --json` and `list --json` keep their shape, and about three hours of elapsed time. `OpenSpecFake` serves this function and the overlap check alike, over the runs recorded from the real tool, so neither needs a double of its own.
- **The overlap check** (`src/devops_cli/openspec/overlap.py`) reads `openspec show <change> --json --deltas-only` for each active change and reports a (capability, requirement) that two of them `MODIFY`, `REMOVE` or `RENAME`. OpenSpec's bulk-archive conflict detection is an agent skill, not a command, so no open tool does it; the module is deleted when OpenSpec ships a deterministic check (the ADR's Revisit Conditions). Cost, an estimate: about 60 lines and two test scenarios, some 10,000 tokens to write and test, near none to maintain while `show --json` keeps its shape, and about an hour of elapsed time.
- **The `openspec` row** of `devops ci` runs `uv run devops openspec check` in every run with no path filter and no exemption. The pre-commit hook `openspec-gate` runs `uv run devops ci --only openspec` when a commit touches `openspec/`, `.claude/skills/` or `.agents/skills/`. The `static` job of `ci.yml` checks out the full history, because the rehearsal reads the cut's order from git, runs `actions/setup-node` pinned to v7.1.0 by its commit with `node-version-file: .node-version`, and installs the pin with `uv run devops install-tools --tool openspec --only-missing` before the gate. `.github/workflows/copilot-setup-steps.yml` is written by hand with the same pinned actions, the pinned install and the opt-outs; `openspec init --copilot-cloud` is not used, because its workflow runs an unpinned `actions/checkout@v4` and `npm install -g`.
- **Documents.** `openspec/changes/**/*.md` is class `record`, `openspec/specs/**/*.md` class `release artifact`, and the eight `SKILL.md` a new class `tool-generated`, which is not name-checked; the review routing gains `openspec/**` and the generated skill globs and keeps the task-file entry until the switch. `devops openspec check` and `regenerate` are excluded from the MCP tools, as `devops docs check` and `install-tools` are. The bump runbook in the header of `tools.lock` gains the regeneration and the gate; `RELEASE_CYCLE.md`, `SDLC.md`, the gate's knowledge-base page and `TESTING.md` name the row and the fake; AGENTS.md's CI row ends "docs, deps, openspec)" and the file ends at 39,953 of its 40,000 characters; ADR 0010 says that the values go through `env` and that the `static` checkout is full.
- **Tests.** `tests/test_change_folders.py` holds every active folder to the name `<issue>-<slug>`, a proposal with `## Feasibility` and `## Existing Tool Considered` found with markdown-it, a `tasks.md` with a `## <n>.` group holding a task-list item, and no PR, Status, Milestone or Priority line. `tests/test_openspec_scaffold.py` parses the configuration with `yaml.compose` (only `schema`, `context`, `rules` and `operations`, and only folded or literal scalars), reads `generatedBy` of all eight skills against the pin, compares the two trees, checks what git keeps, the inventory classes, the routing and the hook; `tests/test_workflow_contracts.py` checks the `static` job and `copilot-setup-steps.yml`, and `tests/test_agents_md_claims.py` the CI row. `tests/test_openspec_gate.py`, `test_openspec_archive.py`, `test_openspec_command.py`, `test_openspec_tool.py` and `test_openspec_contract.py` run the gate, the archive function and the commands over `OpenSpecFake`, which replays the real tool's runs recorded over twelve scenarios, writes the skills `update --force` writes, and answers a failure no recording holds (a tool that dies without JSON or runs past its timeout) when a test scripts it; the merge order is tested with real git in `tmp_path`.

## Acceptance Criteria

- [x] `uv run devops ci` runs an `openspec` row, passes on the empty tree, and fails with a clear message when `openspec` is missing, naming `uv run devops install-tools --tool openspec --only-missing`. The real gate passed the repository's empty tree in 4.3 s and failed with the message on a PATH without the tool; `tests/test_openspec_gate.py` checks the commands of the empty tree in order and the missing tool (exit code 1, `DEPENDENCY_MISSING`, no process started), and `tests/test_openspec_command.py` the exit code and output of both cases.
- [x] `uv run devops openspec regenerate` leaves the tree unchanged under any developer's global profile, and `check` fails when a skill file was hand-edited or the profile is wider. The real tool did, as the Feasibility field records; `tests/test_openspec_command.py` checks that `regenerate` sets the four isolated settings and runs `update --force` and never a bare `update`, `tests/test_openspec_gate.py` that every run opts out under a configuration directory of its own whatever the environment says, and that a hand-edited skill, an added archive skill, a deleted skill and a skill tree deleted whole are each reported.
- [x] `check` fails a change that passes `validate` but would not archive and a requirement modified by two active changes. `tests/test_openspec_gate.py` reports, from the real tool's recorded runs, a missing Purpose, a `MODIFIED` of a spec that does not exist, a duplicate `ADDED`, a requirement modified twice and a requirement renamed and modified, each by the check that finds it; that a change archives after the change whose requirement it modifies, whatever the issue numbers; and that a change declaring `skip_specs` passes. `tests/test_openspec_archive.py` tests the order with real git: history order, a change authored on top of another, 999 before 1000, folders not yet committed last, a renamed folder; and that the cut archives only complete changes, in a scratch copy first, and writes nothing when the tool refuses one or when `openspec/` holds a symbolic link.
- [x] `tests/test_change_folders.py` fails a folder not named `<issue>-<slug>`, one with no `tasks.md` group and one carrying a `Status` line, and `tests/test_openspec_scaffold.py` fails a plain scalar rule and an unknown key, each with its line.
- [x] The inventory classifies every new Markdown file and `devops docs check` passes.
- [x] The pre-commit hook and the `static` job run the row, `copilot-setup-steps.yml` exists, and AGENTS.md is within its 40,000-character cap (39,953). `devops ci --dry-run` lists the row, and `tests/test_openspec_scaffold.py` checks the hook and `tests/test_workflow_contracts.py` both workflows and that every remote action is pinned.
- [x] The tests that replay the tool hold the record to the pin and to the gate's commands: `tests/test_openspec_contract.py` fails when the record is not of the locked version, when a scenario is not recorded, and when the record holds a run the gate no longer starts.
- Not done: the `permissions` entries in `.claude/settings.json` and the test that reads them. They are the last part of #1844. An agent's session may not edit that file, so a person applies the JSON kept below, and the last part adds the test.
- Pending a person: after the release that carries `.github/workflows/copilot-setup-steps.yml` merges to `main`, run the workflow once from the Actions tab and confirm that a Copilot cloud agent session finds `openspec` on its PATH. GitHub runs the file only from the default branch, so until then that agent finds the committed skills and no binary.
- Pending a person: with a devcontainer rebuilt after #1842, run `uv run devops ci` and expect every row, the `openspec` row included, to pass with `openspec` on PATH.

## Deliverables

- [x] `src/devops_cli/commands/openspec.py` and `src/devops_cli/openspec/` (`tool.py`, `gate.py`, `skills.py`, `archive.py`, `overlap.py`), registered in `src/devops_cli/main.py`; `OpenSpecArchiveError` in `src/devops_cli/exceptions/tools.py`; the constants in `src/devops_cli/config/constants.py`, the timeout in `defaults.py`, the command builders in `commands.py`, the messages and help in `lang/en/`; the `openspec` row in `src/devops_cli/commands/ci.py`.
- [x] `openspec/config.yaml`, the two `.gitkeep`, the eight `SKILL.md` and `.agents/skills/.openspec-target`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/workflows/copilot-setup-steps.yml`, the header of `src/devops_cli/tools_lock/tools.lock`, and the CI row in `AGENTS.md`.
- [x] The tests named above, `OpenSpecFake` in `tests/support/fakes/openspec.py`, the scenarios in `tests/support/openspec_scenarios.py`, the recorder in `tests/support/openspec_recording.py` and its record in `tests/fixtures/openspec_runs/recorded_runs.json`, the allowance for the install step in `tests/test_ci.py`, and the new command in the expected list of `tests/test_otel_command_coverage.py`.
- [x] The regenerated CLI reference and error catalogue, the documents named above and the `command` variable of `k8s/monitoring/dashboards/devops-cli.json`, which lists every command.
- The changelog fragment `changelog.d/1844.md`: the last part of #1844 adds it, because a part adds none.
- `GEMINI.md` and its generator: #1845.
- The cut's call of `archive_complete_changes`, its `_cut_makes` allowances and its report: #1846.

## Permission Entries Kept for the Last Part

A person applies this change to `.claude/settings.json` and leaves its `env` block as it is. The last part of #1844 then adds the test below to `tests/test_openspec_scaffold.py` and removes this section. Every generated skill carries `allowed-tools: Bash(openspec:*)`, and Claude Code evaluates deny rules before allow rules. A deny entry therefore holds where a narrow allowlist would not. No bare `Bash(openspec *)` is allowed.

```json
"permissions": {
  "allow": [
    "Bash(uv run devops *)",
    "Bash(openspec status *)",
    "Bash(openspec list *)",
    "Bash(openspec instructions *)",
    "Bash(openspec context *)",
    "Bash(openspec show *)",
    "Bash(openspec schemas *)",
    "Bash(openspec validate *)",
    "Bash(openspec new change *)"
  ],
  "deny": [
    "Read(//**/.claude/settings.local.json)",
    "Read(~/.claude/settings.json)",
    "Read(~/.kube/**)",
    "Bash(openspec init *)",
    "Bash(openspec update *)",
    "Bash(openspec archive *)",
    "Bash(openspec config *)",
    "Bash(openspec completion *)"
  ]
}
```

```python
ALLOWED_OPENSPEC_VERBS = (
    "status",
    "list",
    "instructions",
    "context",
    "show",
    "schemas",
    "validate",
    "new change",
)
DENIED_OPENSPEC_VERBS = ("init", "update", "archive", "config", "completion")


def test_the_settings_allow_the_verbs_the_skills_call_and_deny_the_ones_that_write() -> None:
    """Every generated skill carries `allowed-tools: Bash(openspec:*)`, which grants the whole verb
    set during the turn, and Claude Code evaluates deny rules before allow rules, so a deny entry
    holds where a narrow allowlist would not. No bare `Bash(openspec *)` is allowed."""
    settings = json.loads((REPO_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    permissions = settings["permissions"]

    def openspec_rules(kind: str) -> list[str]:
        return [rule for rule in permissions[kind] if rule.startswith("Bash(openspec")]

    assert (openspec_rules("allow"), openspec_rules("deny")) == (
        [f"Bash(openspec {verb} *)" for verb in ALLOWED_OPENSPEC_VERBS],
        [f"Bash(openspec {verb} *)" for verb in DENIED_OPENSPEC_VERBS],
    )
```
