# Design

## Decisions

- Resolve the project with `uv workspace dir --project <target>`, the command uv itself uses to name the project from a directory, and refuse the audit when the project lies outside the workspace. Asking uv keeps the check honest to the project uv would audit, rather than a re-implementation of uv's discovery.
- Run the probe in the uv audit adapter, not in the generic tool layer, because the adapter knows uv's project resolution. The workspace is the working directory of the process, which the agent tool sets to the workspace.
- Run the probe only when uv is installed, so the `not installed` outcome is unchanged, and before the audit, so a wrong project is never audited and no finding of it reaches a reply.
- Give the refusal `not_applicable`, with a reason that names the project, since the audit is not applicable to a project outside the workspace and a person must see which project uv would have audited.

## Rejected alternatives

- Report the project root in the reply only. Adds transparency but still audits the wrong project, and does not meet the expected behavior that the tool audits only a `uv.lock` inside the workspace.
- Walk the parents of the target to the nearest `pyproject.toml`. Re-implements uv's project discovery, which uv owns, and can diverge from the project uv audits.
