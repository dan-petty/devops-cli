# Design

## Decisions
- **The replay names the Python of the venv of the checkout.**: `checkout_python` in `runner_tools.py` gives `<checkout>/.venv/bin/python`, next to `checkout_environment`, which already puts that folder first on the PATH of the checks.
- **The interpreter is a keyword argument with the default `sys.executable`.**: `devops ci fail-to-pass` runs in the venv of the checkout, so it keeps its interpreter and its tests do not change.
- **The replay gets no new reach.**: The agent can write `.venv/bin/python`, but the replay already runs the `conftest.py` and the tests of the head, which the agent writes, in the same environment.

## Rejected alternatives
- **Install pytest into the image venv again.**: Rejected: #6517 removed the dev group from the image so that a check runs the tools of the checkout.
- **Start `python` from the PATH of `checkout_environment`.**: Rejected: the lookup then depends on the order of PATH, and the argv does not show which Python ran.
