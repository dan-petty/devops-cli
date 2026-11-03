# Design

## Decisions

- **Check in `_settle`, not in the schema.** The issue number is not known to the `summary` validator, and the number rule needs it. `_settle` has the title, and a `_Refused` result already sends the problems back to the model once and stops the item on a second refusal.
- **Reuse `title_problems`.** One source of the form. #3215 keeps the same call and adds the body.
- **A tolerant lead.** The pattern takes the last word before `#<number>`, so `fix plan #N plan x` and `re-plan #3 re-plan x` are found. The colon and the dash after the number do not hide the repeat.

## Rejected

- **A check only in the `summary` validator.** It cannot see the issue number.
- **Wait for #3215.** The hole is live today: four titles on main have the repeat.
- **A grammar for the task gate.** The first pull request rejected it, and the word count stays.
