# Resonance Architecture Specification

## 1. Goals and non-goals

### Goals

* Deterministic behavior across repeated runs (no “re-matches” unless inputs/rules changed intentionally).
* Safe-by-default: no irreversible operations without explicit `apply`.
* Directory is the atomic unit of work for moving; no splitting directories automatically.
* Clear separation between:

  * discovery (scan),
  * decision (identify/resolve),
  * planning (compute patch),
  * mutation (apply),
  * audit/rollback.

### Non-goals (initially)

* Perfect classical work/movement modeling in the folder tree.
* Fully automatic resolution for compilations, multi-release directories, or mixed-content folders.

---

## 2. Core invariants (“must-haves”)

1. **Directory atomicity**

* A directory is moved as a whole; files inside are not split across releases.
* If evidence suggests multiple releases, mark `UNSURE` and require user intervention.

2. **Pure → impure boundary**

* Scanner/Identifier/Planner are pure (no filesystem mutations, no tag writes).
* Applier is the only component allowed to mutate filesystem/tags.

3. **Stable directory identity**

* Every directory has a stable ID computed from its contents, not its path.

4. **Persist decisions**

* Once a release decision is made, it is stored and reused unless explicitly invalidated.

5. **Provider results are not trusted unless pinned**

* If you select Discogs/MusicBrainz IDs, persist them; do not “re-search” every run.

6. **Default dry-run**

* The default mode produces a plan and audit output; `apply` is explicit.

---

## 3. High-level pipeline

### Phase A — Scan (pure)

* Enumerate candidate directories containing audio files.
* Compute `dir_id` and `dir_signature`.

### Phase B — Identify (pure)

* Build evidence from:

  * audio fingerprints,
  * track count,
  * approximate durations,
  * existing tags (as weak hints, not truth),
  * provider queries (MB/Discogs) *if not already pinned*.

* Produce `ReleaseCandidates[]` + `ConfidenceTier`.

### Phase C — Resolve (controlled side effects)

* If `CERTAIN`: auto-pin release decision.
* If `PROBABLE` or `UNSURE`: create a prompt queue item (daemon-safe).
* If user selects or provides explicit `mb:...` / `dg:...`: pin decision.

### Phase D — Plan (pure)

* Using pinned release + policy, compute a **Plan**:

  * destination path,
  * per-file rename mapping,
  * tag patch (diff),
  * handling of non-audio,
  * conflict strategy.

### Phase E — Apply (side effects)

* Execute the plan transactionally:

  * preflight checks,
  * move/rename,
  * write tags (if permitted),
  * cleanup (origin dir deletion only after success),
  * audit log + rollback info.

---

## 4. Module boundaries and interfaces

Use these “ports” so implementations can swap without architectural rewrites.

### 4.1 Scanner

**Responsibility:** directory discovery + stable identity computation.

```text
scan(root_paths, settings) -> List[DirectoryInfo]

DirectoryInfo:
  path: Path
  audio_files: List[FileInfo]
  non_audio_files: List[FileInfo]
  dir_id: str              # stable content-based identity
  signature: DirSignature  # details used for invalidation + debugging
```

**DirSignature (suggested fields)**

* relative file paths (audio only) + sizes
* per-file audio fingerprint IDs (if cheap) or a subset thereof
* modification times are *not* part of identity (too unstable), but can be recorded for diagnostics.

### 4.2 Identifier

**Responsibility:** compute release candidates and confidence deterministically.

```text
identify(dir_info, provider_cache, settings) -> IdentificationResult

IdentificationResult:
  candidates: List[ReleaseCandidate]
  tier: ConfidenceTier  # CERTAIN | PROBABLE | UNSURE
  reasons: List[Reason] # for audit + UI
  evidence: EvidenceBundle
```

**ReleaseCandidate (minimum)**

* provider: "musicbrainz" | "discogs"
* release_id: string (MBID or Discogs master/release ID per your policy)
* score: float (deterministic)
* match_stats: (tracks_matched, duration_delta, fingerprint_matches, etc.)

### 4.3 Resolver (prompt + jail + pinning)

**Responsibility:** convert uncertainty into pinned decisions.

```text
resolve(dir_id, identification_result, mode) -> ResolutionOutcome

ResolutionOutcome:
  status: RESOLVED | QUEUED | JAILED
  pinned_release: Optional[PinnedRelease]
```

* In daemon mode: `QUEUED` only, never interactive.
* In CLI prompt mode: present candidates + allow manual `mb:...` / `dg:...` entry.
* If user skips: mark `JAILED` with reason.

### 4.4 Planner

**Responsibility:** compute deterministic plan artifacts (no side effects).

```text
plan(dir_info, pinned_release, policy, settings) -> Plan
```

Plan must be stable given the same inputs.

### 4.5 Applier

**Responsibility:** transactional execution with rollback data.

```text
apply(plan, settings) -> ApplyResult
rollback(apply_record_id) -> RollbackResult
```

Applier must:

* verify preconditions (source exists, file counts, no partial overlaps),
* stage operations to avoid partial moves,
* only delete origin directory after successful move/tag write.

---

## 5. Directory state machine

Persist a per-directory record keyed by `dir_id`.

### States

* `NEW`: never processed.
* `IDENTIFIED`: candidates computed (optional state; can be ephemeral).
* `RESOLVED_CERTAIN`: pinned automatically.
* `RESOLVED_USER`: pinned by user selection/input.
* `QUEUED_PROMPT`: awaiting user decision.
* `JAILED`: skipped; do not reprocess unless `--unjail`.
* `PLANNED`: plan computed and stored.
* `APPLIED`: plan executed successfully.
* `FAILED`: apply error recorded; safe stop.

### Allowed transitions (typical)

* `NEW -> IDENTIFIED -> RESOLVED_CERTAIN -> PLANNED -> APPLIED`
* `NEW -> IDENTIFIED -> QUEUED_PROMPT -> RESOLVED_USER -> PLANNED -> APPLIED`
* `QUEUED_PROMPT -> JAILED`
* `FAILED -> (re-run) -> PLANNED` (only if inputs/policy changed or user requested retry)
* `JAILED -> NEW` via `--unjail`

### Invalidation rules

A directory record should be re-identified if any of these change:

* `dir_signature` changed (files added/removed/changed fingerprints)
* settings hash changed for relevant policies (path rules, confidence thresholds)
* pinned release removed/overridden manually

---

## 6. Confidence model (deterministic, explainable)

### Confidence tiers

* `CERTAIN`: safe to move + tag automatically in apply mode.
* `PROBABLE`: safe to *propose*, not safe to mutate without user confirmation (policy-dependent).
* `UNSURE`: must prompt or jail.

### Suggested evidence inputs

* **Fingerprint agreement**

  * count of tracks with matching recording IDs or AcoustID match (source-dependent)
* **Track count match**
* **Duration fit**

  * total duration delta, per-track deltas (tolerant thresholds)
* **Tag coherence**

  * existing tags consistent with candidate (weak evidence)
* **Uniqueness**

  * clear winner margin vs runner-up

### Deterministic scoring (example shape)

You do not need “ML”; you need stable arithmetic. For each candidate:

* `S = w_fp * fp_ratio + w_cnt * count_match + w_dur * duration_fit + w_unique * winner_margin`

Then classify:

* `CERTAIN` if:

  * `fp_ratio >= 0.9` AND `count_match == 1` AND `duration_fit >= threshold`
  * OR explicit pinned by user
* `PROBABLE` if:

  * `S >= probable_threshold` AND winner margin strong
* else `UNSURE`

Important: whatever formula you choose, persist it as:

* `scoring_version` + `weights_hash` so that later changes are explainable.

---

## 7. Foldering rules (safe, minimal, deterministic)

Treat foldering as policy. Keep it conservative.

### 7.1 Core path strategy

Compute:

* `folder_artist` (single string for path)
* `folder_album` (single string for path, includes year optionally)
* `track_filename` (disc/track padded, title)

**Default (non-classical)**

* `folder_artist = AlbumArtist if reliable else Artist else "Unknown Artist"`
* `target = <LibraryRoot>/<folder_artist>/<folder_album>/<track_filename>`

**Compilation**

* `folder_artist = "Various Artists"`
* `folder_album = release title (+ year)`
* (tags keep per-track artist)

**Classical (initial conservative policy)**

* If single reliable composer across album:
  `folder_artist = ComposerDisplayName`
* Else:
  `folder_artist = AlbumArtist` (often performer/ensemble) or "Various Artists"
* `folder_album = release title (+ year)`
* Avoid Work/movement in folder tree initially; do it in tags.

### 7.2 String canonicalization

Canonicalization for paths must be deterministic and reversible enough:

* normalize whitespace
* normalize punctuation variants
* remove forbidden filesystem characters
* stable case policy
* stable abbreviations (configured, not ad hoc)

Crucially: keep a mapping in the audit log, not just the result.

---

## 8. Tagging policy (diff-based, reversible)

### 8.1 Tag patch (do not “write everything”)

Compute a patch with per-field changes, e.g.:

* set: `album`, `albumartist`, `date`, `tracknumber`, `discnumber`
* optionally: `musicbrainz_releaseid`, `musicbrainz_recordingid`, `discogs_release_id`
* classical-specific: `composer`, `conductor`, `ensemble`, `work`, `movement` (if available)

### 8.2 When tags can be written

* `CERTAIN`: allowed.
* `PROBABLE`: only if policy explicitly allows (default: no).
* `UNSURE`: never.

### 8.3 Provenance tags

Always write provenance if you write anything:

* `resonance.provider=musicbrainz|discogs`
* `resonance.release_id=...`
* `resonance.dir_id=...`
* `resonance.scoring_version=...`

This is the strongest antidote to re-matches.

---

## 9. Plan artifact schema (versioned)

Store plans as JSON (or YAML) on disk, keyed by `dir_id` and a plan hash.

### Plan v1 (suggested)

```json
{
  "plan_version": 1,
  "dir_id": "abc123...",
  "source_path": "/music/inbox/SomeAlbum",
  "pinned_release": {
    "provider": "musicbrainz",
    "release_id": "MBID...",
    "confidence_tier": "CERTAIN",
    "resolution": "AUTO|USER",
    "scoring_version": "score-v3"
  },
  "target": {
    "library_root": "/music/library",
    "target_dir": "/music/library/Artist/Album (Year)",
    "path_policy_version": "paths-v2"
  },
  "files": [
    {
      "source": "01 - foo.flac",
      "dest": "01 - Foo.flac",
      "track_identity": {
        "recording_id": "MBID-recording...",
        "disc": 1,
        "track": 1
      },
      "tag_patch": {
        "set": { "album": "…", "tracknumber": "1", "discnumber": "1" },
        "unset": [ "oldtag" ]
      }
    }
  ],
  "non_audio": {
    "policy": "MOVE_WITH_ALBUM|DELETE|IGNORE|QUARANTINE",
    "actions": [
      { "source": "cover.jpg", "dest": "cover.jpg" }
    ]
  },
  "conflicts": {
    "on_target_exists": "FAIL|SKIP|QUARANTINE|MERGE_IDENTICAL",
    "dedupe": { "enabled": true, "method": "audio_hash" }
  },
  "apply": {
    "delete_source_dir_if_empty": true,
    "allow_tag_writes": true
  }
}
```

---

## 10. Persistence layer (cache/DB)

A single store (SQLite is ideal) with these tables:

### 10.1 `directories`

* `dir_id` (PK)
* `last_seen_path`
* `signature_hash`
* `state`
* `pinned_provider`
* `pinned_release_id`
* `confidence_tier`
* `resolution_type` (AUTO/USER)
* `jail_reason`
* `settings_hash`
* timestamps

### 10.2 `plans`

* `plan_id` (PK)
* `dir_id` (FK)
* `plan_hash`
* `plan_blob` (json)
* `created_at`
* `applied_at` nullable

### 10.3 `apply_records`

* `apply_id` (PK)
* `dir_id` (FK)
* `plan_hash`
* `operations_log` (what was moved/written)
* `rollback_blob`
* `status` (OK/FAILED)
* error fields

### 10.4 Provider caches

* query → results, with TTL and a pinned-choice mechanism
* store raw provider responses for reproducibility (or at least essential fields)

---

## 11. CLI surface (minimal but complete)

### Core commands

* `resonance scan <paths...>`
  Updates directory inventory; no prompts; no apply.

* `resonance identify [--enqueue-uncertain]`
  Runs identification for NEW/changed dirs; sets `CERTAIN` pins; queues uncertain if requested.

* `resonance prompt-uncertain`
  Interactive resolution of queued items:

  * list candidates + scores + reasons
  * allow navigation: show track list with durations + current tags
  * accept selection or `mb:...`/`dg:...`
  * allow skip → jail

* `resonance plan [--only-resolved]`
  Creates plans for resolved directories.

* `resonance apply [--plan-id ... | --dir-id ...]`
  Executes plan(s). Defaults to fail-fast unless `--continue-on-error`.

### Safety utilities

* `resonance doctor`
  Checks invariants, cache integrity, conflicting settings hashes.

* `resonance audit [--dir-id ...]`
  Shows pinned decision, scoring reasons, last plan, apply record.

* `resonance rollback --apply-id ...`

### Jail controls

* `resonance list-jailed`
* `resonance unjail --dir-id ...`

---

## 12. Daemon mode and deferred prompts

In daemon mode, **never prompt**. The daemon should:

* scan + identify
* auto-pin CERTAIN only
* queue PROBABLE/UNSURE
* optionally auto-plan CERTAIN
* optionally auto-apply CERTAIN (only if you enable this; conservative default is no)

The user then runs:

* `resonance prompt-uncertain`
* `resonance plan`
* `resonance apply`

This preserves unattended operation without risking wrong moves.

---

## 13. Determinism checklist (what stops “re-matches”)

You should be able to assert all of these:

1. `dir_id` is content-based and stable.
2. Identification uses deterministic ordering (sort inputs, stable tie-breakers).
3. Provider query results are cached and the chosen release is pinned.
4. Once pinned, the pipeline does not “re-decide” unless invalidated.
5. Plans are deterministic from (dir_signature + pinned_release + settings_hash).
6. Apply records persist what happened; reruns detect “already applied”.

If any of these fail, re-matches will recur.

---

## 14. Minimal test corpus (so refactors do not regress)

Keep a small fixture set, each with expected outcome:

* single album, fully fingerprintable → CERTAIN
* album with one missing fingerprint → PROBABLE
* compilation → “Various Artists”
* classical single-composer album → composer folder
* mixed-composer classical → performer/albumartist folder
* directory with extra non-audio (pdf + jpg) → moved along
* target exists conflict → FAIL and quarantine path
* “two albums in one directory” evidence → UNSURE + queued

For each fixture, test:

* deterministic `dir_id`
* deterministic candidate ordering + scores
* plan identical across repeated runs
* apply idempotency guard

---

## 15. Implementation note on “visitor pattern”

You can still implement scanning with a visitor/walker. Just do not let the visitor own business logic. The “business pipeline” should be explicit: scan → identify → resolve → plan → apply. This will keep Resonance small and comprehensible.