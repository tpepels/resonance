The program has become way too large. I think I want a more basic set up.

A visitor pattern that deals with:
1a. Accepting a directory to determine (if it contains audio files):
   - Canonical artist/composer/performer (singular and short for each!!) -> Using fingerprinting of all files (can be multi--composer/performer (e.g. compilations)) to get the base info
   - Canonical album/release that is in the directory -> Using fingerprinting, number of tracks, track length and doing a search on discogs AND musicbrains to determine the 100% certain correct release. Files already in a directory cannot be split up, they must always be moved together. We can assume that each dir has 1 album. If not then the user has to fix it.
1b If the directory is uncertain, ask the user for input. If the user doesn't know, they can skip the directory after which it's no longer processed (even in subsequent runs, unless --unjail parameter is used). User should choose from a list (this is already implemented) or provide their own dg:xxx or mb:xxx as is already implemented. When asking the user for input they have to be able to navigate the album: show tracks with metadata and duration.
2. Accepting all files one by one in that directory to match them to the Artist/Album using fingerprinting. If the relase information from discogs/musicbrain can enrich or improve the metadata then we also update is (only if we're 100% sure)
3. Based on the results, moving the Album to Artist/Album/tracks*.*
    For classical music:
    - Composer/Performer/tracks*.* if all tracks are composed by one composer
    - Or Performer/tracks*.*
4. Deletes the origin directory if the files were moved. If there is non-audio in the directory then delete those files if --delete-nonaudio is set.

For multiple runs, caching should work as is implemented now, that's good. For daemon runs we should defer user promts and then have a --prompt-uncertain cli to answer the uncertainties.

This is still largely the aim of the code in this project, however it has grown too large to handle. There's too much legacy from earlier development when I didn't really know what I was building. Therefore, we can do two things, use the core, working code from this project to start a new architecture in a new directory (called Resonance). Or refactor this project, but make sure that all unused or legacy code is removed.