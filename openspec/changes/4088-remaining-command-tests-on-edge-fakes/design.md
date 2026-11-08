# Design

## Context

See proposal.md for the scope (#4088, group 4 of #3769). The other command groups are separate items, and other changes migrate them at the same time. This change stays inside group 4.

## Decisions

### 1. Each double is replaced by the fake of the edge the command reaches
- **Decision**: the settings come from the `config` fixture; HTTP from `web`; Valkey from the `valkey` fixture or `serving_valkey`; programs from `process_fake`; the keyring from `keyring_store`; OTLP from `otlp`; the Docker engine from `docker_daemon`.
- **Why**: docs/TESTING.md allows a double only at an edge, through the fake of that edge. A patch of `commands.cloudflare._resolve_client` also hides the HTTP request, so a mutation of the request survives.
- **Rejected**: keep the patch under a lower ceiling. The goal of #3769 is a ban, and no ceiling file exists for these patches in the tree.

### 2. The Cloudflare API is a route table in the test file
- **Decision**: `cloudflare_api(web, routes)` serves `(method, path)` pairs on top of `web.serve`. A result goes into the API envelope. A callable gives the whole response, for a page or an echo of the posted body. A path with no route answers 404.
- **Why**: two files use it, and it is 30 lines. The request record of `web` gives the assertions on what the command sent.
- **Rejected**: a shared `CloudflareFake` in `tests/support/fakes/`. Docs/TESTING.md gives every fake a contract suite over recorded responses, which two test files do not justify.
- **Rejected**: `respx` or `pytest-httpx`. They patch the HTTP library and do not know the egress check of `http_client`.

### 3. A test follows the real code path, and an assertion changes only where the double was the source of the text
- **Decision**: three assertions change. `vault status` for a refused connection checks "did not answer", the text the broker prints (the double printed "Connection refused"). `vault sync` with `--key k1 --key k2` checks "Synchronized 2 secret(s)" and the two keyring writes (the double returned a report of three). `access sync --bypass-ips 198.51.100.1` checks the IP as typed in the output and the `/32` form in the posted policy (the double returned `/32` in the summary).
- **Why**: the behavior under test is the same: the command reports what the code returned, and the code sends the normalized IP.
- **Rejected**: keep the double for these three tests. The patch is what this item removes.

### 4. Three tests lose "mocked" from their names
- **Decision**: `test_tls_commands_mocked` is now `test_tls_ca_cert_and_inspect_commands_read_each_others_files`. It runs `tls ca`, `tls cert` and `tls inspect` on the files each step writes. `test_telemetry_status_live_mocked` and `test_telemetry_test_live_mocked` are now `test_telemetry_status_live` and `test_telemetry_test_live`. They use the `otlp` collector fake.
- **Why**: the old names say that a function is mocked. It is not now, and a name that says the opposite of the code is wrong.
- **Rejected**: keep the names. A name that says "mocked" misleads the reader of a test that runs the real code.

### 5. Some patches and one private import stay out of this change
- **Decision**: `test_mcp_serve_stdio_and_sse.py` (5), and the private `_validate_vault_path` import of four unchanged vault tests, stay for another change.
- **Why**: `commands/mcp.py` finds `run_mcp_server` with `getattr(sys.modules[__name__], ...)` so that a test can replace it, and a test cannot reach the server without a patch until that shape is removed from `src/`. `_validate_vault_path` is imported by two test files of other groups, and a rename in `src/` breaks them while their own items are open.
- **Rejected**: patch the SDK object of the server in the mcp tests. The product code would still hold the shape for tests.
