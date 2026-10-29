# Design

## Context

#2654 delivered `devops roadmap stage`. The Service runs refine, which sets items Ready, but nothing runs the stage job after it. The stage job validates each change with `openspec validate`, and the Service image has no Node and no OpenSpec, so the job would skip the validation there. This change adds the row, its settings and its metric, and puts the pinned OpenSpec in the image.

## Decisions

- **The row follows refine on the model lane.** The stage job calls the model, and the model answers one call at a time, so the row belongs to the model lane with intake and refine. A first run, the interval of 60 minutes and the cross-job rule make the job run in the round that follows a refine round that set an item Ready. The rows run in table order inside a round, so a round that readies an item stages it at once.
- **`JobOutcome.set_ready` carries the cross-job fact.** The refine adapter returns `JobOutcome(set_ready=applied.readied_count > 0)`. `placed_critical_or_p0` stays as it is for refine's own rule. A field of the outcome is the mechanism that `cross_job_predicate` already reads, so the due table needs no new mechanism.
- **The runner is the body of `devops roadmap stage --confirm`.** It reads the settings, calls `plan_stage` and `apply_stage` with the clone path the round gives, counts the results, and calls `raise_for_failed` for the failures of the plan and the writes. The round then records the failure as for any other row, and the ledger of failed rounds suspends a row that fails three rounds in a row. A person sees the same plan and the same messages from the command.
- **The metric is emitted by the stage module, not by the runner.** `emit_stage_results(plan, applied)` sits in `stage.py` and the command and the runner both call it after `apply_stage`. So a person who runs `--confirm` by hand counts the same as the Service. A `--plan` run writes nothing and counts nothing.
- **The result of an item is the first that applies.** An item of `applied.failed` or `plan.failed` is `failed`. An item of `applied.stopped` is `needs_split`. An item of `applied.staged` is `staged`. An item of `plan.left_out` is `skipped`. The plan lists an item in one of these groups only, and a write that fails moves its item from `staged` or `needs_split` to `failed`, so no item counts twice.
- **The filter check moves to `stage_filter.py`.** The settings must refuse a bad entry at load time, and `stage.py` imports the model client, the GitHub session and the settings. A module of its own, with the label families and `split_filter_entry`, lets both import it with no cycle. `stage.parse_filters` keeps its name and its callers.
- **No filter option means the setting.** `parse_filters(())` returns the filter of `roadmap.stage.filter`, and `--limit` falls back to `roadmap.stage.limit`. The setting has a floor of one entry, so an empty list cannot widen the job.
- **Node comes from the official image, as a binary.** `COPY --from=node /usr/local/bin/node` is the pattern the Dockerfile already uses for `uv` and the pinned `gh`. The digest is bumped by Renovate with the other base images. The builder stage also copies npm from the same image, because `devops install-tools` runs `npm ci`. The service stage needs no npm.
- **The installer runs in the builder stage.** The builder stage holds the virtual environment with `devops`, so the install is the command that CI and the devcontainer run. `DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools` for that one command puts the version directory and the link under a path that the service stage can copy to the same place, because the link in `bin/` names the version directory by its absolute path. The variable is not set in the service stage, so the Service's own data paths do not change.
- **The builder makes the tool directory readable.** The installer stages the version directory in a temporary directory, so it is mode 0700. In a user's home that is right. In the image the Service runs as user 1000, so the builder runs `chmod -R a+rX /opt/devops-tools`. The build of the first version of this change showed `Permission denied` for `openspec` as user 1000.

## Rejected alternatives

- **`apt-get install nodejs` in the service stage.** Debian trixie ships Node 20.19.2 (`apt-cache policy nodejs`), which satisfies the `>=20.19.0` of the locked OpenSpec but not the major version of `.node-version` (24). Upstream ended Node 20 in 2026, only Debian's security team patches it, and a later OpenSpec that asks for a newer Node would break the image and no CI job. The disk cost is the same: +122 MB with `apt`, +122 MB with the official binary.
- **`npm ci` in the service stage.** It needs npm and the registry in the image that runs as the Service, and it leaves npm and its cache in the final image. The builder stage does the install, and the service stage gets only the result.
- **A `node` base image for the whole service stage.** It adds Yarn, Corepack and npm to the image (the image is 335 MB against 189 MB for the Python base) and moves the Python runtime out of the base that every other part of the Service pins.
- **A second `devops` virtual environment in a node stage.** `uv sync` there needs a Python that the node image lacks (`UV_PYTHON_DOWNLOADS=never`). Copying the existing virtual environment would break its links to the interpreter.
- **A hand-written `npm ci` line in the Dockerfile.** It would repeat the flags of `build_npm_ci_cmd()` (`--ignore-scripts`, the engine check, no audit, no registry rewrite) and drift from them. The installer is the one source for the install.
- **The metric in the runner only.** A `--confirm` run by a person would then count nothing, and the dashboards would show the Service only. The stage module is the one place that knows the results.
- **A parser for the `filter` variable.** `SettingVariables` already reads a list from a JSON list or comma-separated values for every list setting.
- **A cross-job rule on `placed_critical_or_p0` of refine.** It names the wrong event: refine can set an item Ready that is not critical, and a critical item that refine only comments on is not Ready.

## Risks

- A stage round can make many model calls (at most `roadmap.stage.limit` items, three calls at most for each). The ledger of failed rounds and `RoadmapServiceModelRequestsHigh` already bound a loop of rounds.
- The Node binary adds about 122 MB to the image. The image gains a runtime that runs only OpenSpec, with no network access of its own: OpenSpec's telemetry and update check are off, and the Service's NetworkPolicy still holds.
