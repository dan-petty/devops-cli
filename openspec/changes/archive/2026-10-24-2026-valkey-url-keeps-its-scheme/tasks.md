# Tasks

## 1. The scheme of valkey.url decides TLS

- [x] 1.1 Write `TestValkeyUrl` in `tests/test_valkey.py` and `test_fetch_valkey_status_connects_over_tls_for_a_valkeys_url` in `tests/test_ui_dashboard.py`, and verify that `uv run devops ci test tests/test_valkey.py tests/test_ui_dashboard.py` fails on the base: 14 tests fail and 4 have errors
- [x] 1.2 Add `ValkeyConfig.endpoint` and `_valkey_scheme`, make a `valkey.url` with a Valkey scheme set `valkey.host` and `valkey.port`, and make the four readers of the settings dial the endpoint, and verify that `uv run devops ci test tests/test_valkey.py tests/test_ui_dashboard.py` passes
- [x] 1.3 Verify that the tests of the other modules that read the `valkey` settings pass: `uv run devops ci test tests/test_k8s_bootstrap.py tests/test_k8s_networking.py tests/test_k8s_proxy_addressing.py tests/test_rag_embeddings.py tests/test_embedding_config_retention.py tests/test_ai_subcommands_rag.py tests/test_security_threat_intel.py tests/test_library_vector_tier.py tests/test_config_env_overrides.py tests/test_config_audit_keys.py tests/test_config_cmd.py tests/test_config_commands.py`
- [x] 1.4 Describe `valkey.url` in its field, regenerate the docs with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- The rest of step B of #1113: one validated `valkey://` or `valkeys://` URL names each Valkey endpoint, the database of the URL is read, a URL that is not valid is refused with a message that names the key, and `valkey.host`, `valkey.port`, `valkey.db` and their environment variables go: moved to #2060.
- Pending a person: set `valkey.url` to the `valkeys://` URL of a TLS Valkey whose certificate names the host, and run `uv run devops valkey ping`. It connects. With a certificate for another name, it fails with `certificate verify failed`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
