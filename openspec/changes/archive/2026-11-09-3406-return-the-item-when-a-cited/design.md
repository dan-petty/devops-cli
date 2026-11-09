# Design

## Decisions

- **Probe the field in `probe_premise`, and return the item before the plan call.** The probe
  already reads the staging commit, and the return needs no model. The job returns the item when
  the probe finds a statement of absence that the commit contradicts, so a plan run never starts on
  a false premise.
- **Reuse the `ast` reader of `stage_models` and keep the git commands in the probe.** The reader
  of #3344 parses a module of the commit with no import. A field line is a new parse of the same
  text, so `parse_class_fields` joins that module. The commands run through `_Run.git`, so each one
  counts against the probe budget and the checkout stays unchanged.
- **Confirm the class before the probe reads a field.** A token with one dot is a field reference
  only when `git grep` finds the class of its left part at the staging commit. `README.md` and
  `Dockerfile.amd64` therefore stay paths, and a class name that starts with a capital letter is no
  test.
- **Read a field from the class body, with no inheritance.** The probe names the file and line of
  the definition, so it reads the line that the class body holds. A field of a base class is no
  field of the cited class for the purpose of the line, and the model reader of `check_proposal`
  still judges a read of an inherited field.
- **Detect absence on the line of the body.** A fixed tuple of absence phrases (`defines no`,
  `does not define`, `has no`, `lacks`, `is absent`) names the class before the phrase and the field
  after it, or the two parts of a dotted reference. The check is deterministic and offline, and a
  test sets the exact wording.
- **Return with `refine.next_step` set to `edit`.** The body must change before the item can be
  planned, and only a body edit ends the `edit` wait. A body edit brings the item back to refine,
  as a false premise needs.
- **Make no model call for the item.** The probe decides the return, so the job spends no plan
  tokens on a premise that a merged commit has closed. A golden replay counts the return as a
  refusal with `RoadmapStageError`, as it counts a blocked item.

## Rejected alternatives

- **Tell the planner to restate the plan around the current field.** A full plan run on a false
  premise is the cost that #3406 removes, and the body still says that the field is absent.
- **Use `git grep` for the field name.** A text match finds the name in another class, a comment or
  a string, and it cannot name the class that holds the field.
- **Read the field text with a regular expression over the module.** A class body across many
  lines and a nested class make a line pattern ambiguous, and the project already reads Python
  source with `ast`.
- **Reuse `model_fields` and return no line.** That reader gives the module and the field names,
  and the return comment must quote the file and the line of the field.
- **Treat a token whose left part starts with a capital letter as a field.** `README.md` reads as a
  field reference, and the probe spends a command on every documentation path.
- **Probe the token as a path first, then as a field.** It keeps the false no-file line that #3406
  fixes.
