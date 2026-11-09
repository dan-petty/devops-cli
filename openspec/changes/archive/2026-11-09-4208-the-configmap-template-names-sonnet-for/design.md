# Design

## Decisions

- **Change the `analysis` slot only, and keep the other slots.**: The owner decision of 2026-11-09 (#4204) tries Sonnet where the stage job fails. The task `stage` takes its model and window from `analysis` (`_TASK_PARENTS`), so the one edit moves the planner, refine and the alternatives check, which all read `analysis`. The other slots stay on DeepSeek, so a failure of the other jobs still shows one model.
- **Set `context_window` to 200000.**: The window is the value of the live ConfigMap. It is below the 1,000,000 of the gateway group and above the need of the planner (the first request plus the minimum tool calls).
- **Keep the `verification` window at 256000 and fix its comment.**: The slot stays on DeepSeek, whose smallest fp8 provider window is 256,000. Its comment said that the window is the same as for `analysis`; that is no longer true.
- **Rename the requirement and modify it, not add a second one.**: One requirement already states the rule for the slots. A second requirement that contradicts it would leave the spec wrong, so the delta renames and modifies it.
- **Test the comment text with a list of needles.**: A comment is not data in the parsed YAML. The test reads the lines between `tasks:` and `analysis:` and asserts the issue numbers, the date and the cost, so the trial does not look like drift to a reader.
- **Apply nothing to the cluster.**: The live ConfigMap already holds these values. The PR only makes the template equal to them, so the next `deploy-stack` keeps the trial.

## Rejected alternatives

- **Leave the template and patch the live ConfigMap only.**: `deploy-stack` renders the template and Argo CD removes drift, so the next deploy reverts the trial and the stage job stages nothing again (#4204).
- **Move all chat slots to Sonnet.**: The issue asks for `analysis` only. The review of 12 golden plans put DeepSeek at 38% of the known defects against 56% for Sonnet (`k8s/llm/gateway/config.yaml`), but the cost of Sonnet on every slot was not approved, and #3874 keeps the other slots on one model.
- **Add an override setting for the trial.**: The slot is already a declared setting. A new setting would add code to a one-line change of data.
