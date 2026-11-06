# The roadmap package layout

`src/devops_cli/roadmap/` groups the modules of each job in a subpackage, so that the folder shows which modules belong to one job. A module that serves more than one job stays at the top level of the package.

The package module `src/devops_cli/roadmap/__init__.py` holds a docstring and re-exports no name. A caller imports the module that it needs by its path, such as `from devops_cli.roadmap.stores import store as roadmap_store` or `from devops_cli.roadmap.stage.stage_change import StageProposal`. A subpackage `__init__.py` holds a docstring only.

| Subpackage | Role | Modules | Tests |
| :--- | :--- | :--- | :--- |
| `intake/` | The intake job: it places each candidate (`devops roadmap intake`). | `intake`, `intake_model`, `intake_requests` | `tests/roadmap/intake/` |
| `refine/` | The refine job: it writes the design, tasks and criteria of an item (`devops roadmap refine`). | `refine`, `refine_investigation`, `refine_judge` | `tests/roadmap/refine/` |
| `stage/` | The stage job: it plans an item as an OpenSpec change on a branch and checks the plan (`devops roadmap stage`). | `stage`, `stage_change`, `stage_criteria`, `stage_eval_cases`, `stage_eval_gates`, `stage_eval_render`, `stage_eval_run`, `stage_eval_score`, `stage_eval_usage`, `stage_filter`, `stage_form`, `stage_github`, `stage_move`, `stage_moved`, `stage_overlap`, `stage_paths`, `stage_probe`, `stage_ready`, `stage_references`, `stage_rejected`, `stage_specs`, `stage_split`, `stage_toolbox`, `stage_tools`, `stage_validate`, `stage_verify`, `stage_verify_eval` | `tests/roadmap/stage/` |
| `implement/` | The implement job: it runs the steps of a staged item to a ready pull request (`devops roadmap implement`). | `implement`, `implement_amend`, `implement_base_replay`, `implement_deadline`, `implement_eval`, `implement_eval_properties`, `implement_eval_run`, `implement_hooks`, `implement_limits`, `implement_output_cap`, `implement_outside`, `implement_pull`, `implement_run`, `implement_scoped_ci`, `implement_shell_policy`, `implement_shell_refusal`, `implement_size`, `implement_step`, `implement_steps`, `implement_strays`, `implement_submit`, `implement_test_names`, `implement_tool_log`, `implement_trace`, `implement_wip` | `tests/roadmap/implement/` |
| `stores/` | The store interface and its GitHub adapter. A caller opens a store with `get_roadmap_store`. | `github_store`, `store` | `tests/roadmap/stores/` |

The tests of `tests/roadmap/` mirror this layout. A test module of a job or of the stores sits in the directory of its subpackage, with its `__snapshots__` file beside it. A test of a module at the top level of the package stays in `tests/roadmap/`. The invariant tests in `tests/invariants/test_source_tree.py` hold the layout.

The jobs themselves are in [the roadmap workflow](../ROADMAP_WORKFLOW.md).
