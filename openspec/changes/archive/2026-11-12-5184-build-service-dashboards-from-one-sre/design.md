# Design

## Decisions

- **One module, one spec file.** `src/devops_cli/grafana/service_dashboard.py` holds `ServiceSpec`, the template and `main`. `k8s/monitoring/dashboards/services.toml` holds the specs as `[[service]]` tables, next to the dashboards. TOML, not YAML: many tests read each YAML file under `k8s/` as a Kubernetes manifest. `make dashboards` runs `uv run python -m devops_cli.grafana.service_dashboard` on the file.
- **The SDK lays out the grid.** Each panel gets its width and height, and the dashboard builder puts it in the next free place. A collapsed row takes one grid line, so each collapsed row after the first gets the `y` after the row before it.
- **Variables in every query.** Each query names `$namespace` and `$workload`. A spec with `variables` keeps them as single-value dashboard variables on its values; another spec puts its values in their place. Thus one set of queries serves both dashboards, and an exact matcher never meets a variable with more than one value.
- **Failed requests.** The share of failed requests is `(sum(failed) or sum(requests) * 0) / sum(requests)`. Traefik writes no counter for a code until the first request with it, so with requests and no failure the count is the zero of the requests. It is not a constant: with no request the SLI has no value.
- **Rolling window.** The SLO window rolls. The budget chart shows, at each point, the budget left of the window before it, with the warn line at 25 % and the line at 0 %, which a steady 1x burn holds. The chart reads a Min step of 15m, because each point reads the whole window.
- **Burn-rate lines.** The page lines come from the SRE workbook (Table 5-8): the 1 h window spends 2 % of the budget and the 6 h window 5 %, so the line is `share x window hours / hours`, 14.4 and 6 for 30 days. The 1x pace is a third line in `text`.
- **Colors.** Series 1 and 2 are the token hex of `color.data.cat.1` and `cat.2`, read with `devops_cli.design.tokens`. A single series and a third entity (p99) are `text`, as `color.fg` and the third Grafana entity. A page line and a limit are `red`, a warn line `semi-dark-orange`, and the SLO line and the 1x pace `text`. Series 2 has the dash preset `[10, 10]` and series 3 `[30, 3, 3]`; a reference line has the style `dots`. Stroke widths are the tokens `chart.stroke.data` and `chart.stroke.reference`.
- **Saturation.** The highest share of its limit that one container of the workload uses, for memory and CPU, with the limit line at 100 %. One series for each resource, so the panel does not draw a line for each pod.
- **Pods.** The pods of a Deployment are `<workload>-<hash>-<id>`, so the template selects `pod=~"$workload-[a-z0-9]+-[a-z0-9]+"`. The pattern is anchored, so it does not match a Deployment whose name starts with the workload name and a dash.
- **The check of the build.** The CI job "Design Tokens" runs `make dashboards` and `git diff --exit-code` on `k8s/monitoring/dashboards`, as it does for the token outputs. A test of `tests/grafana` compares each committed dashboard with the build too, so a change of the SDK pin in `uv.lock`, which the job filter does not hold, fails in the test job.
- **Harness of the template.** A case file of `tests/fixtures/dashboard_queries/` with the key `spec` holds the cases of the template build of that spec. Thus the cases of the SLO of 99 % in #5184 need no committed dashboard with that SLO.

## Rejected alternatives

- **A dependency group of its own (`dashboards`).** The Service image and the runner image install only the `dev` group (`uv export --only-dev` in the `Dockerfile`), so the suite in the Service image failed on the import of the SDK, and the type check of a runner step reads all of `src/`. The dev group is a dependency group too, and no runtime install holds it.

- **The calendar window of C12 b, with an even-burn line from 100 % to 0 %.** PromQL has no window that grows from the start of a range, and the cumulative sums of Grafana transformations cannot be checked with promtool. On a rolling window, a steady 1x burn holds the line at 0 %, so the 0 % line is the even burn.
- **`or vector(0)` for no failed request.** `devops grafana dashboards lint` and the chart rules of #4707 refuse a fall back to a constant outside a stat, because it shows a zero with no data.
- **A `devops grafana dashboards build` command.** The issue asks for a Make target, and a command would add a dry-run plan, help and messages for a build step that only a developer runs.
- **The v2 builder of the SDK (`dashboardv2`).** The dashboard sidecar provisions the classic JSON of the files in its ConfigMaps.
- **The sequential steps 5, 7 and 9 for p50, p95 and p99 (C12 d).** Grafana does not change a hex color with the theme, and those steps do not pass 3:1 on the four Grafana backgrounds. The quantiles take the series colors and dashes.
