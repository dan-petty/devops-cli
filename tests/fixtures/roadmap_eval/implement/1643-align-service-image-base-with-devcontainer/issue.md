## Friction

The service image and the devcontainer run on different Debian releases. The project is developed, and `devops ci` runs, in the devcontainer, which is `debian:sid` with Debian's own `python3.14` package. The service image, which ships, has been `python:3.14-slim-trixie` (Debian 13, Python built by the Docker Official Image) since v0.2.26. Code and the system libraries it loads are tested on one distribution and shipped on another.

## Evidence

- `.devcontainer/Dockerfile:1` is `FROM debian:sid`, and it installs `python3.14` with apt. It also rewrites `VERSION_CODENAME=forky` to `trixie` in `/etc/os-release`.
- `Dockerfile:4` (`builder`) and `Dockerfile:26` (`service`) are `python:3.14-slim-trixie@sha256:…`. That base came in with v0.2.26 (e70df90, #1178).
- The Docker Official `python` image publishes trixie, bookworm and alpine variants, and no sid variant. Matching the devcontainer therefore means leaving that image.
- Trivy, which gates the service image in `ci.yml` and `release.yml`, has no advisory data for sid. On 2026-10-17, Trivy 0.75.0 with a fresh database was run at every severity on two images:

  | Image | Trivy's result |
  | --- | --- |
  | `debian:sid` | Detected `debian forky/sid`, warned "This OS version is not on the EOL list", scanned 76 packages, reported 0 vulnerabilities. |
  | The pinned `python:3.14-slim-trixie` base | 167 OS vulnerabilities (45 HIGH). |

  On sid, the image's OS scan would therefore pass while checking nothing.

## Remedy

The owner picks one direction:

- **A. The service image moves to sid.** It builds `FROM debian:sid`, pinned by digest, installs Debian's `python3.14`, and installs the same runtime packages as the devcontainer. This choice has two costs:
  - Production runs on Debian unstable, which gets no security-team support; fixes arrive as ordinary unstable uploads.
  - The image needs an OS vulnerability scanner that has sid data, because Trivy has none. This option is not done until a test proves that scanner reports a known-vulnerable package version on sid.
- **B. Keep trixie, but test what ships.** A CI job runs the test suite inside the built service image, so the distribution that ships is one that was tested.

Either way, a test in `tests/test_architectural_invariants.py` reads both Dockerfiles' base images and fails when they name different Debian releases (A), or when no job runs the suite in the service image (B).

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=d509dba7bf6f37dffe17fe482592946a5310fd32 -->
## Proposed design

### Problem statement
The service image and the devcontainer run on different Debian releases. Development and CI run in the devcontainer on `debian:sid`, while the shipped service image uses `python:3.14-slim-trixie` (Debian 13). Code and system libraries are tested on one distribution and shipped on another, so a defect in a system library may pass in dev and fail in production, or vice versa.

### Acceptance criteria
- Criterion 1: A test in tests/test_architectural_invariants.py enforces the distribution invariant for the chosen direction.
  Verification: Run `pytest tests/test_architectural_invariants.py -k debian` on the delivered tree. The test passes. Modify one Dockerfile to name a different release; the test fails.
- Criterion 2: The delivered state satisfies the chosen direction: either the service image base matches the devcontainer (A), or a CI job runs the test suite inside the built service image (B).
  Verification: For A: `grep '^FROM' Dockerfile` shows `debian:sid` and `grep '^FROM' .devcontainer/Dockerfile` shows `debian:sid`. For B: the CI workflow contains a job that builds the service image and runs the test suite inside it.
- Criterion 3: If direction A is chosen, a vulnerability scanner with sid data reports a known-vulnerable package version on sid.
  Verification: Run the chosen scanner against a `debian:sid` image that contains a package with a known CVE. The scanner reports the vulnerability with a non-zero exit code.

### Key questions
- **Should the service image move to sid or keep trixie?**: The owner has not yet chosen. The issue presents two options: A (move the service image to `debian:sid`, matching the devcontainer) and B (keep trixie, but add a CI job that runs the test suite inside the built service image). No decision is recorded in the issue or its replies. (proposed)

### Open questions
- What is the base image for the devcontainer? (missing verified source)
- What is the base image for the service image? (missing verified source)
- Does Trivy have advisory data for Debian sid? (missing verified source)

### Fit
Fits in one pull request.

### Suspected block
The owner must choose direction A (move to sid) or B (keep trixie, test in image) before implementation can begin.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-01: not-applicable.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.body_hash": "d097c6298895563671a3ad06b25574c1c8dd0dd847f1cac353677f90a3f12c7f", "alternatives.checked_at": "2026-11-01T16:32:04.599227+00:00", "alternatives.tool": null, "alternatives.verdict": "not-applicable", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "d097c6298895563671a3ad06b25574c1c8dd0dd847f1cac353677f90a3f12c7f", "refine.commented_at": "2026-10-28T03:22:19+00:00", "refine.comments_seen": "5", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "person", "refine.section_hash": "9b1be3981a88624bfc4f629f2eb6748f0f6ab1dcc479fe247a46e3f04cb991b1", "refine.wait_refs": null} -->
