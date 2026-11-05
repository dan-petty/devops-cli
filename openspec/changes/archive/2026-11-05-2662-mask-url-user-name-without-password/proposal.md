# Proposal

## Why

Issue #2662: `redact_text` and `mask_uri_credentials` in `src/devops_cli/security/sanitizer.py` leave the user name of a URL as written when the URL has no password.

- `_mask_url_candidate` masks the userinfo only when `parts.password is not None`. `mask_uri_credentials` masks it only when `u.password` is set. A URL such as `http://<token>@example.com:11434/api/embed` has a user name and no password, so both functions return it unchanged.
- Some services take a token as the user name, with an empty password. httpx2 sends such a URL as Basic authentication, and a token can be in `ai.ollama_urls`. An error text that quotes the URL then shows the token. The same text with a user name and a password shows `<masked-user>:<masked-password>`. The two cases differ.
- A parser cannot tell a token from a harmless name such as `git` in `ssh://git@host/`. The issue asks for a rule. The rule goes in the docs of the sanitizer and in its tests.

## What Changes

- The rule: the user name of a URL is masked when the URL has no password. The scheme does not matter. A harmless name is masked too, because a parser cannot tell it from a token.
- `redact_text` shows `<masked-user>` in place of the user name. The host, the port, the path, the query and the fragment stay as written.
- `mask_uri_credentials` shows `***` in place of the user name. A user name with a password keeps its name and shows `user:***`, as before.
- The module docstring of `sanitizer.py` states the rule, and the docstrings of `redact_text` and `mask_uri_credentials` point to it.
- The output of `redact_text`, `mask_secrets` and `mask_uri_credentials` is a result that a consumer sees. So the change carries a spec delta. It adds three requirements to the capability `secret-masking`: the user name with no password is masked, a URL with no user name stays as written, and a user name with a password keeps its masking.
- The tests that held the old behavior now hold the new rule: the cases `custom://myuser@example.com/path` and `https://ghp_x@example.com/o/r` in `tests/ai/client/test_url_credential_masking.py`, the case `user-only` in `tests/security/test_secret_redaction.py`, and the message of the case `ssh-url-form-names-the-tunnel-host` in `tests/k8s/test_gitea_doctor.py`, which quotes `ssh://git@<host>:2222/...`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: the user name of a URL with no password is masked.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py`, `tests/ai/client/test_url_credential_masking.py` and `tests/k8s/test_gitea_doctor.py`.
- A text with `ssh://git@host/path` now shows `ssh://<masked-user>@host/path` in masked output, for example in the message of the Gitea check of `devops k8s doctor` for a wrong `ssh_url`. This is the cost of the rule, and the design records it.

## Feasibility

- On `origin/main` at `f6d57ecd`, `redact_text("error calling http://tok_0123456789abcdef@example.com:11434/api/embed failed")` returned the text as it was. The same text with `user:pw12345` as the userinfo returned `<masked-user>:<masked-password>`. `mask_uri_credentials("http://tok_0123456789abcdef@example.com:11434/api/embed")` returned the URL as it was. The premise of the issue holds.
- httpx2 2.13.1 sends such a URL as Basic authentication. `httpx2.Client().build_request` on `http://tok_0123456789abcdef@example.com:11434/api/embed` gives a `BasicAuth` flow, and the request carries an `authorization` header. So a token in the user name is a real credential.
- `urllib.parse.urlsplit` gives `username='tok_0123456789abcdef'` and `password=None` for the same URL. `httpx2.URL` gives the user name and an empty password. Both parsers separate the userinfo from the host, so the change needs no pattern of its own. The IPv6 host `[2001:db8::1]:11434` and an `@` in a query stay correct, and the tests cover both.
- pip 26.3 masks a user name with no password. `redact_auth_from_url("http://tok_0123456789abcdef@example.com/x")` returns `http://****@example.com/x`, and the form with a password returns `http://user:****@example.com/x`. So the rule follows an open, maintained tool.
- Issue #1109 (closed) made the parsers `urllib` and httpx2. Pull request #3639 (issue #2613) changed `sanitizer.py` and is merged. It changed the keyword rules and not the URL step, so its behavior stays: prose after a token colon is unmasked. No open pull request touches `sanitizer.py`.
- The refine step of the issue answered the open question: mask the user name. The reason is least exposure, as a token and a name look the same. A person can reverse the choice, and the module docstring and the tests are the one place to change.

## Existing Tool Considered

The alternatives check of the issue (2026-11-04) found no tool that scans free text and masks a user name with a placeholder. The change uses the two parsers that the module already uses, `urllib.parse.urlsplit` and `httpx2.URL`. It adds no pattern and no helper. pip uses the same rule for its own output, as the Feasibility section shows. The change deletes no internal code.
