# Classical Music Organization Analysis

## Current Implementation (models.py:123-130)

```python
if self.is_classical:
    # Classical: Composer/Performer or just Performer
    if self.canonical_composer and self.canonical_performer:
        return Path(self.canonical_composer) / self.canonical_performer
    elif self.canonical_performer:
        return Path(self.canonical_performer)
    else:
        return None
```

## Issue Analysis

### Case 1: Single Composer (WORKS ✅)
**Example**: Bach Goldberg Variations by Glenn Gould
- `canonical_composer` = "Johann Sebastian Bach"
- `canonical_performer` = "Glenn Gould"
- `canonical_album` = "Goldberg Variations"

**Current Path**: `Johann Sebastian Bach/Glenn Gould`
**Expected Path**: `Johann Sebastian Bach/Goldberg Variations/Glenn Gould`
❌ **WRONG**: Missing work/album name!

### Case 2: No Single Composer (PARTIALLY WORKS ⚠️)
**Example**: Various composers, performed by Berlin Philharmonic
- `canonical_composer` = None (multiple composers)
- `canonical_performer` = "Berlin Philharmonic Orchestra; Herbert von Karajan"
- `canonical_album` = "Greatest Classical Hits"

**Current Path**: `Berlin Philharmonic Orchestra; Herbert von Karajan`
**Expected Path**: `Berlin Philharmonic Orchestra; Herbert von Karajan/Greatest Classical Hits`
OR
**Expected Path**: `Berlin Philharmonic Orchestra/Greatest Classical Hits`
❌ **WRONG**: Missing album name!

### Case 3: Compilation (Multiple Composers, Various Performers)
**Example**: "100 Best Classical Pieces"
- `canonical_composer` = None
- `canonical_performer` = None (or "Various Artists")
- `canonical_album` = "100 Best Classical Pieces"

**Current Path**: None (returns None!)
**Expected Path**: `Various Artists/100 Best Classical Pieces`
❌ **FAILS**: Returns None, won't organize!

## Correct Structure

According to TODO_new.md:
> For classical music:
> - Composer/Performer/tracks*.* if all tracks are composed by one composer
> - Or Performer/tracks*.*

**But this doesn't mention the album/work name!**

### Analysis of Real-World Cases

#### Real Classical Libraries Use:

**Case A: Single Composer, Single Work**
```
Bach, Johann Sebastian/
  Goldberg Variations/
    Glenn Gould - 1955/
      01 - Aria.flac
      02 - Variation 1.flac
    Glenn Gould - 1981/
      01 - Aria.flac
```

**Case B: Single Composer, Multiple Works (Album)**
```
Bach, Johann Sebastian/
  Well-Tempered Clavier/
    András Schiff/
      CD1/
        01 - Prelude 1.flac
      CD2/
        01 - Prelude 13.flac
```

**Case C: Multiple Composers (Compilation by Performer)**
```
Berlin Philharmonic Orchestra/
  Greatest Symphonies/
    01 - Beethoven - Symphony No. 5.flac
    02 - Mozart - Symphony No. 40.flac
```

OR

```
Karajan, Herbert von/
  20th Century Masterpieces/
    01 - Stravinsky - Rite of Spring.flac
    02 - Bartok - Concerto for Orchestra.flac
```

## Corrected Logic

### Option 1: Always Include Album/Work Name (RECOMMENDED)

```python
if self.is_classical:
    if self.canonical_composer:
        # Single composer: Composer/Album/Performer
        if self.canonical_album and self.canonical_performer:
            return Path(self.canonical_composer) / self.canonical_album / self.canonical_performer
        elif self.canonical_album:
            # No specific performer: Composer/Album
            return Path(self.canonical_composer) / self.canonical_album
        elif self.canonical_performer:
            # No album name: Composer/Performer
            return Path(self.canonical_composer) / self.canonical_performer
    else:
        # Multiple composers: Performer/Album
        if self.canonical_performer and self.canonical_album:
            return Path(self.canonical_performer) / self.canonical_album
        elif self.canonical_performer:
            # No album: just Performer
            return Path(self.canonical_performer)
        elif self.canonical_album:
            # No performer: Various Artists/Album
            return Path("Various Artists") / self.canonical_album
```

### Option 2: Match TODO_new.md Literally

TODO says:
- "Composer/Performer/tracks*.*" - 2 levels
- "Or Performer/tracks*.*" - 1 level

But this seems wrong for real libraries because:
1. Same performer can have multiple albums
2. Same work can have multiple performers
3. Need to separate them somehow

**CONCLUSION**: TODO_new.md is ambiguous about album/work name placement!

## Recommendation

Need to clarify with user:

### Question 1: Single Composer Case
Which structure?
A. `Composer/Album/Performer/` (3 levels) - **RECOMMENDED**
   Example: `Bach/Goldberg Variations/Glenn Gould/`

B. `Composer/Performer/` (2 levels) - **TODO_new.md literal**
   Example: `Bach/Glenn Gould/`
   Problem: All Bach recordings by Gould mixed together!

### Question 2: Multiple Composer Case
Which structure?
A. `Performer/Album/` (2 levels) - **RECOMMENDED**
   Example: `Berlin Philharmonic/Greatest Symphonies/`

B. `Performer/` (1 level) - **TODO_new.md literal**
   Example: `Berlin Philharmonic/`
   Problem: All albums mixed together!

### Question 3: Compilation Case (No clear performer)
What to do with "100 Best Classical Pieces"?
A. `Various Artists/Album/` - **RECOMMENDED**
B. Treat as non-classical?
C. Use first track's performer?

## My Proposed Fix

Based on real-world classical library organization:

```python
if self.is_classical:
    # Case 1: Single composer (most classical music)
    if self.canonical_composer:
        if self.canonical_album and self.canonical_performer:
            # Composer/Work/Performer
            return Path(self.canonical_composer) / self.canonical_album / self.canonical_performer
        elif self.canonical_album:
            # Composer/Work (no specific performer credited)
            return Path(self.canonical_composer) / self.canonical_album
        elif self.canonical_performer:
            # Composer/Performer (no work name - rare)
            return Path(self.canonical_composer) / self.canonical_performer
        else:
            # Just composer (very rare, maybe singles)
            return Path(self.canonical_composer)

    # Case 2: No single composer (compilations, multi-composer albums)
    else:
        if self.canonical_performer and self.canonical_album:
            # Performer/Album
            return Path(self.canonical_performer) / self.canonical_album
        elif self.canonical_performer:
            # Just performer (rare)
            return Path(self.canonical_performer)
        elif self.canonical_album:
            # Various Artists/Album
            return Path("Various Artists") / self.canonical_album
        else:
            # Cannot organize
            return None
```

This gives:
- ✅ Separates different works by same composer/performer
- ✅ Handles compilations properly
- ✅ Falls back gracefully when info is missing
- ✅ Matches how real classical libraries are organized

## Action Required

**Need user confirmation on structure before implementing!**

Current TODO_new.md says literally "Composer/Performer" or "Performer", but this doesn't match real-world needs.
