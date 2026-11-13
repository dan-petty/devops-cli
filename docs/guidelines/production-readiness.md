# Production readiness guideline

This guideline is the production gate of each service and each repository of a managed project. It applies the production readiness review (PRR) of the Google SRE book with the tools of devops-cli. The [SRE guideline](sre.md) sets the targets that the rows check: the SLOs, the alerts, the incidents, the backups and the capacity. This guideline sets the rows, their levels, the check that measures each row, the review and the steps of a new service. Each row names the document that owns its rule and does not copy the rule. It applies with no change to each managed project. [The guideline index](index.md) lists each guideline.

Use the checklist in three cases:

- **A new service.** Meet each required row before the launch pull request merges.
- **A new repository.** Meet each row with the scope `Repo` or `Both` before the first release of the repository. Also meet them before it goes into the managed projects (setting `service.repos`).
- **A running service.** Read the rows again when the service changes its SLO, its dependencies or its data. Also read them again after a window that spent the error budget.

## Levels

**Table 1.** The levels of the rows.

| Level | Meaning |
| :--- | :--- |
| Required | The row blocks the launch of a new service or a new repository. Only the owner can accept a launch with a required row that is not met ([Table 12](#production-readiness-review)). |
| Recommended | Do the row before the launch when it is small. If not, file its issue before the launch. |
| Later | File the issue of the row when its condition occurs, such as a second maintainer or a move of the repository into an organization. |

For a running service, its tier in the catalog data of the environment sets the level. A required row applies to tier 1, and to tier 2 when the service has an SLO. For each other running service, a required row is recommended. For an existing repository, each required row applies.

A required row that a running service or an existing repository does not meet is an exception. The gap tracker of the environment names its issue, and the owner sets the end date on that issue.

The scope `Repo` applies to each repository, `Service` to each workload in the cluster, and `Both` to the two. The column "Measured by" names the check that reads the row. The check is an OpenSSF Scorecard check (`SC <check>`), a kube-linter check, a `devops` command or a query. It can also be a rule file or a file of the repository. A person or an agent can run it again and get the same result. A row that no program can read says `manual`, and a person or an agent reads its evidence. [Table 14](#sources) gives the codes of the column Standard.

## Ownership and documents

**Table 2.** Ownership and documents.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| OWN-1 | The service has a catalog entry with its tier, its data class and its dependencies, an SLO when its tier needs one, and a dashboard. | Service | Required | The entry of the service in the catalog data; the catalog check of the environment | [SRE guideline](sre.md#rules), SRE1 | SRE-32; SRE-E Architecture |
| OWN-2 | The repository has `README.md`, a permissive `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md` with its pointer files, and `CODEOWNERS` for each path. | Repo | Required | SC `License`, `Security-Policy`; the files on the default branch | [`devops ai agents`](../commands/ai.md#devops-ai-agents); the contributing guide of the project | SC License, Security-Policy; BP `floss_license`, `documentation_basics`; SSDF PO.2 |
| OWN-3 | Each change has one issue, one OpenSpec change and one pull request. | Repo | Required | The archived changes under `openspec/changes/archive/` | [AGENTS.md](../../AGENTS.md) rule 1 | SRE-32 Engagement |
| OWN-4 | A choice that is difficult to reverse has an ADR. | Both | Recommended | `manual`: the ADRs of the repository | The ADR index of the project | SSDF PW.1 |
| OWN-5 | The documents tell how to deploy, configure, check and stop the service. They are correct at the merge. | Both | Required | `devops docs check`; the strict build of the docs site | [AGENTS.md](../../AGENTS.md) rule 8 | BP `documentation_basics`; SRE-E Automation |
| OWN-6 | The repository meets the prerequisites of the roadmap jobs. | Repo | Required for a repository in `service.repos` | `devops roadmap onboard --repo <owner>/<name> --plan` shows no row `missing` | [Onboard](../roadmap/onboard.md) | - |
| OWN-7 | `AGENTS.md` routes the agents to the shared guidelines: its "Where to look" table has a row with a link to the guideline index. | Repo | Recommended | The "Where to look" table of `AGENTS.md` | This guideline | - |

## SLOs, monitoring and alerting

**Table 3.** SLOs, monitoring and alerting.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| SLO-1 | Each user journey has an SLI and an SLO with a 28-day window. The owner sets the objective. | Service | Required | A Sloth spec whose `service` field names the service | [SRE guideline](sre.md#slos-and-error-budgets) | SRE-4; WB-2 |
| SLO-2 | Sloth makes the SLO rules and the burn-rate alerts, and `promtool test rules` tests them. | Service | Required | The generated rule file; `promtool test rules` | [SRE guideline](sre.md#rules), SRE2 | WB-5 |
| SLO-3 | A job applies the error budget policy to the service. | Service | Required | `manual`: the items that the jobs hold while the budget is spent | [SRE guideline](sre.md#rules), SRE8 | WB-B |
| SLO-4 | The service has a dashboard from the SRE template. | Service | Required | The entry of the service in the service dashboard table of the environment | [SRE guideline](sre.md#dashboards) | SRE-6 |
| SLO-5 | Prometheus scrapes the service, and Loki holds its logs. The collector gets its spans with W3C trace context. | Service | Required | `up{job="<job>"}` is 1; a LogQL query of the namespace; a trace of one request | The README of the environment tree; the telemetry document of the product | SRE-E Monitoring; 12F XI |
| SLO-6 | Cause alerts find a target that is down, an OOM kill, a crash loop, a full disk and a budget near its limit. A new rule group has a `promtool` test file. | Service | Required | The kubernetes-mixin groups `kubernetes-apps` and `kubernetes-resources`; the `promtool` test file of each rule group | The README of the environment tree; the product document | SRE-6; SRE-E Monitoring |
| SLO-7 | Each alert has a runbook row with a "Do this" step. | Service | Required | `devops prometheus rules` against the alert table of the owner document | [SRE guideline](sre.md#rules), SRE3 | WB-8; SRE-11 |
| SLO-8 | Pages and tickets go on different routes, and each notification arrives. | Service | Required | `amtool config routes test`; `alertmanager_notifications_failed_total` stays at 0 after a test alert | [SRE guideline](sre.md#alerts-and-routing) | WB-5; SRE-11 |
| SLO-9 | A heartbeat outside the cluster finds an alert path that stopped. | Both | Recommended | A missed heartbeat pages the owner | This guideline | SRE-E Monitoring |
| SLO-10 | The dashboards show a marker for each deploy and each alert. | Service | Recommended | The Grafana annotations of each deploy | [SRE guideline](sre.md#change-safety) | DORA |
| SLO-11 | A black-box probe checks each endpoint and each UI journey that users see. | Service | Later | `probe_success` of the probe and its alert | This guideline | SRE-6 |

## Incidents and on-call

**Table 4.** Incidents and on-call.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| INC-1 | The response time of each severity and the incident triggers apply to the service. | Service | Required | `manual`: rule SRE4; the triggers in the settings of the incident job | [SRE guideline](sre.md#incidents-and-postmortems) | SRE-11; WB-8; WB-9 |
| INC-2 | Each incident has an incident issue with a UTC timeline. | Service | Required | The issues with "incident on" in the title | [SRE guideline](sre.md#incident-response), SRE6 | SRE-14; WB-9 |
| INC-3 | An incident that the SRE guideline names gets a postmortem with no blame. Each action item is an issue. | Service | Required | The postmortem of each such incident, with the tables of [the design spec](../DESIGN.md#table-rules) T10 | [SRE guideline](sre.md#postmortems), SRE7 | SRE-15; WB-10 |
| INC-4 | The service has stop steps. | Service | Required | `manual`: the stop switch of the product, or the pause of its GitOps application | The product document; the README of the environment tree | WB-9 |
| INC-5 | A drill does the stop steps or plays a failure of the service, and records the result. | Service | Later | The drill record | [SRE guideline](sre.md#incident-response) | SRE-28 |

## Release and change management

**Table 5.** Release and change management.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REL-1 | The ruleset of the default branch requires a pull request, the required checks and resolved threads. It refuses a deletion and a force push, and no actor bypasses it. | Repo | Required | SC `Branch-Protection`; `devops gh api repos/<owner>/<repo>/rules/branches/main` | The SDLC document of the project | SC Branch-Protection; SSDF PS.1 |
| REL-2 | A person merges each pull request. Only the release pull request merges by a workflow, or by GitHub for an urgent fix. | Repo | Required | `merged_by` of each pull request | [AGENTS.md](../../AGENTS.md) | SSDF PW.7 |
| REL-3 | A person who did not write a change approves it. | Repo | Later, when a second maintainer joins | SC `Code-Review`; `required_approving_review_count` of the ruleset is 1 or more | The SDLC document of the project | SC Code-Review |
| REL-4 | CI gates each merge with the tests, the coverage floor, the static checks, the type checks and SAST. A fix gives its fail-to-pass run. | Repo | Required | SC `CI-Tests`, `SAST`; the required checks of the ruleset; `devops ci fail-to-pass --base <ref>` | The testing guide of the project | SC CI-Tests; SSDF PW.8; BP `test` |
| REL-5 | release-please makes each release from the default branch, with a semantic version and release notes. | Repo | Required | The GitHub Release; `CHANGELOG.md` | The release document of the project | BP `version_unique`, `release_notes`; SSDF PS.3; 12F V |
| REL-6 | A GitOps tool deploys the service from the default branch with prune and self-heal. | Service | Required | `devops argo cd apps status <app>` | The README of the environment tree | K8S-PE; SRE-E Automation |
| REL-7 | The rollout strategy fits the volume and the SLO. The readiness probe gates the traffic, and SIGTERM drains in a limited time. | Service | Required | kube-linter `no-rolling-update-strategy`, `no-readiness-probe`; the drain limit of the product | [SRE guideline](sre.md#change-safety); the nested time limits of the architecture document | 12F IX; WB-16 |
| REL-8 | A change that removes, renames or tightens a setting changes the live configuration first. | Service | Required | `manual`: the go-live check record of the pull request | The product document | WB-16 |
| REL-9 | A new Secret is in the cluster before the merge of the manifest that reads it. | Service | Required | `devops k8s push-secrets --only <namespace>/<name> --plan` shows `unchanged` | The README of the environment tree | WB-16 |
| REL-10 | A go-live check runs after the rollout, with the stop steps ready. | Service | Required for a new service or a new rollout path | The check results in a pull request comment | The product document | SRE-32 Onboarding; WB-16 |
| REL-11 | The steps that go back to the last good version are written and tested. | Service | Required | `manual`: the steps; a record of their test | The release document of the project; the product document | WB-16; DORA |
| REL-12 | Each live change outside git has a record: the key, the reason and the time. | Both | Recommended | A comment on the issue of the change | The README of the environment tree | - |
| REL-13 | The project review gives the five DORA metrics. | Repo | Recommended | `devops roadmap review run` | The SDLC document of the project | DORA |
| REL-14 | A canary or a progressive rollout limits the effect of a bad version. | Service | Later, when the service runs 2 replicas | The rollout analysis | [SRE guideline](sre.md#change-safety) | WB-16 |

## Security and supply chain

**Table 6.** Security and supply chain.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| SEC-1 | The repository has a security policy, private vulnerability reporting and a response time. | Repo | Required | SC `Security-Policy`; `devops gh api repos/<owner>/<repo>/private-vulnerability-reporting` | [SECURITY.md](../../SECURITY.md#reporting-a-vulnerability) | SC Security-Policy; BP `vulnerability_report_process`; SSDF RV.1 |
| SEC-2 | Secret scanning and push protection are on, and git holds no secret. | Repo | Required | `security_and_analysis` of `devops gh api repos/<owner>/<repo>`; the `detect-private-key` hook | [SECURITY.md](../../SECURITY.md) | SSDF PS.1 |
| SEC-3 | CodeQL runs on each pull request as a rule of the default branch, with Bandit and the review scanners. | Repo | Required | SC `SAST`; the `code_scanning` rule of the ruleset | The SDLC document of the project | SC SAST; SSDF PW.7; BP `static_analysis` |
| SEC-4 | Each dependency is pinned: a package by the lockfile, an action by commit SHA, an image by digest and a chart by version. An audit reads the lockfile in each CI run. | Repo | Required | SC `Pinned-Dependencies`, `Vulnerabilities`; `devops ci audit`; `devops k8s image-pins` | The contributing guide of the project | SC Pinned-Dependencies, Vulnerabilities; SSDF PW.4, RV.1 |
| SEC-5 | Each job of a workflow has the token permissions that it needs and no more. zizmor and actionlint pass. | Repo | Required | SC `Token-Permissions`, `Dangerous-Workflow`; `devops scan workflows` | The contributing guide of the project | SC Dangerous-Workflow; SSDF PO.3 |
| SEC-6 | Renovate proposes each update, and a security fix at once. | Repo | Required | SC `Dependency-Update-Tool`; the Renovate pull requests and the Dependency Dashboard issue | The SDLC document of the project | SC Dependency-Update-Tool; SSDF RV.2 |
| SEC-7 | Each scanner finding has a fix, or an ignore entry with a reason, an end date and an issue. | Repo | Required | The open alerts of `devops gh api repos/<owner>/<repo>/code-scanning/alerts`; the ignore files of the scanners | [SECURITY.md](../../SECURITY.md#a-finding-with-no-fix) | SSDF RV.2 |
| SEC-8 | Trivy scans each image that the project builds for HIGH and CRITICAL findings before its push. | Repo | Required | The Trivy step of the build of each image | The release document of the project | K8S-SC Images; SSDF RV.1 |
| SEC-9 | A scan reads each third-party image that the cluster runs. | Service | Recommended | The Trivy report of each running image | This guideline | K8S-SC Images; SSDF RV.1 |
| SEC-10 | Each image has signed build provenance and an SBOM before it gets a tag. | Repo | Required | SC `Signed-Releases`, `SBOM`; `devops gh api repos/<owner>/<repo>/attestations/sha256:<digest>` | The release document of the project | SLSA Build L2; SC Signed-Releases, SBOM; SSDF PS.2 |
| SEC-11 | Code from a model or another untrusted source runs in a sandbox: bubblewrap on a host, RuntimeClass `gvisor` in the cluster. | Service | Recommended | `runtimeClassName: gvisor` on the pod; the sandbox of the host command | The README of the environment tree; [SECURITY.md](../../SECURITY.md) | K8S-SC Pod security |
| SEC-12 | Each outgoing request goes through the HTTP client that checks the egress level. No component sends telemetry home. | Repo | Required | The architecture invariant tests of the repository | [SECURITY.md](../../SECURITY.md) | SSDF PW.9 |
| SEC-13 | A new service has a threat model and a security review before its launch. | Service | Required for a new service | The threat model in the design; the `devops review` run | The architecture document of the project; [SECURITY.md](../../SECURITY.md) | SRE-E Security; SSDF PW.1 |
| SEC-14 | The wheel and the sdist have signed build provenance. | Repo | Later, before a move into an organization | The attestation of each package | The release document of the project | SLSA Build L2; SSDF PS.2 |
| SEC-15 | A license scan refuses a dependency that has no permissive license. | Repo | Later, before a move into an organization | The license scan in CI | The contributing guide of the project | SSDF PW.4 |
| SEC-16 | OpenSSF Scorecard runs on a schedule, each workflow sets read-only permissions at the top level, and the repository has the Best Practices passing badge. | Repo | Later, before a move into an organization | The Scorecard result; SC `Token-Permissions`, `CII-Best-Practices` | This guideline | SC Token-Permissions and the other checks; BP |
| SEC-17 | The cluster runs an image only when its provenance is correct. | Service | Later | An admission policy that checks the attestation | This guideline | SLSA; CIS 5.5.1 |
| SEC-18 | A CIS Kubernetes benchmark runs on a schedule. | Service | Later | The kube-bench report | This guideline | CIS |

## Access and secrets

**Table 7.** Access and secrets.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ACC-1 | Each Secret comes from the keyring through `devops k8s push-secrets`, and the Secret table lists each reference. | Service | Required | `devops k8s push-secrets --plan`; the test of the Secret table | The README of the environment tree | CIS 5.4; K8S-SC Secrets; 12F III |
| ACC-2 | Only a person changes a Secret, a repository or organization setting, a ruleset or an App installation. | Both | Required | `manual`: the code that refuses an agent write to the settings routes | [AGENTS.md](../../AGENTS.md) | SSDF PO.2 |
| ACC-3 | The repository and organization settings are OpenTofu code that the owner applies. | Repo | Later, before a move into an organization | The OpenTofu code; `devops tf plan` shows no change | This guideline | SSDF PO.5 |
| ACC-4 | Each credential has rotation steps and leak steps. | Service | Required | `devops k8s push-secrets --rotate`; `manual`: the steps | The README of the environment tree | K8S-SC Secrets |
| ACC-5 | A workload that calls the Kubernetes API has its own ServiceAccount and only the namespaced Roles that it needs. Each other workload mounts no token. | Service | Required | kube-linter `default-service-account`; `automountServiceAccountToken: false`; `devops k8s rbac-audit` | The README of the environment tree | CIS 5.1.5, 5.1.6; K8S-SC Authentication & Authorization |
| ACC-6 | A service that makes pods or Jobs has a ValidatingAdmissionPolicy that limits them, with a test. | Service | Required for a service that makes pods | The policy and its test | The product document | K8S-SC Admission controllers; CIS 5.2.1 |
| ACC-7 | The namespace enforces Pod Security `restricted`, or its owner document gives the reason for a lower level. | Service | Required | The label `pod-security.kubernetes.io/enforce` of the namespace; kube-linter `run-as-non-root`, `privilege-escalation-container`; `devops k8s lint` | [SECURITY.md](../../SECURITY.md) | CIS 5.2, 5.7.2, 5.7.3; K8S-SC Pod security; K8S-APP |
| ACC-8 | The namespace has NetworkPolicies that let through only the traffic that it needs. | Service | Required | kube-linter `non-isolated-pod`; `kubectl -n <namespace> get networkpolicy` | The README of the environment tree | CIS 5.3.2; K8S-SC Network security |
| ACC-9 | A UI or an API outside the cluster goes only through the tunnel and Cloudflare Access. A listener refuses a request with no token. | Service | Required for a service with an endpoint | The Ingress; the Access policy; a test of the refusal | The README of the environment tree; [SECURITY.md](../../SECURITY.md) | K8S-SC Network security |
| ACC-10 | A datasource that anonymous Grafana viewers read holds no secret and uses a read-only token. | Service | Required for a new datasource | `manual`: the datasource settings | This guideline | K8S-SC Authentication & Authorization |
| ACC-11 | A job acts on GitHub as the App with its listed permissions, not as a person. | Service | Required | The permissions of the App | The product document | SC Token-Permissions; SSDF PO.5 |
| ACC-12 | A pod reads a Secret as a file when its program can. | Service | Later | kube-linter `read-secret-from-env-var` | The README of the environment tree | CIS 5.4.1 |
| ACC-13 | Each long-lived credential has a rotation interval and a metric of its age. | Service | Later | The age metric | This guideline | SSDF PO.5 |
| ACC-14 | The Kubernetes API writes an audit log. | Service | Later | The audit policy that `devops infra` applies | The infra repo of the project | CIS 3.2.1; K8S-SC Logs and auditing |

## Data, backups and recovery

**Table 8.** Data, backups and recovery.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| DATA-1 | The catalog entry gives the data class of the service. The design names each store of personal data. | Service | Required | The data class of the catalog entry | [SRE guideline](sre.md#backups-and-restores) | SRE-26 |
| DATA-2 | Each store of owned state has a backup off its node and a copy outside the cluster. | Service | Required | The `ScheduledBackup` and `ObjectStore` objects; the volume backup schedule | [SRE guideline](sre.md#backups-and-restore-tests) | SRE-26; SRE-E System reliability and failover |
| DATA-3 | A restore test of each store runs each month and writes its result and its time as a metric. | Service | Required | The restore metric | [SRE guideline](sre.md#backups-and-restore-tests), SRE9 | SRE-26 |
| DATA-4 | An alert fires when the last good backup or restore test is older than its target. | Service | Required | The rule and its `promtool test rules` file | [SRE guideline](sre.md#backups-and-restore-tests) | SRE-26 |
| DATA-5 | The owner sets the RTO of each store from its first restore test. | Service | Required | The RTO of the store in the README of the environment tree | [SRE guideline](sre.md#backups-and-restores) | SRE-E System reliability and failover |
| DATA-6 | The GitOps tool cannot prune or delete a store of owned state. | Service | Required | `argocd.argoproj.io/sync-options: Prune=false,Delete=false` on the store | The README of the environment tree | SRE-26 |
| DATA-7 | Logs, spans and errors hold no secret, no prompt text and no personal data. Git holds no host name, private address or local path. | Both | Required | The secret masking of the logs; the content gate of the spans; the committed-address check of the repository | [SECURITY.md](../../SECURITY.md) | SSDF PW.9 |
| DATA-8 | A drill builds the cluster again from git, the keyring and the backups, and measures the RPO and the RTO. | Both | Later, when the backups of DATA-2 exist | The drill record | The README of the environment tree | SRE-E System reliability and failover; K8S-PE |

## Capacity, performance and cost

**Table 9.** Capacity, performance and cost.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CAP-1 | Each container has CPU and memory requests from measured use, and a memory limit. An alert fires near the limit. | Service | Required | kube-linter `unset-cpu-requirements`, `unset-memory-requirements`; the KRR report; the alert | The Kubernetes guideline | K8S-PE |
| CAP-2 | A readiness probe gates the traffic, and a liveness probe restarts a process that does not answer. | Service | Required | kube-linter `no-readiness-probe`, `no-liveness-probe` | The Kubernetes guideline | K8S-PE |
| CAP-3 | The service meets the capacity target when one worker node stops. | Service | Required | The one-node-loss check of the Kubernetes guideline | [SRE guideline](sre.md#capacity) | SRE-E Volume estimates, Growth issues |
| CAP-4 | A load test, or the SLI at the measured peak, shows that the latency SLO holds at the planned load. | Service | Recommended | `devops test load`, or the SLI on the service dashboard | This guideline | SRE-E Volume estimates |
| CAP-5 | Replicas and a PodDisruptionBudget give the availability that the SLO needs. | Service | Later, when the service runs 2 replicas | `status.disruptionsAllowed` of the PodDisruptionBudget is 1 or more | The README of the environment tree | K8S-PE |
| CAP-6 | A service that calls a paid or limited API has a budget, an alert near the budget and a spend dashboard. | Service | Required | The budget setting; the alert; the dashboard | The product document | SRE-E External dependencies |

## Dependencies and failure modes

**Table 10.** Dependencies and failure modes.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| DEP-1 | The catalog entry lists each dependency. The design tells what the service does when each one fails: wait, degrade or stop. A test shows that behavior. | Service | Required | The dependencies of the catalog entry; the fault tests | The architecture document of the project | SRE-E External dependencies; SRE-32 Analysis |
| DEP-2 | Each call has a time limit inside the limit of its caller, and a limited retry. | Both | Required | `manual`: the nested limits | The architecture document of the project | SRE-E External dependencies |
| DEP-3 | The service reads the address of each backing service from a setting. It guesses no address. | Both | Required | The setting in the configuration reference; an error that names a missing setting | The configuration reference of the project | 12F III, IV |
| DEP-4 | A new dependency has a good reputation, current maintainers and a permissive license. Its pull request names the open tool. | Repo | Required | The pull request text; the alternatives check; SC `Maintained` of the dependency | [AGENTS.md](../../AGENTS.md) rule 3 | SSDF PW.4; SC Maintained |
| DEP-5 | A chaos test stops each critical dependency and checks the listed behavior. | Service | Later | The result of [`devops k8s chaos`](../commands/k8s.md#devops-k8s-chaos) | This guideline | SRE-E System reliability and failover |

## Readiness record

**Table 11.** The readiness record.

| ID | Item | Scope | Level | Measured by | Owner | Standard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EVD-1 | The readiness report of the launch branch is the readiness record. A comment on the launch pull request holds it. Only a `manual` row gets its state from a person or an agent. | Both | Required for a launch | The readiness report on the launch pull request | This guideline | SRE-32 Analysis; SSDF PO.4 |
| EVD-2 | The owner approves the launch with the merge. An exception has an owner comment, an issue and an end date. | Both | Required | `merged_by`; the owner comment | [Table 12](#production-readiness-review) | SSDF PO.2 |
| EVD-3 | The review runs again at each trigger of this guideline, and the project review reports the SLOs and the incidents. | Service | Recommended | `devops roadmap review run` | This guideline | SRE-32 Continuous Improvement |

For a running service, the readiness report of the project review is the readiness record. The report runs the check of the column "Measured by" for each row. Until a project has the report, a person or an agent runs the same checks and posts the same table as a comment. No document holds a copy of the state of each row. The gap tracker of the environment holds the issue of each required row that is not met.

## Production readiness review

The review follows the PRR of SRE-32 and WB-18. An agent prepares the evidence. Only a person approves a launch, merges a pull request, and changes a Secret or a setting.

1. **Start.** File the issue with `devops roadmap intake`, and plan the OpenSpec change. Add the draft catalog entry and the draft Sloth spec of the service.
2. **Analyze.** Run the readiness report on the launch branch, and post it on the launch pull request. For each `manual` row, add its evidence and its state to the same comment.
3. **Improve.** Meet each required row in the launch pull request, or in a blocker pull request that merges first. File an issue for each recommended row that is not met.
4. **Check.** Run the checks that the rows name. Write the results as one table with the columns Check, Result and Link ([the design spec](../DESIGN.md#table-rules) T9). An independent review checks the evidence before the pull request is ready.
5. **Prepare the person steps.** In `tasks.md`, write each step for a person. Examples are a Secret push, a setting, an App installation, a webhook and a tunnel route.
6. **Approve.** The owner reads the record, does the person steps and merges. The GitOps tool then syncs the service.
7. **Go live.** Run the go-live check of the service. If a check fails, do the stop steps and open an incident issue.
8. **Continue.** At the end of the first SLO window, compare the SLI with the objective, and tune the alerts. Read the rows again at each trigger of the first section.

**Table 12.** Who decides each part of a launch.

| Decision | Who | Record |
| :--- | :--- | :--- |
| The launch of a service or a repository | The owner | The merge of the launch pull request; the readiness report on it |
| An SLO objective and the error budget policy | The owner | The merge of the Sloth spec |
| A required row that is not met | The owner | An owner comment and an end date on the issue of the row |
| A change of a security or quality threshold | The owner | [SECURITY.md](../../SECURITY.md#a-finding-with-no-fix) |
| A Secret, a setting, a ruleset, an App installation or hardware | The owner | The `devops k8s push-secrets` run; the settings as code |
| The merge of each other pull request | A person | `merged_by`; the release document of the project for the release pull request |
| The evidence, the checks, the gap issues and the go-live checks | An agent | The readiness report; the results in a pull request comment |

## Build a new service

This is the path from an empty repository to a service in production. Each step names the tool that does it, and the rows that it meets. A job of a service stays in the repository of the service as a Job or a Workflow. A product with its own releases gets a new repository.

**Table 13.** The steps of a new service.

| Step | Do | Tool | Rows |
| :--- | :--- | :--- | :--- |
| 1. Plan | File the item, and check its premise against the real system. Name the open tool, or write the cost to build. | `devops roadmap intake`; [AGENTS.md](../../AGENTS.md) rules 2 and 3 | OWN-3, DEP-4 |
| 1. Plan | Plan the change with the draft catalog entry, the SLOs, the data class and the dependencies. | `devops openspec new` | OWN-1, SLO-1, DATA-1, DEP-1 |
| 2. Repository | The owner makes the repository and sets its ruleset and its security settings. | GitHub settings, or the settings as code | REL-1, SEC-1, SEC-2 |
| 2. Repository | Add the baseline files. Use a generator of devops-cli where one exists, so that no repository holds a hand copy of a generated file. | `devops ai agents --repo <path>` writes `AGENTS.md` and its pointer files | OWN-2, OWN-5, OWN-7 |
| 2. Repository | Add the labels file and the status workflow, set up OpenSpec and write the project profile. | `devops roadmap onboard --repo <owner>/<name> --confirm`; `openspec init`; `.devops/project.toml` | OWN-3, OWN-6 |
| 2. Repository | The owner installs the App and adds the repository to `service.repos`. | GitHub settings; `devops config set service.repos` | OWN-6, ACC-11 |
| 2. Repository | Extend the shared Renovate preset of devops-cli. | `renovate.json` | SEC-6 |
| 3. Build | Commit the lockfile. Pin each action, image and chart. Give each job its token permissions. | `uv lock`; `devops scan workflows`; `devops k8s image-pins` | SEC-4, SEC-5 |
| 3. Build | Run the tests, the coverage floor, the static checks, CodeQL and the audit in CI. The owner makes them required checks. | `ci.yml` and `codeql.yml` of devops-cli as the model | REL-4, SEC-3, SEC-7 |
| 3. Build | Build the image in stages as user 1000. Scan it, push it by digest, and attest its provenance and SBOM before the tag. | `release.yml` of devops-cli as the model | SEC-8, SEC-10 |
| 3. Build | Make each release with release-please from the Conventional Commit titles. | release-please; the `Semantic PR title` check | REL-5 |
| 4. Code | Read the settings from the environment and the ConfigMap, and the secrets only from Secret references. | The settings model of devops-cli | DEP-3, ACC-1 |
| 4. Code | Serve `/healthz` and `/readyz`, drain on SIGTERM, and put each time limit inside the limit of its caller. | The health routes of the devops-cli Service as the model | REL-7, DEP-2, CAP-2 |
| 4. Code | Write the logs to stdout. Send the metrics and the spans over OTLP. Turn off the telemetry of third-party tools. | The OpenTelemetry SDK | SLO-5, SEC-12, DATA-7 |
| 5. Deliver | Add the namespace at `restricted`, the manifests with requests, limits and probes, the ServiceAccount, and a NetworkPolicy that refuses all traffic first. | The namespace list of the environment tree; Kustomize or Helm; `devops k8s lint`; `devops k8s validate` | ACC-5, ACC-7, ACC-8, CAP-1, CAP-2 |
| 5. Deliver | Add a row to the Secret table with a generator. The owner pushes the Secret before the merge. | The Secret table of devops-cli; `devops k8s push-secrets` | ACC-1, REL-9 |
| 5. Deliver | Add the GitOps application, and an Image Updater entry for an image that the project builds. | The applications of the environment tree | REL-6 |
| 5. Deliver | Limit the pods that the service makes, and run untrusted code under gVisor. | A ValidatingAdmissionPolicy with a test; RuntimeClass `gvisor` | ACC-6, SEC-11 |
| 6. Observe | Add the entry of the service dashboard table and its query cases. Write the Sloth spec. Add the cause alerts with their runbook rows. | The service dashboard table; Sloth | SLO-1 to SLO-8 |
| 7. Data | Back up the owned state off its node, alert on the age of the backup, and run the first restore test. The owner sets the RTO. | The Barman Cloud plugin; k8up for a volume | DATA-2 to DATA-6 |
| 8. Review | Post the readiness report, get the independent review, and prepare the person steps. | [Production readiness review](#production-readiness-review) | SEC-13, EVD-1 |
| 9. Launch | The owner pushes the Secrets and merges, and the GitOps tool syncs. Run the go-live check. | The go-live check of the product | REL-10, INC-4, EVD-2 |
| 10. First window | Read the SLO each week. At the end of the first window, compare the SLI with the objective. Tune the alerts, and set the requests from the measured use. | The service dashboard; the tuning loop of the Kubernetes guideline | SLO-1, CAP-1, EVD-3 |

## Sources

**Table 14.** The codes of the column Standard. A code with a section or a criterion, such as SRE-E Monitoring, names that part of the source.

| Code | Source |
| :--- | :--- |
| SRE-4 | Google SRE book, chapter 4, [Service Level Objectives](https://sre.google/sre-book/service-level-objectives/) |
| SRE-6 | Google SRE book, chapter 6, [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) |
| SRE-11 | Google SRE book, chapter 11, [Being On-Call](https://sre.google/sre-book/being-on-call/) |
| SRE-14 | Google SRE book, chapter 14, [Managing Incidents](https://sre.google/sre-book/managing-incidents/) |
| SRE-15 | Google SRE book, chapter 15, [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/) |
| SRE-26 | Google SRE book, chapter 26, [Data Integrity](https://sre.google/sre-book/data-integrity/) |
| SRE-28 | Google SRE book, chapter 28, [Accelerating SREs to On-Call and Beyond](https://sre.google/sre-book/accelerating-sre-on-call/) |
| SRE-32 | Google SRE book, chapter 32, [The Evolving SRE Engagement Model](https://sre.google/sre-book/evolving-sre-engagement-model/). Its PRR phases are Engagement, Analysis, Improvements and Refactoring, Training, Onboarding and Continuous Improvement. |
| SRE-E | Google SRE book, appendix E, [Launch Coordination Checklist](https://sre.google/sre-book/launch-checklist/) |
| WB-2 | The Site Reliability Workbook, [Implementing SLOs](https://sre.google/workbook/implementing-slos/) |
| WB-5 | The Site Reliability Workbook, [Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/). Table 2 of the [SRE guideline](sre.md#burn-rate-alerts) holds the burn rates. |
| WB-8 | The Site Reliability Workbook, [On-Call](https://sre.google/workbook/on-call/) |
| WB-9 | The Site Reliability Workbook, [Incident Response](https://sre.google/workbook/incident-response/) |
| WB-10 | The Site Reliability Workbook, [Postmortem Culture](https://sre.google/workbook/postmortem-culture/) |
| WB-16 | The Site Reliability Workbook, [Canarying Releases](https://sre.google/workbook/canarying-releases/) |
| WB-18 | The Site Reliability Workbook, [SRE Engagement Model](https://sre.google/workbook/engagement-model/) |
| WB-B | The Site Reliability Workbook, appendix B, [Example Error Budget Policy](https://sre.google/workbook/error-budget-policy/) |
| DORA | [DORA metrics](https://dora.dev/guides/dora-metrics-four-keys/): change lead time, deployment frequency, change fail rate, failed deployment recovery time and deployment rework rate |
| SC | [OpenSSF Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md), by check name |
| BP | [OpenSSF Best Practices badge](https://www.bestpractices.dev/en/criteria/0), passing criteria, by criterion ID |
| SLSA | [SLSA v1.0 build levels](https://slsa.dev/spec/v1.0/levels). Build L2 is signed provenance from a hosted build platform. |
| SSDF | [NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final), Secure Software Development Framework 1.1, by practice |
| CIS | [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes), by control |
| K8S-PE | Kubernetes documentation, [Production environment](https://kubernetes.io/docs/setup/production-environment/) |
| K8S-SC | Kubernetes documentation, [Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/), by section |
| K8S-APP | Kubernetes documentation, [Application Security Checklist](https://kubernetes.io/docs/concepts/security/application-security-checklist/) |
| 12F | [The Twelve-Factor App](https://12factor.net/), by factor |
| Tools | [kube-linter checks](https://docs.kubelinter.io/#/generated/checks), [kubernetes-mixin](https://github.com/kubernetes-monitoring/kubernetes-mixin), [KRR](https://github.com/robusta-dev/krr), [kube-bench](https://github.com/aquasecurity/kube-bench), [Sloth](https://sloth.dev/introduction/), [Trivy](https://trivy.dev/) |
