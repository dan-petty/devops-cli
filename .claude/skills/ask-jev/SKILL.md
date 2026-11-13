---
name: ask-jev
description: Ask TypeSafe Jev or another decision model one cheap, calibrated question: a yes/no with a probability, a pick of one option, or a score against a rubric. Use for triage, routing, labelling and gate checks on short evidence. Do not use a decision model to write text or to read a long document.
---

# Ask a Decision Model One Question

TypeSafe Jev (`typesafe/jev-1.14`) is a System One decision model. It answers one typed question about a text and gives a calibrated probability. It does not write text, call tools or read the repository. A request costs very little (about 0.042 USD for 1M input tokens).

## A Decision Model Is Not a Generative Model

| The task | The model | Why |
| :--- | :--- | :--- |
| Answer one closed question: yes/no, one option of a list, or a level of a rubric | A decision model | It returns one typed answer and a probability at a low cost |
| Write a plan, a comment, a commit, a finding or code | A generative model | A decision model writes no text |
| Read the repository, run a command or use a tool | A generative model with tools | A decision model sees only the text that you send |
| Judge a long document or a whole diff | A generative model, or a short digest that tools make | A decision model does not read a long state |
| Change a workflow decision | A rule first, then a decision model, then today's behavior (ADR 0020) | A rule is cheaper and testable, and a model answer is evidence |

The two model kinds have separate settings. `ai.model` and `ai.tasks.<task>.model` name generative models. A registered workflow decision point uses the model that `ai.decision_model` names. That setting is empty by default, and the point then does what it does today. A chat model name is not valid there.

## Run It

Use the command or the MCP tool. Both take the same input.

- Command: `uv run devops ai ask-jev <kind> "<question>"`, with `--json` for typed output.
- MCP tool: `ai_ask_jev` (read-only) on the `devops-cli` server.

The three kinds:

1. `noul` is a yes/no. The answer is the probability of yes. Example: `uv run devops ai ask-jev noul "Does this change touch only documents?" --context "<text>"`.
2. `choice` picks one option. Give two or more `--option label=description`. Example: `uv run devops ai ask-jev choice "Which label fits?" --context "<text>" --option bug="A defect" --option idea="A proposal"`.
3. `score` rates the text on a rubric. Give two or more `--level "<description>"` from level 0 up. Example: `uv run devops ai ask-jev score "How complex is this task?" --context "<text>" --level "Trivial" --level "Normal" --level "Hard"`.

`--context` is the text that Jev decides about. With no context, the question is that text. Add `--dry-run` to see the request without a call. The output holds the answer, its probability, the probability of each option and the token count.

## When to Ask a Decision Model

Ask a model only when no file or deterministic check can answer. Then ask a decision model for one of these:

- A cheap yes/no with a probability that you can compare with a threshold.
- A pick of one of N options.
- A score against a rubric.
- Triage, routing, labelling and gate checks on short, closed evidence.

Give the model a short digest that a tool made: a count, a path, a test name, a criterion, a hunk or a quoted line. The answer is only as good as the evidence in the request.

## When to Ask a Generative Model Instead

- Open-ended generation: a decision model writes no text.
- Anything that needs tools or a read of the repository: a decision model sees only the text you send.
- A long document as the state of the question: the answer follows the text poorly.
- A decision that needs a quote from the input: a decision model gives none.
- A security decision that the decision model alone would make.

## Other Decision Models

A decision model answers typed questions through the `pydantic_ai` `DecisionModel` interface. The client accepts TypeSafe Jev under the `typesafe:` prefix and a System One decision model under the `system-one:` prefix. A workflow names one model in `ai.decision_model`; the name must be a System One model, and the settings refuse a chat model. An agent does not choose a model for `ask-jev`: the command asks Jev. Use another decision model only through a `DecisionModel` that the code builds, and keep the same rules: short closed questions, a calibrated probability and a fallback to the current behavior.

## Never Send a Secret

Jev is a hosted model. The text leaves the cluster (SECURITY.md, item 13). Project text and code are fine to send. Never send a secret: a key, a token, a password or a private key. The command refuses an input that holds a secret and an input of more than 16,000 characters.

## A Jev Answer Is Evidence, Not a Verdict

Read the probability. A probability near 0.5 means that Jev does not know. Check the answer yourself against the files, the command output or the upstream document before you act on it. Do not close an issue, merge a change or skip a check on a Jev answer alone.
