# Design

## Context

See `proposal.md`. `_mask_url_candidate` in `src/devops_cli/security/sanitizer.py` handles each URL that `redact_text` finds in free text. `mask_uri_credentials` handles one URL. Both return a URL with no password as it was.

## Goals / Non-Goals

**Goals:**

- A token in the user name of a URL does not show in masked text.
- The rule is written in the docs of the sanitizer and held by tests.

**Non-Goals:**

- A user name that holds a `/`, `?` or `#` that is not percent-encoded. It is not valid userinfo. The parser reads the part after the character as the host or the path, so no rule can mask it.
- A URL with no `://`, such as the scp form `git@host:org/repo.git`. `redact_text` finds a URL by its `://` and has never changed such a text.
- The keyword rules for `token` and `password`. Issue #2613 owns them, and its pull request is merged.

## Decisions

### 1. Mask a user name with no password

The user name is masked in `redact_text` and in `mask_uri_credentials`, in every scheme.

- *Rationale*: a service can take a token as the user name. httpx2 sends the URL as Basic authentication, so the user name is a credential. A parser cannot tell a token from a harmless name. The safe rule masks both.
- *Rationale*: pip masks a user name with no password in the same way.
- *Rejected alternative*: mask only a user name that looks like a token, with `_looks_like_a_credential`. A token with no digit, no capital and fewer than 24 characters would show. A token can be a plain word, and a name such as `git` is also a plain word, so the check cannot split them.
- *Rejected alternative*: keep a list of harmless names such as `git`. The list grows with each service, and a token that matches an entry would show.
- *Cost*: `ssh://git@host/path` shows as `ssh://<masked-user>@host/path` in masked output. The host and the path still show, so the text keeps its use. The message of the `clone-url` check of the Gitea doctor (`devops k8s doctor`) for a wrong `ssh_url` is the one such text in the tests, and its test now expects `<masked-user>`.

### 2. Use the parser that each function already uses

`_mask_url_candidate` reads `urlsplit` and `mask_uri_credentials` reads `httpx2.URL`. Each already finds the userinfo. The change adds one branch to each: a user name with no password.

- *Rejected alternative*: a regex for `scheme://user@`. The issue and `AGENTS.md` ask for a standard parser. A regex fails on IPv6 hosts, on `@` in a query and on a password with `@`, which #1109 fixed.

### 3. Keep the shape of the old placeholders

`redact_text` shows `<masked-user>` for a user name alone, as it shows `<masked-user>:<masked-password>` for a user and a password. `mask_uri_credentials` shows `***` for a user name alone, as it shows `***` for a password with no user. A user name with a password keeps the name and shows `user:***`, so the three forms of one function stay consistent.

- *Rejected alternative*: a new placeholder such as `<masked-token>`. The sanitizer does not know that the name is a token.

### 4. An empty user name stays

`http://@example.com/x` has an empty user name and no password. It holds no credential, so `redact_text` returns it as it was. `mask_uri_credentials` keeps its fail-closed rule from #1109 and returns `<masked-url>` for a text that has an `@` and no userinfo, and this change does not touch that rule. The form `http://:@example.com/` has userinfo, so `mask_uri_credentials` returns it as it was.

## Risks / Trade-offs

- [Risk] A harmless user name in a clone URL is masked, so a person reads `ssh://<masked-user>@host/path` and not the name.
  - Mitigation: the host and the path stay. A person who needs the name reads the config or the remote, which the masker does not touch. The choice is one place in the module docstring, so a person can reverse it.
