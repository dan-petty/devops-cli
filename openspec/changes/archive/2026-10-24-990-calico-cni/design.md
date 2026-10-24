# Design

## Context

Issue #990 identified a discrepancy between the help documentation and the Minikube startup command in `src/devops_cli/commands/k8s/cluster_runtime.py`.
The help documentation indicated that clusters use Calico, but the execution code passed no `--cni` flag to Minikube.
Because default Minikube CNI does not enforce `NetworkPolicy` objects, network policies in sandbox environments (#702) and namespace perimeters (#913) silently do not take effect.

## Goals / Non-Goals

**Goals:**

- Ensure Minikube cluster startup commands pass `--cni=calico` so NetworkPolicy resources are enforced.
- Ensure `devops k8s bootstrap` command help explicitly and accurately states Calico is used.
- Add an offline test that pins the Minikube start argument vector and validates help text.
- Synchronize CLI documentation references.

**Non-Goals:**

- Do not introduce alternative CNI plugins (such as Cilium or Flannel).
- Do not add runtime flags to disable network policy enforcement.
- Do not modify remote or cloud Kubernetes cluster contexts.

## Decisions

- **Decision: Configure `--cni=calico` instead of removing Calico from documentation.**
  *Choice:* We choose Calico. The project network perimeters and sandbox policies require NetworkPolicy enforcement. Without a policy-enforcing CNI, policies fail silently.
  *Rejected Alternative:* Remove Calico from documentation and document that NetworkPolicy is not enforced.
  *Evidence for Rejection:* Network isolation and security perimeters would remain ineffective on local clusters, compromising testing integrity.
- **Decision: Bind `HELP.k8s.bootstrap` in command registration.**
  *Choice:* Pass `help=HELP.k8s.bootstrap` in `app.command("bootstrap")` and align `bootstrap()` docstring.
  *Rejected Alternative:* Rely solely on docstring without referencing `HELP.k8s.bootstrap`.
  *Evidence for Rejection:* Centralized strings in `src/devops_cli/lang/en/help.py` maintain consistency across the CLI and documentation generators.

## Risks / Trade-offs

- [Minikube cluster initial start duration may increase slightly to pull and initialize Calico pods] → Acceptable for security and policy enforcement guarantees.
