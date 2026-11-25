## Problem

`devops config init` prints `CONST_CONFIG_PATH` as the file it writes, but it writes the active config path. When the active path is another file, for example through `DEVOPS_CLI_CONFIG`, the message names the wrong file. The #1921 work found this.

## Proposed fix

Print the path that `save_settings` writes.

## Acceptance criteria

- [ ] A test runs `devops config init` with another active config path and checks that the output names that path.
