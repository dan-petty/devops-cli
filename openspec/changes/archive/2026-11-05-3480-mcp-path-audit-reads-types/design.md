# Design

## Decisions

- **The audit tests `isinstance(param.type, (TyperPath, TyperFile))` for a tool of the exposure table.**: Typer builds the Click type from the annotation, so the audit asks the library and walks no annotation. A `Path` annotation gives `typer.models.TyperPath`. A `FileText` or `FileBinaryRead` annotation gives `typer._click.types.File`, which Typer opens from a path. Neither class is a subclass of `click.Path`. Typer is pinned, so a change of a class fails the test at import.
- **The audit reads `format: path` for a tool that no command backs.**: Pydantic writes it for a `Path` annotation of a hand-written function. The check is four lines and closes the gap for a new hand-written tool with a path under another name.
- **A text option that holds a path is named in the test table `_TEXT_PATH_OPTIONS`.**: A type check cannot find a string. The table is the named decision of the issue for `scan_sast.config`. The audit then requires a decision in `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH`, and a test fails when the table names an unpublished option.
- **Each decision is made by reading the command.**:

  | Option | Decision | Reason |
  | :--- | :--- | :--- |
  | `ai_harness_offload.repo` | confine | The command scans the files of the directory. |
  | `ai_read.repo` | confine | The directory bounds `target_path`, which is confined. A free root would move that bound. |
  | `docker_sandbox.workspace`, `sandbox_deploy.workspace` | confine, and keep `validate_sandbox_workspace` | The check refuses the root, system directories, the home directory, sensitive parts and socket directories. It allows any other directory outside the work tree, so a model could mount a project that it does not serve. Confinement stops that. The check still refuses `.ssh`, `.aws`, `.kube` and `.git` inside the tree. |
  | `k8s_diff_helm.values` | confine | The command reads each YAML file. `chart_path` is confined, and `confine_tool_paths` already resolves each item of a list. |
  | `roadmap_refine.source` | confine | The command reads the checkout. |
  | `scan_injection.suppress` | confine | The command reads a policy file. A policy file in the tree names its parents with `extends`, and a person writes it. |
  | `review_export_feedback.output` | drop from the schema | The command appends to the file. A confined path would still let a model append to a source file of the tree (the reason of #3300). The command writes the configured dataset. |
  | `scan_sast.config` | confine, except a registry id | See the next decision. |

- **`scan_sast.config` keeps a registry id and confines any other value.**: A registry id is a name that the scan reads from the cache, so it needs no confinement. The default `p/default` is one, so a confinement of every value breaks the default call. Any other value is a path for Semgrep, or a URL, or `auto`, which make Semgrep reach the network. After confinement a URL becomes a path that does not exist, and Semgrep fetches nothing. The table `NOT_A_PATH_VALUE` holds the test (`is_registry_id`). It lives beside `PATH_CONFINEMENTS`, because the two tables decide one parameter.
- **`is_registry_id` is imported in a function, not at the top of the module.**: `semgrep_registry` imports the HTTP client and the YAML loader. The module of the tables is imported at server start, and only a `scan_sast` call needs the test.
- **`_check_path_confinement` runs first in `_create_tool_function`.**: The sandbox check then reads the resolved value, the same one that the command gets. A workspace that is relative to a nested directory resolves against the work tree in both. A value outside the tree is refused with the error that names the option, like every other confined option.
- **`_PATH_PARAM_KEYWORDS` does not change.**: `validate_path_parameter` reads the list at run time for every agent tool (`src/devops_cli/ai/agents/context.py`). A word such as `repo`, `source` or `config` would start to refuse `..` in other parameters, and `repo` holds `owner/name` in many tools. Two tests pin the present words and show that the names of this change stay out.
- **The change touches no read-only flag.**: `review_export_feedback` stays read-only until #3642 decides what the class `no-external-request` means for the flag.

## Out of scope

- **Hand-written string options that hold a path under another name.**: No type shows them. A new one needs the same named decision as `scan_sast.config`.
- **The flag of the tools that write local state.**: Issue #3642 owns it.
- **The free-text parameters that can carry a secret.**: Issue #3230 plans a table for them, with an entry for `k8s_diff_helm.values`. That table decides a different risk (a secret in a value). This change decides the path.

## Rejected alternatives

- **Add `repo`, `workspace`, `values`, `source` and `suppress` to `_PATH_PARAM_KEYWORDS`.**: The list is the run-time check of the agent tools, and the issue asks for no widening without a check of `validate_path_parameter`. `repo` names `owner/name` in other tools.
- **Walk the annotations with `typing.get_type_hints`.**: It finds the same 59 options as the Click type (see Feasibility), and needs a walker over `Annotated`, unions and containers. The Click type is one library call.
- **Make the generator publish `Path` for a path option.**: Pydantic would then pass a `Path` object to the tool function. `_validate_arg_hyphen` checks strings only, so a value that starts with a hyphen would skip the flag-injection guard.
- **Drop `scan_sast.config` from the schema.**: The requirement "The MCP Semgrep tool uses the default ruleset unless the caller names one" says that a caller names a ruleset, and a registry id is safe. Dropping the option removes the use and fixes nothing that confinement does not fix.
- **Exempt `scan_sast.config` in `NOT_A_FILE_PATH`.**: The reason would be false. The option takes a local path, and a URL that Semgrep fetches.
- **Keep the sandbox check as the only guard of `workspace`.**: It allows a directory outside the work tree (see the table).
- **Confine `review_export_feedback.output` instead of dropping it.**: A model could then append JSONL lines to any file of the tree.
