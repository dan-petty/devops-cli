---
applies_to:
  - "pkg:pypi/pydantic-ai-harness@0.59.*"
sources:
  - "https://github.com/pydantic/pydantic-ai-harness"
  - "https://pydantic.dev/docs/ai/harness/"
reviewed: "2026-10-29"
tags:
  - "pydantic-ai-harness"
  - "pydantic-ai"
  - "agents"
  - "coder"
---

# Code Library: Pydantic AI Harness (Coding-Agent Capabilities)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [pydantic.dev/docs/ai/harness](https://pydantic.dev/docs/ai/harness/) |
| **Public Git Repository** | [github.com/pydantic/pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness) |
| **Official PyPI Package** | [pypi.org/project/pydantic-ai-harness](https://pypi.org/project/pydantic-ai-harness/) (`0.59.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/roadmap/implement_step.py`](../../../../../../src/devops_cli/roadmap/implement_step.py) |

---

## 2. General Information & Architecture

**Pydantic AI Harness** is a library of capabilities for pydantic-ai agents. A capability adds tools, instructions and hooks to an `Agent`. The library is MIT licensed and is made by the maintainers of pydantic-ai.

In `devops-cli`, `devops roadmap implement` uses two parts:

- `Coder` gives an agent six tools: `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`. It also gives the context controls `ClearToolResults` and `ToolOutputLimits`.
- `LocalWorkspace` of pydantic-ai gives the tools a checkout on this machine. The step passes the checkout as the working directory.

The project builds no agent loop of its own. It builds only the inputs of a step, its exit checks and its report.

---

## 3. Comparable Projects & Tradeoffs

| Tool | Strengths | Weaknesses | Why `devops-cli` Chose the Harness |
| :--- | :--- | :--- | :--- |
| **`pydantic-ai-harness`** | Same runtime as the rest of the project. Runs any pydantic-ai `Model`, so it runs the gateway's local models. | Releases are `0.x`, so the API can change between minor releases. | **Selected**: one agent runtime for the project (#2489). |
| **Claude Agent SDK** | Mature coding agent. | Second agent runtime. Needs Node and an Anthropic key. | Rejected on #2661. |
| **OpenHands, SWE-agent, Aider** | Full coding agents. | Each is its own runtime with its own container needs. | Rejected on #2661. |

---

## 4. Key Concepts & Core Patterns

1. **Version pin.** Each release of the harness pins `pydantic-ai-slim` to the same number. So `pydantic-ai-harness==0.59.0` fits `pydantic-ai==2.59.0`. Move the two pins together.
2. **Workspace.** `Coder` fails at the start of a run that has no workspace. Attach `LocalWorkspace(<dir>)` next to it.
3. **Tuning `Coder`.** `Coder` is a combined capability. `visit_and_replace` swaps one of its parts. The step swaps `Shell` for one with `allowed_commands` and `denied_operators`, `ClearToolResults` and `WarnNearLimits` for copies with `context_window` set, and the `ToolOutputLimits` band for a smaller cap.
4. **`delegate_task`.** `Coder(sub_agents=False)` leaves it out, so one agent run is one budget.
5. **Instruction files.** `Coder(repo_context=False)` does not load `AGENTS.md` and similar files of the checkout into the context.
6. **Shell checks.** `Shell` tests the first word of a command against `allowed_commands`, and tests `denied_operators` as text in the command. The harness states that these checks are best-effort and are not a security boundary. Isolation comes from the environment of the process.
7. **Directories.** `write_file` does not create a directory. A shell command creates it.
8. **Streaming.** The harness drives the model with streamed requests. A `FunctionModel` in a test needs a `stream_function`.

---

## 5. Common & Advanced Usage Examples

### A Coder agent on a checkout
```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import LocalWorkspace
from pydantic_ai_harness.coder import Coder

agent = Agent(
    model,
    capabilities=[LocalWorkspace("/path/to/checkout"), Coder(repo_context=False, sub_agents=False)],
)
result = agent.run_sync("Write the failing test, then the code.")
```

### An allowlist for the shell
```python
from dataclasses import replace
from pydantic_ai_harness.shell import Shell

coder = Coder(sub_agents=False).visit_and_replace(
    lambda leaf: (
        replace(leaf, allowed_commands=["git", "uv"], denied_commands=[])
        if isinstance(leaf, Shell)
        else leaf
    )
)
```

---

## 6. Best Practices & Security Standards

1. **Pin the harness with pydantic-ai.** A mismatch makes the resolver move pydantic-ai.
2. **Bound every run.** Use `UsageLimits` for the requests and the tool calls of a run.
3. **Judge the result outside the model.** Run the checks of the project after the agent returns. Do not ask the model whether it is done.
4. **Give the run no credential.** `LocalWorkspace` passes only `PATH`, `HOME` and the locale to a command. Run the step in a checkout and an environment with no secret.
