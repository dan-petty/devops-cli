# Design

## Context

See proposal.md for the cause (#3507). The row `release_comments` reads the `service` and `runner` digests of each release of its window, newest first, through `live_release`.

## Goals / Non-Goals

**Goals:**
- A missing tag of a new release fails no round and suspends no row.
- A missing tag of an old release, and each other read error, still fail the round.
- `check_pins` keeps its handling of a missing tag.

**Non-Goals:**
- Change the window, the interval of the row or the `Live since` text.
- Read the status of the release workflow.

## Decisions

### 1. The age limit is 20 minutes, in a named constant

- **Decision**: `CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES = 20` in `src/devops_cli/config/constants.py`. A release less than 20 minutes old may lack a tag. At or past 20 minutes, a 404 is a fault. The age is `now` minus `ReleaseInfo.published_at`.
- **Reason**: The image build took 5 min 40 s to 6 min 4 s in the evidence. The row runs every 11 minutes. 20 minutes covers the build, a queue, and one full retry round.
- **Alternative considered**: 10 minutes.
  - *Rejected*: The observed 404s reach 5 min 24 s and the runner build ends at 6 min 4 s, so 10 minutes leaves no room for the queue of the release workflow.
- **Alternative considered**: 15 minutes.
  - *Rejected*: One slow queue uses it up before the next 11-minute round reads the release again.

### 2. The rule lives in `live_release`

- **Decision**: `live_release` catches `RegistryTagNotFoundError` for one release and continues the walk when the release is younger than the limit.
- **Alternative considered**: A guard in `_live_pass`.
  - *Rejected*: `_live_pass` gets one error for the whole walk, so it cannot tell the new release from an older one.
- A skipped release is not marked done in the ledger, so a later round reads it again.

### 3. A subclass tells a missing tag from another read error

- **Decision**: `RegistryTagNotFoundError(RegistryReadError)` with error code `DOCKER_REGISTRY_TAG_NOT_FOUND`, raised on HTTP 404 only.
- **Alternative considered**: A boolean attribute on `RegistryReadError`.
  - *Rejected*: An `except` clause cannot select it.
- **Alternative considered**: An unrelated exception.
  - *Rejected*: `check_pins` would no longer catch a missing tag.

### 4. The `runner` tag follows the same rule

- **Decision**: Both reads of a release are in one `try`. A 404 on either tag skips a new release.
- **Reason**: A release is live only when both digests exist.
