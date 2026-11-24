# Proposal

## Why

Each push runs two hosted image jobs of `.github/workflows/ci.yml` that build one image each, and #4649 asks for one job that builds both images with one bake call. The account runs at most 20 hosted jobs at one time, so the job that the merge removes shortens the queue of every pull request. At the staged commit `mcp-server` builds on the Service chain, so the merge removes one hosted job and the setup it repeats, not the repeated runner build that the issue names.

## What Changes

- The jobs `runner-image` and `mcp-server-image` of `.github/workflows/ci.yml` become one job, with the id `mcp-server-image` and the name `Runner Image`, so one push starts one hosted image job.
- A step writes `docker-bake.hcl` with targets `runner` and `mcp-server`. One `docker/bake-action` step replaces the two `docker/build-push-action` steps, pinned to a full 40-character commit SHA with a version comment.
- Each target keeps its local tag and its `cache-from` of `type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache` inside the workflow, with no literal repository path and no `type=gha` entry, and the `mcp-server` target keeps `no-cache-filter = ["mcp-server"]`.
- The merged job runs both smoke tests and both scans, with the categories `trivy-image-runner` and `trivy-image-mcp-server`, and the runner scan keeps `exit-code: "0"`.
- The merged job sets `timeout-minutes: 18`, the bake step 12 and each scan step 4.
- `tests/invariants/test_runner_image.py`, `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_architectural_invariants.py` and the run-step allowlist of `tests/commands/test_ci.py` read the merged job.
- The change carries no spec delta: it edits a workflow and its tests, and every base requirement that names the job, its smoke tests, its scans and its registry cache stays true, because the cache ref of each target stays in `.github/workflows/ci.yml` with the `${{ github.repository }}` expression.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `.github/workflows/ci.yml`
- Tests: `tests/invariants/test_runner_image.py`, `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_architectural_invariants.py`, `tests/commands/test_ci.py`

## Feasibility

- The `probes` say, word for word: The path `.github/workflows/ci.yml` is a file of the staging commit. The path `docker-bake.hcl` is no file of the staging commit. No commit in the history deleted or renamed it. The plan edits the workflow and creates no file.
- The premise of the issue is false at the staged commit: the body calls the `mcp-server` stage a child of `runner` at `Dockerfile:121`, and `Dockerfile:177:FROM mcp-server-deps AS mcp-server` builds it on the Service chain, which `Dockerfile:170:FROM service-deps AS mcp-server-deps` starts, while the runner chain starts at `Dockerfile:82:FROM devtools AS runner-deps`.
- Comment 4 of the owner, 2026-11-19, says the MCP server image stays on `python:3.14-slim-trixie`, so after #4361 it no longer builds FROM runner and its job no longer repeats the runner build; comment 5 gives two cold runs of the Runner Image job of 4:15 and 6:27, most of it in the `load: true` export and the Trivy scan. The plan therefore claims one hosted job and the setup it repeats, and no repeated runner build.
- The `false_premise` finding is fixed: `docker/bake-action` requires a bake file path in `files`. A workflow step writes `docker-bake.hcl` before the bake step, so the change stays in `.github/workflows/ci.yml` and commits no static bake file to git.
- The `spec_delta_wrong` finding is fixed: the `cache-from` of each target stays in `.github/workflows/ci.yml` in the generated bake file. The `${{ github.repository }}` expression and the `:buildcache` tag stay in the workflow, and no literal repository path is written; the requirement `Each image build keeps its own registry cache` of `container-image-layers` asks for that ref and no `type=gha`, and `docs/CLUSTER.md:76:Each image build reads the registry cache of its target` states the same form.
- The action documentation check is verified: `docker/bake-action` splits `files` by newline or comma into file paths and passes `--file` flags to `docker buildx bake`. It does not accept inline HCL text in `files`. Writing `docker-bake.hcl` in a step gives the action a valid file path.
- `read_file` on `.github/workflows/ci.yml` lines 495 to 760 showed the two jobs at `.github/workflows/ci.yml:539:runner-image:` and `.github/workflows/ci.yml:640:mcp-server-image:`, the two builds at `.github/workflows/ci.yml:599:uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc` with `.github/workflows/ci.yml:603:target: runner` and `.github/workflows/ci.yml:704:target: mcp-server`, and the MCP cache filter at `.github/workflows/ci.yml:708:no-cache-filters: mcp-server`.
- The same call showed the two cache lines at `.github/workflows/ci.yml:608:cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/runner:buildcache` and `.github/workflows/ci.yml:710:cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/mcp-server:buildcache`, both smoke tests by their bounds at `.github/workflows/ci.yml:620:if [ "$size" -gt 7000000000 ]` and `.github/workflows/ci.yml:722:if [ "$size" -gt 3000000000 ]`, the two scans at `.github/workflows/ci.yml:632:category: trivy-image-runner` with `.github/workflows/ci.yml:636:exit-code: "0"` and `.github/workflows/ci.yml:730:category: trivy-image-mcp-server`, and the pull request cache rule at `.github/workflows/ci.yml:506:write none: the release is the one writer of the tag (#4646)`.
- The job limit rule is at `.github/workflows/ci.yml:36:# Each job limit is about two times the longest run of the job, and 5 minutes at least, so a hung`, and `tests/invariants/test_workflow_contracts.py:95:def test_every_job_has_a_limit_and_each_step_limit_is_under_it` refuses a step limit that is not under its job's.
- The tests that read the two jobs are `tests/invariants/test_runner_image.py:36:job = _workflow("ci.yml")["jobs"]["runner-image"]`, `tests/invariants/test_mcp_server_image.py:29:job = _workflow("ci.yml")["jobs"]["mcp-server-image"]` and the parameter `tests/invariants/test_architectural_invariants.py:685:("runner-image", "Dockerfile"),`, and the run-step allowlist is `tests/commands/test_ci.py:1775:allowlist: dict[tuple[str, str], str] = {`, which holds `tests/commands/test_ci.py:1786:("runner-image", "Run Runner Image Smoke Test"): "Docker container tool smoke tests",`.
- The `references` call for `runner-image` answered `files 22, lines 24`, and the four paths outside `openspec/changes/archive/` are `.github/workflows/ci.yml`, `tests/commands/test_ci.py`, `tests/invariants/test_architectural_invariants.py` and `tests/invariants/test_runner_image.py`, which are the changes of groups 1 to 3; the 18 archived files stay unchanged, because an archived change is a record.
- The `references` call for `mcp-server-image` answered `files 26, lines 36`, and the five paths outside `openspec/changes/archive/` are those four and `openspec/specs/mcp-server-image/spec.md`, which decision 3 covers; the 21 archived files stay unchanged, for the same reason.
- The base specs stay true: the merged job keeps the id `mcp-server-image`, which the requirement `The release gate equals the pull request gate` of `openspec/specs/mcp-server-image/spec.md` names, and the name `Runner Image`, which the requirement `The scan of the runner image reports and stops no build` of `openspec/specs/roadmap-implement-runner/spec.md` names, and it keeps both smoke texts, both categories and `exit-code: "0"`.
- The `no-cache-filter` of `mcp-server` rests on `Dockerfile:179:RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*`, and the runner stage runs no upgrade of its own, as `docs/CLUSTER.md:76:the runner runs no` and `Dockerfile:79:through Renovate, so the runner runs no` say, so the runner target sets no `no-cache-filter`.
- The plan calls no function; the implement step resolves the 40-character commit SHA of `docker/bake-action` with a network read of the GitHub API, which is a precondition of that step and of no group command.
- The verify programs are `uv run devops ci --check --only actionlint,zizmor` and `uv run devops ci test tests/invariants`, which run `uv`, `devops`, `pytest`, `actionlint` and `zizmor`: each is a runner tool of the image, none is `NOT_IN_RUNNER`, the plan introduces no program, and a failing row stops the step with the failure class `test`; the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The workflow steps run on a GitHub-hosted runner and need `docker` and `docker buildx`, which are `NOT_IN_RUNNER` for the pod, so no group command builds an image.
- The first checks against the real system: `uv run devops ci --check --only actionlint,zizmor` parses and lints the edited workflow; `uv run devops ci test tests/invariants` and `uv run devops ci test tests/commands/test_ci.py` read the job ids, the step names and the run steps of `.github/workflows/ci.yml`; and after the merge `gh api repos/dan-petty/devops-cli/actions/runs/<run-id>/jobs --jq '.jobs[] | [.name, .started_at, .completed_at]'` gives the run of the merged job.
- The dependency #4646 is delivered: `.github/workflows/ci.yml:506:write none: the release is the one writer of the tag (#4646)` shows that the pull request jobs write no cache, so the merged job reads the registry cache of each target and writes none.

## Existing Tool Considered

The official, maintained Docker action `docker/bake-action` covers the need: one step resolves the `runner` and `mcp-server` targets of one `Dockerfile` in one build graph, loads both images, and keeps each target's tags, `cache-from` and `no-cache-filter` in the workflow. The repository pins no other action for a bake, and `docker/build-push-action` stays in the Service image job and in the release. The change writes no tool of its own and no new code.

## Dependencies

- #4646: it stopped the cache export of the pull request image jobs and its change is archived, so the merged job reads the registry cache of each target with `cache-from` and writes none, and the release stays the one writer of the cache.
