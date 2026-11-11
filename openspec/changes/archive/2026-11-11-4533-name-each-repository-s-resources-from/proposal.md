# Proposal: #4533

## Why
The roadmap Service works on 7 repositories of 1 owner. The move of its work to Jobs, Argo Workflows and Valkey (#4517) adds Jobs, Workflows, locks, Valkey keys, labels and telemetry values for each repository. Each part makes names in its own way: 7 `.split("/")` calls parse `owner/name`, and the roadmap store, the cluster Job module and the Service each have their own check of a repository name. `service.repos` has no check, so two spellings of one repository give two sets of names and keys. Without one rule, each later step makes its own names. Closes #4533.

## What Changes
- Add `src/devops_cli/github/repo_ref.py` with the value type `RepoRef`. It parses `owner/name` one time. `key` is the casefolded `owner/name`, `display` is the GitHub spelling, and `id` is the first 16 hex characters of the sha256 of `key` (the value of the Job label `implement-repo` today).
- Builders: the owner and repository label values, the unit name and the ad hoc name of a Job or Workflow, the lock name, the `valkey-roadmap` keys of a repository and of the installation, the two `SCAN MATCH` patterns of a repository, the metric `repo` value, the OpenTelemetry VCS span attributes and the clone path parts. `ServiceRow` holds the rows that run in pods of their own.
- Add `CONST_K8S_LABEL_VALUE_RE` (the label value rule of Kubernetes) to `src/devops_cli/config/constants.py`, and correct the comment of `CONST_CACHE_NAMESPACE_ROOT`: the root prefixes only the workstation run index, and each Valkey instance has one owner.
- `service.repos` refuses an entry that is not `owner/name` and two entries with one `key`. The error names `service.repos`. The inbox command loses its own check of the entries, because the settings refuse a bad entry first.
- `is_name_segment` and `is_repository_name` move from `src/devops_cli/roadmap/stores/store.py` into the new module, and their callers change.
- Add ADR 0022, which owns the rules of names, labels, the annotation, the service names, the Valkey key forms, the lock names, the telemetry values and the cleanup of a removed repository.
- A consumer observes the refusal of `service.repos` and the new names, so the change has a delta on the new capability `repository-names`.

## Capabilities
- New: `repository-names`.

## Impact
- `src/devops_cli/github/repo_ref.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `docs/adr/`.
- A configuration with a bad `service.repos` entry stops at load. The live ConfigMap passes: its 7 entries parse, their 7 keys are distinct, and each label value is the plain casefolded part.
- No new runtime dependency. No consumer uses the builders yet: #4558, #4576, #4564, #4574 and #4603 move their consumers.
- The change fits one pull request.

## Feasibility
- Source on `main` at 5f75d256: `is_name_segment` and `is_repository_name` in `src/devops_cli/roadmap/stores/store.py`, `repository_label` (the sha256 of the casefolded name, cut to 16 hex) and `job_name` in `src/devops_cli/k8s/cluster_job.py`, and `ServiceConfig._parse_repos` in `src/devops_cli/config/settings.py`, which checks no form.
- Kubernetes label value rule: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set. `kubernetes==36.0.3` has no public check of a label value.
- Valkey glob: https://valkey.io/commands/keys/. The test runs each pattern through `KEYS` on the in-memory Valkey server of the tests (fakeredis).
- OpenTelemetry VCS attributes: `opentelemetry-semantic-conventions==0.66b1` has `VCS_PROVIDER_NAME`, `VCS_OWNER_NAME`, `VCS_REPOSITORY_NAME` and `VcsProviderNameValues.GITHUB`.
- Live read of ConfigMap `devops-cli-config` (counts only): 7 entries parse, 7 keys are distinct, 7 of 7 have plain label values, and the longest unit name over all rows with a 6-digit item has 63 characters.

## Existing Tool Considered
- Kubernetes `metadata.generateName`: rejected for Service work. The claim record names the Job before the create, a dry run must show the name with no request, and a repeated create must get 409.
- `python-slugify`: rejected. GitHub names are ASCII, so one `re.sub` makes the slug.
- The Helm pattern `trunc 63 | trimSuffix "-"`: adopted, with a hash. `hashlib.sha256` and `secrets.token_hex` from the standard library: adopted.
- OpenTelemetry semantic conventions: adopted for the span attribute names.
- Cost to build: about 120 lines of code and 150 lines of Hypothesis tests; about 200,000 tokens and 2 hours to build, about 10,000 tokens a month to keep, about 40,000 tokens to fix a defect.
- Internal code that the change deletes: `is_name_segment` and `is_repository_name` in `store.py` (moved), and the entry check of `_inbox_repos` with its message `inbox_bad_repo`.
