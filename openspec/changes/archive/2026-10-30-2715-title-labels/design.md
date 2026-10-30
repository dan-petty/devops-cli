# Design

## Decisions

- **The title decides, the model fills a gap.** `_title_labels` reads the type and the scope of the title. A title with a type that maps to a declared `type/*` label gives the type; the model's `type` is not used, and the request sets `needs_type` to false. A title with no type, or with a type whose label the file does not declare, keeps the old path: the model picks one declared type.
- **One mapping, one place.** `CONST_ROADMAP_COMMIT_TYPE_LABELS` maps `feat` to `type/feature`, `fix` to `type/bug`, `perf`, `build` and `ci` to `type/infra`, `refactor`, `docs` and `test` to their labels, and `chore`, `style` and `revert` to `type/chore`. It covers `CONST_BRANCH_TYPES`. `type/security` is a label a person adds, and a `fix(security)` title gets it as the scope `scope/security`.
- **A scope is a declared label or a finding.** The file `.github/labels.yml` is the list of scopes. A title scope outside the list gives no label, because a label that GitHub creates on first use would grow the taxonomy by typo. The reason comment says which label to add, so a person adds it once and the next item gets it.
- **A person's label stays.** An issue that holds a `type/*` or `scope/*` label keeps it, as the rule of ADR 0016 says for a field a person set. The comment has no line for a label that intake did not add.
- **The parse stays beside its twin.** `commit_type` moves to `roadmap/commit_title.py` with `commit_scope`, so `stage`, `implement` and `intake` share one reader of the title and none imports another job.
- **The labels file is read once.** `_Run.declared` holds the names of the labels, and `types` and `scopes` filter it, so a run still makes one read of `.github/labels.yml`.

## Rejected alternatives

- **Let the model pick both labels with a list of scopes.** The model returned a type that disagreed with the title in five of the last forty issues. A second judge for a fact that the title states is the cause of the fault.
- **Create the missing scope label at intake.** A typo in a title would add a label to the repository. Repository labels are a declared file (`devops gh labels sync`), and the file is the source.
- **A `type/bugfix` label.** The code that finds a critical fix (`CONST_ROADMAP_CRITICAL_FIX_LABELS`) and the defect classifier name `type/bug`, and hundreds of issues hold it. A rename adds work and gives no new fact.
- **Backfill in the code.** A one-time relabel of open issues is a data migration. A person or an agent runs it with `devops gh issues edit`, and it needs no code in the product.
