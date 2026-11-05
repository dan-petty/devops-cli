# Design

## One tier for every step class

The ladder of each class holds `deepseek-v4.1-flash-1017` and nothing else.

- Rejected: keep `devops-coder` as a second, stronger tier. It is the slow local model that the owner wants to leave, and a step that moves to it waits on the local GPU.
- Rejected: `claude-sonnet-5-5` as a second tier. The owner chose DeepSeek, and a Sonnet tier would send the same prompts to a second provider at a higher price.
- Accepted cost: a failure of class `change_tier` ends the step, because no tier remains (`roadmap-implement-step`). A person or a retry comment restarts the item.

## The window of the task

The window is 256000, the smallest window of an fp8 endpoint of the group. The gateway group allows 1,048,576.

- Rejected: 1,048,576. The route `:floor` can pick an endpoint with 256,000, and then a long step fails at the provider.
- Rejected: 128000, the default. It works (the live run used it), but it compacts the context earlier than the endpoints need. The output cap of a reply is a quarter of the window (64,000 tokens), which still cuts only a model that does not stop.
- `roadmap.stage.step_tokens` stays at 64000: with the turn reserve of 40000 a step needs 104000 tokens, and 256000 holds it.

## The test

The test reads the example ConfigMap and the gateway config and compares them. A rename of the group in the gateway config fails it.

- Rejected: a constant in the test that names the group. It would not follow a rename of the gateway group.
