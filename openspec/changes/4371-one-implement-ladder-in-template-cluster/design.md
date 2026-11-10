# Design

## Decisions

- **One tier in the template.** The template is what a render writes. The owner chose DeepSeek first (2026-11-09 and 2026-11-10), the live ConfigMap has one tier, and the README says that a step has one tier. The template takes the same value, so the three places agree.
- **The code keeps the support for more tiers.** #4274 added two-tier ladders to the settings and to the step. A later Sonnet trial sets a second tier in the ConfigMap, with no code change. The comment above `implement` says so.
- **A test pins the ladder and the comment.** A later edit of the template that adds a tier fails the first test, and a comment that loses the decision fails the second. The trial then needs a visible edit of the test and of the README.
- **The spec gets a scenario.** The requirement already says "the one tier of each step class". The new scenario makes the value testable.

## Rejected alternatives

- **Two tiers in the template, the live ConfigMap and the README.** Rejected: it sends the prompts of a step, which hold repository code, to Anthropic at a higher price, against the owner decision of DeepSeek first. It also needs a cluster change that the issue and the owner did not ask for.
- **Remove the support for more tiers from the code.** Rejected: #4274 added it on purpose for a later trial, and the owner asked to keep it.
- **Leave the template and change the live ConfigMap and the README.** Rejected: the live ConfigMap holds the decided value already.
