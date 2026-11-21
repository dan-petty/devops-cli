# Tasks

## 1. Manifests

- [x] 1.1 CronJob `roadmap-stage` runs the image `ghcr.io/dan-petty/devops-cli/runner`; the gate checks of the stage template and of the Image Updater render read the runner image
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter`
- [x] 1.2 The admission policy `roadmap-service-jobs` admits the runner image for every Job and refuses the Service image for a stage Job; the gate check runs the policy against a stage Job in each form of the runner image, in the Service image and in an image that only starts with the runner repository
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.3 The comment of ImageUpdater `devops` names the 3 templates of the runner image
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

- [x] 2.1 `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `RELEASE_CYCLE.md` and the docstring of `src/devops_cli/roadmap/runner_tools.py` name the runner image for the stage Job
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- #6528: the stage Job runs as a `Coder` agent with a shell and the bootstrap of its checkout.
- Pending a person: after the merge and the Argo CD sync, `devops k8s run-job --template stage` plans one Ready item in the runner image and pushes its branch, the admission policy admits the stage Job of the Service, and the memory peak of the pod goes on #6417.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
