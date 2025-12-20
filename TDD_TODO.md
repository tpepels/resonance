# Resonance TDD TODO (Final, Determinism-First)

This checklist is ordered for test-driven development. Each section starts with
unit tests, then minimal implementation to satisfy them. The ordering enforces
the Resonance pipeline and prevents “re-matches” and accidental library damage.

**Notes / guiding constraints (apply throughout):**

* **Purity boundary:** Scanner / Identifier / Planner are **pure** (no filesystem mutations, no tag writes, no persistence writes). Applier is the only mutator.
* **Keying:** All processing is keyed by **`dir_id`** (content-based), never by path.
* **Pinned decisions:** Once a directory is `RESOLVED_*`, subsequent runs must **reuse** the pinned release unless invalidated.
* **Plan-first:** Apply executes a **stored Plan artifact**; Applier must not recompute decisions.
* **Default safety:** Default non-audio handling is **MOVE_WITH_ALBUM**; deleting non-audio requires explicit opt-in.

---

## 0) Test scaffolding + fixtures (Unit/Integration)

* [x] Tempdir / in-memory FS helpers to create album directories with:

  * audio file stubs (stable “fingerprint id”, duration, size)
  * non-audio stubs (jpg/pdf/cue/log/txt)
* [x] Deterministic ordering helpers (`sorted_paths`, stable tiebreak utility).
* [x] Snapshot assertion helper for Plan JSON (stable formatting + ordering).
* [x] Fixture builder for golden scenarios:

  * [x] pop_certain (all fingerprints match one release)
  * [x] pop_probable (one missing/weak match)
  * [x] compilation (various artists)
  * [x] classical_single_composer
  * [x] classical_mixed_composer
  * [x] mixed_release_in_one_dir (conflicting evidence)
  * [x] non_audio_present (cover/booklet/log)
  * [x] target_exists_conflict

---

## 1) Stable Identity + Signature (Unit)

**Goal:** stable directory identity across runs and paths.

* [x] `dir_signature(audio_files)` is order-independent (input order does not matter).
* [x] `dir_signature` ignores mtimes and other unstable metadata.
* [x] `dir_id(signature)` stable across repeated scans.
* [x] Same content in different filesystem paths yields the same `dir_id`.
* [x] Adding/removing an audio file changes `signature_hash`.
* [x] Changing audio content (size/fingerprint) changes `signature_hash`.
* [x] Non-audio changes do **not** change `dir_id` (but are recorded for diagnostics).

**Comment:** Keep `dir_id` strictly content-based. Path is a diagnostic attribute only.

---

## 2) Canonicalization Policy (Unit)

**Goal:** deterministic, path-focused canonical names (no musicology guesses).

### 2.1 Token normalization + parsing

* [x] `normalize_token()`:

  * Unicode normalization (NFKC), trim, collapse whitespace
  * produces a stable comparison key (casefolded), preserving display string separately
  * normalizes joiners: `feat`, `ft.`, `with`, `&`, `and`, `/`, `;`
  * handles mononyms without special-casing into first/last
* [x] `split_names()` parses multi-name strings deterministically.
* [x] `dedupe_names()` collapses duplicates (“A / A”, “A & A” → “A”).

### 2.2 Canonical mapping store usage

* [x] Canonicalizer uses cache mappings: raw_key → canonical_display.
* [x] If mapping missing, return original display (but stable-normalized for keys).
* [x] Canonicalizer never invents expansions; it only normalizes + maps.

### 2.3 “Short folder name” rule (define + test)

* [x] Define “short folder name” rule and enforce it:

  * [x] max length (e.g., 60 chars) enforced
  * [x] featuring/with clauses removed from folder-name representation
  * [x] deterministic shortening strategy when over limit (drop trailing clauses; fallback to primary token)
* [x] Shortening does not change canonical mapping keys (only affects folder display).

**Comment:** Canonicalization is for stable folder naming and mapping; richness belongs in tags and provider metadata.

---

## 3) Persistence + Directory State Machine (Unit)

**Goal:** explicit, testable states; no ad hoc “is_uncertain” flags.

* [ ] `DirectoryRecord` keyed by `dir_id` (not by path).
* [ ] States supported:

  * [ ] `NEW`
  * [ ] `QUEUED_PROMPT`
  * [ ] `JAILED`
  * [ ] `RESOLVED_AUTO`
  * [ ] `RESOLVED_USER`
  * [ ] `PLANNED`
  * [ ] `APPLIED`
  * [ ] `FAILED`
* [ ] If `state == JAILED`, pipeline excludes directory unless `--unjail`.
* [ ] `--unjail` transitions `JAILED -> NEW` and clears jail reason.
* [ ] Invalidation rule:

  * [ ] if `signature_hash` changed: record becomes `NEW` (audit preserved), pinned release cleared unless policy says otherwise.

### Critical determinism additions (must-have)

* [ ] Path changes do **not** create new records:

  * [ ] if `last_seen_path` changes but `dir_id` same, update `last_seen_path` and keep the same record.
* [ ] Pinned decisions are reused:

  * [ ] if `RESOLVED_*` and signature/settings unchanged, identification must not change pinned release.
* [ ] Pinned means **no re-search**:

  * [ ] if `RESOLVED_*` and unchanged, Identifier must not call provider search (no re-query).

**Comment:** This section is where you prevent “re-matches” structurally. If you get this right, later logic can remain conservative without becoming annoying.

---

## 4) Scanner (Unit)

**Goal:** discovery only; no provider calls; produces `DirectoryInfo`.

* [ ] Scans root(s) and returns only directories that contain audio files.
* [ ] Skips empty directories and directories with only non-audio.
* [ ] Produces deterministic output ordering of directories and files.
* [ ] Produces `DirectoryInfo` with:

  * [ ] `audio_files[]`, `non_audio_files[]`
  * [ ] `dir_id`, `signature_hash`
  * [ ] diagnostic fields (e.g., total_duration, counts) as needed

### Purity boundary addition (must-have)

* [ ] Scanner is **pure**:

  * [ ] does not read/write persistence; it returns `DirectoryInfo` only.

**Comment:** Persisting scan results is the job of an orchestrator/pipeline runner, not Scanner itself.

---

## 5) Identifier: Evidence + Release Candidate Scoring (Unit)

**Goal:** deterministic candidate list + confidence tier.

### 5.1 Evidence extraction

* [ ] Extract per-track evidence from stubs:

  * [ ] duration
  * [ ] fingerprint id
  * [ ] existing tags (optional, weak signal)
* [ ] Directory-level evidence:

  * [ ] track_count
  * [ ] duration_sum
  * [ ] per-track list in stable order

### 5.2 Provider scoring (MusicBrainz + Discogs)

* [ ] Scores MusicBrainz release by:

  * [ ] fingerprint coverage ratio
  * [ ] track count match
  * [ ] duration fit (coarse)
  * [ ] year difference penalty (optional)
* [ ] Scores Discogs release similarly.
* [ ] Merges candidates into a single list with deterministic ordering:

  * [ ] sort by score desc
  * [ ] tie-break by provider priority
  * [ ] then by release_id lexicographically

### 5.3 Multi-release detection (directory cannot be split)

* [ ] If evidence indicates ≥2 incompatible releases materially supported:

  * [ ] tier becomes `UNSURE`
  * [ ] reasons include multi-release conflict details

### Quantitative rule addition (must-have)

* [ ] Multi-release UNSURE heuristic is defined **quantitatively** in tests (example shape):

  * [ ] if two distinct release IDs each exceed a minimum support threshold (e.g., coverage ≥ 0.30) → `UNSURE`
  * [ ] rule is encoded in tests so it cannot drift silently

### 5.4 Confidence tiers (replace “100% certain” with defined thresholds)

* [ ] Define thresholds (constants + version tag):

  * [ ] `CERTAIN` condition (e.g., coverage ≥ 0.90, count match, winner margin ≥ 0.10)
  * [ ] `PROBABLE` condition (score ≥ X and winner margin ≥ Y)
  * [ ] else `UNSURE`
* [ ] Auto-select only when `CERTAIN`.
* [ ] Reject low-coverage candidates.
* [ ] Ambiguous tie (winner margin too small) yields `UNSURE`.
* [ ] `IdentificationResult` includes:

  * [ ] candidates
  * [ ] tier
  * [ ] reasons (human-readable, stable)
  * [ ] scoring_version/weights hash

### Determinism addition (must-have)

* [ ] Identification output is deterministic:

  * [ ] same inputs → same ordered candidates, same tier, same reasons (no randomness, no provider-order dependence)

**Comment:** Avoid “majority of track tags” as a primary driver here. Prefer provider-pinned release evidence; treat existing tags as weak hints only.

---

## 6) Resolver: Prompt Queue, Jail, Manual IDs (Unit)

**Goal:** daemon-safe uncertainty handling; user decisions are persisted.

* [ ] Non-interactive mode:

  * [ ] if tier != `CERTAIN`, set `QUEUED_PROMPT` and stop for that dir
  * [ ] no interactive calls, no partial planning/apply
* [ ] Interactive mode (prompt service):

  * [ ] shows full track list with durations (no truncation)
  * [ ] shows candidate list with scores and reasons
  * [ ] user can pick candidate → pins `RESOLVED_USER`
  * [ ] manual input accepts `mb:`/`dg:` and validates basic format
* [ ] Skip/jail:

  * [ ] sets state `JAILED`
  * [ ] stores reason + timestamp
  * [ ] prevents reprocessing on subsequent runs (unless `--unjail`)
* [ ] When `CERTAIN`:

  * [ ] pins automatically as `RESOLVED_AUTO` (provider + release_id + tier + scoring_version)

### Persistence clarity addition (must-have)

* [ ] Resolver persists `resolution_type`:

  * [ ] `AUTO` for `RESOLVED_AUTO`
  * [ ] `USER` for `RESOLVED_USER`
  * [ ] persisted alongside pinned release metadata

**Comment:** Resolver is the only place user interaction occurs. Everything else consumes its output.

---

## 7) Planner: Deterministic Plan Artifact (Unit)

**Goal:** compute a plan (pure) from pinned decision + directory info + settings.

* [ ] Planner never consults providers (uses pinned release only).
* [ ] Plan generation is deterministic:

  * [ ] stable file ordering
  * [ ] stable formatting
  * [ ] byte-for-byte identical Plan JSON for identical inputs

### State gating addition (must-have)

* [ ] Planner refuses unless directory state is `RESOLVED_*` (or explicit override):

  * [ ] prevents planning while still uncertain/queued/jailed

### 7.1 Destination path rules (define + test precisely)

* [ ] Popular albums default path: `Artist/Album`

  * [ ] define `Artist` precedence (e.g., albumartist → artist → Unknown Artist)
* [ ] Compilation path: `Various Artists/Album`
* [ ] Classical path (conservative v1):

  * [ ] if single reliable composer: `Composer/Album`
  * [ ] else: `PerformerOrAlbumArtist/Album`
  * [ ] define precedence chain for “PerformerOrAlbumArtist”
* [ ] “Short name” canonicalization applied to folder components.

**Comment (classical):** v1 deliberately avoids deep Work/Movement foldering; keep richness in tags, not the folder tree.

### 7.2 Track filename rules

* [ ] Disc/track padding rules defined and tested.
* [ ] Safe character policy applied deterministically.
* [ ] No per-run randomness in capitalization or punctuation.

### 7.3 Directory atomicity enforced

* [ ] Plan never splits files into different target directories.
* [ ] If directory flagged multi-release/UNSURE, planner refuses and requires resolution.

### 7.4 Conflict strategy encoded in Plan

* [ ] Plan includes `on_target_exists` policy (e.g., `FAIL|SKIP|QUARANTINE|MERGE_IDENTICAL`)
* [ ] Tests verify chosen policy is preserved into Plan artifact.

### Non-audio policy encoded in Plan (must-have)

* [ ] Plan explicitly encodes non-audio handling:

  * [ ] default `MOVE_WITH_ALBUM`
  * [ ] delete only when explicitly configured later
  * [ ] behavior is visible in plan snapshots

**Comment:** This prevents non-audio behavior from becoming ad hoc Applier logic.

---

## 8) Enricher: Tag Patch Policy (Unit)

**Goal:** conservative metadata updates; diff-based; provenance recorded.

* [ ] Computes a `tag_patch` (set/unset) rather than rewriting everything.
* [ ] Writes provenance tags when tag writes are allowed:

  * [ ] provider, release_id, dir_id, scoring_version
* [ ] Tag patch created only when:

  * [ ] tier == `CERTAIN` (default)
  * [ ] (optional) tier == `PROBABLE` only if policy explicitly enables it
* [ ] Does not overwrite existing tags when not confident:

  * [ ] define allowlist/denylist policy and test it

**Comment:** Enricher should be strictly policy-driven. Keep the default conservative.

---

## 9) Applier: Transactional Move + Cleanup (Integration)

**Goal:** safe mutations only; idempotent; never partial.

* [ ] Applier consumes stored Plan artifact (does not recompute plan).
* [ ] Preflight checks:

  * [ ] source exists and matches expected file list
  * [ ] target conflict handled according to plan policy
* [ ] Transaction-safe execution order:

  * [ ] stage/move files
  * [ ] write tags (if enabled)
  * [ ] only then cleanup source dir
* [ ] Deletes source dir only when empty and apply succeeded.
* [ ] Idempotency:

  * [ ] applying the same plan twice results in no duplication/corruption (no-op or “already applied”).
* [ ] Non-audio policy:

  * [ ] default `MOVE_WITH_ALBUM`
  * [ ] delete only when explicitly enabled (`--delete-nonaudio`)
  * [ ] behavior is captured in Plan and audited

**Comment:** Applier is the only mutator. Keep it boring and transactional.

---

## 10) Daemon Mode + Prompt CLI (Integration)

**Goal:** unattended runs that queue uncertainty; interactive resolution later.

### 10.0 Pipeline runner / orchestrator (Integration) — required glue

* [ ] Pipeline runner processes directories by state:

  * [ ] `NEW` → identify
  * [ ] `CERTAIN` → auto-pin (`RESOLVED_AUTO`)
  * [ ] `PROBABLE/UNSURE` → `QUEUED_PROMPT` (daemon) or prompt (interactive mode)
  * [ ] respects `JAILED` (skips) and `QUEUED_PROMPT` (does not re-identify unless policy says so)

**Comment:** This prevents “visitors calling each other” and keeps the system as an explicit pipeline.

### Daemon run

* [ ] Daemon run:

  * [ ] scan + identify
  * [ ] auto-pin `CERTAIN`
  * [ ] queue `PROBABLE/UNSURE`
  * [ ] never prompts

### Prompt command

* [ ] `prompt-uncertain` processes queued dirs:

  * [ ] pins selection as `RESOLVED_USER`
  * [ ] supports manual `mb:`/`dg:` entry
  * [ ] supports skip → `JAILED`

### Jail control

* [ ] `--unjail` reprocesses skipped dirs as `NEW`.

---

## 11) Prescan CLI: Canonical Mapping Builder (Integration)

**Goal:** improve canonicalization; does not decide releases.

* [ ] Scans library and records observed raw names into canonical mapping store.
* [ ] Skips empty/non-audio-only directories.
* [ ] Produces stable mapping keys (from normalized tokens).
* [ ] Does not pin releases; only updates canonical mapping inventory.

**Comment:** Prescan is purely about mapping coverage and reducing later prompts, not about choosing releases.

---

## 12) Audit + Doctor + Rollback (Integration)

**Goal:** operational safety and debuggability (especially during refactors).

* [ ] `audit --dir-id` shows:

  * [ ] state, last seen path, signature hash
  * [ ] pinned release and confidence
  * [ ] last plan hash
  * [ ] last apply record summary
* [ ] `doctor` validates:

  * [ ] no “planned without resolved”
  * [ ] no “applied without plan”
  * [ ] cache/settings hash mismatches surfaced clearly
* [ ] Rollback support:

  * [ ] apply records contain enough information to undo moves/tag writes (minimum: file move rollback; tags optional initially)

**Comment:** Start rollback with filesystem moves (reversible). Tag rollback can be added once tagging is stable.