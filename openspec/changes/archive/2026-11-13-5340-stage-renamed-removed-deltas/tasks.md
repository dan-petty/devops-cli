# Tasks

## 1. The stage job writes and checks RENAMED and REMOVED deltas

Kind: behavior

- [x] 1.1 Write failing tests: the plan of #5182 with a rename renders a RENAMED block that the pinned `openspec validate --strict` accepts against its base spec, a removal renders a REMOVED block with its reason and its migration, the gate refuses an unknown FROM, an unknown removed name, a TO that the base spec has and a rename on a new capability, the scenario copy reads the base scenarios under the old name, and the stale-command check accepts a removed or a renamed and modified base requirement
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_renames.py`
- [x] 1.2 Add `StageRename` and `StageRemoval` with the fields `renamed` and `removed` of `StageSpec`, write them in `spec_file`, list them in the capabilities of `proposal.md` and in `plan_texts`, check them in `_delta_problems`, map the new name to the old name in `restore_omitted_scenarios` and in `_stale_command_problems`, and add the messages
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_renames.py tests/roadmap/stage/test_roadmap_stage_specs.py tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py tests/roadmap/stage/test_roadmap_stage_plan.py`

## 2. The plan reader and plan-check read the deltas back

Kind: behavior

- [x] 2.1 Write failing tests: the real RENAMED delta of #5150 and the real REMOVED delta of #4798 read back with their names, reasons and migrations, a FROM line with no TO line is a read error, a REMOVED block with no reason is a read error, the property test generates renames and removals, and plan-check reports no moved spec for a requirement that a plan renames and modifies
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py`
- [x] 2.2 Read the two sections in `_spec` of `plan_read.py`, and compare a MODIFIED requirement under a new name with the base text under its old name in `_moved_problems` of `plan_check.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py`

## 3. The prompts ask for a fitting name

Kind: behavior

- [x] 3.1 Write failing tests: the reply keys of the stage prompt name the fields of `StageRename` and `StageRemoval`, the stage prompt tells when to rename and when to remove, and the review prompt makes a modified requirement whose name no longer fits its text a `spec_delta_wrong` finding
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 3.2 Update `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## 4. Documents

Kind: other

- [x] 4.1 Describe the four delta kinds in `docs/roadmap/stage.md`, and the moved-spec check under a rename in `docs/roadmap/plan-check.md`
  - Verification: `$ uv run devops ci --check --only docs,openspec`
- [x] 4.2 Check that the generated documents are current
  - Verification: `$ uv run devops docs generate --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
