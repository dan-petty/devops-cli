# Tasks

## 1. Publish the release after its images

Kind: other. Changes: `.github/workflows/release.yml`, `.github/workflows/release-image.yml`.

- [x] 1.1 Let the job `assets` need `release-please`, `image`, `devcontainer-image` and `devcontainer`, and state the order in the comments of both workflows
  - Verification: `$ uv run devops ci --check --only actionlint --only zizmor`
  - Verification: `$ uv run python -c "import yaml; j = yaml.safe_load(open('.github/workflows/release.yml'))['jobs']; push = {k for k, v in j.items() if (v.get('permissions') or {}).get('packages') == 'write'}; n = set(j['assets']['needs']); print(sorted(push), sorted(n)); assert push <= n"` prints `['devcontainer', 'devcontainer-image', 'image'] ['devcontainer', 'devcontainer-image', 'image', 'release-please']` and exits 0; on the base it fails with `AssertionError`

## 2. Documents

Kind: other. Changes: `RELEASE_CYCLE.md`, `docs/SDLC.md`.

- [x] 2.1 State that the image jobs publish first and that a failed image job keeps the draft, add the uv-seed image to the table, and give the order of the release step of the SDLC diagram
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The image grace of the row `release_comments` (`CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES`) stays until a real release proves the order: #5249.
- Pending a person: after the next release, check that each job of its `Release` run passed, and that the `published_at` of the release (`devops gh api repos/dan-petty/devops-cli/releases/tags/<tag> --jq .published_at`) is later than the last `completed_at` of its `Attest & Tag` jobs (`devops gh api repos/dan-petty/devops-cli/actions/runs/<run>/jobs --jq '[.jobs[] | select(.name | test("Attest & Tag")) | .completed_at] | max'`).
