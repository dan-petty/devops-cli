# Proposal: #4428

## Why

The LiteLLM upgrade changes the provider path of each hosted group, and no offline test reaches a
provider. `k8s/README.md` documents one `curl` call for `gemini-3.8-flash` only, and a person
types the other calls by hand and records no result. A short documented check shows that each
group still answers after a roll. Closes #4428.

## What Changes

- `k8s/README.md` gets a "Smoke check after a gateway upgrade" subsection with one call for each
  hosted group, one structured call, the provider key of each group and the steps that run the
  calls and open a fix issue for a failure.
- `tests/k8s/test_gateway_smoke_docs.py` reads that section and asserts each call, the provider
  keys, the gateway key and the record steps.

## Capabilities

`ai-gateway-routing`: four requirements for the documented calls and their record.

## Impact

Docs and tests only. No command, manifest, image or gateway config changes. The live run after
the gateway rolls is #4885.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): the gateway config holds the four
hosted groups and the Anthropic structured-output flags, and `k8s/README.md` holds one Gemini call.
The five tests pass.

## Existing Tool Considered

`curl` is open and maintained, and the repository documents it for the Gemini group already. A
`devops ai gateway smoke` command would cost about 50,000 tokens to build and would prove only its
own stub offline. No new tool.
