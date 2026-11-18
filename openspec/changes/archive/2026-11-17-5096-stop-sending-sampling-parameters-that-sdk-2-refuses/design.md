# Design

## Decisions

### Gate on the installed SDK major version

`_installed_sdk_major()` reads `importlib.metadata.version("anthropic")` and returns the major
number, cached for the process. `_sdk_accepts_sampling_parameters()` returns true only for a
major below 2. A version that cannot be read returns 0, which keeps the SDK 1 behavior rather
than drop a working setting on no evidence.

### Keep the SDK 1 sampling path

SDK 1.17.0 accepts the fields, so the existing capability, adaptive-thinking and
`use_model_sampling` gates stay. The SDK check joins them at the front of the same expression.

### Test at the HTTP seam

The SDK 1.17.0 types accept `extra_body`, and a mocked client hides the body. The new test uses
the fake Anthropic transport and returns HTTP 400 when the JSON body holds `temperature`,
`top_p` or `top_k`. It forces the SDK 2 path by patching `_installed_sdk_major`, so it exercises
the installed SDK's request construction without a second SDK install.

## Rejected alternatives

- **Remove sampling parameters on every SDK version:** it drops a working setting for the pinned
  SDK 1.17.0 and changes more than the issue asks.
- **Keep `extra_body` and rely on the HTTP 400:** every Claude call fails on SDK 2 at run time.
- **Mock the client:** it hides the request body, so the test cannot catch the refusal.
- **A live API call:** it needs a secret and network and is not an offline test.
