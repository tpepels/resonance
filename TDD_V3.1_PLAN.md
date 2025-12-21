# V3.1 PLAN — Real-World Corpus Regression Harness (Canonical)

*(Merged; includes File B code in appendices)*

## 1. Purpose

V3 established correctness on a curated golden corpus.
**V3.1 adds a real-world corpus regression harness** that turns an existing music library (or curated subset) into a **repeatable, deterministic, snapshot-driven test**, using the same artifact model as golden.

This document is the **single execution guide** for reaching the V3.1 Definition of Done.

---

## 2. Non-Goals (Explicit)

V3.1 does **not**:

* add new providers, tagging formats, layouts, or scoring logic
* change core pipeline behavior (resolver/planner/applier)
* add new persistent schemas or migrations beyond what already exists
* require CI to have access to a real music library

---

## 3. Hard Constraints (Inviolable)

1. **Never mutate a live library path.** Tests must run against a copy under `tests/real_corpus/input/`.
2. **Regen is explicit and gated.** Snapshots only written when `REGEN_REAL_CORPUS=1`.
3. **Determinism on rerun is enforced.** Second pass is no-op (no provider calls, no prompts, no churn).
4. **Fixed clock for provenance timestamps.** Inject stable `now`.

---

## 4. Locked Decisions

### D1 — Two-lane corpus strategy

* Fast lane via `MANIFEST.txt` (10–50 albums).
* Full lane manual (e.g., ~177GB) supported but not used day-to-day.

### D2 — Snapshot artifacts

* `expected_state.json`
* `expected_layout.json`
* `expected_tags.json`

Stable JSON: sorted keys, stable ordering, newline at EOF.

### D3 — Resolution is non-interactive

Primary: `decisions.json` mapping `dir_id -> mb:<id> | dg:<id> | JAIL`.
Optional fallback: CERTAIN→autopin; PROBABLE→top; UNSURE→jail.

### D4 — Offline-first

Real-corpus tests run offline by default; provider data served from cache; cache misses must be deterministic (explicit fail or queue/jail).

### D5 — CI posture

Real-corpus test is opt-in: skipped unless `RUN_REAL_CORPUS=1`.

---

## 5. Repository Layout

```
tests/
  integration/
    _corpus_harness.py
    test_golden_corpus.py
    test_real_world_corpus.py
  real_corpus/
    README.md
    MANIFEST.txt
    decisions.json
    input/                       # gitignored
    expected_state.json
    expected_layout.json
    expected_tags.json
scripts/
  snapshot_real_corpus.sh
regen_real_corpus.py
```

`.gitignore` must ignore `tests/real_corpus/input/**`.

---

## 6. Execution Plan

### Phase 1 — Extract snapshot mechanics (minimal churn)

* Create `tests/integration/_corpus_harness.py` per **Appendix A**.
* Modify `test_golden_corpus.py` per **Appendix B**.
* Acceptance: golden tests green, no behavior change.

### Phase 2 — Real corpus scaffolding + safety rails

* Add `tests/real_corpus/README.md`, `MANIFEST.txt`, `decisions.json`.
* Add `.gitignore` entry.

### Phase 3 — Snapshot script

* Implement `scripts/snapshot_real_corpus.sh` (safe rsync; manifest support; idempotent).

### Phase 4 — Real corpus test

* Add `tests/integration/test_real_world_corpus.py` per **Appendix C** and the workflow constraints above.
* Assertions: idempotent apply, no rematch on rerun, stable snapshots.

### Phase 5 — Regen script

* Add `regen_real_corpus.py` mirroring `regen_golden.py`.

---

## 7. Definition of Done (V3.1)

1. Snapshotting into `tests/real_corpus/input/` is safe and repeatable.
2. `pytest tests/integration/test_real_world_corpus.py`:

   * offline by default
   * deterministic
   * asserts rerun is a no-op
3. Snapshots written only under `REGEN_REAL_CORPUS=1`.
4. CI skips unless `RUN_REAL_CORPUS=1`.
5. Documentation exists and is sufficient.

---

# Appendix A — `_corpus_harness.py` (Minimal-Churn Reference)

**Create** `tests/integration/_corpus_harness.py`:

```python
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# NOTE: Keep tag filtering policy aligned with golden.
PROV_KEYS = (
    "resonance.prov.version",
    "resonance.prov.tool",
    "resonance.prov.tool_version",
    "resonance.prov.dir_id",
    "resonance.prov.pinned_provider",
    "resonance.prov.pinned_release_id",
    "resonance.prov.applied_at_utc",
)

def is_regen_enabled(env_var: str) -> bool:
    return os.environ.get(env_var) == "1"


def snapshot_path(expected_root: Path, scenario: str, name: str) -> Path:
    return expected_root / scenario / name


def assert_or_write_snapshot(
    *,
    path: Path,
    payload: Any,
    regen: bool,
    regen_env_var: str,
) -> None:
    if regen:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        return

    if not path.exists():
        raise FileNotFoundError(
            f"Missing snapshot: {path}. Set {regen_env_var}=1 to create."
        )

    expected = json.loads(path.read_text())
    assert payload == expected


def filter_relevant_tags(tags: dict[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {k: tags[k] for k in PROV_KEYS if k in tags}
    for key in ("album", "albumartist", "title", "tracknumber"):
        if key in tags:
            filtered[key] = tags[key]
    return filtered


def assert_valid_plan_hash(tags: dict[str, str]) -> None:
    plan_hash = tags.get("resonance.prov.plan_hash")
    assert plan_hash is not None
    assert re.fullmatch(r"[0-9a-f]{64}", plan_hash)
```

---

# Appendix B — Mechanical Patch Plan for `test_golden_corpus.py`

**Goal:** import harness helpers; remove local snapshot/tag helpers; keep workflow logic unchanged.

1. Add imports:

```python
from tests.integration._corpus_harness import (
    assert_or_write_snapshot,
    snapshot_path,
    is_regen_enabled,
    filter_relevant_tags,
    assert_valid_plan_hash,
)
```

2. Replace regen logic:

**From**

```python
regen = os.environ.get("REGEN_GOLDEN") == "1"
```

**To**

```python
REGEN_ENV = "REGEN_GOLDEN"
regen = is_regen_enabled(REGEN_ENV)
```

3. Replace snapshot calls:

**From**

```python
_assert_or_write_snapshot(
    _snapshot_path(scenario, "expected_layout.json"),
    actual_layout,
    regen,
)
```

**To**

```python
assert_or_write_snapshot(
    path=snapshot_path(EXPECTED_ROOT, scenario, "expected_layout.json"),
    payload=actual_layout,
    regen=regen,
    regen_env_var=REGEN_ENV,
)
```

Repeat for:

* `expected_tags.json`
* `expected_state.json`

4. Replace tag helpers usage:

* `_filter_tags(...)` → `filter_relevant_tags(...)`
* `_assert_plan_hash(...)` → `assert_valid_plan_hash(...)`

**Do NOT extract**:

* evidence building
* fixture providers
* workflow sequencing (scanner/resolver/planner/applier)

---

# Appendix C — `test_real_world_corpus.py` Skeleton

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.integration._corpus_harness import (
    assert_or_write_snapshot,
    snapshot_path,
    is_regen_enabled,
    filter_relevant_tags,
    assert_valid_plan_hash,
)

REAL_ROOT = Path(__file__).resolve().parents[1] / "real_corpus"
INPUT_ROOT = REAL_ROOT / "input"
EXPECTED_ROOT = REAL_ROOT
REGEN_ENV = "REGEN_REAL_CORPUS"

@pytest.mark.skipif(not INPUT_ROOT.exists(), reason="Real-world corpus not present")
@pytest.mark.skipif(os.environ.get("RUN_REAL_CORPUS") != "1", reason="Opt-in: RUN_REAL_CORPUS=1")
def test_real_world_corpus(tmp_path: Path):
    regen = is_regen_enabled(REGEN_ENV)

    # 1) Use copied snapshot only (INPUT_ROOT), optionally copy into tmp_path workspace.
    # 2) Run same primitives as golden:
    #    - LibraryScanner
    #    - resolve_directory (offline-first provider client)
    #    - plan_directory
    #    - build_tag_patch with fixed clock
    #    - apply_plan
    #
    # 3) Produce:
    #    - actual_layout
    #    - actual_tags (filtered)
    #    - actual_state
    #
    # 4) Snapshot/compare:
    assert_or_write_snapshot(
        path=snapshot_path(EXPECTED_ROOT, "root", "expected_layout.json"),
        payload=actual_layout,
        regen=regen,
        regen_env_var=REGEN_ENV,
    )
    assert_or_write_snapshot(
        path=snapshot_path(EXPECTED_ROOT, "root", "expected_tags.json"),
        payload=actual_tags,
        regen=regen,
        regen_env_var=REGEN_ENV,
    )
    assert_or_write_snapshot(
        path=snapshot_path(EXPECTED_ROOT, "root", "expected_state.json"),
        payload=actual_state,
        regen=regen,
        regen_env_var=REGEN_ENV,
    )
```

---

# Appendix D — Prep List and Guardrails

## Prep List (do before deep implementation)

1. Create `tests/real_corpus/MANIFEST.txt` (10–50 albums).
2. Implement `scripts/snapshot_real_corpus.sh`.
3. Create `tests/real_corpus/decisions.json`.
4. One-time online run to populate cache; confirm offline rerun works.
5. Write `tests/real_corpus/README.md`.

## Explicit “Do Not Extract”

To prevent churn, do not refactor these out of golden:

* `_evidence_from_files`
* fixture providers
* workflow ordering / orchestration