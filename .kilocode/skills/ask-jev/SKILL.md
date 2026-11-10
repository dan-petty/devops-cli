---
name: ask-jev
description: Ask TypeSafe Jev one cheap, calibrated question: a yes/no with a probability, a pick of one option, or a score against a rubric. Use for triage, routing, labelling and gate checks on project text and code.
---

# Ask Jev One Question

TypeSafe Jev (`typesafe/jev-1.14`) is a small decision model. It does not write text. It answers one typed question about a text and gives a calibrated probability. A request costs very little (about 0.042 USD for 1M input tokens).

## Run It

Use the command or the MCP tool. Both take the same input.

- Command: `uv run devops ai ask-jev <kind> "<question>"`, with `--json` for typed output.
- MCP tool: `ai_ask_jev` (read-only) on the `devops-cli` server.

The three kinds:

1. `noul` is a yes/no. The answer is the probability of yes. Example: `uv run devops ai ask-jev noul "Does this change touch only documents?" --context "<text>"`.
2. `choice` picks one option. Give two or more `--option label=description`. Example: `uv run devops ai ask-jev choice "Which label fits?" --context "<text>" --option bug="A defect" --option idea="A proposal"`.
3. `score` rates the text on a rubric. Give two or more `--level "<description>"` from level 0 up. Example: `uv run devops ai ask-jev score "How complex is this task?" --context "<text>" --level "Trivial" --level "Normal" --level "Hard"`.

`--context` is the text that Jev decides about. With no context, the question is that text. Add `--dry-run` to see the request without a call. The output holds the answer, its probability, the probability of each option and the token count.

## When to Ask

- A cheap yes/no with a probability that you can compare with a threshold.
- A pick of one of N options.
- A score against a rubric.
- Triage, routing, labelling and gate checks.

## When Not to Ask

- Open-ended generation: Jev writes no text.
- Anything that needs tools or a read of the repository: Jev sees only the text you send.
- A security decision that Jev alone would make.
- A secret: see the next section.

## Never Send a Secret

Jev is a hosted model. The text leaves the cluster (SECURITY.md, item 13). Project text and code are fine to send. Never send a secret: a key, a token, a password or a private key. The command refuses an input that holds a secret and an input of more than 16,000 characters.

## A Jev Answer Is Evidence, Not a Verdict

Read the probability. A probability near 0.5 means that Jev does not know. Check the answer yourself against the files, the command output or the upstream document before you act on it. Do not close an issue, merge a change or skip a check on a Jev answer alone.
