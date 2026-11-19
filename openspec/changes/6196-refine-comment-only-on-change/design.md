# Design

## Decisions

- The gate compares the result of the round with the round before: the recorded `refine.next_step`, the refine section of the current body without its `checked-at` line, and the recorded `refine.frame`. A selected item whose section a person edited is left out (`check_person_edits`), so the section in the body is the one that refine wrote last. No new hash is recorded, and `refine.section_hash` keeps the full section for the check of person edits.
- The `checked-at` line holds the commit, so it is left out of the compared text. A new commit with the same result posts nothing.
- The watched files are sorted in the section. Two rounds that give the same paths in another order give the same section. The record `refine.block_paths` keeps the order of the proposal, so the cap on the paths keeps its first paths.
- The new items of deferred parts are known only after apply files them. The plan writes the section with the numbers that the record holds, and apply writes the last part of the section again with all the numbers and records the new section hash. A round that files a part always posts its event.
- The refusal of intake for a deferred part goes into the open questions of the section, so the frame that asks it can name the section.
- The frame of an item that links the frame of an older item ended its wait through the issue number in the link comment. The wait text no longer reads the comment, so refine records the item that holds the frame (`refine.frame`). A wait ends when the open item that holds the frame of its question is not that item, and the next round posts the frame.
- Wait selection uses the later of refine's last comment and `refine.repeated_at` as the start of the wait, for a reply and an owner answer on another item. The model input stays at refine's last comment, so a reply that a round with no comment read still reaches the model.
- A stage return counts from refine's last comment. A round that answers a return with the same result posts no comment, so the second return of the stage job has the same text as the first, and the store refuses it as a repeat. The first return comment is then the only trace, and with `refine.returned_body_hash` it tells a second return. A person who sets such an item back with no comment gets the reason of a second return.
- The repeat guard of the store masks each hexadecimal identifier, also the hash of a frame. The refine frame names the place of its question, so the fingerprint adds the hash of the question back: `test_a_round_that_asks_the_same_question_again_posts_no_second_comment` showed that the store refused the frame of a new question.
- A frame moves when the open item that holds its question is another item: the older item closed, or a reply answered its question and its record no longer holds the hash. In the second case the newer item waited before on a link to a frame that no answer could reach.
- A round that posts its event clears `refine.repeated_at`, so the record tells whether the last round posted. A refusal of the store still records it (#4793).

## Rejected alternatives

- A hash of the full comment as the gate: the comment named the commit and the Status, which change each round, as the repeats on #3655 and #6048 show.
- The next step alone as the gate: a changed question, dependency, path or new item would post nothing.
- A new record of the section hash without the `checked-at` line: the current body holds the section of the last round, so a record would only copy it.
- The wait text from the last refine comment: the event line names no issue and no path, so a person wait would never end on a named cause.
- The anchor of a stage return at `refine.repeated_at`: the store refused the second return comment as a repeat of the first in `test_a_second_stage_return_on_the_same_body_waits_on_a_person_with_the_reason`, so the item showed the reason of a person who set it back.
- The anchor of the model input at `refine.repeated_at`: a reply between refine's last comment and the round with no comment would not reach the model again.
- Edit of one bot comment in place (peter-evans/create-or-update-comment): it runs as a workflow step and has no gate on a changed result, as the alternatives check of #6196 records.
