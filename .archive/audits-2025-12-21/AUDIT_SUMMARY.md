# Golden Corpus Audit Summary

**Date:** 2025-12-21
**Audit Scope:** Determinism analysis of all proposed golden corpus scenarios

---

## Quick Reference

**Documents Created:**
1. **CANONICALIZATION_AUDIT.md** - Full determinism analysis (all 18 proposed scenarios)
2. **GOLDEN_CORPUS_ROADMAP.md** - Implementation quick reference
3. **TDD_TODO_V3.md** - Updated with sections 0.8 (V3 work) and 0.9 (post-V3 backlog)

**All documents properly cross-referenced in TDD_TODO_V3.md header.**

---

## Determinism Verdict

✅ **All proposed scenarios are deterministic**
- No network calls required
- All use fixed fingerprints, tags, and file structures
- Can be tested with snapshot-based golden corpus approach

---

## V3 Scope (Section 0.8)

**Current:** 18 scenarios (all deterministic)
**Target:** 26 scenarios (+8 new)

**Already implemented (4 scenarios):**
- ✅ opus_normalization
- ✅ conductor_vs_performer
- ✅ multi_performer_work
- ✅ catalog_variants

**Ready to add for V3 (8 scenarios, ~4 hours):**
1. GC-5: Partial opera (non-contiguous excerpts)
2. GC-10: Partial tags (missing album/artist)
3. GC-11: Duplicate files (same fingerprint)
4. GC-13: Remaster vs original (year disambiguation)
5. GC-14: Non-audio-only directory
6. GC-15: Hidden track (track 0 and 99)
7. GC-17: Unicode normalization (NFD vs NFC)
8. GC-18: Invalid year tags ("0000", "UNKNOWN")

**Not golden corpus - add as integration tests (2 scenarios):**
- GC-8: Orphaned track reunification
- GC-9: Split album merge

---

## Post-V3 Backlog (Section 0.9)

**Deferred until canonicalization system exists (3 scenarios):**
1. GC-12: Featured artist normalization ("feat." ⇔ "ft" ⇔ "featuring")
2. GC-6: Work nickname aliases ("Eroica" ⇔ "Symphony No. 3")
3. GC-7: Ensemble abbreviations ("LSO" ⇔ "London Symphony Orchestra")

**Blocker:** Requires `match_key_*` vs `display_*` separation (TDD_TODO_V3.md lines 68-77)

**Skipped (non-deterministic):**
- ❌ GC-16: Mixed encoding/mojibake (unreliable to simulate)

---

## Key Decisions

1. **100% deterministic for V3** - All 8 new scenarios can be added immediately
2. **Canonicalization properly deferred** - 3 scenarios align with existing post-V3 plan
3. **Integration tests separated** - 2 scanner scenarios don't fit golden corpus model
4. **Non-deterministic skipped** - 1 scenario rejected as unreliable

---

## Next Steps

1. ✅ **Documents created and cross-referenced**
2. 🎯 **Ready to implement Phase 1** (8 scenarios, ~4 hours)
3. 📋 **Post-V3 backlog documented** (3 scenarios)
4. 🔧 **Integration tests scoped** (2 tests, ~1 hour)

---

**For implementation details, see GOLDEN_CORPUS_ROADMAP.md**
**For full analysis, see CANONICALIZATION_AUDIT.md**
**For V3 checklist, see TDD_TODO_V3.md sections 0.8 and 0.9**
