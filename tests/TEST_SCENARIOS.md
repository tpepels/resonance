# Integration Test Scenarios

Real-world challenging cases for audio metadata organization.

## Test Categories

### 1. Multi-Artist Collaborations

**Challenge**: Multiple artists on same album, proper attribution

#### Test Case 1.1: Jazz Collaboration
- **Album**: "Getz/Gilberto" (1964)
- **Artists**: Stan Getz, João Gilberto
- **Variations**: "Stan Getz & João Gilberto", "Getz, Gilberto", "Getz/Gilberto"
- **Expected**: Should recognize as single album despite artist name variations
- **MusicBrainz ID**: `c4f86c97-d672-33d0-8f2c-a0a5bfdb2a7e`

#### Test Case 1.2: Electronic Duo
- **Album**: "Random Access Memories" (2013)
- **Artists**: Daft Punk (featuring various artists on different tracks)
- **Challenge**: Some tracks have "feat. Pharrell Williams", others "feat. Nile Rodgers"
- **Expected**: Album stays together under "Daft Punk"
- **MusicBrainz ID**: `1144319e-eacb-4d00-8eff-743345475e16`

### 2. Classical Music (Composer/Performer Structure)

**Challenge**: Separate composer from performer, handle multiple performers

#### Test Case 2.1: Bach Goldberg Variations
- **Composer**: Johann Sebastian Bach (variants: "J.S. Bach", "Bach, Johann Sebastian", "JS Bach")
- **Performers**:
  - Glenn Gould (1955 recording)
  - Glenn Gould (1981 recording)
  - András Schiff
  - Murray Perahia
- **Expected Path**: `Bach, Johann Sebastian/Goldberg Variations/Glenn Gould - 1955/`
- **Challenge**: Same work, different performers should be separate directories
- **MusicBrainz IDs**:
  - 1955: `b8a6ddd8-1f2e-4bff-b546-a65c5bfdb5a5`
  - 1981: `c86dd3df-d7ef-4c7b-80b0-1c7c2f9d5f8a`

#### Test Case 2.2: Beethoven Symphony with Orchestra
- **Composer**: Ludwig van Beethoven
- **Performers**:
  - Conductor: Herbert von Karajan
  - Orchestra: Berlin Philharmonic Orchestra
- **Work**: Symphony No. 9
- **Expected Path**: `Beethoven, Ludwig van/Symphony No. 9/Karajan, Herbert von; Berlin Philharmonic/`
- **Challenge**: Multiple performer credits (conductor + orchestra)

### 3. Artist Name Variants & Canonicalization

**Challenge**: Same artist with different name spellings/formats

#### Test Case 3.1: Icelandic Artist
- **Artist**: Björk
- **Variants**: "Bjork", "Björk Guðmundsdóttir", "Bjork Gudmundsdottir"
- **Album**: "Homogenic" (1997)
- **Expected**: All variants → canonical "Björk"
- **MusicBrainz ID**: `87c5dedd-371d-4a53-9f7f-80522fb7f3cb`

#### Test Case 3.2: The/No The Variants
- **Artist**: The Beatles
- **Variants**: "Beatles", "The Beatles", "Beatles, The"
- **Album**: "Abbey Road"
- **Expected**: All variants → canonical "The Beatles"
- **MusicBrainz ID**: `b8a7c51f-362c-4dcb-a259-bc6e0095f0a6`

#### Test Case 3.3: Name with Featuring
- **Track**: "Get Lucky"
- **Variants**:
  - "Daft Punk feat. Pharrell Williams"
  - "Daft Punk (feat. Pharrell Williams & Nile Rodgers)"
  - "Daft Punk featuring Pharrell Williams"
- **Expected**: Canonical artist = "Daft Punk" (featuring stripped)

### 4. Jazz Trios & Ensembles

**Challenge**: Trio/ensemble names vs individual artist credits

#### Test Case 4.1: Bill Evans Trio
- **Name Variants**:
  - "Bill Evans Trio"
  - "Bill Evans, Scott LaFaro, Paul Motian"
  - "The Bill Evans Trio"
- **Album**: "Sunday at the Village Vanguard" (1961)
- **Expected**: Canonical "Bill Evans Trio"
- **MusicBrainz ID**: `bfcc6d75-a6a5-4bc6-8282-47aec8531818`

#### Test Case 4.2: Keith Jarrett Trio
- **Name Variants**:
  - "Keith Jarrett Trio"
  - "Keith Jarrett, Gary Peacock, Jack DeJohnette"
  - "The Keith Jarrett Trio"
- **Album**: "Standards, Vol. 1"
- **Expected**: Canonical "Keith Jarrett Trio"

### 5. Multiple Releases of Same Album

**Challenge**: Different releases (remaster, deluxe, international) should be grouped or separated based on track matching

#### Test Case 5.1: Pink Floyd - Dark Side of the Moon
- **Original**: 1973, 10 tracks
- **2003 Remaster**: 10 tracks (same)
- **2011 Remaster**: 10 tracks + bonus tracks
- **Expected Behavior**:
  - If track fingerprints match: Same release
  - If different masters: Separate releases (but same artist/album path)
  - User should be prompted if uncertain
- **MusicBrainz IDs**:
  - Original: `f5093c06-23e3-404f-aeaa-40f72885ee3a`
  - 2003 Remaster: `4a0e9c30-3e1f-4e0e-a59d-1e0a6c0ea1d2`

#### Test Case 5.2: Japanese vs US Release
- **Album**: "Kind of Blue" - Miles Davis
- **US Release**: Standard track listing
- **Japanese Release**: May have bonus tracks or different order
- **Expected**: User prompted to choose which release, files stay together

### 6. Compilation Albums

**Challenge**: "Various Artists" albums should NOT mix with artist's solo work

#### Test Case 6.1: Movie Soundtrack
- **Album**: "Pulp Fiction OST"
- **Album Artist**: "Various Artists"
- **Track Artists**: Various (Urge Overkill, Chuck Berry, etc.)
- **Expected Path**: `Various Artists/Pulp Fiction OST/`
- **NOT**: Separate directories for each track artist

### 7. Edge Cases

#### Test Case 7.1: Artist with Special Characters
- **Artist**: "Sigur Rós"
- **Variants**: "Sigur Ros", "Sigur Rós", "Sigur-Ros"
- **Expected**: Canonical "Sigur Rós" (preserve correct unicode)

#### Test Case 7.2: Album with Disc Numbers
- **Album**: "The Wall" - Pink Floyd
- **Format**: 2 CDs, tracks numbered per-disc
- **Expected**: All tracks in same directory, preserve disc metadata

#### Test Case 7.3: Live Album with Date
- **Album**: "Sunday at the Village Vanguard"
- **Date**: June 25, 1961
- **Expected**: Date in metadata, but not necessarily in path

## Test Data Structure

For each test case, we need:

```
tests/fixtures/
├── multi_artist/
│   ├── getz_gilberto/
│   │   ├── 01-variant1.flac (artist: "Stan Getz & João Gilberto")
│   │   ├── 02-variant2.flac (artist: "Getz, Gilberto")
│   │   └── 03-variant3.flac (artist: "Getz/Gilberto")
│   └── expected.json (expected outcome)
├── classical/
│   ├── bach_goldberg_gould_1955/
│   └── bach_goldberg_gould_1981/
├── name_variants/
│   ├── bjork_homogenic/
│   └── beatles_abbeyroad/
├── trios/
│   ├── billevans_trio/
│   └── keithjarrett_trio/
├── multiple_releases/
│   ├── darkside_original/
│   └── darkside_remaster/
└── compilations/
    └── pulpfiction_ost/
```

## Test Assertions

Each test should verify:

1. ✅ **Fingerprinting succeeds** - All tracks get AcoustID fingerprints
2. ✅ **Canonical names applied** - Artist variants → single canonical form
3. ✅ **Release matching works** - Correct MusicBrainz/Discogs release identified
4. ✅ **Score is reasonable** - Match score >= threshold (0.6 for uncertain, 0.8 for auto)
5. ✅ **Files organized correctly** - Moved to expected directory structure
6. ✅ **Metadata enriched** - Title, artist, album filled from release
7. ✅ **Cache persists** - Re-running uses cached decision
8. ✅ **Source directory cleaned** - Original directory removed (if --delete-nonaudio)

## Mock vs Real API

**Strategy**:
- Use **real MusicBrainz/AcoustID** for test case design (verify IDs exist)
- Create **mock responses** for CI testing (fast, reproducible)
- Provide **`--use-real-api`** flag for integration testing against live services

## Success Criteria

Tests pass when:
- ✅ All 15+ test cases pass with mock data
- ✅ At least 5 test cases verified with real API (manual validation)
- ✅ Edge cases handled gracefully (no crashes)
- ✅ User prompts triggered when expected (uncertain matches)
- ✅ Auto-selection works for high-confidence matches
