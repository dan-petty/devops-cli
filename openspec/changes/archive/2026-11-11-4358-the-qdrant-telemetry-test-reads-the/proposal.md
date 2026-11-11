# Proposal: #4358

## Why

`test_upsert_span_names_the_server_by_host_and_port` in `tests/ai/rag/test_qdrant_request_telemetry.py` fails on a branch whose name holds `secret`, `token` or `user`. The tracer adds the branch name of the checkout to each span as `vcs.ref.name` and `vcs.branch`. The test scans every attribute value of the span for the words `secret`, `token`, `user`, `/prefix` and `://`, and finds them in the branch name. Thus agents rename their branches to make the test pass. Closes #4358.

## What Changes

- Each part of a test URL that a span must not show (the userinfo, the path and the query) holds the marker `..hidden`. Git refuses `..` in a branch name, so the branch name of the checkout never holds the marker.
- The test scans every attribute value of the span for `..hidden` and `://`. The scan stays on all attributes, so a leak in an attribute that the tracer adds is still found.
- The change alters no behavior that a consumer observes: it changes one test file only. Thus it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/ai/rag/test_qdrant_request_telemetry.py`
- Code: none. The tracer continues to add the branch name to each span.

## Feasibility

- Command output: on the local branch `probe/4358-token-probe` at `1ca0133a`, `uv run pytest tests/ai/rag/test_qdrant_request_telemetry.py` failed 7 of 9 tests, each with `assert not ['probe/4358-token-probe', 'probe/4358-token-probe']`. With this change, the same command on the same branch passed 9 of 9 tests.
- Source: `_enrich_span_attributes` in `src/devops_cli/telemetry/tracer.py` sets `vcs.ref.name` and `vcs.branch` from `_detect_vcs_metadata`, which reads `.git/HEAD` of the first directory above the current directory that holds `.git`.
- git 2.55.0: `git check-ref-format --branch 'fix/a..hidden'` refuses the name, and `git check-ref-format --branch 'fix/push-token-example'` accepts it. `urllib.parse.quote` and `httpx.URL` keep `..` as it is, so an encoded leak still holds the marker.
- The scan still finds a leak: a temporary edit that put the URL into a span attribute of `QdrantClient` made 6 of the 7 cases fail. The 7th case (`k8s-malformed`) returns before the edited line.

## Existing Tool Considered

pytest covers the need with plain test data. The change adds no library and no helper, and deletes no internal code. The proposed design of the issue named pytest's `monkeypatch` on `_detect_vcs_metadata` and `_detect_k8s_context`. `docs/TESTING.md` does not let a test patch a devops-cli function or import a private name, so the change does not use it (see `design.md`).
