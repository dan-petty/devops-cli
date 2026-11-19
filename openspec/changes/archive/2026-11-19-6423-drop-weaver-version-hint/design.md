# Design

## Decisions
- The hint names the devtools image `ghcr.io/dan-petty/devtools`, which has weaver in `/usr/local/bin`, and the weaver releases page. It names no version: the version lives in the mise files of dan-petty/devtools, which Renovate bumps.
- The hint text is `MESSAGES.telemetry.weaver_missing_hint`, as the install hints of npm and OpenSpec are in `MESSAGES`. The image name is the constant `CONST_DEVTOOLS_IMAGE` next to the other image names in `constants.py`.

## Rejected alternatives
- Keep the version and add a Renovate regex manager on the constant. The owner rule of 2026-11-19 forbids a tool version in `src/` that a dependency update must change.
- Read the version from weaver at run time for the hint. The hint shows only when no weaver is on PATH, so no weaver can report a version.
- Add a version file under `src/` that the code reads. It puts a tool version back in `src/` that a dependency update must change.
