# Design

## Decisions

- **Write the audit in `docs/DASHBOARD_TABS_AUDIT.md`, a hand-written page of its own.**: A task group may not change a path under the change folder, which the stage job writes before the groups run, so the evidence needs a page that a group can write.
- **Write one task group for each tab section, one group for the links and one group for the summary and the follow-up drafts.**: Each group reads one tab's panel, provider and tests, so its inputs stay inside the step budget of 64,000 tokens.
- **State the deleted lines as file and line ranges read from the staged commit.**: The follow-up issue deletes those lines, and a line count alone does not tell a person which code goes.
- **State each pin from the file that holds it: the tools lock for k9s, the Argo CD Application for the Grafana and Loki charts.**: The repository holds each pin, so the audit cites it and invents no version.
- **State in the Docker section that no file of the repository pins lazydocker, with the person-run release check.**: No file of the commit holds lazydocker, and the runner has no network, so the audit cannot state its version or its licence.
- **Draft each follow-up issue in the page and leave the filing to a person.**: A rerun of a group would file a second issue, and no offline check can confirm that GitHub holds the first.
- **Link the page from `README.md` and `docs/index.md`.**: The two-link test fails for a hand-written page that no chain of two links from the agent router reaches, and `README.md` is one link away.
- **Give the tab's request cost from its own code and the tool's cost as a person-run step.**: The runner has no cluster client, so it can count the requests of the fetchers but not those of the open tool.

## Rejected alternatives

- **Write the audit in design.md of the change folder, as the refine block proposes.**: The plan check refuses a group whose changes or creates path sits under the change folder, because the stage job writes that folder before the groups run.
- **Add the audit to `docs/commands/dashboard.md`.**: `docs/commands/*.md` is in the generated class of `src/devops_cli/config/constants.py:459:CONST_DOCS_INVENTORY: Final[dict[str, tuple[str, ...]]] = {`, so `uv run devops docs generate --sync-readme` overwrites a hand edit.
- **Record the tabs as capabilities in `.devops/survey.toml`.**: A survey capability holds one description and one comparable tool per entry, so it cannot hold the five sections with the deleted lines, the request cost and the person-run steps that the issue asks for.
- **Use Portainer for the Docker tab.**: Portainer is a web server with a browser user interface, and the tab is a terminal view, so it is no terminal tool and it adds a service to run.
- **Keep the Telemetry tab beside the deployed Grafana dashboards.**: `k8s/monitoring/dashboards` holds 15 dashboards and the infra stack deploys Grafana, so the tab repeats a view that the cluster already serves.
