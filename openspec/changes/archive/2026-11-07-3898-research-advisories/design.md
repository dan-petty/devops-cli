# Design

## Context

The inventory of #3896 lists 558 pins. A research agent has to learn which of them have an advisory. OSV is the one source that the project already calls (`OSVClient`) and that needs no key and no new egress destination.

## Goals / Non-Goals

**Goals:**
- One finding for each advisory that affects the pin of a Python or Node package, with severity, affected range and fixed version.
- No model, no store, and no request to a host that is not `api.osv.dev`.
- A failed lookup is a failure in the report, never a clean component.

**Non-Goals:**
- `GET /advisories` of GitHub, the CISA KEV flag, and the components that OSV cannot match. See "Not in this change" in the proposal.
- A comparison of versions in our code.
- Filing issues from the findings (`devops research sweep`).

## Decisions

- **Decision: OSV matches the version, not our code.**
  *Choice:* Each query holds the exact version, so an advisory in the answer affects the pin. The finding has no "affected" flag, because it would always be true.
  *Rejected alternative:* Ask for the package with no version and compare the version with the ranges. It needs a version comparison for each ecosystem (PEP 440, semver), which is home-made code that OSV already has.
- **Decision: Ask about packages only, and only about an exact pin.**
  *Choice:* The kinds `python-package` and `node-package` go to OSV. A pin that is a range (`>=5.3`) or empty is counted in `unpinned`, because OSV answers a query with no version with every advisory of the package.
  *Rejected alternative:* Ask about the tool entries of the tools lock. The key of a tool can be another package on the registry.
- **Decision: One finding for each advisory and pinned version, with all locations.**
  *Choice:* The same package at the same version in `pyproject.toml` and a requirement file is asked once and has two locations.
  *Rejected alternative:* One finding for each place. It repeats the same advisory.
- **Decision: Read each record once for each package.**
  *Choice:* A batch answer holds ids only, so `get_vulnerability` reads the record for severity, ranges and fixed versions. The command keeps the records it read, so two versions of one package that share an advisory read it once.
  *Rejected alternative:* `POST /v1/query` for each package. It sends one request for each package, and a batch of 340 is one request.
- **Decision: The client refuses what it cannot trust to be complete.**
  *Choice:* An answer over 4 MiB, a redirect, and a batch answer with a next page are failed lookups.
  *Rejected alternative:* Follow the next page. No package of this repository has more than one page, and a first page that reads as complete is the risk. A loop can come with the first case that needs it.
- **Decision: The exit code is 1 when a lookup failed.**
  *Choice:* The report is printed first, then the command exits with 1. Findings alone do not change the exit code, because this command reports and `devops ci audit` gates.
  *Rejected alternative:* Raise an error. It would print no report.
- **Decision: The MCP tool takes no argument.**
  *Choice:* `--root` is not an option of the tool, as for `research_inventory`.
