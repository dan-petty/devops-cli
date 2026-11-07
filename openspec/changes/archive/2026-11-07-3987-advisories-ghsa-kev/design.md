# Design

## Context

#3898 built `devops research advisories` on OSV. OSV cannot match an Action's version, and has no record of an advisory that a vendor published only on its repository. GitHub holds both kinds, in two endpoints.

## Goals / Non-Goals

**Goals:**
- A finding for an Action and for a mapped component, matched to the version that the repository pins.
- The `exploited` flag from the CISA KEV list.
- Each new client refuses a large reply and a redirect, as the OSV client does, and sends no contact data.

**Non-Goals:**
- A model, a store, or a new scanner.
- Resolving a commit or a major tag to a release.
- Filing issues from the findings (`devops research sweep`).

## Decisions

- **Decision: Two GitHub endpoints.**
  *Choice:* Actions go to `GET /advisories` with `ecosystem=actions` and `affects`; mapped components go to `GET /repos/{owner}/{repo}/security-advisories`.
  *Rejected alternative:* `GET /advisories` for every component. Both Qdrant advisories answer 404 there (2026-11-07), because the repository published them and GitHub did not review them. The test for the Qdrant case would fail.
- **Decision: We match the version, with `packaging`.**
  *Choice:* GitHub returns the range as text. `SpecifierSet` compares it with the pinned `Version`, after `=` becomes `==`.
  *Rejected alternative:* `affects=<name>@<version>`, so that GitHub matches. The repository endpoint has no such parameter, and a second way to match would have two sets of results to keep equal.
- **Decision: A pin names a release only with three numbers.**
  *Choice:* `v45.0.0` and `2026.10.4` are releases. `v7`, `3.14`, a commit and `9.1.2-alpine` are `unpinned`.
  *Rejected alternative:* Take `v7` as `7.0.0`. It would report an advisory for `>= 7.2` as absent and one for `< 7.5` as present, both by luck of the number.
- **Decision: A range that cannot be read is a failure.**
  *Choice:* An advisory with an empty or unreadable range is a `LookupFailure` that names the advisory. The exit code is 1.
  *Rejected alternative:* Skip it. A skipped advisory reads as clean.
- **Decision: One watch list file, with the binaries repeated.**
  *Choice:* `.devops/research-watch.toml` maps ecosystem and name to a repository. A test holds the binary entries to the `source` of `tools.lock`.
  *Rejected alternative:* Read the `source` in `advisories.py`. The inventory `Component` has no source, and a second reader of the lock would be new code for 20 lines of data.
- **Decision: The KEV list is read once, and only when a finding names a CVE.**
  *Choice:* A run with no CVE sends no request to `www.cisa.gov`. A list that cannot be read is `kev_failure`, and the exit code is 1.
  *Rejected alternative:* Mark `exploited: false` when the list fails. That reads as "not exploited".
- **Decision: A shared helper for the public API clients.**
  *Choice:* `devops_cli.http.public_api` holds the client builder and the bounded JSON read. OSV, GitHub and KEV use it.
  *Rejected alternative:* Copy `_osv_json` for each client. Three copies of the cap and redirect rule drift.
- **Decision: The token is optional and goes to `api.github.com` only.**
  *Choice:* The command asks `github_token()` and runs without one. The client follows no redirect and reads a next page only when its URL is on `api.github.com`.
  *Rejected alternative:* Require a token. The data is public, and a run without a token is useful at the limit of 60 requests an hour. A run on this repository sends one request for the Actions and one for each of the 29 repositories of the watch list, so two runs in one hour pass the limit of 60 without a token; the command works without one.
