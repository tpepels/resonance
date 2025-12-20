# Lint Report

Command:

```sh
python -m ruff check resonance --fix
python -m ruff check resonance
```

Summary:
- Rule set: `F` (unused imports/variables and related).
- Scope: `resonance/` only (tests excluded; `resonance/legacy/` excluded).

Notes:
- Ruff reported 29 F-rule findings and auto-fixed them.
- A follow-up `ruff check` is clean.
