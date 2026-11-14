# Proposal

## Why

The retitle job can overwrite a title that a person set with an unlisted type. The job writes a skip comment with the retitle marker, and that comment becomes the last job comment. After a body edit, the skip mark no longer holds, and the job selects the item again. It then reads the skip comment as newer than the person's rename and writes the correction (#4620).

## What Changes

- `person_changed_title` compares the rename with the newest job comment that does not report the person-edit reason.
- The requirements `A run is bounded` and `Skip mark` name an item with an unlisted title type.
- A test holds a person's title across a body edit.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-retitle`: A person's unlisted title survives a body edit, and the two requirements name the unlisted type.

## Impact

- Code: `src/devops_cli/roadmap/retitle.py`
- Spec: `openspec/specs/roadmap-retitle/spec.md`
- Tests: `tests/roadmap/test_roadmap_retitle_type.py`

## Feasibility

- The skip comment already holds the person-edit reason text.
- The store records each rename time.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_retitle.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The change reads the comments that the store already gives. No tool and no model call.
