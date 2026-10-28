# Design

## Context

Parts 1 (#2415) and 2 (#2419) of #883 are merged. This part adds the command that hands the findings of one review session to roadmap intake. The owner's answers on #883 (2026-10-28) set the rules: one candidate for each finding, a fingerprint match is not a model verdict, a finding whose issue is closed as not planned is not filed again, one closed as completed is, and the hand-off is an explicit command.

## Decisions

### A qualifying finding is a saved finding with a fingerprint v2 and a verdict that keeps it

A finding qualifies when `SavedFinding.fingerprint` is 64 lowercase hex characters and `status` is not INVALIDATED or MITIGATED. Admission writes the fingerprint v2 into that field and saves no suppressed finding, so the field marks an admitted tool finding, and the finding is OPEN. A finding with any other fingerprint, such as one that no admission saw, cannot carry a marker, so it stays out.

- Rejected: a list of tool names to tell a tool finding from a model one. No such list exists, and the producer of a tool finding is the tool's own name.
- Rejected: findings.sarif as the source. It holds the admitted findings, but not the verdict a person gave.
- CONFIRMED findings join with #2414, which stores a finding's state. A verdict of VERIFIED or UNVERIFIED keeps an OPEN finding.

### One intake call for each finding, through one store

The command calls `intake_candidate` once for each candidate, in the order of findings.json, with one roadmap store and one intake model for the run.

- Rejected: change `plan_intake` to decide many new candidates in one plan. It would save one read of `.github/labels.yml` for each candidate after the first, and it changes intake for one caller.
- Rejected: one candidate for each session. The owner chose one candidate for each finding.

### What a run costs

For N candidates that no issue settles:

| Mode | GitHub | Model |
| :--- | :--- | :--- |
| `--dry-run` | none | none |
| `--plan` | 1 issue search (#2419), 1 listing of every issue (its pages), N reads of `.github/labels.yml`, and the evidence reads that a proposal cites | N `analysis` chat calls and N embedding calls |
| `--confirm` | as `--plan`, and about 11 REST requests for each placed candidate | as `--plan` |

Each embedding call holds the comparison set and the candidate. `EmbeddingsEngine` caches each text, so after the first call only the texts that the cache does not hold reach the gateway. A finding that an issue settles costs no model call. A session of 41 tool findings that no issue carries costs 41 chat calls and 41 embedding calls in `--plan`.

### The merged-code test runs in the checkout of the working directory

The command reads the working directory one time, finds its checkout, and asks `why_not_on_merged_code` of that checkout. The test reads the local `origin/main`, so a person fetches first. A commit that the checkout does not hold raises `GitOperationError`, and the command exits 1.

### Checks before any request

The command refuses a session that is not on merged code, and a candidate whose text looks like it holds a secret (`NewCandidate.refuse_secrets`), before it reads GitHub. A dry run makes the same checks.

- Rejected: skip a finding whose text looks like a secret, and hand off the rest. A skipped secret finding would leave the run with no sign of it.

### `review path` names the hand-off without git

When `review path` keeps a session, it reads the published findings.json. When the session reviewed a clean tree and has qualifying findings, it prints their count and `devops review intake <session> --plan`. It runs only the part of the merged-code test that needs no git (a `path` subject and a clean checkout), and the command makes the full test.

- Rejected: run `git merge-base` in `review path`. A checkout with no `origin/main` would then fail a review that has already written its session.

### The dry run shows intake's requests one time

A dry run prints the candidates in order, then the issue search, then the requests that intake makes for the first candidate, and a note that intake makes the same requests for each candidate.

- Rejected: print the full plan of each candidate. That is about 18 lines for each finding.

### Exit codes

- 0: the run finished, or no finding qualifies, or every qualifying finding is already filed.
- 1: the session is not on merged code, a candidate looks like it holds a secret, a read or write failed, or, with `--confirm`, intake skipped a candidate because the model's proposal was not usable.

A `--confirm` run that stops part-way leaves each issue that it filed with its marker, so the next run leaves those findings out.

## Risks

- GitHub's search index can lag behind an issue filed seconds before, as #2419 records. Two runs close together can file one finding twice.
- `fix:` in the title is a default. Intake's model sets the type label.
