# TODO_REVIEW_V3 — Technical Debt & Architectural Compliance

Generated: 2025-12-21

## Executive Summary

**Overall architectural health:** The core V3 pipeline (scan → identify → resolve → plan → apply) has strong separation between pure phases and side effects. The fundamental invariants (determinism, dir_id-keyed state, no re-matches) are enforced at the right boundaries. The golden corpus provides excellent regression protection for correctness.

However, **two parallel architectures coexist**: the V2 visitor pipeline (`AlbumInfo` + `BaseVisitor`) and the V3 pure pipeline (`resolve_directory`, `plan_directory`, `apply_plan`). This creates:
1. **Architectural drift risk** — V2 visitors bypass V3 state management
2. **Business logic in wrong layers** — Visitors contain identification/organization logic that duplicates planner/applier
3. **Implicit service construction** — Multiple locations construct `DirectoryStateStore`, violating single composition root
4. **Incomplete invariant enforcement** — Path changes can bypass signature validation in visitors

The V3 core is sound. The V2 legacy must be either fully deprecated or harmonized before V3 is complete.

**High-risk areas:**
- Visitor pipeline bypasses `DirectoryStateStore` and `resolve_directory` invariants
- Service construction scattered across commands (no single composition root)
- `AlbumInfo.destination_path` duplicates `plan_directory` layout logic
- Mutable `AlbumInfo` and `TrackInfo` violate purity boundaries
- `sanitize_filename` duplicated between `FileService` and `planner`

**Status note (2025-12-21):**
The critical C-items below remain open because the V2 visitor pipeline is still present,
composition root is not unified, and planner purity/layout logic are still split between
V2 and V3 paths. These are architectural cleanups, not functional regressions, so they
are tracked as V3 closeout work.

---

## Critical Issues (Must fix before V3 is complete)

### C-1: Dual architecture creates determinism bypass

- **Location:**
  - [resonance/visitors/](resonance/visitors/) (entire directory)
  - [resonance/app.py:101-142](resonance/app.py#L101-L142)
  - [resonance/commands/scan.py:94-117](resonance/commands/scan.py#L94-L117)

- **Violation:**
  The V2 visitor pipeline (`IdentifyVisitor`, `OrganizeVisitor`, etc.) operates on mutable `AlbumInfo` objects and does **not** flow through `resolve_directory`, `plan_directory`, or `apply_plan`. This bypasses:
  - `DirectoryStateStore` state transitions
  - Signature-based re-identification prevention
  - Plan serialization and audit trails
  - Deterministic conflict policies

  Example: `IdentifyVisitor.visit()` directly mutates `album.canonical_artist` and checks `cache.get_directory_release()` instead of using `DirectoryStateStore.get()`. Path changes won't reset state because visitors don't use `get_or_create()`.

- **Risk:**
  - Visitors can trigger re-matches on every run (violates "no re-matches unless signature changes")
  - No audit trail for visitor-based operations
  - Golden corpus only validates V3 pipeline; visitor path is untested for determinism
  - Two code paths for the same logical operation → drift over time

- **Done looks like:**
  - [ ] Decision: Either deprecate visitor pipeline entirely OR harmonize it with V3 state machine
  - [ ] If deprecated: Remove `resonance/visitors/`, `resonance/commands/scan.py`, `AlbumInfo` model
  - [ ] If harmonized: Refactor visitors to call `resolve_directory` → `plan_directory` → `apply_plan` instead of mutating `AlbumInfo`
  - [ ] All CLI commands use V3 pipeline exclusively
  - [ ] Golden corpus covers all entry points

---

### C-2: No single composition root — DirectoryStateStore constructed ad-hoc

- **Location:**
  - [resonance/commands/plan.py:41](resonance/commands/plan.py#L41)
  - [resonance/commands/apply.py:87](resonance/commands/apply.py#L87)
  - [tests/integration/test_applier.py:80](tests/integration/test_applier.py#L80) (and 80+ other test locations)

- **Violation:**
  `DirectoryStateStore` is constructed inline in commands and tests, violating the stated design principle: "All real services should be constructed at a single composition root (CLI / daemon bootstrap)."

  `ResonanceApp` does not expose or construct a `DirectoryStateStore`. Each command (`plan`, `apply`) creates its own instance from `args.state_db`. This means:
  - No shared configuration (e.g., `now_fn` for deterministic timestamps)
  - Testing requires manual store construction in every test
  - Cannot inject store for dry-run simulation or transactional testing

- **Risk:**
  - Future features (daemon mode, multi-process) cannot share state safely
  - Tests cannot reliably mock/inject stores
  - Harder to enforce lifecycle (e.g., schema migrations, connection pooling)

- **Done looks like:**
  - [ ] Add `DirectoryStateStore` to `ResonanceApp.__init__()` and expose it as `app.store`
  - [ ] Commands accept `--state-db` but delegate construction to `ResonanceApp.from_env()`
  - [ ] Tests use fixture like `@pytest.fixture def app_with_store(tmp_path) -> ResonanceApp`
  - [ ] Grep for `DirectoryStateStore(` outside `resonance/app.py` returns zero results in `resonance/` (tests OK)

---

### C-3: Planner not pure — depends on DirectoryStateStore

- **Location:** [resonance/core/planner.py:198-297](resonance/core/planner.py#L198-L297)

- **Violation:**
  `plan_directory()` is declared pure but takes `DirectoryStateStore` as a dependency and queries it:
  ```python
  def plan_directory(
      dir_id: str,
      store: DirectoryStateStore,  # ← I/O dependency
      pinned_release: ProviderRelease,
      ...
  ) -> Plan:
      record = store.get(dir_id)  # ← I/O call in "pure" function
      if not record:
          raise ValueError(...)
  ```

  The stated architecture says "Planner is **pure**." But `plan_directory` performs I/O to validate state and read `last_seen_path` / `signature_hash`.

- **Risk:**
  - Cannot unit test planner without mocking or constructing a real store
  - Violates functional purity claims in architecture docs
  - Future parallelization or plan pre-generation blocked by I/O coupling

- **Done looks like:**
  - [ ] Refactor `plan_directory` to accept `DirectoryRecord` (not `DirectoryStateStore`)
  - [ ] Caller (command/resolver) fetches record from store first
  - [ ] Planner signature: `plan_directory(record: DirectoryRecord, pinned_release: ProviderRelease, ...) -> Plan`
  - [ ] Planner unit tests no longer need `tmp_path` or store construction

---

### C-4: AlbumInfo.destination_path duplicates planner layout logic

- **Location:**
  - [resonance/core/models.py:147-208](resonance/core/models.py#L147-L208) (`AlbumInfo.destination_path`)
  - [resonance/core/planner.py:168-196](resonance/core/planner.py#L168-L196) (`_compute_destination_path`)

- **Violation:**
  The same layout logic (classical detection, compilation detection, path construction) exists in **two places**:
  1. `AlbumInfo.destination_path` (V2 visitor pipeline)
  2. `_compute_destination_path()` in planner (V3 pipeline)

  Both apply rules like:
  - Classical with single composer → `Composer/Album/Performer`
  - Compilation → `Various Artists/Album`
  - Regular → `Artist/Album`

  But the implementations differ:
  - Planner uses `_compilation_reason()`, `_is_classical()`, `canonicalize_display`
  - `AlbumInfo.destination_path` uses `is_classical` property and inline logic

  This violates DRY and creates drift risk. Year formatting (`{year:04d}`) is only in planner, not in `AlbumInfo`.

- **Risk:**
  - Changes to layout rules must be duplicated in two places
  - Visitor-based paths may diverge from planner-based paths
  - Golden corpus only validates planner; visitor paths untested

- **Done looks like:**
  - [ ] If V2 visitors are kept: Refactor `AlbumInfo.destination_path` to call planner's `_compute_destination_path()`
  - [ ] If V2 visitors deprecated: Delete `AlbumInfo.destination_path` entirely
  - [ ] Extract single source of truth for layout rules into `planner` module
  - [ ] Visitor-based tests either deleted or migrated to V3 pipeline

---

### C-5: Mutable models violate purity boundary

- **Location:**
  - [resonance/core/models.py:20-262](resonance/core/models.py#L20-L262) (`TrackInfo`, `AlbumInfo`)
  - [resonance/visitors/identify.py:79-110](resonance/visitors/identify.py#L79-L110)
  - [resonance/visitors/organize.py:119-121](resonance/visitors/organize.py#L119-L121)

- **Violation:**
  `TrackInfo` and `AlbumInfo` are mutable dataclasses (`@dataclass(slots=True)` without `frozen=True`) that visitors mutate during processing:

  ```python
  # IdentifyVisitor mutates album
  album.tracks.append(track)
  album.canonical_artist = self._most_common(artists)
  album.is_uncertain = True

  # OrganizeVisitor mutates track paths
  track.path = new_path
  album.directory = destination_dir
  ```

  This violates the stated principle "Scanner, Identifier, Planner are **pure**." While identifier functions are pure, the visitor-based workflow mutates shared state.

- **Risk:**
  - Hard to reason about state changes across pipeline stages
  - Cannot parallelize visitor pipeline safely
  - Re-running a visitor has side effects (not idempotent)
  - Conflicts with V3's immutable `Plan` and `DirectoryRecord` design

- **Done looks like:**
  - [ ] If V2 visitors are kept: Make `TrackInfo`/`AlbumInfo` frozen, visitors return new instances
  - [ ] If V2 visitors deprecated: Delete these models entirely
  - [ ] Document explicitly: V3 uses immutable `Plan`/`DirectoryRecord`, V2 uses mutable `AlbumInfo`

---

### C-6: Visitor business logic duplicates core phases

- **Location:**
  - [resonance/visitors/identify.py:46-152](resonance/visitors/identify.py#L46-L152)
  - [resonance/visitors/organize.py:35-124](resonance/visitors/organize.py#L35-L124)

- **Violation:**
  `IdentifyVisitor` contains fingerprinting, canonicalization, and candidate selection logic that duplicates `extract_evidence()`, `identify()`, and `resolve_directory()`.

  `OrganizeVisitor` contains file-move logic that duplicates `apply_plan()`.

---

## V3 Closeout Checklist (Concrete Steps)

1) **Decide visitor fate (deprecate vs harmonize)**
   - Owner: TBD
   - Steps:
     - Choose policy: remove V2 visitor entrypoints or refactor them to call V3 pipeline.
     - If deprecating: remove `resonance/visitors/*` and `resonance/app.py` legacy path,
       update CLI to use V3-only commands.
     - If harmonizing: replace visitor mutations with calls to `resolve_directory`,
       `plan_directory`, and `apply_plan`; delete duplicated logic.

2) **Introduce a single composition root for services**
   - Owner: TBD
   - Steps:
     - Add `DirectoryStateStore` to `ResonanceApp` and expose as `app.store`.
     - Update CLI commands to obtain store from app, not instantiate directly.
     - Keep tests constructing stores, but add fixtures that mimic app wiring.

3) **Restore planner purity**
   - Owner: TBD
   - Steps:
     - Change `plan_directory` signature to accept `DirectoryRecord`.
     - Move `store.get()` calls to command/resolver layer.
     - Update unit tests accordingly (no tmp_path store required).

4) **Unify layout logic (single source of truth)**
   - Owner: TBD
   - Steps:
     - If V2 kept: route `AlbumInfo.destination_path` through planner logic.
     - If V2 removed: delete `AlbumInfo.destination_path`.
     - Add a single layout helper in planner module and re-use it everywhere.

5) **Address mutable V2 models**
   - Owner: TBD
   - Steps:
     - If V2 kept: make `AlbumInfo`/`TrackInfo` frozen and return new instances.
     - If V2 removed: delete models and visitor path.

  Per architecture: "No business logic in visitors." But visitors implement:
  - `IdentifyVisitor._determine_canonical_identities()` (canonicalization)
  - `OrganizeVisitor._move_files()` (transactional moves)
  - Cache reads/writes (`cache.get_directory_release()`, `cache.set_directory_release()`)

- **Risk:**
  - Changes to identification or layout logic must be duplicated
  - Golden corpus doesn't cover visitor paths
  - V2 and V3 pipelines can produce different results for identical inputs

- **Done looks like:**
  - [ ] Extract business logic from visitors into pure functions in `core/`
  - [ ] Visitors become thin adapters: call `resolve_directory()`, `plan_directory()`, `apply_plan()` and adapt results to `AlbumInfo`
  - [ ] OR: Deprecate visitor pipeline entirely

---

## High Priority Debt (Fix during V3 if possible)

### H-1: applier.py violates "only mutator" by reading cache

- **Location:** [resonance/core/applier.py:100-109](resonance/core/applier.py#L100-L109)

- **Issue:**
  `_collect_audio_files()` calls `LibraryScanner.DEFAULT_EXTENSIONS` and performs filesystem reads inside the applier. While the applier is the designated mutator, it should accept pre-computed inputs (not scan the filesystem).

  This makes applier non-deterministic if files appear/disappear between plan generation and apply.

- **Risk:**
  - Apply can fail if files removed after planning
  - Signature validation at apply time can mismatch plan signature
  - Re-scanning introduces non-determinism

- **Fix:**
  - [ ] Pass audio file list to `apply_plan()` instead of re-scanning
  - [ ] Validate that file list matches plan operations (no extras, no missing)
  - [ ] Or: Accept that applier must validate current filesystem state (document as intentional)

---

### H-2: sanitize_filename duplicated in FileService and planner

- **Location:**
  - [resonance/services/file_service.py:132-167](resonance/services/file_service.py#L132-L167)
  - [resonance/core/planner.py:80-123](resonance/core/planner.py#L80-L123)

- **Issue:**
  Two implementations of filename sanitization:
  1. `FileService.sanitize_filename()` — runtime sanitization
  2. `planner.sanitize_filename()` — plan-time sanitization

  Implementations differ:
  - Planner checks Windows reserved names (`CON`, `PRN`, etc.)
  - Planner limits to 200 chars
  - FileService limits to 200 chars
  - Planner replaces forbidden chars with space, FileService uses context-specific replacements

- **Risk:**
  - Plan says filename `"foo"` but applier writes `"_foo"` due to reserved name detection
  - Drift between plan and actual filesystem
  - Golden corpus may not catch discrepancies

- **Fix:**
  - [ ] Extract single `sanitize_filename()` into `resonance/core/validation.py`
  - [ ] Both planner and FileService use shared implementation
  - [ ] Add golden scenario: reserved filename (e.g., album named `"CON - The Album"`)

---

### H-3: IdentifyVisitor bypasses resolve_directory for cached decisions

- **Location:** [resonance/visitors/identify.py:63-76](resonance/visitors/identify.py#L63-L76)

- **Issue:**
  ```python
  cached = self.cache.get_directory_release(album.directory)
  if cached:
      provider, release_id, confidence = cached
      album.musicbrainz_release_id = release_id
  ```

  This reads `MetadataCache.get_directory_release()` instead of `DirectoryStateStore.get()`. The cache is indexed by **path**, not `dir_id`, so path changes bypass the "dir_id is identity" invariant.

- **Risk:**
  - Directory moved to new path → cache miss → re-identification triggered
  - Violates "Path changes do not trigger re-identification"
  - Not validated by golden corpus

- **Fix:**
  - [ ] If V2 visitors kept: Change cache key from `path` to `dir_id`
  - [ ] Or: Delete cache entirely, use `DirectoryStateStore` as single source of truth
  - [ ] Add golden scenario: directory renamed mid-pipeline (already exists: "Renamed folder mid-processing")

---

### H-4: Enricher not pure — depends on DirectoryState

- **Location:** [resonance/core/enricher.py:117-146](resonance/core/enricher.py#L117-L146)

- **Issue:**
  `build_tag_patch()` takes `resolution_state: DirectoryState` and rejects `RESOLVED_USER` unless explicitly allowed. This means enricher behavior depends on state machine status, not just inputs.

  Per architecture: "Enricher is pure." But it has conditional logic based on resolution state.

- **Risk:**
  - Cannot pre-generate tag patches without knowing resolution state
  - Callers must pass correct state or get silent no-op patch
  - Not obvious from function signature that state matters

- **Fix:**
  - [ ] Document explicitly: "Enricher is pure but state-conditional"
  - [ ] OR: Remove state checks, push to caller (apply rejects patches for wrong states)
  - [ ] Add test: tag patch for `RESOLVED_USER` with `allow_user_resolved=False` returns empty patch

---

### H-5: No validation that plan.source_path matches record.last_seen_path

- **Location:** [resonance/core/applier.py:345-356](resonance/core/applier.py#L345-L356)

- **Issue:**
  Applier validates signature hash but **not** that `plan.source_path == record.last_seen_path`. If a plan is serialized and deserialized, the source path could be stale.

- **Risk:**
  - Plan generated at `/old/path`, directory moved to `/new/path`, apply uses stale path
  - Signature check catches content changes but not path moves
  - Edge case: path move + re-scan + apply old plan

- **Fix:**
  - [ ] Add validation: `if plan.source_path != record.last_seen_path: error("stale plan")`
  - [ ] OR: Document that plans are ephemeral (must regenerate after path changes)
  - [ ] Add golden scenario: serialize plan, move directory, apply → should fail

---

### H-6: Visitors construct services inline

- **Location:**
  - [resonance/visitors/identify.py:79](resonance/visitors/identify.py#L79) (`MetadataReader.read_track()`)
  - [resonance/visitors/organize.py:113](resonance/visitors/organize.py#L113) (`FileService.move_track()`)

- **Issue:**
  Visitors call static service methods or accept pre-constructed services in `__init__`. This is implicit service location (not explicit DI).

  Example: `MetadataReader.read_track()` is a static method, not injected.

- **Risk:**
  - Hard to test visitors with mocked services
  - Static methods cannot be swapped for different backends
  - Violates "no implicit DI, no service locator"

- **Fix:**
  - [ ] Inject `MetadataReader` into `IdentifyVisitor.__init__()`
  - [ ] Convert `MetadataReader.read_track()` from static to instance method
  - [ ] Same for other service calls in visitors

---

## Medium / Low Priority Debt (Post-V3)

### M-1: VisitorPipeline.process() swallows exceptions in print

- **Location:** [resonance/core/visitor.py:84-91](resonance/core/visitor.py#L84-L91)

- **Issue:**
  ```python
  except Exception as e:
      print(f"Error in {visitor}: {e}")
      raise
  ```

  Using `print()` instead of logging. Also, error is printed **then** re-raised, so output appears twice (once from print, once from caller's logging).

- **Fix:**
  - [ ] Replace `print()` with `logger.error()`
  - [ ] Don't re-raise after logging (or remove logging and let caller handle)

---

### M-2: AlbumInfo._cached_destination_path bypass via direct assignment

- **Location:** [resonance/core/models.py:119-122](resonance/core/models.py#L119-L122)

- **Issue:**
  `_cached_destination_path` is a private cached field but can be directly assigned by external code (no enforcement). If mutated, `destination_path` property returns stale value.

- **Fix:**
  - [ ] Make `AlbumInfo` frozen if V2 visitors kept
  - [ ] Or delete entirely if V2 deprecated

---

### M-3: Planner uses lambda for default canonicalize_display

- **Location:** [resonance/core/planner.py:240](resonance/core/planner.py#L240)

- **Issue:**
  ```python
  if canonicalize_display is None:
      canonicalize_display = lambda value, _category: value
  ```

  Mutable default argument pattern (though safe here). Harder to test.

- **Fix:**
  - [ ] Define `_identity_canonicalize` at module level
  - [ ] Use as default: `canonicalize_display = canonicalize_display or _identity_canonicalize`

---

### M-4: DirectoryStateStore allows partial RESOLVED states

- **Location:** [resonance/infrastructure/directory_store.py:432-437](resonance/infrastructure/directory_store.py#L432-L437)

- **Issue:**
  Validation checks:
  ```python
  if state in (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER):
      if not pinned_provider or not pinned_release_id:
          raise ValueError(...)
  ```

  But line 445 sets `pinned_provider=pinned_provider if pinned_release_id else None`. This means you can pass `pinned_provider="mb"` with `pinned_release_id=None` and validation passes (then clears provider). Confusing.

- **Fix:**
  - [ ] Validate earlier: reject if any pin field is set without all required fields
  - [ ] Or: Make pinned fields a single frozen dataclass (`PinnedRelease`)

---

### M-5: No test coverage for DirectoryStateStore.record_plan_summary

- **Location:** [resonance/infrastructure/directory_store.py:167-184](resonance/infrastructure/directory_store.py#L167-L184)

- **Issue:**
  Audit artifacts table is written but never read in main code path. Only via `get_audit_artifacts()` which is not called in V3 pipeline.

- **Fix:**
  - [ ] Add integration test: plan → apply → read audit artifacts → verify
  - [ ] Or: Document as "future audit trail, not yet used"

---

### M-6: Applier rollback only rolls back file moves, not tag writes

- **Location:** [resonance/core/applier.py:591-621](resonance/core/applier.py#L591-L621)

- **Issue:**
  If tag write fails, applier rolls back **file moves** but not previous successful tag writes. This leaves partial state (some tracks tagged, some not, all files rolled back).

- **Risk:**
  - Re-running apply will overwrite already-written tags
  - No way to know which tracks were partially tagged

- **Fix:**
  - [ ] Track successful tag writes and roll them back on failure
  - [ ] OR: Document that tag failures require manual cleanup
  - [ ] Add test: tag write fails mid-batch → verify rollback completeness

---

### L-1: No logging in planner or identifier

- **Location:**
  - [resonance/core/planner.py](resonance/core/planner.py) (no logging)
  - [resonance/core/identifier.py](resonance/core/identifier.py) (no logging)

- **Issue:**
  Pure functions don't log. Visitors log. This makes debugging harder when using V3 pipeline directly (no visibility into scoring, tier decisions, etc.).

- **Fix:**
  - [ ] Add optional callback parameter for logging: `identify(..., log_fn=None)`
  - [ ] Caller can inject logger or print function
  - [ ] Or: Document that pure functions must not log (caller logs results)

---

### L-2: Plan.from_json uses import inside method

- **Location:** [resonance/core/planner.py:74-77](resonance/core/planner.py#L74-L77)

- **Issue:**
  ```python
  @classmethod
  def from_json(cls, path: Path, *, allowed_roots: tuple[Path, ...]) -> "Plan":
      from resonance.core.artifacts import load_plan
      return load_plan(path, allowed_roots=allowed_roots)
  ```

  Lazy import inside method. Why not import at top?

- **Fix:**
  - [ ] Move import to top of file
  - [ ] OR: Document circular dependency that requires lazy import

---

### L-3: FileService.delete_if_empty checks library_root but planner doesn't

- **Location:** [resonance/services/file_service.py:86-92](resonance/services/file_service.py#L86-L92)

- **Issue:**
  `delete_if_empty()` has safety check: only delete within `library_root`. But planner doesn't enforce this for destination paths. You can plan a move to `/tmp/foo` and applier will execute it.

- **Fix:**
  - [ ] Applier already has `allowed_roots` validation (line 401-404)
  - [ ] Document that FileService is defensive, planner/applier trust caller

---

### L-4: ProviderRelease.track_count is redundant

- **Location:** [resonance/core/identifier.py:70-73](resonance/core/identifier.py#L70-L73)

- **Issue:**
  ```python
  @property
  def track_count(self) -> int:
      return len(self.tracks)
  ```

  Property just returns `len(tracks)`. Caller can compute this. No caching, no logic.

- **Fix:**
  - [ ] Delete property, use `len(release.tracks)` at call sites
  - [ ] OR: Keep for clarity (explicit is better than implicit)

---

## Explicit Non-Issues

These patterns **look** suspicious but are acceptable given the design intent:

### N-1: Applier performs signature validation instead of trusting plan

**Why it looks wrong:** Plan already contains `signature_hash`. Why re-scan?

**Why it's OK:** Applier is the mutator and must validate filesystem state before making irreversible changes. Files could have been added/removed since plan generation. This is an intentional safety check.

**Evidence:** Lines 345-356 re-scan and validate signature. Tests cover mismatch scenarios.

---

### N-2: DirectoryStateStore uses threading.Lock but is not async

**Why it looks wrong:** Synchronous code using threading primitives.

**Why it's OK:** SQLite connection is marked `check_same_thread=False` (line 23), enabling multi-threaded access. Lock protects concurrent writes from daemon mode or future parallelization.

**Evidence:** Line 22 initializes lock, used throughout (lines 168, 190, 210, 231).

---

### N-3: Planner computes classical/compilation but enricher also has classical detection

**Why it looks wrong:** Duplicate `is_classical` logic.

**Why it's OK:**
- `AlbumInfo.is_classical` (V2 model) checks track-level `composer`/`work` fields
- `planner._is_classical()` checks provider release metadata

These are different data sources. V2 uses existing tags, V3 uses provider data. Not duplication.

**Evidence:** Line 159-166 in planner, line 125-131 in models.py.

---

### N-4: Tests construct DirectoryStateStore inline

**Why it looks wrong:** Violates "single composition root" principle.

**Why it's OK:** Test code is allowed to construct services directly. Only production code (`resonance/`) must use composition root. Tests are explicitly excluded from this requirement.

**Evidence:** See C-2 which only requires fixing production code, not tests.

---

### N-5: extract_evidence is stubbed

**Why it looks wrong:** Function in `identifier.py` has placeholder implementation (lines 159-176).

**Why it's OK:** V3 is mid-implementation. Stub exists to define interface. Tests use provider fixtures, not real evidence extraction. Golden corpus validates end-to-end behavior despite stub.

**Evidence:** Line 159 comment says "stub implementation - will be filled in".

---

### N-6: Applier dry_run still writes audit artifacts

**Why it looks wrong:** Dry run shouldn't have side effects.

**Why it's OK:** Audit trail is metadata about what *would* happen. Recording dry-run attempts helps debugging. State transitions are not applied (line 448 doesn't call `set_state`).

**Evidence:** Lines 430-449 show dry-run returns early but still records to store.

---

## Meta-Observations

### Pattern: V2/V3 coexistence creates drift

**Locations:** Visitors, AlbumInfo, commands

**Root cause:** V3 was added incrementally without deprecating V2. Now two pipelines exist side-by-side with overlapping responsibilities.

**Recommended action:** Explicit deprecation plan:
- [ ] Mark `resonance/visitors/` as deprecated in docstrings
- [ ] Add warning log when visitor pipeline is used
- [ ] Set deadline: remove visitors before V3.1 ships
- [ ] Migrate all commands to V3 pipeline (`resolve → plan → apply`)

---

### Pattern: Where guardrails are missing

**Purity claims not enforced:** Functions are documented as "pure" but contain I/O or depend on mutable state. No static enforcement (e.g., type hints like `-> Pure[Plan]`, freeze decorators).

**Fix:**
- [ ] Add `# type: ignore[effectful]` comments where I/O is intentional
- [ ] OR: Revise docs to say "deterministic" instead of "pure" (since some I/O is acceptable)

**State machine transitions not typed:** `DirectoryState` is an enum, but valid transitions are not encoded (e.g., can't transition `APPLIED → PLANNED` directly, must go through `NEW`).

**Fix:**
- [ ] Add `DirectoryStateStore.validate_transition(from, to)` method
- [ ] Call before every `set_state()`

---

### Pattern: Where tests are doing architectural work that code does not enforce

**Signature validation:** Tests construct fixtures with correct signatures, but nothing prevents passing mismatched signatures in production.

**Fix:** Already handled by applier preflight checks (line 237-265). But planner doesn't validate. Add validation to planner or document that applier is the validation gate.

**Dir_id validity:** Tests use valid `dir_id` strings, but `DirectoryStateStore` only validates length and hex format (line 48). No validation that `dir_id` matches signature hash.

**Fix:**
- [ ] Add `dir_id == sha256(signature_hash)` validation in `get_or_create()`
- [ ] OR: Document that `dir_id` is opaque (caller computes, store trusts)

**Plan serializability:** Golden corpus validates that plans are JSON-serializable, but no runtime check enforces this.

**Fix:**
- [ ] Add `Plan.to_json()` method that fails loudly if not serializable
- [ ] Call in `plan_directory()` before returning

---

## Summary Metrics

- **Critical issues:** 6 (must fix before V3 complete)
- **High priority:** 6 (fix during V3 if possible)
- **Medium priority:** 6 (post-V3)
- **Low priority:** 4 (post-V3)
- **Explicit non-issues:** 6 (intentional patterns)

**Biggest risk:** Dual V2/V3 architecture. Must be resolved before V3 ships.

**Recommendation:** Prioritize C-1 (dual architecture decision) immediately. All other critical issues depend on whether V2 visitors are kept or deprecated.
