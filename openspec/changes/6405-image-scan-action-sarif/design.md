# Design

## Decisions

- **A composite action with `docker://` steps.** The action `.github/actions/image-scan` runs Trivy from its image, pinned by tag and digest, with `uses: docker://`. The GitHub metadata syntax lists `docker://` references as composite steps. The runner starts the container with the workspace as its working directory and the Docker socket mounted, so Trivy reads the image that the job loaded and the ignore file of the checkout. Renovate's github-actions manager reads `uses: docker://` lines in `action.yml` files, so it moves the tag and the digest with no custom manager.
- **The calling step holds the timeout.** A composite step has no `timeout-minutes`. Each calling step sets `timeout-minutes: 4`, above the `--timeout 3m` of Trivy and below the job timeouts of 12 min (image jobs) and 5 min (third-party scan).
- **A table pass after the SARIF scan.** With `--format sarif --output`, Trivy writes no finding to the log, so a failed job named no CVE. The second step scans again with `--skip-db-update` and `--format table`. It reads the database and the layer analysis that the first step cached under the home folder of the container, and took 1 s to 2 s on each image. It runs after a failed scan too, has `continue-on-error`, and never changes the gate.
- **The category input is the full code scanning category.** The callers give `trivy-image-service`, `trivy-image-runner`, `trivy-image-mcp-server` and `trivy-image-crawl4ai`. The SARIF file of the workspace takes the same name, and the action gives it as the output `sarif-file`, so a later caller such as #6406 can upload it from another job.
- **One entry for each finding and binary.** Each entry of `vulnerabilities:` names the Trivy target of the binary in `paths` and the package in `purls`. A version in the path or the purl makes an entry stop when the tool or module changes, and then the scan fails, which is safe.
- **Entry dates.** The entries keep the date that applied to them on 2026-11-19: the OpenTofu and promtool entries and the kubectl x/net entries 2026-11-21, the Go stdlib entries 2026-11-22. The kubectl x/text entry expired on 2026-11-20 with no released fix, so it goes to 2026-11-22, the limit of 14 days from its first entry on 2026-11-08 (SECURITY.md, Renewal).
- **The image jobs watch the action.** The 3 `IMAGE_CONTENT_PATHS` lists name `.trivyignore.yaml` and `.github/actions/image-scan`, so a change of an entry or of the action (a Renovate bump of the Trivy image included) runs the three scans.

## Rejected alternatives

- **A `run` step that calls `docker run`.** Renovate's github-actions manager does not read an image in a shell line, so the pin would need a custom manager, which the issue rules out. The `docker://` step works in a composite action (GitHub metadata syntax), so the risk that the issue names did not happen.
- **A job-level step in each job.** It keeps six copies of the scan and the drift that the issue removes.
- **SARIF only, with no table.** A failed scan then names no finding in the job log, and an agent that reads the log of a failed job cannot see which CVE to fix. The table pass from the cache costs 1 s to 2 s.
- **One JSON scan and two `trivy convert` runs.** It also gives SARIF and a table from one scan, but it needs three container steps instead of two, and the gate then sits on a convert step and not on the scan.
- **A cache of the Trivy database in the Actions cache.** The scan with a new database took 54 s to 62 s on this host, and the issue leaves the cache out. If ghcr.io limits the rate, `TRIVY_DB_REPOSITORY` is the next step.
- **Keep the legacy text files.** The text format has no path field, so an entry for OpenTofu also hid the same ID in kubectl.
- **Keep the parity and input tests.** They assert values of workflow files (owner rule of 2026-11-16). The one action is now the single place that holds the threshold, and actionlint and zizmor check the workflows.
