# Design

## Decisions

- **Read the live trace from the Job pod log through the Kubernetes client.**: The runner is a pod and its log already holds each step, tool call, check result and attempt (CONTEXT.md, Runner). The live part therefore sends no GitHub request.
- **Read the history of past runs from the hidden job record of the issue body, with one GitHub request.**: docs/adr/0001-github-is-the-roadmap-source.md says the issue body holds the job record, and docs/ROADMAP_WORKFLOW.md lists its keys by job.
- **Render every row with the PR comment table renderer.**: The issue asks for the shape of the PR comment table, and one renderer cannot drift from it.
- **Mask each value with the masker that the log lines already use.**: The `secret-masking` capability holds the rules, and a second masker can miss a value that the first one catches.
- **Print the follow command in the existing inbox and explain output.**: The issue asks both commands to link to follow, and each already builds its rows in one place.

## Rejected alternatives

- **Read the live trace from GitHub issue comments.**: The issue states that the live part sends no GitHub request, and docs/ROADMAP_WORKFLOW.md shows that the runner writes its comment when the Job ends.
- **Read the history from a local trace file or an external database.**: CONTEXT.md, Runner: the Service runs in a cluster and the Job pod shares no local file; docs/adr/0001-github-is-the-roadmap-source.md keeps the record in the issue body with no database.
- **Add a second table renderer for the follow output.**: The acceptance criteria of #3076 require the header and the column order of the PR comment table, and a second renderer drifts from it.
- **Add a new secret masker for follow.**: The `secret-masking` capability already states the rules that the log lines use, so a second masker can miss a value that the first one catches.
