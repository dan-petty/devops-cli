# Design

## Decisions

- One function, `_Planner._returned`, settles a reply, sends it back with `previous` and `problem` when the checks refuse it, and ends the item when the reply stays refused. `_gated` (first reply) and `_repaired` (revision) call it. One rule serves both, so the two paths cannot differ.
- The number of returns is `CONST_ROADMAP_STAGE_GATE_RETURNS` (1) for each reply and each repair round. The number of repair rounds stays `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`. So a repair round costs two planner calls at most and the loop has a fixed bound.
- The refused replies of the item are a list on the planner, cleared at the start of each item. The asks of the first reply and of each revision add to it, so `<n>.refused.json` holds all of them when the item fails (#4312). The key of the plan input comes from `plan` through `_verified` and `_repaired`.
- A revision that stays refused has its own failure text, so a person sees that the plan passed the checks before the review and failed after it.
- The check for a reply of placeholders applies to a revision too. The same request gives the same reply, so a second request is useless.

## Rejected alternatives

- Several returns for each round: it adds cost and delay, and the issue asks for one.
- A copy of the return code in `_repaired`: the two paths could then differ.
- A second file for the refused revision: it adds a file and a reader and splits the replies of one item.
