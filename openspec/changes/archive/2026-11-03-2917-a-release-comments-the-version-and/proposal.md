# Proposal

## Why

Issue #2917: after a merge, the owner learns that a fix is live from three places: the release pull request, the images and Argo CD. The issue asks the Service to comment `Released in <version>` once on each closed issue that a release carries. When the Service and runner images of that release run in the cluster, it asks for one more comment, `Live since <time>`. The job must be read-only toward releases.

Nothing of this exists. On 2026-11-02, 12 releases were published (7 on 2026-11-01, 15 on 2026-10-31), so a person cannot follow them by hand (Feasibility 4).

## What Changes

- A new row `release_comments` joins the status lane after `stage_ready`. It calls no model and needs no clone. It is due every 11 minutes and on a first run.
- Each round reads the 30 newest releases of the repository (1 request) and keeps the ones that are published within the last 12 hours, are not a draft and are not a prerelease.
- For a release that the ledger does not hold as done, the row reads the pull request numbers `(#N)` in the release body, the body of each pull request, and each issue that a closing keyword names (`Closes #N`, `Fixes #N`, `Resolves #N`). An issue that is closed and is not a pull request gets the comment `Released in <tag>`, once. The marker `<!-- devops roadmap release <tag> released -->` heads the comment. The row posts no comment on an issue that already holds the marker.
- The row reads the digest that the tags of the release name for the `service` and `runner` images in the registry `ghcr.io`, and the digests that Deployment `roadmap-service` and CronJob `devops-cli-runner` run now. When both match, it posts `Live since <time>` once on each issue of the release, headed by the marker `<!-- devops roadmap release <tag> live -->`. The time is the time of the round, in UTC, to the minute. When the cluster runs the digests of a newer release, the older releases of the list are live too.
- The row keeps a ledger file `release_comments.json` beside `schedule.json`. It holds, for each release of the window, whether the `Released in` comments and the `Live since` comments are done. The comments stay the source of truth: a lost ledger costs requests and never a second comment.
- `ClusterJobs` gets `deployment_digest`, which reads the digest in the image of a container of a Deployment. Role `roadmap-service-jobs` gets `get` on `deployments` named `roadmap-service`.
- The row sends only reads and issue comments to GitHub. It writes no release, tag, branch, label or file.
- The change carries a spec delta: the row, its comments and the Role are observable (`openspec/config.yaml`). A new capability `roadmap-release-comments` holds the row. The requirements "The Service creates Jobs through a narrow Role" (`roadmap-implement-runner`) and "A model-lane round that has not ended does not delay the implement row" (`roadmap-implement-job`) are MODIFIED.
- The change fits one pull request: five groups of code with two to six files each, one manifest group and one group of documents.

## Capabilities

### New Capabilities

- `roadmap-release-comments`: the row that comments the version and the deploy time of a release on the issues it carries

### Modified Capabilities

- `roadmap-implement-runner`: the Role of the Service reads one Deployment
- `roadmap-implement-job`: the status lane holds one more row

## Impact

- Code: `src/devops_cli/roadmap/release_feed.py` (new), `src/devops_cli/roadmap/release_roll.py` (new), `src/devops_cli/roadmap/release_comments.py` (new), `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`
- Manifests: `k8s/devops/roadmap-service/role.yaml`
- Tests: `tests/roadmap/test_roadmap_release_feed.py` (new), `tests/roadmap/test_roadmap_release_roll.py` (new), `tests/roadmap/test_roadmap_release_comments.py` (new), `tests/roadmap_github_fake.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/test_roadmap_run.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/core/test_k8s_runner.py`
- Documents: `k8s/README.md` (the Role bullet and the list of rows), `docs/ROADMAP_WORKFLOW.md` (step 8 and the list of planned changes), `CONTEXT.md` (the status lane)
- Left as they are, on purpose: `RELEASE_CYCLE.md` and `.github/workflows/release.yml` (the row reads the release after it exists, so the workflow does not change). `docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md` says the roadmap consumer takes `release` events, but the code takes `issues` only (Feasibility 7). This change adds no webhook event, so the ADR text stays for a person to settle. `src/devops_cli/roadmap/run.py` `SCOPED_UPDATES` stays: no event runs this row at once. `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/CONFIGURATION.md` name no row, command or setting that changes (`git grep -n "stage_ready" -- README.md docs/CLI_REFERENCE.md docs/MCP_TOOLS.md docs/CONFIGURATION.md` prints nothing). A pull request of type `docs`, `test`, `ci` or `chore` is hidden in the changelog (`release-please-config.json:14-18`), so the issue it closes gets no comment (design.md).

## Dependencies

- #2908 is the parent tracker (open). This item is its step W9.
- #2968 (inbox counts as gauges and the image digest line, open, no plan) also needs the digest that the cluster runs and the digest that a tag names. This change puts the two reads in `release_roll.py` and `ClusterJobs.deployment_digest`. #2968 can reuse them. Whichever change merges second adapts.
- #3220 (a Deployment for the MCP server, open) copies `k8s/devops/roadmap-service/` and adds its own Role. It does not edit `role.yaml` of the Service (its text says it adds `k8s/devops/mcp-server/`).
- #1387 (Argo CD records a deploy as a GitHub deployment, open, `status/new`) is another source for "live since". It is not built and no plan exists, so this change does not wait for it. If it lands, the `Live since` pass can read the deployment and drop the cluster read.
- Open plan pull requests that name the same files: #3205 and #3183 edit `docs/ROADMAP_WORKFLOW.md`, #3169 edits `tests/roadmap/test_roadmap_run.py`, and #3183, #3228 and #3248 edit `src/devops_cli/config/constants.py`. These are different lines; whichever merges second merges main. No open plan modifies the two requirements that this change modifies (`git diff origin/main...<head> -- 'openspec/changes/*/specs'` of each open plan, searched for the requirement names).
- Merged and read: #3195 (failure taxonomy, `src/devops_cli/roadmap/failure.py`) classifies a stop of the implement job, not a failed row, so this row raises `RoadmapRunError` and uses no class. #3196 (deadline) is about the runner Job. #3213 (`pull_form`) is about pull request text.
- I searched the open issues and pull requests for `2917`, `roadmap-service/role.yaml`, `image digest` and `release comment` on 2026-11-02. No issue says to park or wait for this change.

## Feasibility

Checked on `origin/main` 80ffc5c1 (2026-11-02), with the commands and reads below.

1. Nothing of it exists. `git grep -n -i "released in\|live since\|release_comment" -- . ':!CHANGELOG.md' ':!openspec/changes'` prints nothing (exit 1). `gh api -X GET search/issues -f q='repo:dan-petty/devops-cli is:issue "Released in" in:comments'` lists 2 closed issues, #2537 and #1113, whose comments hold the words by chance. No job writes such a comment.
2. The release is a GitHub release object with the changelog as its body. `get_latest_release` printed for `v0.47.0`: `"draft":false,"prerelease":false,"published_at":"2026-11-02T17:34:44Z"`, author `dan-petty-release[bot]`, and a body that lists `(#3233)` and `(#3232)`. Those are pull request numbers. The body has no word `closes`. ADR 0013 says release-please makes the release and "no code ... predicts, computes or checks a future version", so the row reads the tag of the release and builds none.
3. The pull request body, not the changelog, names the closed issue. A scratch script (outside the tree) read the 12 newest releases. For each release it took the numbers `(#N)` of the body, read `GET issues/<N>` for each (the issue endpoint of a pull request holds its body and a `pull_request` object; for an issue that key is null), and took each `Closes|Fixes|Resolves #M` at the start of a line. It printed: `v0.47.0 [3232, 3233] -> [3222, 3219]`, `v0.46.1 [3223] -> [3206]`, `v0.42.0 [3177, 3178, 3182] -> [3013, 3012, 3153]`, `v0.41.0 [3154, 3160] -> [3152, 3037]`, `v0.39.0` with 6 pull requests and 6 issues. All 26 issues of the 12 releases were closed and none was a pull request. The changelog text `closes [#M]` named 6 of the 26 (`v0.41.0`, `v0.40.0`, `v0.39.1`, `v0.39.0`). A parse of the changelog would miss 20 of 26. The 12 releases cost 52 requests, about 4.3 for each release.
4. The release rate needs a ledger. `GET releases?per_page=100` gave 12 releases on 2026-11-02, 7 on 2026-11-01, 15 on 2026-10-31, 13 on 2026-10-30 and 19 on 2026-10-29. In a 12-hour window that is about 6 releases. Without a ledger, a round reads about 4.3 + 2 (one comment listing for each issue) = 6.3 requests for each release, 38 for 6 releases. At 6 rounds an hour that is 227 requests an hour, 45% of the budget of 500 (`DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR`, `src/devops_cli/config/defaults.py:903`). With a ledger, a round with nothing new sends 1 request (the release list), 6 an hour. These numbers are arithmetic from the probe, not a live run of the row.
5. Webhooks do not carry a release to the Service. `CONST_ROADMAP_WEBHOOK_EVENTS` is `frozenset` of the events in `CONST_ROADMAP_INTAKE_BATCH_KEYS` (`src/devops_cli/config/constants.py:3245-3255`), and that tuple holds `("webhook", "issues", "opened")` and `("webhook", "issues", "reopened")` only. ADR 0009 says the roadmap consumer takes `issues`, `pull_request`, `milestone` and `release`. The code takes `issues` only. The row therefore polls (ADR 0003), and no repository hook changes, so no person step is needed. The ADR text and the code disagree. This change leaves the ADR for a person (Impact).
6. A tag names one digest per image, and the digest changes with each release. `uv run python -I` over `devops_cli.docker.registry.tag_digest` with a temporary HOME printed, anonymously: `service v0.46.1 sha256:55223feb...71b5`, `runner v0.46.1 sha256:98e3dee1...7555`, `service v0.47.0 sha256:96830ee8...02a0`, `runner v0.47.0 sha256:344fc4c1...b25f`. The tags `latest` printed the same digests as `v0.47.0` for both images. So a cluster on `latest` never runs the digest of `v0.46.1` after `v0.47.0` is out. That is why a newer rolled release makes an older one live (design.md).
7. The cluster side is partly there. `image_digest` reads the text after `@` in the image of a CronJob container (`src/devops_cli/k8s/cluster_job.py:101-109`) and `ClusterJobs.template_digest(RUNNER_TEMPLATE)` calls it (`src/devops_cli/k8s/cluster_job_api.py:129`). Image Updater writes `service:latest@sha256:<digest>` and `runner:latest@sha256:<digest>` every two minutes (`k8s/README.md:1013`). The Role grants `get` on the CronJob `devops-cli-runner` and nothing on Deployments (`k8s/devops/roadmap-service/role.yaml:16-32`). The requirement says "and nothing else" (`openspec/specs/roadmap-implement-runner/spec.md:97`) and `test_the_role_of_the_service_holds_four_rules_and_one_binding` pins the four rules (`tests/core/test_k8s_runner.py:203`). So the Deployment read needs a Role change, a changed pin and a changed requirement. `k8s/devops/roadmap-service/deployment.yaml:72-86` holds the secret as `envFrom` and no secret value, so a read of the Deployment object shows no secret.
8. The registry is reachable from the Service. The package is public (`k8s/argocd/image-updater-values.yaml:8`, "The GHCR package is public"). `devops k8s image-pins` and `devops argo cd apps status` already resolve tags with `tag_digest` as an anonymous client (`src/devops_cli/argo/image_pins.py:84`). The Service pod has public HTTPS through `devops-default-perimeter` (`k8s/devops/roadmap-service/networkpolicy-egress.yaml:1-3`). Not verified from the pod.
9. The row fits the loop. The loop passes each runner `repo_dir` (the directory of `schedule.json`) and `now` (`src/devops_cli/roadmap/run.py:1135-1143`), so the ledger needs no new plumbing. A row that needs no clone is `stage_ready` (`:680-686`).
10. `uv run devops docs check` printed `All documentation files are up to date.` on this tree.

Not verified: a live run of the row (this is a plan); that the digest which Image Updater writes equals the digest that `tag_digest` prints (the command `devops argo cd apps status devops` exits 1 when they differ, `k8s/README.md:1025`, and it is in use, but I could not read the cluster); that the Service pod reaches `ghcr.io`; and the count of requests in a live round.

## Existing Tool Considered

The need has two halves. For the first half, a comment on each issue of a release, open GitHub Actions exist. `apexskier/github-release-commenter` runs on the `release` event, finds the issues and pull requests linked to the commits between two releases, and comments with a template. `remix-run/release-comment-action` and `agrc/release-issue-notifications-action` do the same. I read the README of the first and the last on 2026-11-02. I did not verify their maintenance: the first README shows no release list, and the last shows no date.

I do not use them, for four reasons, each from a fact.

- They cover half. "Live since" needs the cluster, and a GitHub Actions job has no cluster access (`release.yml` sets `permissions: {}` and holds no kubeconfig). The Service must be built for the second half, and it must find the issues of a release with the same code (Feasibility 3). Both halves in one row share that code, one marker and one ledger.
- `release-commenter` comments on pull requests too. A merged pull request would get a comment that no one asked for. Its `skip-label` works by label only.
- Each of them puts third-party code in a job with `issues: write`. The repository pins each action to a commit and the release job holds a GitHub App token; one more action widens that surface for a half of the need.
- release-please has no setting that comments on issues. A web search on 2026-11-02 found no action built for release-please; the results were general actions on the `release` event.

Cost to build: about 90,000 tokens (three modules, a Role change, wiring, tests in nine files, documents) and about 6 hours with two CI runs. Cost to keep: about 4,000 tokens each quarter. Cost to fix one miss: about 12,000 tokens. The tool for the first half would cost about 8,000 tokens and 1 hour (a workflow, a pinned action, a review of its permissions) and would save about 45,000 tokens of the build, but the change would then hold two mechanisms, one marker rule that the workflow cannot share, and a duplicate comment when a person re-runs the failed jobs of `Release` (`RELEASE_CYCLE.md`, "When a Publish Job Fails"). The change deletes no internal code.
