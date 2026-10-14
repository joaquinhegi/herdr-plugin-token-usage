# Sidebar Metadata Specification

## Purpose
Formatting, publish/clear and approval-gated config patch.

## Requirements

### Requirement: Formatting (RF05)
The `tokens` value MUST be: <1000 → `N tokens`; <1,000,000 → `X.Yk tokens`; else `X.YM tokens`; one decimal, at most 80 chars. Internal values stay unrounded integers.

#### Scenario: Examples
- GIVEN 950, 1250, 125400, 1200000
- WHEN formatted
- THEN `950 tokens`, `1.3k tokens`, `125.4k tokens`, `1.2M tokens`

### Requirement: Publish and clear (RF04, C11)
The plugin MUST publish `tokens` under a fixed local source only when the value changes, with a ~60 s TTL refreshed while the pane is alive, with reads (`pane list`) via the socket API with CLI fallback and metadata writes via the CLI (`herdr pane report-metadata`) until socket `report_metadata` is verified (see design.md Open Questions). It MUST clear it on pane close, session change or loss of reliable mapping, never touching other panes or sources. It MUST NOT publish `0` for unknown.

#### Scenario: Unchanged value
- GIVEN the last published value equals the current one
- WHEN polled within the TTL
- THEN no redundant publish occurs beyond TTL refresh

#### Scenario: Pane closed
- GIVEN panes A and B
- WHEN A closes
- THEN A's state is dropped and B is unaffected

#### Scenario: Herdr unreachable
- GIVEN the socket fails
- WHEN publishing
- THEN the CLI fallback is tried and failure is logged without crashing

### Requirement: Approval-gated config patch (RF04, C14)
The plugin MUST NOT auto-edit `~/.config/herdr/config.toml`. It MUST provide a minimal reversible patch with backup and diff, adding `$tokens` to `rows` and any `rows_by_agent` overrides without duplicating tables or dropping custom rows.

#### Scenario: Custom sidebar
- GIVEN a config with custom rows and `rows_by_agent.claude`
- WHEN the patch is generated
- THEN the diff only adds `$tokens`, and nothing is written before approval
