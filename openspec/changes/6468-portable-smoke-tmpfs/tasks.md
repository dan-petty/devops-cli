# Tasks

## 1. Portable tmpfs home in the image smoke steps

Kind: other (workflows). Changes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`.

- [ ] 1.1 Replace `--tmpfs /home/devops:uid=1000,gid=1000` with `--tmpfs /home/devops:mode=1777` in the 8 smoke commands of the two workflows, and keep `exec,size=3g` where a command sets it
  - Verification: `$ ! git grep -n 'home/devops:uid=' -- .github/workflows`
- [ ] 1.2 Keep the smoke steps of `ci.yml` and `release.yml` the same text
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/invariants/test_runner_image.py`
- [ ] 1.3 Validate the changed workflows
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [ ] 1.4 Run the changed smoke commands of `ci.yml` in the devcontainer, with `docker` set to `podman-docker`: build `devops-cli-service:local` (target `service`) and `devops-cli-runner:local` (target `runner`) from `Dockerfile`, run each changed command from a script with `set -euo pipefail`, record the exit codes in a pull request comment, and remove the images
