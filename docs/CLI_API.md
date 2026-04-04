# CLI API Reference

All commands emit deterministic output. Use `--json` for machine-readable envelopes.

## Global options

| Flag | Description |
|------|-------------|
| `--version` | Print version and exit |
| `--json` | Emit JSON envelope instead of human-readable text |

---

## Workflow commands

### `scan`

Discover audio directories and populate the state DB.

```
resonance scan <library_root> --state-db <path> [--json]
```

Supports `--mode interactive|automation|admin`.

| Argument | Required | Description |
|----------|----------|-------------|
| `library_root` | yes | Root directory to scan |
| `--state-db` | yes | Path to SQLite state database |

### `resolve`

Match scanned directories to provider releases using fingerprints and metadata.

```
resonance resolve <library_root> --state-db <path> [--cache-db <path>] [--offline] [--json]
```

Supports `--mode interactive|automation|admin`.

| Argument | Required | Description |
|----------|----------|-------------|
| `library_root` | yes | Library root directory |
| `--state-db` | yes | State database path |
| `--cache-db` | no | Provider cache DB for offline/repeat runs |
| `--offline` | no | Use cached data only, no network |

### `prompt`

Interactively resolve directories that couldn't be auto-matched.

```
resonance prompt --state-db <path> [--cache-db <path>] [--decisions-file <path>] [--json]
```

Supports `--mode interactive|automation|admin`.
In `automation` and `admin` mode, provide `--decisions-file` or `--replay-file`.

| Argument | Required | Description |
|----------|----------|-------------|
| `--state-db` | yes | State database path |
| `--cache-db` | no | Provider cache DB |
| `--decisions-file` | no | Scripted decisions for non-interactive mode |
| `--record-replay` | no | Record decisions to replay file |
| `--replay-file` | no | Replay recorded decisions |

### `plan`

Generate a deterministic plan artifact for a resolved directory.

```
resonance plan --dir-id <id> --state-db <path> [--cache-db <path>] [--library-root <path>] [--json]
```

Supports `--plan-dir <path>` and `--mode interactive|automation|admin`.

| Argument | Required | Description |
|----------|----------|-------------|
| `--dir-id` | yes | Directory identifier to plan |
| `--state-db` | yes | State database path |
| `--cache-db` | no | Provider cache DB (required if release not cached) |
| `--library-root` | no | Library root for provider bootstrap |

### `apply`

Execute a stored plan artifact (file moves + tag writes).

```
resonance apply --plan <path> --state-db <path> --library-root <path> [--tag-patch <path>] [--no-dry-run] [--config <path>] [--tag-writer-backend meta-json|mutagen] [--json]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--plan` | yes | Path to plan JSON artifact |
| `--state-db` | yes | State database path |
| `--library-root` | yes | Library root for path validation |
| `--tag-patch` | no | Tag patch artifact for metadata writes |
| `--no-dry-run` | no | Execute for real (default: dry-run) |
| `--config` | no | Settings JSON path |
| `--tag-writer-backend` | no | Override: `meta-json` or `mutagen` |

### `decide`

Single-command orchestration: scan → resolve → prompt → plan.

```
resonance decide <library_root> --state-db <path> [--cache-db <path>] [--offline] [--decisions-file <path>] [--json]
```

Supports `--auto-probable`, `--auto-probable-min-gap`, `--headless`, `--plan-dir`, `--fail-on-prompt`, and `--mode interactive|automation|admin`.

In `automation` and `admin` mode, decide runs headless by policy.

| Argument | Required | Description |
|----------|----------|-------------|
| `library_root` | yes | Library root directory |
| `--state-db` | yes | State database path |
| `--cache-db` | no | Provider cache DB |
| `--offline` | no | Use cached data only |
| `--decisions-file` | no | Scripted decisions for non-interactive prompt |

### `app`

Unified interactive entrypoint with access to all major capabilities.

```
resonance app <library_root> --state-db <path> [--cache-db <path>] [--offline] [--plan-dir <path>] [--json]
```

`app` is the default human workflow surface; expert automation flows should use command-specific CLI invocations with `--mode automation|admin`.

---

## Diagnostic commands

### `identify`

Score provider candidates for a single directory.

```
resonance identify <directory> [--cache-db <path>] [--json]
```

### `audit`

Inspect a directory's state record and artifacts.

```
resonance audit <dir_id> --state-db <path> [--json]
```

### `doctor`

Validate store invariants and environment sanity.

```
resonance doctor --state-db <path> [--config <path>] [--json]
```

### `rollback`

Revert an applied plan using the apply report.

```
resonance rollback --report <path> --state-db <path> --library-root <path> [--json]
```

### `unjail`

Reset a jailed directory back to NEW state.

```
resonance unjail <dir_id> --state-db <path> [--json]
```

---

## JSON envelope format

All `--json` output uses this envelope:

```json
{
  "schema_version": "v1",
  "command": "<command-name>",
  "data": { ... }
}
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime failure |
| 2 | Validation error (bad input) |
| 3 | I/O failure (filesystem) |
