# Proposal

## Why

Issue #909: `src/devops_cli/ai/gateway_bench.py` runs in an ephemeral `python:3.14-slim` container attached to the gateway pod, so it may import only the standard library. The issue asks for three things:

- A test that fails when the module imports a module outside the standard library.
- A comment that says why `_validate_http_url` raises the standard library's `ValueError` and not `InvalidURLError`.
- An error text that does not echo the URL. `run_level` writes `f"{type(exc).__name__}: {exc}"` into `last_error`, and the sweep's JSON and the stored run hold that text. A URL with userinfo or a query token thus put its credential into the benchmark output.

## What Changes

- `_validate_http_url` raises `ValueError("Backend URL is not an http or https URL with a host.")`. The text names no part of the URL. The scheme is not named either: `urllib.parse.urlparse("user:pass@host")` returns `user` as the scheme.
- A comment above the `raise` says why the error is the standard library's `ValueError`: the module runs without `devops_cli`, and `_get_text` and `run_level` catch the error.
- A new test sends a URL with a password and a query token to `run_level` and asserts that `last_error` holds neither.
- The error text reaches the output of `devops ai gateway tune`, so the change carries a spec delta: an ADDED requirement in `gateway-tuning`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `gateway-tuning`: a refused backend URL reaches the sweep's output without its credentials.

## Impact

- `src/devops_cli/ai/gateway_bench.py`.
- `tests/test_ai_gateway_tune.py`.

## Feasibility

- On `origin/main` bb46660c, `_validate_http_url` raised `ValueError(f"Invalid HTTP URL scheme or destination: {url!r}")`, and `run_level` put the text of a `ValueError` from `_post_json` into `last_error`. The new test failed on that code: `last_error` held both `s3cr3t` and `t0k3n`.
- The first criterion of the issue is already met. `test_gateway_bench_imports_only_standard_library` in `tests/test_ai_gateway_tune.py` parses the module with `ast` and compares its imports with `sys.stdlib_module_names`. A copy of the module with `from devops_cli.exceptions import InvalidURLError` made it fail with `assert ['devops_cli'] == []`. The change adds no second test for the same rule.

## Existing Tool Considered

`devops_cli.security.sanitizer.mask_uri_credentials` removes the userinfo of a URL, but the container has no `devops_cli`, so the module cannot import it. The standard library has no function that removes the credentials of a URL. A fixed text with no part of the URL needs no tool. The change deletes the URL from the error text and adds no code.
