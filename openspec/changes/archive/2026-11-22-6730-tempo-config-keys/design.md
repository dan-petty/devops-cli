# Design

## Decisions

- **Parse the rendered configuration with the Tempo image of the chart, with `-config.verify=true`.**: The pod fails at the strict parse of `cmd/tempo/main.go`, and only the binary of the pinned version knows its keys. The check takes the image and the container arguments from the rendered StatefulSet, so a chart update that moves Tempo to a new version runs the new binary, and no test change is necessary.
- **Render the chart as Argo CD does, from the Application.**: `chart_objects` reads `k8s/argocd/apps/tempo.yaml`: the chart, the repository, the `targetRevision`, the destination namespace and the value files. A `$values/` file resolves to the checkout through `SourceTrees.value_file`. This is the command of `devops k8s image-pins`. The check holds no chart version.
- **Write each ConfigMap that the container mounts, at its mount path, and run the container with no network.**: The pod mounts ConfigMap `tempo` at `/conf`, with `tempo.yaml` and `overrides.yaml`. The check mounts the same files read-only. The folders get mode `0755` and the files `0644`, because Tempo runs as user `10001`, which is not the owner of the folder on a GitHub runner or under rootless Podman.
- **Fail on a warning too.**: `-config.verify=true` without `-config.verify-errors-only=true` exits 1 on a warning of `CheckConfig`. The configuration of this change gives no warning, so the strict form passes.
- **Bound the two programs.**: `helm template` gets 60 s, and `docker run` gets 90 s, which includes the first pull of the image. The two bounds and the 23 s of the other checks stay under the 3 min of the Static Analysis Quality Gate step. A usual run takes about 5 s for each.
- **Move the trace size limit to `tempo.overrides.defaults.global.max_bytes_per_trace`.**: The chart renders `tempo.overrides` into `overrides` (`templates/configmap-tempo.yaml`). Tempo applies the limit to a search, to the traces that it receives and to compaction. Helm merges the map, so the chart keeps `per_tenant_override_config: /conf/overrides.yaml`.
- **Remove `target_bytes_per_second`.**: Tempo 3.1.1 has no limit on the byte rate of a search. `throughput_bytes_slo` only sets a metric, and `target_bytes_per_job` sets the size of a job, not a rate.
- **Replace `max_duration: 30s` with `api_timeout: 30s`.**: `max_duration` is the largest time range of a search, so `30s` refuses a search of the last hour with HTTP 400. `api_timeout` stops a read after 30 s and cancels its queued jobs, which frees their memory. The default of `max_duration`, `168h`, is the retention.
- **Assert bounds of the rendered configuration in `tempo_query_limits.py`, not values of the values file.**: The old check read `tempo.global_overrides` from the values file and passed, while the chart dropped the key. The rendered configuration is what Tempo gets. docs/TESTING.md refuses an assert of a limit value, so the check asserts only the bounds under the memory limit, which a new value within the bounds keeps.
- **Keep `tempo_query_limits.py` and add `tempo_config.py`.**: The parse check proves the keys, and the bound check proves the memory aim of #6616. They share one render.

## Rejected alternatives

- **Keep `max_duration: 30s`.**: `modules/frontend/search_sharder.go:104` refuses a search whose range is more than `max_duration`, so a search of the last hour in Grafana fails. The acceptance criterion of #6730 asks for a TraceQL search through Grafana that returns traces.
- **Put the byte rate under `throughput_bytes_slo` or `target_bytes_per_job`.**: Neither is a rate limit. `SLOConfig` only counts requests that meet the SLO, and `target_bytes_per_job` sets the size of each job.
- **Keep the exact-value asserts of `tempo_query_limits.py`.**: They read the values file, which the chart did not render as the check expected. docs/TESTING.md and #6060 refuse an assert of a limit value, because each change of a value then needs a test change.
- **Check the rendered keys against a list of Tempo keys in the repository.**: The list repeats one Tempo version, and a chart update breaks it. The binary of the pinned image knows its own keys.
- **Download the Tempo binary from a GitHub release.**: It adds an installer and a version map to the repository, and the version can differ from the image of the chart.
- **Run the check in a new `devops ci` row with a host refusal.**: It adds a row, a message and a refusal for one check. No step of a Job runs the `k8s` row: the implement Job runs `constructs`, `docs` and `openspec`, and the fixers of the fix-checks Job run ruff, the tests of a snapshot, the docs and `uv lock`.
- **Run the check only in the Image Pins workflow.**: That check is not required, so a pull request can merge while it fails.
- **Start the whole Tempo binary in the check.**: It needs a writable `/var/tempo` and a wait for the modules. `-config.verify=true` gives the parse result and stops.

## Unchanged references

- `k8s/argocd/apps/tempo.yaml`: It pins chart `3.2.1` and names the values file, and the change keeps both.
- `k8s/README.md`: Its Tempo row names the release and its values file, not a limit.
- `.github/workflows/ci.yml`: The Static Analysis job runs the `k8s` row on the runner host, which has `helm`, `kubectl` and Docker.

## Security

The check runs a public image of the chart with `--network none` and read-only mounts of rendered files. It sends no credential: `helm` reads a public chart repository, and the engine pulls a public image as an anonymous client. The change adds no host name, address or secret.
