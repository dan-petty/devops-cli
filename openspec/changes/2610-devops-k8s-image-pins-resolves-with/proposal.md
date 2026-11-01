# Proposal

## Why

Issue #2610: devops k8s image-pins resolves each pin with a GET request via docker buildx imagetools inspect. Docker Hub counts that read as an anonymous pull. Thirteen of the 31 pins are on Docker Hub, so each run spends 13 pulls from the shared allowance. A run can fail with toomanyrequests when the allowance is exhausted.

## What Changes

- Replace the docker buildx imagetools inspect subprocess call in resolve_image with tag_digest from devops_cli.docker.registry, which sends a HEAD request
- Remove inspect_command and image_reference from src/devops_cli/k8s/image_pins.py
- Remove ImagetoolsFake, its contract suite, its recording script, and its fixture data
- Rewrite the resolution tests in tests/k8s/test_image_pins.py to double the registry at the HTTP edge with an httpx2 client
- No new tool pin in tools.lock is needed because tag_digest is project code
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-image-pins`: HEAD resolution, No subprocess for resolution

## Impact

- Code: `src/devops_cli/k8s/image_pins.py`
- Tests: `tests/k8s/test_image_pins.py`, `tests/support/fakes/imagetools.py`, `tests/k8s/test_imagetools_contract.py`, `tests/support/imagetools_recording.py`, `tests/fixtures/imagetools_runs/recorded_runs.json`

## Feasibility

- The premise is confirmed by the code: src/devops_cli/k8s/image_pins.py line 109 builds a docker buildx imagetools inspect command, and its docstring records the measurement of three inspects taking ratelimit-remaining from 100 to 97.
- src/devops_cli/docker/registry.py line 79 defines tag_digest, which calls client.head(url, ...) and reads Docker-Content-Digest from the response headers. It handles the 401 Bearer token challenge.
- src/devops_cli/argo/image_pins.py line 84 already calls tag_digest(pin.image, client, timeout=timeout), proving the function works in production.
- First checks the implementation runs: uv run pytest tests/k8s/test_image_pins.py -x verifies the new resolution path; uv run pytest tests/docker/test_registry_tag_digest.py -x verifies tag_digest still passes; ! git grep -n ImagetoolsFake src/ tests/ confirms the fake is fully removed.

## Existing Tool Considered

crane (go-containerregistry, Apache-2.0, maintained by Google) sends a HEAD and is the open tool that covers the need. The project's own tag_digest in src/devops_cli/docker/registry.py already implements the same HEAD read with Bearer token handling, added in #1997 and used by devops argo cd apps status. Using tag_digest avoids a new binary pin, a new fake, and a new contract suite. The written cost of building crane's pin, fake, and contract suite is roughly 8000 tokens of code and 30 minutes of elapsed time for the pin alone, plus the fake and contract suite. The change deletes ImagetoolsFake in tests/support/fakes/imagetools.py, its contract suite in tests/k8s/test_imagetools_contract.py, and its recording in tests/support/imagetools_recording.py.
