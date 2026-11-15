# Design

## Decisions

- **Put the requirement in the capability `roadmap-refine/selection`.**: The inputs hold that file's requirements, among them "Only the limit stops a refine round", and `capabilities` lists the nested capabilities of the area and no flat `roadmap-refine`.
- **Change the queue subject in `MESSAGES.roadmap.inbox_subjects` and the queue item of `docs/roadmap/inbox.md` in one step with the two tests.**: The subject is the text that a person reads, and its only caller is the inbox line, so one message change reaches the line and one behavior group proves it.
- **Add "for the stage job only" inside the existing explain sentence and regenerate the two pages from it.**: `docs/commands/roadmap.md` and `docs/CLI_REFERENCE.md` mirror `HELP.roadmap.explain`, and `uv run devops ci docs` refuses a page that differs from the help.
- **Keep the readers of the setting unchanged: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/run.py` and `src/devops_cli/config/settings.py`.**: They hold every use of the setting, and the rule they implement is the one the owner stated.
- **Leave the stage requirement at `openspec/specs/roadmap-stage/selection/spec.md` as it is.**: Its text "The limit SHALL NOT apply to the filing of issues" is true for the stage job, and the new refine requirement names refine.
- **Edit no `README.md` line.**: `references` for `planned_limit` lists no `README.md` among its 50 files, so the line that the issue cites no longer holds the setting.
- **Make the queue subject and both tests one `behavior` group, and the help text one `other` group.**: The queue subject changes what a command prints, so its step starts with a failing test; the help catalog holds text whose generated pages `uv run devops ci docs` compares, so that step is a document edit with one command.
- **Seed 50 Planned items, set the limit with the `config` fixture, then run `plan_refine` and `apply_refine`.**: The round is the unit that the requirement names, and the fake store and `model_fake` reach no network and no cluster.
- **Name `tests/roadmap/test_roadmap_limit_classes.py` and `tests/roadmap/implement/test_roadmap_implement_amend.py` in the first group and change neither.**: The first is the table that a new roadmap limit joins, and the new case adds none; the second imports `MESSAGES`, and the new sentence keeps the catalog contract.

## Rejected alternatives

- **Run `devops roadmap refine` end to end against GitHub.**: It needs a client of GitHub and a model call, while the round test doubles both with the fake store and `model_fake` and reaches no network.
- **Write the requirement into a flat `roadmap-refine` spec.**: `list_files` of `openspec/specs/roadmap-refine` shows nested folders and no `spec.md`, and `capabilities` lists `roadmap-refine/selection`, `roadmap-refine/waits` and `roadmap-refine/proposal`.
- **Add a separate note after the explain sentence instead of naming the stage job in it.**: The reader can still read the setting as a rule of every job, and the generated page would carry two sentences where one names the stage job.
- **Set `skip_specs` to true and add no requirement.**: The change edits the explain help and the inbox queue line, which are observable `devops` messages, and it adds a rule that no living requirement holds.
- **Change the stage requirement to name refine.**: `openspec/specs/roadmap-stage/selection/spec.md:172:The limit SHALL NOT apply to the filing of issues.` is the stage job's rule and stays true, and a refine rule belongs to the refine capability.
- **Change the help text and its pages in a `behavior` group with a new test of the help string.**: The help catalog holds text, and `uv run devops ci docs` already refuses a page that differs from it, so a second test of the same text adds no check.
- **Copy the refine round case into a new test module.**: `tests/roadmap/refine/test_roadmap_refine_selection.py` already holds the round, the fixtures and the seed helper, so a new module would add setup for no new behavior.
