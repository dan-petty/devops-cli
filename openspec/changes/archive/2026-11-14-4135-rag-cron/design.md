# Design

## Context

The module reads `cronworkflow-rag-ingest.yaml` directly and pins the schedule. It never checks the template link or the ingest args, and it cannot fail when the resource is absent.

## Goals

- Fail when no scheduled ingest is rendered.
- Check the schedule shape and the command in the referenced template.

## Decisions

- **Read the kustomization resources.** The harness refuses a real `kubectl`, so the helper reads the files that `k8s/devops/kustomization.yaml` lists.
- **Accept a CronWorkflow or a CronJob.** The selector skips a suspended resource. A CronWorkflow resolves its template through `workflowTemplateRef`; the template gives the container.
- **Helpers raise AssertionError.** A missing resource and an invalid schedule fail with a message that names the field.

## Risks

- A kustomization that patches a resource rather than listing it would not appear. The `k8s/devops` kustomization lists these files directly.

## Tests

- The rendered schedule is `*/3 * * * *`.
- The template runs `devops ai rag ingest`.
- Another command, no resource and an empty schedule are refused.
