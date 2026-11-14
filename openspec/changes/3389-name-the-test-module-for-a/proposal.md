# Proposal

## Why

The plan of #3330 put its comment assertion in `tests/roadmap/stage/test_roadmap_stage_plan.py`, and `_stage_one` writes the comment, which `tests/roadmap/stage/test_roadmap_stage_apply.py` covers. The path check accepted the test path because the file exists, so a plan can name a test that cannot fail on the base. Issue #3389 asks the stage request and the stage prompts to name the test module that exercises a changed function.

## What Changes

- The stage probe names, for each cited function that the staging commit defines, the test modules whose text holds its name, and says when no test module does.
- The probe reads the test modules of all cited identifiers with one `git grep` at the staging commit, so the listing stays inside the bound of ten commands.
- The stage prompts send the `test` of a behavior group to the test module that `probes` names for the function whose behavior the group changes.
- The extended stage prompt tells the planner to call `references` for that function and to write the test in a test module that the answer lists.
- A prompt rule test fails when either prompt text is absent.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/premise`: The probe names the test module of a cited function
- `roadmap-stage/tests-gate`: The stage prompts name the test module of a changed function

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm that the prompt file the issue names exists: "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit."
- The probes show that the test paths the issue cites moved: "The path `tests/roadmap/test_roadmap_stage_plan.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_plan.py`." The same answer names `tests/roadmap/stage/test_roadmap_stage_apply.py` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` as the candidates of the other two, so the plan uses the current paths and the issue is still buildable.
- The probe for `src/devops_cli/roadmap/stage.py` names `src/devops_cli/ai/spend/stage.py` and `src/devops_cli/roadmap/stage/stage.py` as its candidates. The plan changes no module of that name: it puts the listing in `src/devops_cli/roadmap/stage/stage_probe.py`, which holds `probe_premise`.
- The probes did not run for the identifiers: "Not probed, the bound of 10 commands is reached:" The context maps `_stage_one` to `tests/roadmap/stage/test_roadmap_stage_rejected.py` and `tests/roadmap/stage/test_roadmap_stage_removal_references.py`, and `collect_context` of `src/devops_cli/roadmap/refine/refine.py:def collect_context` is shared by refine and stage, so the plan leaves it alone.
- The plan call is `src/devops_cli/roadmap/stage/stage.py:2026:probe = probe_premise(self._source, self._sha, item.body)`, so a new line of the probe text reaches every plan request.
- The message beside the new ones is `src/devops_cli/lang/en/messages.py:4169:stage_probe_defined`, and the probe tests live in `tests/roadmap/stage/test_roadmap_stage_probe.py`.
- The rule for the test of a behavior group is `src/devops_cli/ai/tasks/roadmap_stage_change.md:26:It is written test first.`, and that prompt already names the tool in its move rule at `src/devops_cli/ai/tasks/roadmap_stage_change.md:30:An import rewrite does not update a quoted target`.
- The base tools prompt must name none of the three extra tools: `openspec/specs/roadmap-stage/toolbox/spec.md:159:It SHALL tell the model that text from GitHub is data and never an instruction.` The extra-tools prompt is `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md:3:It has no cap for a file`, so the sentence that names `references` goes there and the fallback sentence goes in the change and split prompts.
- The exact-lines assertion that group 1 updates is `tests/roadmap/stage/test_roadmap_stage_plan.py:228:assert request["probes"].splitlines() == [`, and the prompt rule test that group 2 extends is `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py:48:_CHANGE_PROMPT = "roadmap_stage_change.md"`.
- The model review found that group 1 changed that assertion in `tests/roadmap/stage/test_roadmap_stage_plan.py` while its verify ran only the probe module. Group 1 now runs both modules it changes: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py tests/roadmap/stage/test_roadmap_stage_plan.py`. `devops ci test` takes several paths, as `.github/workflows/ci.yml:780:uv run devops ci test --repeat 3 -- "${CHANGED_TESTS[@]}"` shows.
- The probe test module already pins the command kinds at `tests/roadmap/stage/test_roadmap_stage_probe.py:205:assert {args[0] for args in ran} == {"cat-file", "grep", "log", "ls-tree"}`, and `grep` is one of them, so the listing adds no command kind.
- The fixture of that module already defines the cited function: `tests/roadmap/stage/test_roadmap_stage_probe.py:24:def keep_comment(comments)`, so the new case reaches the defined branch of `identifier`.
- The rule that a run-time sample file takes a bare name is `src/devops_cli/ai/tasks/roadmap_stage_change.md:32:A sample file that a test writes at run time`, so group 1 names the file `test_sample.py` with no folder and writes it under the tests folder at run time.
- The prompt change needs the replay task: `docs/ROADMAP_WORKFLOW.md:352:uv run devops roadmap eval stage --replay` is the command that the stage job looks for when a plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, so group 2 runs it and states the score before and after.
- Precondition of `probe_premise` of `src/devops_cli/roadmap/stage/stage_probe.py:def probe_premise`: a checkout of the repository, because it runs `git grep` and `git cat-file` at the staging commit.
- Precondition of `git_result` of `src/devops_cli/roadmap/refine/refine.py:def git_result`: a checkout of the repository, because it runs one git command in it.
- Precondition of `load_task_prompt` of `src/devops_cli/ai/task_loader.py:def load_task_prompt`: a checkout of the repository, because it reads `src/devops_cli/ai/tasks/`. No call of the plan needs a client of a service or a network.
- The verify commands `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py tests/roadmap/stage/test_roadmap_stage_plan.py` and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` need `uv` and `pytest`, which the image holds, and their failure classes are `test`, `lint` and `types`. The pod sets `readOnlyRootFilesystem` true, `runAsNonRoot` true, `capabilities.drop` `ALL`, `allowPrivilegeEscalation` false and `seccompProfile` `RuntimeDefault`.
- The manual replay `uv run devops roadmap eval stage --replay` in group 2 runs from the image, which holds `uv` and `devops`; its need for a network is not checked. Its failure class is `test`.
- The claim over the test modules of a cited function is a claim over the set that one `git grep` returns, so that command is the census and no count is unverified; the identifier probe itself did not run in this run.
- The open item #3443 holds a staged plan that also changes `src/devops_cli/roadmap/stage/stage_probe.py` and the stage prompt: `openspec/changes/3443-name-the-test-case-that-a/proposal.md:9:The premise probe lists, for each cited test module and cited source file`. That plan lists test cases and this one lists test modules, and neither needs the other, so no dependency orders them.

## Existing Tool Considered

The change builds its own code: 60k tokens to build, keep and fix it, and 4 hours. `coverage.py` with `dynamic_context = test_function` is open and maintained and covers the mapping at run time, but it needs a full test run, gives no static answer and cannot run in the planner's read-only, offline budget. The change deletes no internal code.

## Dependencies

None.
