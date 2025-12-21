"""Legacy V2 code - deprecated.

This module contains the V2 pipeline code that has been superseded by V3.
It is preserved for reference but is not used by the V3 core.

V2 code includes:
- TrackInfo/AlbumInfo models (core/models.py)
- metadata_reader service (reads tags into TrackInfo)
- release_search service (searches providers using AlbumInfo)
- prompt_service (user prompts for AlbumInfo)
- discogs/musicbrainz providers (return TrackInfo)

Status: CLOSED - No new V2 features will be added.

Migration path:
- Phase C.1/C.2 will rebuild providers using V3 DTOs (ProviderRelease, etc.)
- Offline provider mode deferred to post-V3
- Advanced canonical aliasing deferred to post-V3

See: TDD_TODO_V3.md Phase B.2 for V2 closure declaration
"""

__all__: list[str] = []  # Nothing exported - legacy code only
