# Design

## Decisions

- The ceiling is 3, the measured default of #4802. In 8 of 10 sampled refused items the reply had fewer problems at the second ask, so 3 returns hold the progress that #4802 measured. A higher ceiling waits for the progress check of #4851, which gives a bounded extension with its own hard limit.
- The ceiling is a constant and not a setting, so a ConfigMap value cannot pass it. The settings load refuses a value above it with the name of the setting, as `deadline_ceiling_seconds` does with `CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS`.
- The stop check comes after the last-return check. A reply that has used its returns fails the item as before, because it starts no new plan run. Only a new return reads the stop.
- A stop before a return raises `ServiceStoppingError` with the work "return <n> of the plan of #<item>". The item keeps no refused-reply file, because it did not fail: the next pod plans it again.

## Rejected alternatives

- A time guard before each return. The stage job has no item or round deadline in code, so the guard has no outer limit to fit. #4847 adds the guards of the cap points.
- A ceiling of 2 (the value of the #4802 scope comment). The merged default is 3, so a ceiling of 2 would change the live behavior of the next release.
- A check of the stop inside each tool call of a plan run. The request budget already raises the stop at the next GitHub request of a run, and the model requests of a run have no stop seam.
