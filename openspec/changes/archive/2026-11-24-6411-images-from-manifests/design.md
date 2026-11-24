# Design

## Decisions
- Add suspended CronJob templates under `k8s/devops/` with restricted Pod Security context.
- Read CronJobs via `kubectl get cronjob <name> -n devops --ignore-not-found -o json`.
- For `service-probe`, copy the container image and both pod and container security contexts.
- For `volume-move`, copy only the container image. Volume copy pods require root privileges to preserve file ownership.
- Ship the harbor task `Dockerfile` inside package directory `src/devops_cli/roadmap/implement/harbor/Dockerfile`.
- Read the shipped `Dockerfile` using `importlib.resources`.

## Rejected alternatives
- Keep constants in Python: Renovate cannot track them without custom regex managers.
- Copy restricted security context for volume move: GNU tar cannot preserve file permissions as a non-root user.
- Root Dockerfile for harbor: Mixes workspace Dockerfile with product artifact.
