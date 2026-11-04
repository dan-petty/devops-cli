# Design

## Decisions

- **Derive the glob from the created path and match the files of the staged commit with `PurePosixPath.full_match`.**: A fixed list of known trees misses a new file family until a person edits the list. The glob `*/skills/*/SKILL.md` finds every tree of the skill family in one pass.
- **Return the first two segments of each matching file as the tree, and drop the tree of the created path.**: The first segment is the agent root and the second is the fixed folder that the glob keeps, so the result names `.agents/skills/` and `.kilocode/skills/` and not `.claude/skills/`.
- **Keep the glob derivation and the match in `stage_paths.py`, and render the section in `stage.py`.**: The path module already owns the rules over the staged tree, and a unit test calls the helper without a model or a request.
- **Read the created paths from the issue body, as the probe does, and treat a cited path that the staged tree lacks as a path that the plan creates.**: The plan does not exist when the request is built. The issue cites the path that the plan creates, and the staged tree shows that it is new.
- **Append the section after `collect_context`, outside its token cut.**: The section is short, and the plan must see it whole.
- **Omit the section when no other tree matches `sibling_trees`.**: A single tree gives no choice to the plan.
- **Sort the tree names.**: The request text is a deterministic function of the issue and the tree.

## Rejected alternatives

- **A fixed list of the known agent roots.**: It misses a new family, such as a skill under a new root, until a person edits the list.
- **Match the file name anywhere in the tree.**: It lists unrelated files such as `.agents/notes/SKILL.md` and uses context space.
- **Put the list in the stage prompt only.**: The prompt has no knowledge of the staged tree, so the list must come from the request.
- **List the trees with no instruction to cover them.**: The plan can ignore the list; the prompt rule asks for each tree or a stated reason.
