# Design

## Count what the check counts

The check `Semantic PR title` decides if a title can merge. It counts UTF-16 code units, so the form check, the schema and the title must count the same, or the Service opens a pull request that the check refuses. `summary_length(text)` is `len(text.encode("utf-16-le")) // 2` and lives in `pull_form.py` next to `SUMMARY_MAX_CHARS`. `stage_change.py` imports it. The constant `STAGE_SUMMARY_MAX_CHARS` is the room after the lead in the same unit, which is the same number for the ASCII lead.

Rejected: refuse any character outside the Basic Multilingual Plane in a summary. It needs a second rule and a second message, and a title of 30 emoji is valid for the check. One measure is simpler and cannot disagree with the check.

Rejected: change the pattern of the workflow to use the `u` flag. A pattern change is a change of the gate, and AGENTS.md leaves a lower threshold to the owner. The gate counts units today.

## A blank summary

`min_length=1` counts the raw text, so the schema kept it only for the JSON schema that the model reads. The validator folds the text with `safe_text` and refuses a result with no text. A test holds both: the bound in the JSON schema and the refusal.
