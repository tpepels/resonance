Below is a **V4 TODO** that is deliberately **post-V3 in character**: it assumes the software *works*, and focuses on **usability, ergonomics, confidence, and adoption**, not new core features or architecture.

Think of V4 as: *turning a powerful internal tool into something other people (and future-you) can use comfortably and repeatedly.*

---

# TDD TODO V4 — Productization, UX, and Operator Confidence

## V4 Theme

> V3 proves correctness and real-world capability.
> **V4 proves usability, clarity, and trust at scale.**

No new providers.
No new tagging formats unless unavoidable.
No architectural rewrites.

---

## 1. CLI UX & Human-Readable Feedback

### 1.1 Clear operational modes (CLI polish)

* [ ] Review and stabilize CLI surface:

  * `scan`
  * `resolve`
  * `apply`
  * `prompt` (or equivalent)
  * `doctor`
* [ ] Ensure **every command answers three questions**:

  1. What did you do?
  2. What changed?
  3. What happens next?

### 1.2 Output clarity (Integration)

* [ ] Tests asserting:

  * stable, readable summaries after each run
  * counts: scanned / resolved / queued / skipped / applied
  * no raw stack traces in normal failure paths
* [ ] Explicit “nothing to do” output (silence is confusing)

### 1.3 Dry-run ergonomics

* [ ] `--dry-run` output mirrors real apply structure
* [ ] Clear distinction between:

  * *would move*
  * *would tag*
  * *would skip*
* [ ] Users can understand impact without reading JSON plans

---

## 2. Prompt / Interactive Resolution UX

### 2.1 Candidate presentation quality

* [ ] Tests asserting candidate lists show:

  * provider (Discogs / MB)
  * year, label, format
  * disc/track count
  * confidence reason codes (short, human)
* [ ] Stable ordering across runs

### 2.2 Interactive affordances

* [ ] Allow:

  * accept
  * reject
  * skip
  * manual ID entry
* [ ] Clear indication of permanence (“this choice will be remembered”)

### 2.3 Error-resistant prompting

* [ ] Invalid input does not corrupt state
* [ ] Ctrl-C / abort returns directory to a safe queued state
* [ ] Prompt session resumable

---

## 3. Observability for Humans (not auditors)

### 3.1 Run summaries & history

* [ ] `resonance runs` shows:

  * timestamp
  * number of changes
  * unresolved items
* [ ] `resonance status` answers:

  * “Is my library clean right now?”

### 3.2 Explainability tooling

* [ ] `resonance explain <dir>`:

  * why it matched this release
  * why alternatives lost
  * why it is (or isn’t) resolved
* [ ] No provider-internal jargon exposed

---

## 4. Error Handling & User Trust

### 4.1 Error taxonomy cleanup

* [ ] All user-visible errors categorized:

  * configuration
  * provider/network
  * filesystem
  * metadata ambiguity
* [ ] Each error answers:

  * what failed
  * whether it is safe to retry
  * what the user should do

### 4.2 “Nothing bad happened” guarantees

* [ ] On failure, user is explicitly told:

  * whether any files were changed
  * whether rollback occurred
* [ ] No silent partial success

---

## 5. Documentation as a First-Class Artifact

### 5.1 Minimal but complete docs

* [ ] README answers:

  * what the tool does
  * what it does *not* do
  * who it is for
* [ ] “First run” guide:

  * scan → resolve → apply → rerun
* [ ] Explanation of deterministic behavior (why it won’t keep asking)

### 5.2 Mental model documentation

* [ ] One page: “How Resonance thinks about your library”
* [ ] One page: “When it will ask you questions (and why)”

---

## 6. Safe Defaults & Configuration Hygiene

### 6.1 Defaults audit

* [ ] Default config produces:

  * conservative behavior
  * no destructive surprises
* [ ] Advanced options are opt-in and documented

### 6.2 Config validation

* [ ] `doctor` validates:

  * conflicting options
  * dangerous combinations
* [ ] Clear warnings, not silent acceptance

---

## 7. Packaging & Distribution Readiness

### 7.1 Installation confidence

* [ ] Clean install via pipx / venv smoke-tested
* [ ] Version shown in all outputs
* [ ] Upgrade path tested from V3 → V4

### 7.2 Platform sanity

* [ ] Linux + macOS tested explicitly
* [ ] Filesystem edge behavior documented per platform

---

## 8. Acceptance Test: “Hand it to a friend”

This is the V4 gate.

* [ ] A technically literate but *non-involved* user:

  * installs it
  * runs it on a small real library
  * resolves ambiguities
  * reruns it
* [ ] They:

  * understand what happened
  * trust the result
  * are not afraid to rerun

If this succeeds, V4 is done.

---

## V4 Definition of Done

V4 is complete when:

1. Users can **understand what the software is doing without reading the code**.
2. Interactive resolution feels intentional, not fragile.
3. Errors are informative, not alarming.
4. Documentation matches actual behavior.
5. You are comfortable saying:

   > “Yes, you can try this on your own library.”