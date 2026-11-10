# Proposal: #4308

## Why

The Service marks a green stage draft ready when its check runs pass (`stage_ready`, #2865). A passing check does not say that the plan delivers what its issue asks: about 10 of 37 plans of 2026-11-01 dropped an acceptance criterion. #2867 asks for a full draft evaluator. This item adds its first small part: one cheap decision from TypeSafe Jev (`typesafe/jev-1.14`), which holds a draft that it doubts. Closes #4308.

## What Changes

- Add `roadmap.stage.jev_completeness` (bool, default `false`).
- Add `src/devops_cli/roadmap/jev_completeness.py`. One Jev request holds one Noul question for each acceptance criterion of the issue and one Score question for the tests. The diff and the criteria are inline text. A criterion below `CONST_ROADMAP_JEV_CRITERION_THRESHOLD`, a test score below `CONST_ROADMAP_JEV_MIN_TEST_SCORE`, or an error of Jev holds the draft. A diff over `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`, no criterion, or more than `CONST_ROADMAP_JEV_MAX_CRITERIA` criteria skips the check with a logged reason.
- Call the check from `stage_ready` after the checks pass and before the draft is marked. A hold posts one note and records `stage.jev` with the head commit. The check never marks a draft ready, merges or closes.
- Add the counter `devops_cli_roadmap_jev_completeness_total` with the label `outcome` (4 series).
- Add `devops roadmap eval completeness` and a labelled set of 47 cases under `tests/fixtures/roadmap_eval/completeness/`.
- The change fits one pull request. It does not close #2867.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a requirement for the Jev completeness check in the row `stage_ready`.
- `roadmap-stage-eval`: a requirement for the labelled set and the command `devops roadmap eval completeness`.

## Impact

- Code: `src/devops_cli/roadmap/jev_completeness.py`, `src/devops_cli/roadmap/jev_completeness_eval.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/commands/roadmap_eval_completeness.py`, `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Tests: `tests/roadmap/test_jev_completeness.py`, `tests/roadmap/test_jev_completeness_eval.py`, `tests/roadmap/stage/test_roadmap_stage_ready_jev.py`
- Fixtures: `tests/fixtures/roadmap_eval/completeness/`
- Documents: `docs/ROADMAP_WORKFLOW.md` and the generated `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Cost: a check is one request of about 4 to 15K input tokens, about 0.0002 USD at 0.042 USD for one million input tokens. The live run of the set (47 requests) cost 0.0084 USD.
- Metric series: 4 (one for each outcome).

## Feasibility

- Confirmed on 2026-11-10 against the live gateway: `create_jev_model()` and one `DecisionRequest` with Noul and Score questions give calibrated probabilities. A second request on one model fails with "Event loop is closed", because the HTTP client of a model belongs to the event loop of its first `asyncio.run`. The check and the eval therefore build a new model for each request.
- Confirmed against `pydantic_ai.models.decision` (`DecisionRequest`, `NoulQuestion`, `ScoreQuestion`, `NoulAnswer`, `ScoreAnswer`) and `devops_cli.ai.jev.create_jev_model`.
- Confirmed that #2867 (open, status New) asks for a wider evaluator with a replay of PR #2801 and a verdict for each head commit; this item delivers one slice of its source-issue dimension and does not close it.
- Measured on the labelled set (see the pull request): the check does not meet the bar to go on. The recall of incomplete drafts is 43% and the false holds are 28%, above the limit of 10%. So the setting stays `false`.

## Existing Tool Considered

`danger/danger` (named in the alternatives check of #2867) runs rules over file patterns. It does not judge whether prose criteria are delivered by a diff. The change reuses `devops_cli.ai.jev.create_jev_model` and the upstream `DecisionModel` types, and builds no client or parser. Cost of building: about 15K tokens; keeping it: about 2K tokens a quarter; one day of elapsed time.
