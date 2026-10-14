# Delta for Sidebar Metadata

POSIX behavior unchanged when no override variables are set. Baseline: agent-token-usage-mvp `sidebar-metadata`.

## MODIFIED Requirements

### Requirement: Approval-gated config patch (RF04, C14)
The plugin MUST NOT auto-edit the Herdr config file. It MUST provide a minimal reversible patch with backup and diff, adding `$tokens` to `rows` and to the Claude override (`rows_by_agent.claude`) only (Claude-only MVP; other agents' overrides are left untouched), without duplicating tables or dropping custom rows. The target config path MUST resolve in this order: `HERDR_CONFIG_PATH`; `XDG_CONFIG_HOME/herdr/config.toml`; on Windows `%APPDATA%\herdr\config.toml`; else `~/.config/herdr/config.toml`.
(Previously: path fixed to `~/.config/herdr/config.toml`.)

#### Scenario: Custom sidebar
- GIVEN a config with custom rows and `rows_by_agent.claude`
- WHEN the patch is generated
- THEN the diff only adds `$tokens`, and nothing is written before approval

#### Scenario: Explicit override
- GIVEN `HERDR_CONFIG_PATH` and `XDG_CONFIG_HOME` are set
- WHEN the path resolves
- THEN `HERDR_CONFIG_PATH` is used

#### Scenario: XDG
- GIVEN only `XDG_CONFIG_HOME` is set
- WHEN the path resolves
- THEN `XDG_CONFIG_HOME/herdr/config.toml` is used

#### Scenario: Windows default
- GIVEN Windows, `APPDATA` set, no override variables
- WHEN the path resolves
- THEN `%APPDATA%\herdr\config.toml` is used

#### Scenario: POSIX default
- GIVEN Linux/macOS, no override variables
- WHEN the path resolves
- THEN `~/.config/herdr/config.toml` is used
