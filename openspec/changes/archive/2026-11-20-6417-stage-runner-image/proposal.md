# Proposal

## Why

The owner decided on 2026-11-19 that the Jobs that change git run in the devtools-based runner image: the stage, implement and fix-checks Jobs (#6417). The implement and fix-checks Jobs use the runner template. The stage Job template `roadmap-stage` still runs the Service image, and the admission policy `roadmap-service-jobs` admits only the Service image for a stage Job.

## What Changes

- CronJob `roadmap-stage` runs the image `ghcr.io/dan-petty/devops-cli/runner`. The template keeps its name, its resources, its volumes, its user, its keys and its retries. The Job runs no bootstrap of its checkout and gets no shell: #6528 adds them.
- The admission policy `roadmap-service-jobs` admits the runner image for every Job of the Service, and refuses the Service image for a stage Job.
- The comment of ImageUpdater `devops` names the 3 templates of the runner image. Its entry `runner` already sets the digest of each of them, because a kustomize image entry matches the image by name.
- The gate checks of the k8s row read the new template and run the policy against a stage Job in each form of the runner image and in the Service image.
- `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `RELEASE_CYCLE.md` and the module docstring of `src/devops_cli/roadmap/runner_tools.py` name the runner image for the stage Job.
- The change carries a spec delta in `roadmap-stage/job`, because a manifest and the admission of a Job are observable.
- The change fits one pull request: about 60 changed lines outside this folder.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/job`: the stage template runs the runner image, and the policy admits the runner image and refuses the Service image for a stage Job.

## Impact

- Manifests: `k8s/devops/cronjob-stage.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`, and a comment in `k8s/argocd/image-updater-values.yaml`.
- Gate checks: `tests/gate/k8s_checks/job_admission_policy.py`, `tests/gate/k8s_checks/stage_job.py` and `tests/gate/k8s_checks/devops_runtime.py`.
- Code: a docstring in `src/devops_cli/roadmap/runner_tools.py`. No stage code changes.
- Live Jobs: Argo CD syncs the CronJob and the policy in one sync. For some seconds, the old policy can refuse a stage Job of the new template. The stage row takes back the check-out and the claim of a refused create, and the next round tries again.
- The pod: the runner image is larger than the Service image, so the first pull on a node takes longer. The runner Jobs pull the same image with `IfNotPresent`. The deadline of the Job includes the pull, and the time budget of the plan comes from that deadline.
- The Service image keeps gh and OpenSpec. The Service round still runs OpenSpec in the row `fix_plan` (`steps/fix_plan.py` calls `revise_plan`, which opens `openspec_tool`), and its clones use the git credential helper `gh auth git-credential`.

## Feasibility

- The dependency #4361 is closed: the runner image builds FROM `ghcr.io/dan-petty/devtools`, pinned by digest in `Dockerfile`.
- The stage Job starts these programs, found in the import closure of `devops roadmap stage --job-item` (332 modules) and in the stage code: `git` (`roadmap/clone_git.py`, `git/worktree_add.py`, `roadmap/stage/stage_paths.py`), `gh` (`github/rate_limiter.py`, `core/process.py`, and the git credential helper), `openspec` (`openspec/tool.py`, `roadmap/stage/stage.py`), the Node runtime of `openspec`, and the entry point `devops`. The stage code calls no `bootstrap_checkout` and starts no tool of its checkout.
- `podman run` of the pinned devtools image (`sha256:a7b2f111…`) on 2026-11-20 found `git` 2.55.0 at `/usr/bin/git`, `gh` 2.105.0 at `/usr/local/bin/gh`, `node` v24.22.3 at `/usr/bin/node`, `openspec` 2.1.0 at `/usr/local/bin/openspec` and `python3.14` at `/usr/bin/python3.14`. `package-lock.json` pins OpenSpec 2.1.0, the version of the Service image. The `runner` stage adds the venv with `devops` on `PATH`, the tiktoken cache, the git credential helper of `gh`, and user `devops` (1000:1000) with the home `/home/devops`. The smoke test of `ci.yml` and `release.yml` runs `python -m devops_cli.roadmap.runner_tools` on each runner image, which checks each of these programs.
- The pod runs as 1000:1000 with a read-only root, and mounts `emptyDir` volumes at `/home/devops` and `/tmp`: the user, the `HOME` and the writable paths of the runner image. The runner Job template has the same user and paths.
- `kubectl kustomize` of `k8s/overlays/homelab/devops` with the image entry `ghcr.io/dan-petty/devops-cli/runner` (`newTag: latest` and a digest), as Image Updater writes it, gave that digest to the containers of CronJobs `devops-cli-runner`, `devops-cli-planner-run` and `roadmap-stage`.

## Existing Tool Considered

Kubernetes CronJob, ValidatingAdmissionPolicy, kustomize image entries and Argo CD Image Updater cover the need, and the runner template already uses them. The change builds nothing: about 120,000 agent tokens and 1 hour to check, change and prove. It deletes the stage branch of the image rule of the policy.
