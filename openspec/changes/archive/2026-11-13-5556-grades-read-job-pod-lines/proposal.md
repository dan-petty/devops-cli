# Proposal

## Why

`devops roadmap eval grades` (#5165) reads only the result lines of the Service pod and of the stage Job pods, and it parses each line with `| json message` (#5556). The roadmap jobs now run in Job pods too, and these pods write a plain line:

- The fix-plan Jobs write their line to stderr as plain text. The selector does not read them, so `fix_plan` shows no attempts, and Loki holds attempts of `fix_plan`.
- The stage Jobs (#5483, #4559) write no line to the log at all. A CLI process has no handler for the `INFO` records of `devops_cli.roadmap.job_result`, so the line of each stage Job is lost. From release 0.133.0 the Service plans no stage item, so the grades lose every stage attempt.
- A plain line in a stream that the selector reads stops each query: `| json message` gives `JSONParserErr`, and Loki refuses a metric query with a pipeline error.

## What Changes

- One base of the result lines, in `src/devops_cli/roadmap/job_grade_report.py`: the selector `{namespace="devops", container=~"service|stage|fix-plan"}`, the line filter, and one parse for the two forms of a line. `| json message | drop __error__, __error_details__ | line_format "{{ or .message __line__ }}"` gives the message of a JSON line and the full text of a plain line, and `|~ "^roadmap job result: "` then keeps only a line that starts with the prefix. Each query of the report and each panel of the row `Roadmap Job Success` starts with this base, and a test holds the dashboard to the constant.
- The selector names the container of each unit that writes result lines: the Service (`service`), a stage Job (`stage`) and a fix-plan Job (`fix-plan`). It reads no runner pod and no other pod that runs a coding agent and its tests, because their logs can hold copies of result lines. A stream that OpenTelemetry exports has no label `namespace`, so the selector does not read a line twice.
- `devops roadmap stage --job-item` writes the result line and the round lines to stderr as plain text, as `devops roadmap step fix-plan` does. The context manager moves from the fix-plan command to `src/devops_cli/roadmap/job_result.py`, and both commands use it.
- One line for each attempt: the actor that writes the check-in of a stage attempt writes its line. The stage Job writes its line after its check-in, and writes no line when the check-in finds no check-out of the Job, because the Service then ended the attempt and wrote the line of a failed end. The Service writes a line only with the check-in of a failed end that it recovers.
- The fake Loki of the tests evaluates the subset of LogQL that the report sends, on streams of labels and lines. Like Loki, it refuses a metric query whose pipeline leaves an error label.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-job-grades`: the report reads the result lines of the Service, the stage Jobs and the fix-plan Jobs, in both forms.
- `roadmap-stage/job`: the stage Job writes its result line to stderr after its check-in, and the grades read the fix-plan Jobs too.

## Impact

- Code: `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/roadmap/job_result.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`.
- Manifests: `k8s/devops/dashboards/devops-cli.json` (the four queries of the row `Roadmap Job Success`). The ConfigMap of the dashboard changes, and no pod restarts.
- Tests: `tests/support/fakes/loki.py` (new), `tests/support/roadmap_job_grades.py`, `tests/roadmap/test_job_grade_report.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- Documents: `docs/roadmap/job-success.md`, `docs/roadmap/stage.md`, `docs/CLUSTER.md`.
- The change fits one pull request: about 400 changed lines.
- A release is necessary: the grades of a person read Loki with the installed CLI, and the stage Jobs write their line only with the new image.

## Feasibility

- `origin/main` at 5dc588289: `_SELECTOR` of `job_grade_report.py` is `{namespace="devops", app_kubernetes_io_name=~"roadmap-service|devops-cli-job", container=~"service|stage"}`, and `_lines` adds `| json message | line_format "{{.message}}"`.
- Loki, 2026-11-13, `{namespace="devops"} |= "roadmap job result:"` for 7 days: the Service (`app_kubernetes_io_name="roadmap-service"`, container `service`, stdout) holds JSON lines with the line in `message`. Two Job pods with `app_kubernetes_io_name="roadmap-fix-plan-validation"`, container `fix-plan`, stderr, hold plain lines: `roadmap job result: job=fix_plan repo=<owner/repo> item=#5272 result=timeout ...` and `... item=#4472 result=cleared ...`. No other stream holds the text.
- The stage Job pod `devops-cli-stage-devops-cli-4449-c68895` (labels `app_kubernetes_io_name="devops-cli-job"`, container `stage`, component `roadmap-stage`) ran from 21:05 to 21:49 UTC on 2026-11-13 and ended `staged`. Its log holds 8 lines: the plan report on stdout, the line `The stage Job of item #4449 ended: staged, exit code 0.` and the elapsed line. It holds no result line. The Service wrote no `job=stage` line from 21:00 UTC. So that attempt is in no grade.
- `src/devops_cli/commands/roadmap.py` `_stage_job` sets no handler. Only `roadmap_step_fix_plan.py` routes the `INFO` records of `devops_cli.roadmap.job_result` to stderr (`_lines_to_stderr`, #5363). The Service sets its JSON handler in `server/json_logs.py`.
- The new base, run as an instant query on that Loki for the 7 days to 22:00 UTC on 2026-11-13, gives `fix_plan` 2 attempts and the same counts as the old query for each other job: `alternatives` 34, `implement` 12, `intake` 305, `refine` 93, `refine_judge` 7, `stage` 18. The `quantile_over_time` query of the tokens runs on the new base too. With the old base and a selector that reads the fix-plan pods, Loki answers 400: `pipeline error: 'JSONParserErr'`.
- The containers of the namespace in Loki for 7 days: `service`, `stage`, `fix-plan`, `implement`, `runner`, `mcp-server`, `crawl4ai`, `searxng` and `p`. The OpenTelemetry stream `{service_name="roadmap-stage"}` has the labels `k8s_cluster_name` and `service_name` only.

## Existing Tool Considered

LogQL itself parses the two forms: the `json` parser, `drop`, and the `__line__` function of `line_format` (Loki documentation, "Log queries" and "Template functions"). The change builds no parser of its own in `src/`.

The tests need a Loki that runs the queries. No maintained Python package evaluates LogQL, and a real Loki needs a container, which the test run does not start. The fake evaluates only the stages and the metric forms that the report sends, and refuses each other form. Cost: about 40,000 tokens and 1 hour to build, about 5,000 tokens a year to keep, and about 10,000 tokens to fix when the report sends a new form.

The change deletes `_lines_to_stderr` of `roadmap_step_fix_plan.py` (it moves to `job_result.py`) and the second copy of the selector in the test of the grades.
