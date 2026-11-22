"""The phases of a roadmap step that runs an agent: `prepare`, `agent` and `publish` (#3702, #6601).

The parent item #2695 splits a run into three trust zones. `prepare` holds the App key and runs no
agent code: it makes the GitHub reads, checks the claim and makes a plain clone of the issue
branch. `agent` holds the model key only: it runs the agent and its checks in the clone, makes no
GitHub call, and writes its outputs. `publish` holds the App key again: it reads the outputs of the
agent as data, applies each patch in a new repository as one commit of the bot, checks the claim
again, pushes with a lease and makes the GitHub writes of the outcome.

- `checkout.py`: the plain clone of the issue branch that `prepare` makes, with its base and lease.
- `files.py`: the run folder (`state/`, `work/`, `out/`), the models of the agent outputs, and the
  read of an output as data.
- `patch.py`: the patch of the agent phase, written in the agent clone with fixed format flags.
- `publish.py`: each patch applied as data in a new repository, one commit of the bot for each,
  and the push. #6528 uses it for stage.

`devops roadmap step fix-checks` is the first step on the phases. The runner template runs each
phase in its own container (#3700), and `--phase all` runs the three in one process.
"""
