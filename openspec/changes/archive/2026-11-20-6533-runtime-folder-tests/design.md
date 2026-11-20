# Design

## Decisions

- The tests check the code of devops-cli: the token folder goes directly into the runtime folder that platformdirs gives. Which `XDG_RUNTIME_DIR` platformdirs accepts is a rule of platformdirs, so the tests set `user_runtime_path` and do not depend on the parents of `tmp_path`.

## Rejected alternatives

- Pin platformdirs to 4.14.7: this keeps out a stricter check of the runtime folder, and Renovate would move the pin again.
- Make the parents of `tmp_path` private in the test container: the test would then depend on the layout of one container.
