# Design

## Decisions

- **One page for each job, in `docs/roadmap/`.** The issue asks for one document for each job. The six pages share one shape: what the job does, in the order of its work, then the modes, then a table that names the specs. A directory keeps the pages together, and one glob in the inventory classes all of them.
- **The page is hand-written, not generated.** The generated class is the output of `devops docs generate`. A page that explains a job is prose, so it belongs to the hand-written class. That class is name-checked by `devops docs check`, which is the check the issue asks for.
- **The help names the page as a path, not as a link.** Typer prints plain text on a terminal, and the generated Markdown escapes the text. The path `docs/roadmap/<command>.md` works in both. A test pins that the path is in the help and that the file exists.
- **Three sentences, counted by a test.** The limit of the issue is "one to three sentences". The test splits the help at a full stop followed by a space, and the path ends in `.md` with no space after the dot, so it is not a split point.
- **A page states a fact only when no spec states it, or when it gives the order of the work.** The tables "Where the rules are" point to the spec of each topic. Where a spec holds a list in full (the items that stage leaves out, the items that alternatives takes), the page gives a pointer and at most an example.
- **The inbox request count moves to a test of the plan.** The old help said "5 requests, or 6". The plan of the reads is the true source: three listings that repeat for each page, one file read, and one conditional commit read. A test reads that plan, and the spec `roadmap-inbox` states the rule. The page restates it as a table.
- **The two repeated bullets of `docs/ROADMAP_WORKFLOW.md` become pointers.** They repeated the help of `inbox` and `refine`. The test `tests/invariants/test_roadmap_workflow_doc.py` does not read them.

## Rejected alternatives

- **Put the long text in the Typer `epilog` or in a `--help-long` option.** It keeps the text in the code, which is the duplication the issue wants removed, and it changes the options of the command. Rejected.
- **Generate the pages from the specs.** The specs hold rules in "SHALL" form with scenarios, and a reader of the help needs a description of the job. `devops docs generate` has no feature for this, and building one costs more than six pages. Rejected.
- **One page `docs/ROADMAP_COMMANDS.md` for all six jobs.** A page of about 20,000 characters would repeat the problem of the long help at a larger scale, and a link from the help could not name the section of the job without an anchor that a heading change breaks. Rejected.
- **Shorten the help of the five other long commands in the same change.** `run`, `eval stage`, `eval implement`, `explain` and `intake-eval` have 575 to 837 characters. The issue names six commands and gives their sizes, so this change keeps to them.
