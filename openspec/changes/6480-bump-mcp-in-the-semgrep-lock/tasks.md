# Tasks

## 1. Record where the Semgrep pin and its advisories are owned

Kind: other. Reads: `docs/SDLC.md`, `CHANGELOG.md`. Changes: `docs/SDLC.md`.

- [ ] 1.1 Extend the `audit` row of `docs/SDLC.md` with one sentence: the Semgrep requirement file and the advisories of the tools that the devtools image installs belong to the devtools repository, which audits and bumps them. Keep the sentence of that row that names the devtools repository and issue #4363, and add that this repository therefore holds no Semgrep requirement file and no osv-scanner ignore entry, so GHSA-qx49-fqc8-xw99 needs no entry here
  - Verification: `$ uv run devops ci --check --only docs` passes
- [ ] 1.2 Edit `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: When a Semgrep release allows `mcp` 1.30.0 or later, the tools lock takes that release, `semgrep.txt` is compiled again, and the entry for GHSA-qx49-fqc8-xw99 goes. The four other `mcp` 1.29.0 entries go in the same change., The Semgrep requirement file and the ignore file were deleted by #6555, so no release can move a pin here; only a person decides that the item is obsolete.
- Pending person: Until then, the entry is renewed in 3-day steps with new proof, at most 14 days in all (SECURITY.md). After that, the owner decides., No osv-scanner ignore entry remains to renew, because the ignore file and the tools lock that it named are gone (#6555), and only the owner decides what the end of the window means.
