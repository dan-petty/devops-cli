# Design

## Decisions
- **Parse `OwnerQuestion.link_comment` via `linked_frame_item` (`src/devops_cli/roadmap/owner_question.py`)**: avoids adding redundant job-record state and still locates the frame item even if the frame item already closed or moved to Ready.
- **Reuse `answer_of` with the covers `OwnerQuestion.hash` and `actor`**: guarantees identical trust filtering (`is_person_comment`, ignoring bots, strangers, and the job account) and post-frame ordering without duplicating reply-filtering logic.
- **Keep `covers_question` pure with optional `frame_comments` and `actor`**: lets unit tests exercise `covers_question` offline with explicit comment sequences while `refine_one_item` fetches frame comments via `_frame_comments` only when a `covers` check has a linked frame comment.

## Rejected alternatives
- **Store a new job-record field for the linked covers frame**: rejected because `link_comment` already records `#<frame_item>` and adds no state drift.
- **Read all comments on the frame item without checking `frame_hash` or `is_person_comment`**: rejected because unrelated earlier comments, bots, or the job account would answer the covers question.
