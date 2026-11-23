# Design

## Decisions
1. **Recognize false conditional skip reasons in `_check_mode_caused`.** When `_FALSE_CONDITION` is not in `result`, inspect `skip_reason`. If `skip_reason` is `"Conditional result was False"` or begins with `"end_host conditional evaluated to False"`, check if `ansible_check_mode` is named in the string. If check mode is not named, the skip was caused by an ordinary conditional evaluation, not by check mode, so it returns `False`.
2. **Keep all other skips unchecked.** Any skip that does not match a known false condition skip pattern and lacks `false_condition` continues to be treated as a check-mode skip (`True`), preserving safe defaults.

## Rejected alternatives
- **Match only on action `ansible.builtin.meta`.** Rejected: `"Conditional result was False"` can appear on other tasks whose callback output omits `false_condition`. Inspecting `skip_reason` generically for false conditional markers correctly handles both cases without action-specific branching.
- **Ignore all `skip_reason` entries.** Rejected: this would treat unknown skips as checked, violating the safe-side default that treats unproven skips as unchecked.
