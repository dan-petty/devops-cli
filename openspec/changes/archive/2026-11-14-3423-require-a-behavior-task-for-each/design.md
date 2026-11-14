# Design

## Decisions

**The rule applies to a scenario that names no code.** The rule of #3321 already judges a scenario that names code, and a plan that satisfies it is accepted. A second refusal for the same scenario would add noise. A scenario whose only code spans are commands or untouched data files is judged by the new rule.

**A base-spec scenario is exempt.** A MODIFIED requirement restates the scenarios of the base requirement, and those scenarios have tests in the merged change. A caller that gives no base scenario names skips the new rule, as a caller that gives no requirement texts skips the rule of #3287.

**The base spec reader carries the scenario names.** `BaseSpec` gains a tuple of the scenario names of the file, and `scenario_names_at` reads the same files for the commands that read a commit rather than a checkout. A second parser of the spec text would drift.

**The gate is `SPEC_DELTA`.** The rule judges the spec delta, like #3321, so a person reads it under that gate.

## Rejected alternatives

- **A separate module `stage_scenarios.py`.** The existing `_scenario_problems` is the one place of the scenario rules, and the new rule is ten lines beside it.
- **A count of behavior groups against scenarios.** A plan can cover several scenarios with one test module, and a count would refuse it.
- **A new setting.** The rule follows the same failure model as the other plan rules: a refusal goes back to the model with the problem.
