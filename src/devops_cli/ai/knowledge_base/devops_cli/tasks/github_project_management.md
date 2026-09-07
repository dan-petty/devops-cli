# Knowledge Base Task: GitHub Project Governance, Views, Milestones & Labels

## 1. Overview & Purpose

GitHub project governance in `devops-cli` standardizes repository metadata across four foundational pillars:
1. **GitHub Views & Projects v2**: Declarative workspace templates defining custom fields (`Status`, `Milestone`, `Priority`, `Category`, `Value`, `Effort`) and four standardized views for agile sprint execution, chronological roadmap tracking, defect triage, and portfolio prioritization.
2. **Roadmap Milestones**: Synchronized milestone lifecycle directly extracted from `docs/ROADMAP.md` release headings, providing issue completion ratios and health metrics.
3. **Declarative Label Taxonomy**: Repository label synchronization driven by `.github/labels.yml`, enforcing strict categorization across `type/*`, `scope/*`, `priority/*`, `status/*`, and `review/*`.
4. **Pull Request Quality Auditing**: Automated validation ensuring every active pull request possesses mandatory `type/*` and `scope/*` classification labels.

---

## 2. Architecture & Governance Lifecycle

```mermaid
graph TD
    A[Declarative Schemas<br/>.github/labels.yml & project-template.json] -->|devops gh labels sync| B[Remote GitHub Labels]
    C[docs/ROADMAP.md Headings] -->|devops gh milestones sync| D[Remote GitHub Milestones]
    E[docs/agent/task.md Lifecycles] -->|devops gh project sync| F[GitHub Projects v2 Items]
    B --> G[devops gh labels audit]
    D --> H[devops gh milestones list]
    F --> I[Standardized Views Engine]
    I --> J[Sprint Kanban]
    I --> K[Roadmap Timeline]
    I --> L[Triage & Quality Table]
    I --> M[Value vs Effort Matrix]
```

### The 4 Standardized Projects v2 Views

| View Name | Layout | Group By | Purpose & Filtering |
| :--- | :--- | :--- | :--- |
| **Sprint Kanban** | Board | `Status` | Active sprint tracking (`Backlog`, `Ready`, `In Progress`, `In Review`, `Done`). Filtered to current milestone. |
| **Roadmap Timeline** | Roadmap | `Milestone` | Chronological release milestones with target delivery dates and status health. |
| **Triage & Quality Table** | Table | None | Priority-ordered queue (`P0` to `P3`) filtering open defects (`type/bug`, `status/blocked`, `status/triage`). |
| **Value vs Effort Priority Matrix** | Table | `Category` | Strategic portfolio matrix grouping deliverables into Quick Wins, Major Projects, Fill-Ins, and Foundation. |

---

## 3. Useful Usage Information & Common Commands

### Label Management Commands
```bash
# List all labels defined in the remote repository
devops gh labels list

# Preview reconciliation against .github/labels.yml without mutating remote state
devops gh labels sync --dry-run

# Synchronize labels against declarative schema
devops gh labels sync

# Audit open pull requests for mandatory type/ and scope/ taxonomy labels
devops gh labels audit
```

### Milestone Management Commands
```bash
# List release milestones and issue progress rates
devops gh milestones list

# Preview extraction and synchronization from docs/ROADMAP.md
devops gh milestones sync --dry-run

# Reconcile milestones with docs/ROADMAP.md
devops gh milestones sync

# Inspect health and completion metrics for a specific milestone
devops gh milestones status v0.2.11

# Close a release milestone upon release merge or publish
devops gh milestones close v0.2.11
```

### Project & Views Inspection Commands
```bash
# Display project template summary, custom fields, and views
devops gh project status

# Synchronize task.md item cards, provision fields, and link project
devops gh project sync

# Preview task.md item synchronization into project statuses
devops gh project sync --dry-run

# Link an existing project board to the repository
devops gh project link 1

# Inspect all 4 standardized project views in Rich table format
devops gh views list

# Output JSON specification for GitHub Projects v2 views
devops gh views spec
```

---

## 4. Best Practice Guidance

1. **Mandatory PR Taxonomy Labels**:
   - Every Pull Request must be labeled with at least one **type** (`type/feature`, `type/bug`, `type/refactor`, `type/docs`, `type/infra`, `type/test`, `type/security`, `type/chore`).
   - Every Pull Request must be labeled with at least one **scope** (`scope/ai`, `scope/k8s`, `scope/cli`, `scope/review`, `scope/config`, `scope/security`, `scope/infra`, `scope/docs`, `scope/test`).
2. **Roadmap-Driven Milestones & Closure**:
   - Milestones must originate from `docs/ROADMAP.md` chronological headings (e.g. `### Feature Topic (vX.Y.Z - Status)`).
   - Pull requests targeting a release branch must link to the corresponding milestone.
   - Upon release PR squash-merge or cutting a release, close the completed milestone via `devops gh milestones close <version>` to avoid milestone staleness.
3. **Projects v2 Board Linkage & Issues Views Item State Transitions (`https://github.com/dan-petty/devops-cli/projects` & `https://github.com/dan-petty/devops-cli/issues/views`)**:
   - Ensure the project board is linked to the repository via `devops gh project link <number>`, surfacing the project board under `https://github.com/dan-petty/devops-cli/projects` and its 4 canonical views under `https://github.com/dan-petty/devops-cli/issues/views`.
   - Populate all 6 custom project fields (`Status`, `Milestone`, `Priority`, `Category`, `Value`, `Effort`) for each issue and PR card.
   - When beginning a task: transition card from `Backlog` to `In Progress`.
   - When PR is submitted: transition card to `In Review`.
   - When PR is merged: transition card to `Done`.
4. **Active Milestone Resource Population & Zero-Empty Queue/Projects Policy**:
   - When initializing a new release branch or activating a milestone, AI agents must proactively author GitHub tracking issues for every planned deliverable in `docs/ROADMAP.md`.
   - The open issues queue (`https://github.com/dan-petty/devops-cli/issues?q=is%3Aissue+state%3Aopen`), projects tab (`https://github.com/dan-petty/devops-cli/projects`), and issue views (`https://github.com/dan-petty/devops-cli/issues/views`) must never be left empty during an active release cycle.
   - Each issue must follow Conventional Commits (`feat(<scope>): ...`), assign the milestone (`vX.Y.Z`), and include mandatory taxonomy labels (`type/*`, `scope/*`, `priority/*`).
5. **Strict Remote Branch Lifecycle & PR Governance**:
   - Every remote topic branch on `origin` must have an associated open PR targeting the active release branch or `main`.
   - Remote branches must be deleted immediately upon PR merge or supersession (`git push origin --delete <branch>` and `git fetch --prune origin`).
   - Orphan remote branches are strictly prohibited.
6. **Use Dry-Run First**: Always run `devops gh labels sync --dry-run` and `devops gh milestones sync --dry-run` to preview reconciliations before applying changes.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Zero-Plaintext Credentials**: GitHub tokens must be retrieved from the OS Keyring (`github_token`) or environment variable (`GITHUB_TOKEN`), never hardcoded or logged.
- **Granular Token Scopes**:
  - Labels and Milestones require `repo` scope.
  - Projects v2 mutations require `project` or `read:project` scopes. When scopes are restricted, `devops gh` falls back gracefully with clear instructions (`gh auth refresh -s project,read:project`) and preserves read-only/offline functionality.
- **Dry-Run Mode for Project Sync**: Task items and project synchronization can be simulated without remote mutations using `--dry-run`.

---

## 6. General Standards & Reference Guidelines

- **Declarative Schema Canonical Paths**:
  - Labels: [`.github/labels.yml`](../../../../../../.github/labels.yml)
  - Project Template: [`.github/project-template.json`](../../../../../../.github/project-template.json)
- **FastMCP Tool Integration**: AI coding agents can interact with GitHub governance via MCP tools:
  - `gh_label_list`, `gh_label_sync`
  - `gh_milestone_list`, `gh_milestone_sync`, `gh_milestone_close`
  - `gh_project_status`, `gh_project_sync`, `gh_view_spec`

---

## 7. Official References & Published Artifacts

- **GitHub CLI Documentation**: [cli.github.com/manual](https://cli.github.com/manual)
- **GitHub Projects v2 API & Views**: [docs.github.com/en/issues/planning-and-tracking-with-projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- **DevOps CLI GitHub Subsystem**: [src/devops_cli/commands/gh.py](../../../../commands/gh.py)
- **Declarative Label Engine**: [src/devops_cli/github/labels.py](../../../../github/labels.py)
- **Milestone Engine**: [src/devops_cli/github/milestones.py](../../../../github/milestones.py)
- **Projects & Views Engine**: [src/devops_cli/github/projects.py](../../../../github/projects.py)
