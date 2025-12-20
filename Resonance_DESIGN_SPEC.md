# Resonance Architecture Specification (Determinism-First, Foundation-Aligned)

## 1. Goals and non-goals

### Goals

* Deterministic behavior across repeated runs (no “re-matches” unless inputs or rules change intentionally).
* Safe-by-default: no irreversible operations without explicit `apply`.
* Directory is the atomic unit of work for moving; no splitting directories automatically.
* Clear separation between:

  * discovery (scan),
  * decision (identify / resolve),
  * planning (compute plan),
  * mutation (apply),
  * audit / rollback.
* Explicit persistence of decisions so the system never “forgets” prior conclusions.

### Non-goals (initially)

* Perfect classical work/movement modeling in the folder tree.
* Fully automatic resolution for compilations, multi-release directories, or mixed-content folders.
* Semantic name inference without explicit mappings.

---

## 2. Core invariants (“must-haves”)

### 2.1 Directory atomicity

* A directory is moved as a whole; files inside are not split across releases.
* If evidence suggests multiple releases, mark `UNSURE` and require user intervention.

### 2.2 Pure → impure boundary

* Scan, Identify, and Plan stages are **non-mutating**:

  * no filesystem mutations,
  * no tag writes.
* Provider queries (MusicBrainz, Discogs, etc.) are allowed during Identify, but:

  * results must be cached deterministically,
  * results must be ordered deterministically,
  * results must not be treated as decisions unless pinned.
* Apply is the **only** stage allowed to mutate filesystem or tags.

### 2.3 Stable directory identity

* Every directory has a stable ID computed from its **audio content**, not its filesystem path.
* Renames or moves must not change identity.

### 2.4 Persisted decisions override re-identification

* Once a release decision is pinned, it must be reused on subsequent runs unless explicitly invalidated.
* If a directory is pinned and its identity and relevant settings are unchanged:

  * provider searches must be skipped,
  * candidate recomputation must be skipped.

### 2.5 Provider results are advisory until pinned

* Discogs/MusicBrainz results are evidence, not truth.
* Only pinned IDs influence planning or mutation.

### 2.6 Default dry-run

* The default execution mode produces plans and audit output only.
* Mutation requires explicit `apply`.

### 2.7 Identity normalization vs canonicalization (critical separation)

**Mechanical normalization (`normalize_token`)**

* Produces a deterministic **comparison key only**.
* Performs:

  * Unicode normalization,
  * case folding,
  * punctuation and whitespace removal,
  * joiner normalization (`&`, `and`, `/`, `;`, `x`),
  * removal of featuring tokens (`feat`, `ft`, `featuring`, including bracketed/parenthesized forms).
* Must NOT:

  * reorder names (e.g. `"Beatles, The"` ≠ `"The Beatles"`),
  * invent semantic equivalences,
  * choose display names.

**Canonicalization (`IdentityCanonicalizer`)**

* Applies explicit mappings:
  `<namespace>::<normalized_key> → canonical_display_name`
* Never invents mappings.
* If no mapping exists, preserves the original display string.
* May deduplicate equivalent normalized keys once mapped.

**Rationale:** This separation prevents accidental semantic drift and ensures determinism.

---

## 3. High-level pipeline

### Phase A — Scan (non-mutating)

* Enumerate candidate directories containing audio files.
* Compute `dir_id` and `dir_signature`.

### Phase B — Identify (non-mutating)

* Build evidence from:

  * audio fingerprints or stable proxies,
  * track count,
  * approximate durations,
  * existing tags (weak hints),
  * provider queries (only if no pinned release exists).
* Produce:

  * `ReleaseCandidates[]`,
  * `ConfidenceTier`,
  * human-readable reasons.

### Phase C — Resolve (controlled side effects)

* If `CERTAIN`: auto-pin release decision.
* If `PROBABLE` or `UNSURE`: enqueue for user resolution.
* If user provides `mb:...` or `dg:...`: pin explicitly.
* If user skips: mark as `JAILED`.

### Phase D — Plan (non-mutating)

* Using pinned release and policy, compute a deterministic **Plan**:

  * destination path,
  * per-file rename mapping,
  * tag patch (diff),
  * non-audio handling,
  * conflict strategy.

### Phase E — Apply (mutating)

* Execute plan transactionally:

  * preflight checks,
  * move/rename,
  * write tags (if permitted),
  * cleanup source directory,
  * write audit and rollback data.

---

## 4. Module boundaries and interfaces

### 4.1 Scanner

**Responsibility:** directory discovery and stable identity computation.

```text
scan(root_paths, settings) -> List[DirectoryInfo]

DirectoryInfo:
  path: Path
  audio_files: List[FileInfo]
  non_audio_files: List[FileInfo]
  dir_id: str
  signature: DirSignature
```

**DirSignature**

* `signature_hash` (identity/invalidation):

  * derived from audio content only,
  * order-independent,
  * ignores mtimes and non-audio.
* `debug_info` (non-identity):

  * relative paths,
  * sizes,
  * mtimes,
  * counts.

---

### 4.2 Identifier

```text
identify(dir_info, provider_cache, settings) -> IdentificationResult

IdentificationResult:
  candidates: List[ReleaseCandidate]
  tier: ConfidenceTier  # CERTAIN | PROBABLE | UNSURE
  reasons: List[Reason]
  evidence: EvidenceBundle
  scoring_version: str
```

Pinned releases short-circuit identification.

---

### 4.3 Resolver

```text
resolve(dir_id, identification_result, mode) -> ResolutionOutcome

ResolutionOutcome:
  status: RESOLVED | QUEUED | JAILED
  pinned_release: Optional[PinnedRelease]
```

---

### 4.4 Planner

```text
plan(dir_info, pinned_release, policy, settings) -> Plan
```

Planner is pure and deterministic.

---

### 4.5 Applier

```text
apply(plan, settings) -> ApplyResult
rollback(apply_id) -> RollbackResult
```

Applier performs all mutations transactionally.

---

## 5. Directory state machine

Keyed by `dir_id`.

### States

* `NEW`
* `RESOLVED_CERTAIN`
* `RESOLVED_USER`
* `QUEUED_PROMPT`
* `JAILED`
* `PLANNED`
* `APPLIED`
* `FAILED`

### Invalidation

Re-identify only if:

* `signature_hash` changed,
* relevant `settings_hash` changed,
* pinned release removed manually.

---

## 6. Confidence model (deterministic)

### Tiers

* `CERTAIN`: safe for automatic apply.
* `PROBABLE`: safe to propose, not mutate.
* `UNSURE`: requires user input.

### Scoring

Deterministic arithmetic scoring with persisted `scoring_version` and weights hash. No ML.

---

## 7. Foldering rules (Planner-only policy)

Folder layout decisions are **Planner responsibilities only**.

### Default (non-classical)

```
<LibraryRoot>/<AlbumArtist>/<Album>/<Track>
```

### Compilation

```
<LibraryRoot>/Various Artists/<Album>/<Track>
```

### Classical (initial conservative)

* Single composer: composer as folder artist.
* Else: album artist or performer.
* Works/movements live in tags, not folders.

---

## 8. Tagging policy

* Diff-based tag patches only.
* Tags written only when confidence allows.
* Always write provenance tags when mutating.

---

## 9. Plan artifact (versioned)

Plans are persisted JSON/YAML blobs keyed by `dir_id` and plan hash.

---

## 10. Persistence layer

Single durable store (SQLite recommended):

* `directories`
* `plans`
* `apply_records`
* provider caches (raw + pinned choice)

---

## 11. CLI surface

* `scan`
* `identify`
* `prompt-uncertain`
* `plan`
* `apply`
* `audit`
* `doctor`
* `rollback`
* `unjail`

---

## 12. Daemon mode

* Never prompts.
* Auto-pins CERTAIN only.
* Queues PROBABLE/UNSURE.
* User resolves later via CLI.

---

## 13. Determinism checklist

1. Content-based `dir_id`
2. Deterministic ordering everywhere
3. Provider results cached
4. Pinned decisions override re-identification
5. Plans deterministic from inputs
6. Apply is idempotent and auditable

---

## 14. Minimal test corpus

Each fixture must assert:

* stable `dir_id`,
* deterministic identification,
* stable plan across runs,
* safe apply behavior.

---

## 15. Visitor pattern note

Visitors may be used for traversal, but **business logic must remain explicit**:
scan → identify → resolve → plan → apply.

---