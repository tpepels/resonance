## Dependencies
- **Language-agnostic:** rules apply to all languages; examples are illustrative.
- **Use requires declaration:** any new third-party dependency MUST be added to the relevant **Dependency Manifest** (e.g., `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `.csproj`) in the same change, plus lockfile updates where applicable.
- **Forbidden:** vendoring/replacing libraries, “mini packages”, skipping/xfailing tests, or weakening assertions to avoid installing dependencies.
- **Required gate:** clean-environment install from manifest/lockfile + default test tier.

## Legacy
- If the active version plan requires deletion/retirement, it is binding; “still compliant” is not a reason to keep legacy code.
- End state must be: **delete** OR **quarantine** under an explicit legacy boundary + “unreachable” tests OR **explicit version gate** + audit note.
- If uncertain: remove wiring first → prove unreachable/replaced → then delete.

