# TDD TODO V5 — Stabilization, Release, and Maintenance Mode

## V5 Theme

> **Stop changing behavior. Start guaranteeing it.**

No new features.
No new providers.
No new tagging logic.
No new layouts.

Only:

* stabilization
* guarantees
* long-term sanity

---

## 1. Behavioral Freeze & Compatibility Guarantees

### 1.1 Behavior lock-in

* [ ] Explicitly declare:

  * supported audio formats
  * supported providers
  * supported layouts
* [ ] Add tests asserting:

  * canonical layouts do not change between versions
  * tagging output for fixed inputs is byte-identical

### 1.2 Versioned behavior expectations

* [ ] Record expected behavior for:

  * tagging keys per format
  * move layouts
  * overwrite defaults
* [ ] Failing tests are required to change any of the above

**This is where “future refactors” stop being allowed to change results.**

---

## 2. Long-Term Library Stability

### 2.1 Upgrade safety

* [ ] Test: upgrading from V3 → V4 → V5 does not:

  * rematch resolved directories
  * rewrite tags unnecessarily
  * move files again
* [ ] Explicit upgrade notes emitted once per version jump

### 2.2 Regression corpus

* [ ] Freeze a small “golden library”:

  * representative albums
  * edge cases
  * classical + compilations
* [ ] Every release runs against this corpus
* [ ] Any diff requires explicit justification

---

## 3. Performance & Scale Sanity (No Heroics)

### 3.1 Large library smoke test

* [ ] Test against:

  * 10k+ tracks
  * hundreds of directories
* [ ] Assert:

  * no exponential behavior
  * bounded memory usage
  * no provider storms

This is not optimization — it is *guarding against accidental disasters*.

---

## 4. Maintenance Mode Tooling

### 4.1 Diagnostics completeness

* [ ] `doctor` covers:

  * config sanity
  * provider credentials
  * filesystem permissions
  * tag backend availability
* [ ] Every doctor failure is actionable

### 4.2 Self-reporting confidence

* [ ] `resonance status` answers:

  * “Is my library clean?”
  * “What is unresolved?”
* [ ] No hidden state that only the developer understands

---

## 5. Documentation: Final Pass

### 5.1 Declare non-goals (important)

* [ ] Explicitly document:

  * what Resonance will *never* try to do
  * why certain things are manual by design
* [ ] Prevent feature creep by design clarity

### 5.2 Maintenance README

* [ ] Add:

  * how to add a provider (theoretically)
  * how to update fixtures
  * how to reason about a bug report
* [ ] Future-you can pick this up after 18 months

---

## 6. Release Ritual

### 6.1 One-shot release checklist

* [ ] Version bump
* [ ] Changelog written in human language
* [ ] Tagged release
* [ ] Announcement text drafted (even if never posted)

### 6.2 Psychological closure test

* [ ] You feel comfortable:

  * not touching this code for weeks
  * running it on your own library unattended
  * saying “no” to feature requests

If that is true, V5 is done.

---

## V5 Definition of Done

V5 is complete when:

1. Behavior is frozen and defended by tests.
2. Upgrades are safe and boring.
3. The software can sit unchanged without anxiety.
4. You trust it enough to **forget about it**.

That last point matters.