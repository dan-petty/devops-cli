# Design

## Decisions

- **A ValidatingAdmissionPolicy, built in.** It is GA in the cluster (Kubernetes 1.31.4), runs inside the API server, and needs no component, no webhook and no certificate. Argo CD syncs it with the other `k8s/devops` manifests.
- **The user is a match condition, not part of a rule.** `matchConditions` runs before the validations. A Job of any other identity (the CLI user that runs `devops k8s run-job`, Argo CD, the CronJob controller) does not match, so the policy never evaluates it and cannot refuse it. The Jobs of those identities keep only the checks they have today.
- **`failurePolicy: Fail`.** The policy runs in the API server, not behind a webhook, so no outage of a component can block a request. `Fail` only matters when an expression errors, for example on a missing field. Then the Service's Job is refused, and the refusal is loud: the create raises `ClusterJobError`, the round takes the record back, and the next round tries again. `Ignore` would let a mistake in the policy open the gap again in silence. The error cannot reach another identity, because of the match condition.
- **`validationActions: [Deny, Audit]`.** `Deny` refuses. `Audit` writes the refusal and its message to the audit log of the API server.
- **`CREATE` and `UPDATE`.** The Role grants `create`, `get` and `list` on `jobs` and no `update` or `patch`, so RBAC refuses an update already. The policy covers `UPDATE` so that a Role that later gains the verb cannot change the pod template of an admitted Job. The pod template of a Job is immutable, so on an update the policy sees the same template.
- **Literal values, checked against the template by a test.** The policy holds the image repository, the names and the bounds as literals. The test renders `k8s/devops`, builds the Job from CronJob `devops-cli-runner` with `build_job`, and evaluates the policy on it. A change to the template that the policy refuses fails in CI. The test also reads the user from the subject of the RoleBinding, so the two cannot drift apart.
- **The image is the repository, with `:` or `@` after it.** A bare prefix test would admit `runner-evil` and `runner2`. The repository alone is the form of the template in git. Image Updater writes `runner:latest@sha256:<digest>` into the Application, which starts with `runner:`. The policy does not pin the tag or digest (see Guarantees).
- **No `valueFrom` in `env`.** `envFrom` pins the Secrets by whole Secret, but `env[].valueFrom.secretKeyRef` reads one key of any Secret. The template has no `valueFrom`, and the Service sets plain values only.
- **`envFrom` may be absent.** The rule is that no other source is named. A Job with no `envFrom` has less access, not more.
- **The bounds come from the template.** `backoffLimit` is 0 ("a job that changed GitHub never runs twice"). `activeDeadlineSeconds` is set and at most 7200. The API server sets the default of `backoffLimit` (6) before admission, so a Job that leaves it out reaches the policy as 6 and is refused. The rules require the fields to be present, so a Job without them is refused too.
- **Full object paths, no policy `variables`.** A `variables` entry would shorten the expressions, but the offline runtime returns a map as accessor objects that it cannot take back as input. The test would then need glue that evaluates variables in a second pass. The long paths cost a few characters and keep the test free of glue.
- **Standard CEL only.** The expressions use operators, `has`, `all`, `size` and `startsWith`. The offline runtime compiles them, and it fails to compile a Kubernetes-only function such as `isSorted`. So a later edit that uses a Kubernetes extension fails the test before it can differ from the runtime.
- **The test runtime is `cel-expr-python` 0.1.3.** It is the CEL project's wrapper of the C++ runtime, has no dependencies, and ships a wheel for Python 3.14 on Linux x86-64 and arm64, so the devcontainer and the GitHub runner both run it with no install. It is a dev dependency only.

## Rejected alternatives

- **Kyverno or OPA Gatekeeper.** Each adds a controller and an admission webhook to the cluster. The webhook is a new failure point for every request it covers. ValidatingAdmissionPolicy covers the need with nothing added.
- **Kyverno CLI to test the policy.** It runs ValidatingAdmissionPolicy offline on `cel-go`, which is the engine of the API server. But it is a Go binary that the devcontainer and the runner would have to install, and the rule for CI is no package installs on runners. The standard CEL language is the same in both engines, and the policy uses nothing else.
- **`cel-python` 0.5.0 and `common-expression-language` 0.10.0.** Both run the sample expressions with the same answers. `cel-python` is pure Python but needs `google-re2`, `pendulum`, `lark` and `jmespath`. `common-expression-language` needs `typer`, `rich`, `prompt-toolkit` and `pygments` for a command line that the test does not use. `cel-expr-python` needs nothing.
- **`kubeconform` or a server-side dry run alone.** `kubeconform` checks the schema and cannot tell that an expression is wrong. A server-side dry run needs a cluster, and a test never reaches one.
- **The CronJob as policy parameter (`paramKind`).** A binding with the CronJob as `paramRef` would pin the digest to the template exactly. But a Service that read the template just before Image Updater changed the digest would see its Job refused for a moment, and a missing CronJob would refuse every Job. A literal repository has neither effect, and the test already ties the literals to the template.
- **Pin `args`, `command` and `env` values.** The Service sets the args and the repository value for each item, so they cannot be pinned. The Service holds Secret `devops-cli` already, so these fields give it nothing it has not.
- **Move the Jobs to a namespace of their own with a narrower Secret.** It is the better end state, as the README says, but a person makes secrets, and it also needs a copy of the policies and the Pod Security labels. It is a separate item.

## Guarantees

A Job that the Service makes in namespace `devops` has, at admission: the runner repository as its one image, no init container, ServiceAccount `devops-cli` with no token, only Secret `devops-cli` as a source of environment, only the three volumes of the template, no host namespace, no retry, and a deadline of two hours at most. So it cannot read another Secret, cannot mount a host path or a Secret volume, and cannot run an image from another repository.

These are not guaranteed:

- The tag or digest of the runner image. A Job can name another tag of the repository. Only the release workflow publishes to the repository.
- The `args`, the `command` and the plain `env` values. The Service sets them for each item.
- The resources, `nodeSelector`, `tolerations`, the number of Jobs and `parallelism`. The `restricted` Pod Security level, which the API server enforces on the pod, still applies to the pod.
- The security context of the container. Pod Security `restricted` enforces it on the pod, not this policy.
- Any other identity. A person with an admin role, Argo CD and the CLI user are not bound. A person with an admin role can delete the policy, and Argo CD restores it on the next sync (`selfHeal`).
- The policy does not give the Service less than it has: the Service pod holds Secret `devops-cli` and all its environment.

## Risks

- The offline runtime and the API server are two implementations of CEL. The policy uses only the standard language, so the answers agree. The test feeds plain maps. The API server feeds the typed Job, converted to a map after the defaults are set. A field that is false or empty may be missing there, so every rule on such a field accepts "missing" as the safe value (`!has(x) || !x`). Two rules need a value that is present: `automountServiceAccountToken: false` and `backoffLimit: 0`. Both are pointer fields in the Job type, which the API keeps when they are false or zero. If the API dropped them, the policy would refuse every Job of the Service. That fails closed and shows at once, as `ClusterJobError` in the round. A person checks it once after the first sync, with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server -f <job>`.
- A change to the CronJob template that the policy refuses fails the test in CI. A change to the template and to the policy that merge together reach the cluster in one sync, but a Job made in the moment between the two is refused once and made in the next round.
- The policy is cluster-scoped, so Application `devops` owns two cluster objects. `prune` removes them if the file is deleted. A rollback is a revert of the pull request.
