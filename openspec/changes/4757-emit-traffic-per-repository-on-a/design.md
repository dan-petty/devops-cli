# Design

## Decisions

- **Add `administration` at level `read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, the one permission set of every token.**: The code mints one token set for every job, and the issue allows the shared set with one amendment line to ADR 0015, as #3519 did for `workflows: write`.
- **Keep the refused set of repositories and turn the refusal into one warning that names `administration: read`.**: The set stops the four requests of a refused repository for the rest of the process, and a refusal that no log names costs the operator the reason.
- **Modify the base requirement `A path that the token cannot read is not asked again` instead of adding a requirement for the refused repository.**: The base requirement already holds the refusal rule and its guard, so a second requirement would duplicate it; the modification adds the refused repository and the warning and corrects the count of its first scenario.
- **Keep the modified requirement text under 500 characters and put the refused-set rule and its warning in the first scenario.**: The check refuses a requirement text above 500 characters, and the scenario names the four paths, the one warning and the second collection that the test asserts.
- **Modify the base requirement `The Service collects no repository traffic` in place.**: A modified requirement replaces the base requirement under its exact name, and its text now states that a process that acts as the App reads the traffic when its token holds the permission.
- **Leave `k8s/monitoring/dashboards/project-metrics.json` and `docs/TELEMETRY.md` unchanged.**: The traffic gauges already carry the `repo` label and the panels read `last_over_time`, so a series appears for each repository once the token reads the endpoints.
- **Run the traffic reads on the metrics row that runs today and add no schedule.**: #4574 is open with status ready, and the issue says that this item adds no schedule.
- **Give the ADR group a manual check and no command.**: No command of the repository reads ADR text, so `uv run devops ci docs` would pass with or without the amendment line; the group states the lines that a person reads instead.

## Rejected alternatives

- **Add a new requirement for the refused repository next to the existing refusal requirement.**: `read_spec project-metrics-dashboard` returned `A path that the token cannot read is not asked again`, which already states that a refused path is asked once, so a second requirement duplicates it and contradicts its first scenario.
- **Keep the 612-character text of the refusal requirement and let the check pass it.**: The check refused the previous plan: the requirement text has more characters than the 500 it allows, so the plan moves the refused-set rule and its warning into the first scenario.
- **Verify the ADR group with `uv run devops ci docs`.**: `src/devops_cli/commands/ci.py:2140` verifies generated CLI documentation and configuration, and it reads no ADR text, so it passes with or without the amendment line.
- **Mint a separate installation token for the metrics row with its own permission set.**: `CONST_GITHUB_APP_TOKEN_PERMISSIONS` is one constant for every token (`src/devops_cli/config/constants.py:1477`), and choosing a set per row needs code outside the five files that the issue lists; the issue allows the shared set with an ADR amendment.
- **Keep the `acts_as_github_app()` skip and read the traffic only from a workstation.**: The token gains Administration read, so the skip would keep the four panels empty: `src/devops_cli/github/metrics.py:763`.
- **Read the traffic with the Grafana Infinity data source or prometheus-community/json_exporter.**: Neither can mint an App installation token, so each needs a long-lived token with Administration read, and the owner kept the emitter on 2026-11-11.
