# Resonance Audit & Documentation Index

**Last Updated:** 2025-12-21

---

## Current Documentation

### Primary Documents (Active)

1. **[CONSOLIDATED_AUDIT.md](CONSOLIDATED_AUDIT.md)** ⭐ **START HERE**
   - **Purpose:** Single source of truth for all audit information
   - **Contents:**
     - Test coverage analysis (483 tests)
     - Golden corpus status (26/26 scenarios)
     - Architectural compliance review
     - Critical gaps and safety issues
     - Prioritized recommendations
   - **Replaces:** AUDIT_SUMMARY.md, CANONICALIZATION_AUDIT.md, TEST_AUDIT.md, V3_TEST_AUDIT.md, GOLDEN_CORPUS_ROADMAP.md
   - **When to read:** Before starting V3 work, quarterly reviews, onboarding

2. **[TODO_REVIEW_V3.md](TODO_REVIEW_V3.md)** 🔍 **ARCHITECTURAL REVIEW**
   - **Purpose:** Technical debt and architectural compliance deep-dive
   - **Contents:**
     - 6 critical issues (dual architecture, composition root, planner purity)
     - 6 high-priority debt items
     - 6 medium/low priority items
     - Explicit non-issues (acceptable patterns)
   - **When to read:** Planning architectural refactors, code review prep

3. **[TDD_TODO_V3.md](TDD_TODO_V3.md)** 📋 **IMPLEMENTATION ROADMAP**
   - **Purpose:** V3 feature delivery checklist (DO NOT MODIFY during audit updates)
   - **Contents:**
     - Golden corpus implementation plan
     - Provider integration roadmap
     - Tag writing requirements
     - V3 definition of done
   - **When to read:** Daily implementation work, sprint planning

4. **[Resonance_DESIGN_SPEC.md](Resonance_DESIGN_SPEC.md)** 📐 **ARCHITECTURE SPEC**
   - **Purpose:** Authoritative architecture and design principles
   - **Contents:**
     - Pipeline invariants (scan → identify → resolve → plan → apply)
     - Purity boundaries
     - State machine transitions
     - Determinism requirements
   - **When to read:** Architectural decisions, new feature design

5. **[README.md](README.md)** 🚀 **PROJECT OVERVIEW**
   - **Purpose:** Getting started guide
   - **Contents:**
     - Installation instructions
     - Basic usage examples
     - Project goals
   - **When to read:** First-time setup, documentation reference

---

## Archived Documents

**Location:** `.archive/audits-2025-12-21/`

These documents have been **consolidated into CONSOLIDATED_AUDIT.md**. Archived for historical reference only.

- `AUDIT_SUMMARY.md` (Dec 21, 2025) - Golden corpus quick reference
- `CANONICALIZATION_AUDIT.md` (Dec 21, 2025) - Determinism analysis
- `TEST_AUDIT.md` (Dec 20, 2025) - Original unit test audit
- `V3_TEST_AUDIT.md` (Dec 21, 2025) - V3 DoD compliance check
- `GOLDEN_CORPUS_ROADMAP.md` (Dec 21, 2025) - Implementation quick reference

**Note:** If you need detailed historical context (e.g., "Why was scenario X deferred?"), refer to archived docs. Otherwise, use CONSOLIDATED_AUDIT.md.

---

## Document Hierarchy

```
Documentation Tree
├── CONSOLIDATED_AUDIT.md ⭐ Current state, gaps, recommendations
├── TODO_REVIEW_V3.md 🔍 Architectural debt analysis
├── TDD_TODO_V3.md 📋 Implementation roadmap (protected)
├── Resonance_DESIGN_SPEC.md 📐 Architecture spec
├── README.md 🚀 Getting started
└── .archive/audits-2025-12-21/ 📦 Historical audits
```

---

## Quick Reference: What to Read When

| Situation | Read This |
|-----------|-----------|
| **Starting V3 work** | CONSOLIDATED_AUDIT.md → TDD_TODO_V3.md |
| **Code review prep** | TODO_REVIEW_V3.md (architectural violations) |
| **Quarterly health check** | CONSOLIDATED_AUDIT.md (sections 1-3) |
| **Planning refactor** | TODO_REVIEW_V3.md + Resonance_DESIGN_SPEC.md |
| **Onboarding new dev** | README.md → CONSOLIDATED_AUDIT.md → Resonance_DESIGN_SPEC.md |
| **Investigating test failure** | CONSOLIDATED_AUDIT.md (section 1.2 - Golden Corpus) |
| **Adding new feature** | Resonance_DESIGN_SPEC.md + TODO_REVIEW_V3.md (check for violations) |
| **Sprint planning** | TDD_TODO_V3.md + CONSOLIDATED_AUDIT.md (section 6 - Recommendations) |

---

## Key Metrics (As of Dec 21, 2025)

| Metric | Value | Grade |
|--------|-------|-------|
| **Total Tests** | 483 | ✅ |
| **Golden Corpus Scenarios** | 26/26 (V3 target) | ✅ |
| **Determinism Score** | Excellent | 🟢 |
| **Crash Recovery Coverage** | 17% | 🔴 |
| **Schema Versioning Coverage** | 36% | 🔴 |
| **Overall Test Quality** | B- | 🟡 |
| **V3 Definition of Done** | 40% (1/5 complete) | ⚙️ |

**Stop-Ship Issues:** 6 (see CONSOLIDATED_AUDIT.md section 6.1)

---

## Maintenance Notes

### When to Update This Index

- After consolidating/archiving audit documents
- After major architectural changes (e.g., V2 visitor deprecation)
- Quarterly during V3 development

### When to Update CONSOLIDATED_AUDIT.md

- After adding golden corpus scenarios
- After implementing stop-ship fixes
- When test count changes significantly (>50 tests added/removed)
- Quarterly health checks

### Do NOT Update (Protected)

- **TDD_TODO_V3.md** - Only update during implementation work, not during audits
- **Resonance_DESIGN_SPEC.md** - Only update during architectural decisions

---

## Contact / Ownership

- **CONSOLIDATED_AUDIT.md:** Maintained by audit reviews (quarterly)
- **TODO_REVIEW_V3.md:** Architectural compliance reviews (as-needed)
- **TDD_TODO_V3.md:** Implementation team (daily)
- **Resonance_DESIGN_SPEC.md:** Architecture owner (rare updates)

---

**End of Index**
