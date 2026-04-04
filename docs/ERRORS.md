# Error Taxonomy

Resonance uses a deterministic error hierarchy mapped to CLI exit codes.

## Exit codes

| Code | Error class | Meaning |
|------|-------------|---------|
| 0 | — | Success |
| 1 | `RuntimeFailure` | Unexpected runtime error |
| 2 | `ValidationError` | Invalid user input or command misuse |
| 3 | `IOFailure` | Filesystem or I/O failure |

## Error hierarchy

```
BaseException
└── Exception
    └── ResonanceError (exit_code=1)
        ├── ValidationError (exit_code=2)
        ├── RuntimeFailure (exit_code=1)
        └── IOFailure (exit_code=3)
```

## When each error fires

### ValidationError (exit 2)

Raised when user input is invalid or a precondition fails.

| Situation | Message pattern |
|-----------|----------------|
| Missing required argument | `"apply requires --plan"` |
| Directory not found in store | `"Directory {dir_id} not found in store"` |
| Directory not in expected state | `"directory is not pinned"` |
| Missing provider credentials | `"provider_client is required"` |
| Store not injected | `"store is required"` |
| Unsupported backend | `"Unsupported tag writer backend: {name}"` |

### IOFailure (exit 3)

Raised for filesystem errors.

| Situation | Message pattern |
|-----------|----------------|
| Library root missing | `"Library root does not exist: {path}"` |
| Plan file unreadable | Wrapped `OSError` |

### RuntimeFailure (exit 1)

Raised for unexpected internal errors and provider integration issues.

| Situation | Message pattern |
|-----------|----------------|
| Offline mode + cache miss | `"Provider {name} requires network"` |
| Plan generation failure | `"plan generation failed: {detail}"` |

## JSON error output

With `--json`, errors are embedded in the standard envelope:

```json
{
  "schema_version": "v1",
  "command": "apply",
  "data": {
    "status": "PLAN_LOAD_ERROR",
    "error": "..."
  }
}
```

## Apply-specific statuses

The `apply` command reports these in the `status` field:

| Status | Meaning |
|--------|---------|
| `APPLIED` | Plan executed successfully |
| `NOOP_ALREADY_APPLIED` | Files already in destination (idempotent) |
| `PARTIAL_COMPLETE` | Inconsistent file state detected |
| `FAILED` | Errors during execution (rollback attempted) |
