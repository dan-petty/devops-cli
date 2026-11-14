# Design

## Context

`person_changed_title` takes the newest job comment as the bound of a person's rename. `_skip_comment_of` for an unlisted title writes a comment with the retitle marker and the person-edit reason, so it is a job comment.

## Goals

- Keep a title that a person set after a body edit.
- Keep the run bound and the skip mark clear for an unlisted type.

## Decisions

- **One exclusion.** A job comment whose body holds `retitle_reason_person_edit` does not bound the rename. Only the person-edit skip comment holds that text.
- **The mark stays.** The skip mark still holds the hash of the title and body, so a body edit selects the item, and the job then takes the person-edit path again.

## Risks

- A comment that quotes the reason text without being the skip comment does not bound the rename. Only the job writes that text.

## Tests

- A person's unlisted title stays after a body edit, and the item holds one skip comment.
