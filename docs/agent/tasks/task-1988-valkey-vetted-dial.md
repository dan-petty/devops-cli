# Task: The Valkey client resolves a name once, vets every answer and dials the vetted address (#1988)

**Issue**: [#1988](https://github.com/dan-petty/devops-cli/issues/1988)
**Scope**: scope/security
**Feasibility**: This check used the source of valkey-py 6.2.0 in the project environment. `Connection._connect` calls `socket.getaddrinfo(self.host, ...)` itself and has no resolver hook. `SSLConnection._connect` gets its socket from `super()._connect()` and then calls `_wrap_socket_with_ssl`, which sends `server_hostname=self.host`. `ssl_check_hostname` is `False` by default. The default retry is `Retry(NoBackoff(), 0)`, and `AbstractConnection.connect` catches only `socket.timeout` and `OSError`. So `SSRFBlockedError` and `httpcore2.ConnectError` pass through valkey-py unchanged. A probe on the tree before the change counted the lookups of one `ping` with a resolver that changes its answer. The client made three lookups and dialled the third answer, 127.0.0.2, which no check saw. `vet_addresses` of #898 at `EgressLevel.PRIVATE` refuses every spelling of a cloud metadata address and admits 169.254.1.2.

## Description

Step C of #1113. Before this change, the Valkey client resolved a name three times: in the constructor, in the check of `_GuardedConnection.connect`, and in the dial of valkey-py. The check saw only the first two answers. A rebinding DNS server could give the dial an address that no check saw. A failed lookup passed the check with no address when private networks were allowed, and the check refused every link-local address, also the 169.254.1.2 that a rootless Podman container reaches its host at.

Now the constructor makes no lookup. `_VettedConnection._connect` resolves the host once for each dial with `vet_addresses` at `EgressLevel.PRIVATE`. It dials the vetted IP literals in answer order and raises the last failure, as `VettingBackend.connect_tcp` does. `_VettedSSLConnection` puts the `SSLConnection` of valkey-py in front of the vetted dial. The TCP connection goes to the vetted literal, and the handshake uses the host name of the endpoint for SNI and for the certificate check, with `ssl_check_hostname=True` and the platform CA store. `_valkey_failures` makes a refusal of the egress check and a failed lookup a `ValkeyConnectionError` that names the host and the port.

Behaviour that changes:

- A cloud metadata address and a scoped IPv6 address are refused when the client dials, not when it is built. The error is `ValkeyConnectionError`.
- A link-local address that is not a cloud metadata address, such as 169.254.1.2, is dialled.
- A failed lookup is a `ValkeyConnectionError` that names the host.
- A `valkeys://` or `rediss://` endpoint in the `host` argument connects over TLS and checks the certificate against the host name. Before, it connected in plaintext. `runs.index_url` gives the client its URL in this argument.
- `validate_destination`, `_resolved_addresses`, `_GuardedConnection` and the `allow_private_network` argument of `ValkeyClient` are gone. No caller in `src` passed the argument, so every connection used the private level before and after.

Open tools used: `vet_addresses` of #898 for the lookup and the check, `SSLConnection` of valkey-py for TLS, and the generators of `devops_cli.crypto.tls_certificates` for the test CA. The build is one `_connect` override of 16 lines and one TLS class with no body.

## Acceptance Criteria

- [x] The constructor makes no DNS lookup (`test_the_constructor_makes_no_lookup`).
- [x] One dial makes one lookup. The name answers loopback first and a public address after, and the client dials loopback (`test_one_dial_makes_one_lookup_and_dials_the_address_it_vetted`).
- [x] The client dials the vetted IP literals in answer order. The first answer refuses the connection and the second accepts it (`test_the_client_dials_the_vetted_addresses_in_answer_order`).
- [x] A name that answers a metadata address, `169.254.169.254`, `2852039166` and `::ffff:169.254.169.254` each give `ValkeyConnectionError`, not `SSRFBlockedError`, and no connect (`test_a_host_that_answers_cloud_metadata_is_a_connection_error_with_no_dial`). The floor fails a test whose code connects to an address that is not loopback.
- [x] A failed lookup gives `ValkeyConnectionError`, and the message names the host (`test_a_failed_lookup_is_a_connection_error_that_names_the_host`).
- [x] The client dials 169.254.1.2 (`test_a_link_local_address_that_is_not_cloud_metadata_is_dialled`).
- [x] The client dials `2130706433` as 127.0.0.1 (`test_a_numeric_spelling_is_dialled_as_the_address_it_spells`). The metadata test refuses the spelling `2852039166`.
- [x] For `valkeys://`, a loopback TLS server with a CA that the generators of `devops_cli.crypto.tls_certificates` make shows that the client accepts a certificate for the URL host and refuses a certificate for another name from the same CA. The server of the refused handshake records no command (`TestValkeyClientTls`).
- [x] `validate_destination`, `_resolved_addresses` and the `allow_private_network` argument are not in `valkey/client.py`.
- [x] The new tests failed on the tree before the change, 11 of them, and pass after it. A change of `ssl_check_hostname` to `False` fails the TLS test. A dial of the host name in place of the vetted literal fails five tests.
- [x] These commands pass: `uv run ruff check`, `uv run ruff format` and `uv run mypy` on the changed files, and the targeted tests of the modules that reach the client.
- Pending a person: against a real Valkey 8 that a DNS name reaches, run `uv run devops valkey ping` and `uv run devops ai runs reindex`. Both connect.
- Pending a person: set `runs.index_url` to the `valkeys://` URL of a TLS Valkey whose certificate names the host, and run `uv run devops ai runs reindex`. It connects. With a certificate for another name, it fails with `certificate verify failed`.

## Deliverables

- [x] Replace the destination check in `src/devops_cli/valkey/client.py` with `_VettedConnection` and `_VettedSSLConnection`. Map the refusals in `_valkey_failures`. Remove the `allow_private_network` argument.
- [x] Add `CONST_VALKEY_TLS_SCHEMES` to `src/devops_cli/config/constants.py`.
- [x] Replace `TestValkeyClientDestination` in `tests/test_valkey.py` and add `TestValkeyClientTls`. The tests use the shared `ScriptedResolver` of `tests/web_fakes.py`.
- [x] Add the TLS handshake to `serving_valkey` in `tests/support/fakes/valkey.py`, and add the `local_ca` fixture in `tests/support/certificates.py`.
- [x] Add an update line to `docs/agent/tasks/task-1113-valkey-py-replaces-the-hand-written-client.md`, and tick its step.
- `valkey.url` gives the client a host and a port, not the scheme, so a `valkeys://` URL there still connects in plaintext. Step B of #1113 gives every endpoint one validated URL: moved to #2026.
