# Design: #4428

## Context

The Gateway section of `k8s/README.md` documents the master key, the hosted groups and one Gemini
call. The upgrade changes the provider path of each group, so one call per group after a roll is
the cheapest proof that the paths still answer.

## Decisions

- The calls send no provider key. The gateway pod holds the provider keys, and a caller sends
  only its gateway key.
- The structured call goes to `claude-sonnet-5-5`, whose group sets
  `supports_native_structured_output` and `supports_response_schema`. A failure names a lost flag.
- `tests/k8s/test_gateway_smoke_docs.py` reads the section between its heading and the next
  heading, so a later section neither hides nor supplies a call.
- The record steps name the upgrade issue and `devops gh issue create --label source/agent`, so a
  failed call becomes an issue with no priority label.

## Risks

- The calls use a node address and the node port, which a person reads from the cluster. The test
  asserts the literal `<node>:<node-port>` and needs no cluster.
