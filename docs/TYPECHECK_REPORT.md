# Typecheck Report

Command:

```sh
python -m mypy resonance
```

Summary:
- mypy is configured to ignore missing imports and skip `tests/` and `resonance/legacy/`.
- mypy does not currently support unused-import/unused-def checks; see notes in `mypy.ini`.
- Legacy/dynamic modules are suppressed with per-module `ignore_errors` to keep output deterministic.

## A) likely-unused (safe candidates)

- None reported by mypy (unused import/def detection not supported by mypy).

## B) likely-legacy-only references

- Suppressed via mypy config:
  - `resonance.app`
  - `resonance.visitors.*`
  - `resonance.providers.musicbrainz`
  - `resonance.providers.discogs`
  - `resonance.services.metadata_reader`
  - `resonance.infrastructure.transaction`

## C) likely-false-positives / dynamic entrypoints

- Suppressed via mypy config:
  - `resonance.services.tag_writer`
  - `resonance.commands.apply`
