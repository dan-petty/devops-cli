# Design

## Decisions

- **A digest, not the payload.** The state of the request is a digest that code builds: the criteria of the issue (cut to 300 characters), the groups of the plan (the work and the test cut to 260 and 220 characters), the paths that the repository does not hold, and whether the verify command names a test file of the group. Measured on the golden set: the whole payload as state (9,800 tokens) ranked the cases worse than the digest (1,700 tokens), and the cited files added to the digest did not help.
- **One request, nine questions.** The nine questions are the nine defect types of `VERIFY_TYPES`. Nine requests of one question gave the same ranking at nine times the tokens.
- **The cuts.** `continue` when every probability is under its cut. `flag` when a probability reaches its `flag_at` cut, which needs three cases above it that must all run. The data file holds one shared cut for all nine questions: on the recorded split it lost no serious defect in either direction, and a cut for each question lost 6 in one direction. An earlier split (a shuffle that the hash split replaced, because the shuffle used a pseudo-random generator that the security scan refuses) showed the reverse for one case, so the evidence is weak. The report gives both ways.
- **Three modes.** `shadow` is the step before a switch: it logs and counts, and the review always runs. The counter `devops_cli_roadmap_decision_step_review_total` gives the false-clear rate from real reviews.
- **Fail open.** `FAILED` in `decision_step.py` lists the errors. The screen logs one warning and counts `error`.
- **Refine stays out.** The judge of refine always runs its reviewer. A clean screen there would approve an item with no review.
- **The label of the fit.** A case must run when the reviewer alone found a serious defect (blocker or major) in it. The reviewer is stochastic. One run of the reviewer is the label, because a second run costs about 8 USD.

## Rejected alternatives

- **Piece-local requests (one request for each group, criterion or claim).** Rejected: 20,000 tokens for each plan, and a worse ranking than the digest.
- **Per-question cuts as the shipped rule.** Rejected as the rule: on halves of about 24 cases the cut of one question moved with one case. The report keeps both rules.
- **A cut in a constant.** Rejected by ADR 0019: the cuts are data with their provenance.
- **Score questions with levels.** Tried: they ranked the cases as well as the yes/no questions, with no gain for the skip rate.
- **A second reviewer run to measure noise.** Rejected on cost.
