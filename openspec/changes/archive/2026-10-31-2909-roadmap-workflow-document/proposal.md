# Proposal

## Why

Issue #2909 is the first item (W1) of tracker #2908. The rules of an issue's life are in five documents and in the specs of the jobs. No page names all the steps, the states and the three human gates. A reader must join `docs/SDLC.md`, ADR 0016, `k8s/README.md`, `docs/ROUTINE_TASKS.md` and `CONTEXT.md` to learn what happens to an issue, and who does it. The Service, an agentic coder and a person must follow one workflow.

## What Changes

- Add `docs/ROADMAP_WORKFLOW.md`. It holds the purpose, the eight steps with their actors and commands, a table of the transitions, the labels and record keys of each state, the stop and retry path as built, the three gates, the manual path, one diagram, and one section for the planned work with its issue numbers.
- Add `tests/invariants/test_roadmap_workflow_doc.py`. It fails when a `status/*` or `owner/*` label of `.github/labels.yml`, a Status or Owner value of the code, or a record key of the job record is missing from the document. It also fails when the document names a label or a record key that does not exist.
- Register the document as hand-written in `CONST_DOCS_INVENTORY`.
- Route to the document from the table in `AGENTS.md`: the SDLC row now routes to the document, the command row merges into the CONTRIBUTING row, and the ADR row merges into the term row, because the file is at its cap. Route also from Phase 1 of `docs/SDLC.md` (shorter than before), and from `docs/index.md`.
- The change alters no behavior that a consumer observes: it adds a document and a test, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `docs/ROADMAP_WORKFLOW.md`: new.
- `tests/invariants/test_roadmap_workflow_doc.py`: new.
- `src/devops_cli/config/constants.py`: one path added to `CONST_DOCS_INVENTORY`.
- `AGENTS.md`, `docs/SDLC.md`, `docs/index.md`: one link each.

## Feasibility

- The premise holds. W2 (`status/planned` and `status_sync.py`) and W3 (`owner/*` labels and `claim.py`) are merged, so the document describes built code. The labels `status/new`, `status/ready`, `status/planned`, `status/in-progress`, `status/in-review`, `status/blocked`, `owner/service`, `owner/agent` and `owner/human` are in `.github/labels.yml`, and `CONST_ROADMAP_STATUS_VALUES` and `CONST_ROADMAP_OWNER_VALUES` name the same values.
- The issue text lists `status/done` as a label. It does not exist: ADR 0016 rejects it, and `.github/workflows/clear-status.yml` removes the `status/*` and `owner/*` labels when an issue closes. The document names a closed issue as the end state and has no `status/done` label.
- The stop and retry path was read in `roadmap/implement.py`, `roadmap/implement_run.py` and `roadmap/implement_submit.py`: a stop sets Ready, records `implement.stopped`, and waits for the comment `implement: retry`. A Job that the runner could not report is recorded as `implement.stopped` = `job`. A row that fails 3 rounds in a row is suspended (`k8s/README.md`, Roadmap service, step 12).
- The manual path was read in `devops k8s run-job --help` and `devops roadmap implement --help`: `--repo` is required for the runner template and is also an option of `roadmap implement`.
- `devops docs check` resolves every `devops` command line of a hand-written document against the live command tree. The planned commands (#2911, #2915) do not exist yet, so the document names them without a command line.
- The file `AGENTS.md` holds 6,500 characters at most (`tests/invariants/test_agents_md_claims.py`). Two rows merge into others and the SDLC row routes to the document. The file ends at 6,471 characters.

## Existing Tool Considered

- `markdown-it-py` is already a dependency and the other invariant tests use it. The new test reads tables, code spans and fences from its tokens, and parses no Markdown by hand.
- `declared_label_names` in `devops_cli.roadmap.title_labels` reads `.github/labels.yml`. The test reuses it.
- No open, maintained tool writes a project workflow document or checks it against a local label file and a local state enum. The document and the test are built. The cost is about 25,000 tokens to write both, about 2,000 tokens each time a label or a state changes, and about 2 hours of elapsed time. The test turns a drift into a failed check, so a reader never meets a stale state name.
- The change deletes no internal code. It shortens Phase 1 of `docs/SDLC.md`.
