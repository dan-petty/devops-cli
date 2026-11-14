# Design

## Decisions

- **Base the new case on `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/`.**: Every gate accepts that plan, so the only problem the replay reports is the wrong constant, and its tracked files and change folder already match its groups.
- **Record `SUMMARY_MAX_CHARS` with 60 and state 40 in the `why` of the plan.**: `src/devops_cli/roadmap/pull_form.py` defines the constant at 60, and `constant_problems` gives exactly the message `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40.`
- **Record the defect with type `other` and gate `paths`.**: The replay's paths gate runs `check_proposal`, which runs the constants rule, and `GateName` has no constants member, so a new gate name would not be judged.
- **Reuse issue 3410 and pull 3435 for the new case.**: The reviewed set stays at 53 pulls, so the count test changes only its case count, from 59 to 60.
- **Add the new case to half A of `tests/fixtures/roadmap_eval/stage/split.json`.**: Half A holds 29 names and half B 30, so one more name in half A gives 30 and 30, and the split test then covers each case once.
- **Add a `--record` option to `devops roadmap eval stage` instead of a second command.**: The issue names the option, and the command already loads the cases and the replay path, so one entry point holds the reader and the recorder.
- **Record the constants from `staged_constants` at the case's base commit.**: The value must be the one of the commit that the case replays, and `staged_constants` is the reader that the stage job itself uses at `src/devops_cli/roadmap/stage/stage.py:2230`.
- **Write the constants into the existing facts file of a case.**: `load_cases` reads one `facts.json` for each case, so a second file would add a path to load and to record.
- **Keep the tuple of name and integer value pairs in `CaseFacts`.**: `PlanUnderTest.of_case` reads `dict(case.facts.constants)`, and the empty default keeps every recorded case valid.
- **Give the new option a literal help text in the command module.**: `src/devops_cli/commands/ai_gateway.py:783:typer.Option("--apply", help="Write rendered gateway configuration to file."),` shows the same shape, and the help catalog would add a module whose test this change does not need.
- **Regenerate `docs/commands/roadmap.md` and no other generated page for the new option.**: `docs/CLI_REFERENCE.md:3:holds the full text of each command: its usage, its arguments and its options.` is an index of the group pages, and `docs/commands/roadmap.md` holds the option table that gains the row.
- **Read `tests/roadmap/implement/test_roadmap_implement_amend.py` in the recorder group.**: It is the one test that imports the messages module, and the tests gate refuses a group that changes `src/devops_cli/lang/en/messages.py` and names no existing test of it.
- **Document the field in the module docstring and the `CaseFacts` docstring.**: `docs/roadmap/eval.md` does not exist, and the two docstrings are where a reader looks for the shape of the facts file and its fields.

## Rejected alternatives

- **Cite `uv run devops roadmap eval stage --record --case 3410` as a first check of the plan.**: The option does not exist at the staged commit: `src/devops_cli/commands/roadmap_eval_stage.py:def eval_stage_cmd` holds `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--replay`, `--cases`, `--source` and `--no-toolbox`, so the plan check refuses that command.
- **Leave the recorder for a separate issue and record the new case by hand.**: The issue asks to "Make `devops roadmap eval stage --record` (or the recorder that builds a case) store the constants that the plan cites, so a new case holds the values without a hand edit." The option is small, and it reuses `candidate_names`, `staged_constants` and `plan_texts`.
- **Add `docs/roadmap/eval.md` to document the field.**: The probe says "The path `docs/roadmap/eval.md` is no file of the staging commit. No commit in the history deleted or renamed it.", and the issue makes that document conditional on its existence.
- **Regenerate `docs/CLI_REFERENCE.md` for the new option.**: `docs/CLI_REFERENCE.md:3:holds the full text of each command: its usage, its arguments and its options.` shows that the file is an index of the group pages, so an option adds no text to it; the option table is in `docs/commands/roadmap.md`.
- **Record `CONST_AGENTS_MD_MAX_CHARS` with the value 6500.**: The copied plan does not cite that bound, so the case would invent the citation; `SUMMARY_MAX_CHARS` is the constant that the constants rule already names in the stage eval test at `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:681:def test_the_replay_passes_recorded_constants(cases: list[StageCase]) -> None:`.
- **Add a `constants` member to `GateName` and record that gate.**: `src/devops_cli/roadmap/stage/stage_eval_cases.py:99:class GateName(StrEnum):` has no such member, and the replay runs the constants rule inside the paths gate, so a new gate name would leave the defect unjudged.
- **Replace the tuple of `CaseFacts.constants` with a mapping.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:145:constants=dict(case.facts.constants),` reads the tuple, and every recorded case keeps the tuple shape with an empty default.
- **Leave `tests/fixtures/roadmap_eval/stage/split.json` unchanged.**: `tests/roadmap/stage/test_roadmap_stage_screen_eval.py` asserts that the two halves hold every case once, and that test fails when a case joins the folder and no half names it.
