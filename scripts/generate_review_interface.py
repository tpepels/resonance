#!/usr/bin/env python3
"""
Generate static HTML review interface for corpus validation using Strategy A.

This creates a multi-file HTML interface that fetches JSON assets on demand,
avoiding embedding large data in the HTML file to prevent agent context overflow.

Strategy A: Static JSON assets + fetch
- dist/index.json: Directory tree structure (small)
- dist/dir/<dir_id>.json: Per-directory contents (chunked)
- HTML loads index.json on start and fetches dir chunks on demand
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def create_stable_id(text: str) -> str:
    """Create a stable, URL-safe identifier from text."""
    # Use first 8 chars of SHA256 for stable ID
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]

def build_directory_tree(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Build a hierarchical directory tree structure."""
    tree = {"directories": [], "summary": bundle["corpus_summary"]}

    for dir_info in bundle["directory_tree"]:
        dir_path = dir_info["dir_path"]
        dir_id = create_stable_id(dir_path)

        # Get directory state
        expected_states = bundle.get("expected_outcomes", {}).get("states", {})
        state_info = expected_states.get(dir_path, {})
        state = state_info.get("state", "PENDING") if state_info else "PENDING"

        tree["directories"].append({
            "id": dir_id,
            "path": dir_path,
            "state": state,
            "audio_files": dir_info["audio_files"],
            "total_files": dir_info["total_files"],
            "total_size": dir_info["total_size"],
            "has_cover_art": dir_info.get("has_cover_art", False),
            "has_extras": dir_info.get("has_extras", False)
        })

    return tree

def build_directory_details(bundle: Dict[str, Any], dir_path: str) -> Dict[str, Any]:
    """Build detailed data for a specific directory."""
    dir_info = None
    for d in bundle["directory_tree"]:
        if d["dir_path"] == dir_path:
            dir_info = d
            break

    if not dir_info:
        return {"error": "Directory not found"}

    # Get expected state and tags
    expected_states = bundle.get("expected_outcomes", {}).get("states", {})
    expected_tags = bundle.get("expected_outcomes", {}).get("tags", [])
    decisions = bundle.get("expected_outcomes", {}).get("decisions", {})

    state_info = expected_states.get(dir_path, {})
    # expected_tags is a list, not a dict - handle empty case
    tags_info = {}

    # Build track list
    tracks = []
    for file_info in dir_info["files"]:
        if file_info["is_audio"]:
            track_path = file_info["path"]
            # expected_tags is currently a list (empty), so no track tags available
            track_tags = {}

            tracks.append({
                "path": track_path,
                "filename": Path(track_path).name,
                "size": file_info["size"],
                "duration": file_info["audio_info"]["duration"],
                "permissions": file_info["permissions"],
                "expected_tags": track_tags,
                "has_mapping": bool(track_tags)
            })

    return {
        "path": dir_path,
        "state": state_info.get("state", "PENDING") if state_info else "PENDING",
        "state_info": state_info,
        "tags_info": tags_info,
        "decisions": decisions.get(dir_path, {}),
        "tracks": sorted(tracks, key=lambda t: t["filename"]),
        "summary": {
            "audio_files": dir_info["audio_files"],
            "total_files": dir_info["total_files"],
            "total_size": dir_info["total_size"],
            "has_cover_art": dir_info.get("has_cover_art", False),
            "has_extras": dir_info.get("has_extras", False)
        }
    }

def generate_html(bundle: Dict[str, Any]) -> str:
    """Generate the HTML file with 3-column layout."""
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resonance Real Corpus Review</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px;
            background: #f8f9fa;
            line-height: 1.5;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 2.5em; }}
        .header .subtitle {{ opacity: 0.9; font-size: 1.1em; }}
        .corpus-stats {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9em;
            margin-top: 20px;
        }}

        /* Control panel */
        .control-panel {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            min-width: 200px;
        }}
        .control-group label {{
            font-weight: 600;
            margin-bottom: 5px;
            color: #555;
            font-size: 0.9em;
        }}
        .control-group input, .control-group select {{
            padding: 8px 12px;
            border: 2px solid #e1e5e9;
            border-radius: 6px;
            font-size: 14px;
        }}

        /* Main layout - 3 columns */
        .main-layout {{
            display: grid;
            grid-template-columns: 350px 1fr 400px;
            gap: 20px;
            height: calc(100vh - 300px);
        }}

        /* Directory Tree */
        .tree-panel {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .tree-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            font-weight: 600;
            color: #333;
        }}
        .tree-container {{
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }}
        .tree-node {{
            margin-bottom: 5px;
        }}
        .tree-item {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        .tree-item:hover {{ background: #f8f9fa; }}
        .tree-item.selected {{ background: #e3f2fd; border-left: 3px solid #2196f3; }}
        .tree-item-icon {{
            width: 16px;
            height: 16px;
            margin-right: 8px;
            opacity: 0.6;
        }}
        .tree-item-text {{
            flex: 1;
            font-size: 0.9em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .tree-item-count {{
            font-size: 0.8em;
            color: #666;
            margin-left: 8px;
        }}
        .tree-item-state {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            margin-left: 8px;
        }}
        .state-applied {{ background: #d4edda; color: #155724; }}
        .state-jailed {{ background: #fff3cd; color: #856404; }}
        .state-pending {{ background: #d1ecf1; color: #0c5460; }}

        /* Directory Contents */
        .content-panel {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .content-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .breadcrumb {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }}
        .breadcrumb span {{
            cursor: pointer;
            color: #007bff;
        }}
        .breadcrumb span:hover {{ text-decoration: underline; }}
        .content-controls {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }}
        .sort-select {{
            padding: 4px 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.8em;
        }}
        .content-container {{
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }}
        .track-item {{
            display: flex;
            align-items: center;
            padding: 10px 12px;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .track-item:hover {{ background: #f8f9fa; border-color: #007bff; }}
        .track-item.selected {{ background: #e3f2fd; border-color: #2196f3; }}
        .track-icon {{ margin-right: 10px; opacity: 0.6; }}
        .track-info {{ flex: 1; }}
        .track-filename {{ font-weight: 500; font-size: 0.9em; margin-bottom: 2px; }}
        .track-details {{ font-size: 0.8em; color: #666; }}
        .track-badges {{
            display: flex;
            gap: 5px;
        }}
        .badge {{
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 0.7em;
            font-weight: 600;
        }}
        .badge-mapped {{ background: #d4edda; color: #155724; }}
        .badge-missing {{ background: #f8d7da; color: #721c24; }}

        /* Detail Inspector */
        .detail-panel {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .detail-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            font-weight: 600;
        }}
        .detail-container {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}
        .detail-section {{
            margin-bottom: 20px;
        }}
        .detail-section h4 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 1em;
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 5px;
        }}
        .detail-path {{
            font-family: monospace;
            font-size: 0.9em;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 10px;
            word-break: break-all;
        }}
        .tag-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .tag-table th, .tag-table td {{
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }}
        .tag-table th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        .tag-key {{ font-family: monospace; }}
        .tag-value {{ font-family: monospace; color: #007bff; }}
        .empty-state {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 20px;
        }}

        /* Loading and error states */
        .loading {{ text-align: center; padding: 20px; color: #666; }}
        .error {{ text-align: center; padding: 20px; color: #dc3545; }}

        /* Responsive */
        @media (max-width: 1200px) {{
            .main-layout {{ grid-template-columns: 300px 1fr 350px; }}
        }}
        @media (max-width: 900px) {{
            .main-layout {{ grid-template-columns: 1fr; height: auto; }}
            .control-panel {{ flex-direction: column; align-items: stretch; }}
            .control-group {{ min-width: auto; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Resonance Real Corpus Review</h1>
            <div class="subtitle">Manual review interface for directory canonicalness</div>
            <div class="corpus-stats">
                Generated: {bundle["_generated_at"]}<br>
                Total Files: {bundle["corpus_summary"]["total_files"]} |
                Audio Tracks: {bundle["corpus_summary"]["audio_files"]} |
                Directories: {bundle["corpus_summary"]["total_directories"]} |
                Max Depth: 2
            </div>
        </div>

        <div class="control-panel">
            <div class="control-group">
                <label for="searchFilter">Search:</label>
                <input type="text" id="searchFilter" placeholder="Path, artist, album...">
            </div>
            <div class="control-group">
                <label for="stateFilter">State Filter:</label>
                <select id="stateFilter">
                    <option value="">All States</option>
                    <option value="APPLIED">APPLIED</option>
                    <option value="JAILED">JAILED</option>
                    <option value="PENDING">PENDING</option>
                </select>
            </div>
            <div class="control-group">
                <label for="trackFilter">Track Filter:</label>
                <select id="trackFilter">
                    <option value="">All Tracks</option>
                    <option value="mapped">Mapped Only</option>
                    <option value="unmapped">Unmapped Only</option>
                </select>
            </div>
        </div>

        <div class="main-layout">
            <div class="tree-panel">
                <div class="tree-header">Directory Tree</div>
                <div class="tree-container" id="directoryTree">
                    <div class="loading">Loading directory tree...</div>
                </div>
            </div>

            <div class="content-panel">
                <div class="content-header">
                    <div class="breadcrumb" id="breadcrumb">Select a directory</div>
                    <div class="content-controls">
                        <select class="sort-select" id="sortSelect">
                            <option value="filename">Sort by Filename</option>
                            <option value="size">Sort by Size</option>
                            <option value="duration">Sort by Duration</option>
                        </select>
                    </div>
                </div>
                <div class="content-container" id="directoryContent">
                    <div class="empty-state">Select a directory from the tree to view its contents</div>
                </div>
            </div>

            <div class="detail-panel">
                <div class="detail-header" id="detailHeader">Detail Inspector</div>
                <div class="detail-container" id="detailContent">
                    <div class="empty-state">Select a track to view details</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global state
        let directoryTree = null;
        let currentDirectory = null;
        let currentTrack = null;
        let filteredDirectories = [];

        // Initialize the application
        async function init() {{
            try {{
                // Load directory tree
                const response = await fetch('index.json');
                directoryTree = await response.json();

                // Set up event listeners
                document.getElementById('searchFilter').addEventListener('input', applyFilters);
                document.getElementById('stateFilter').addEventListener('change', applyFilters);
                document.getElementById('trackFilter').addEventListener('change', applyFilters);
                document.getElementById('sortSelect').addEventListener('change', () => {{
                    if (currentDirectory) renderDirectoryContent(currentDirectory);
                }});

                // Render initial tree
                applyFilters();
            }} catch (error) {{
                console.error('Failed to initialize:', error);
                document.getElementById('directoryTree').innerHTML = '<div class="error">Failed to load directory tree</div>';
            }}
        }}

        // Apply filters to directory tree
        function applyFilters() {{
            const searchTerm = document.getElementById('searchFilter').value.toLowerCase();
            const stateFilter = document.getElementById('stateFilter').value;

            filteredDirectories = directoryTree.directories.filter(dir => {{
                // State filter
                if (stateFilter && dir.state !== stateFilter) return false;

                // Search filter
                if (searchTerm && !dir.path.toLowerCase().includes(searchTerm)) return false;

                return true;
            }});

            renderDirectoryTree();
        }}

        // Render directory tree
        function renderDirectoryTree() {{
            const container = document.getElementById('directoryTree');

            if (filteredDirectories.length === 0) {{
                container.innerHTML = '<div class="empty-state">No directories match the current filters</div>';
                return;
            }}

            let html = '';
            filteredDirectories.forEach(dir => {{
                const isSelected = currentDirectory && currentDirectory.path === dir.path;
                const stateClass = `state-${{dir.state.toLowerCase()}}`;

                html += `<div class="tree-node">
                    <div class="tree-item ${{isSelected ? 'selected' : ''}}" onclick="selectDirectory('${{dir.id}}')">
                        <div class="tree-item-icon">📁</div>
                        <div class="tree-item-text" title="${{dir.path}}">${{dir.path.split('/').pop()}}</div>
                        <div class="tree-item-count">${{dir.audio_files}}</div>
                        <div class="tree-item-state ${{stateClass}}">${{dir.state}}</div>
                    </div>
                </div>`;
            }});

            container.innerHTML = html;
        }}

        // Select a directory
        async function selectDirectory(dirId) {{
            try {{
                const dir = directoryTree.directories.find(d => d.id === dirId);
                if (!dir) return;

                // Fetch directory details
                const response = await fetch(`dir/${{dirId}}.json`);
                const details = await response.json();

                currentDirectory = details;
                currentTrack = null;

                renderDirectoryContent(details);
                updateBreadcrumb(details.path);
                updateDetailPanel();

                // Update tree selection
                document.querySelectorAll('.tree-item').forEach(item => {{
                    item.classList.remove('selected');
                }});
                event.currentTarget.classList.add('selected');

            }} catch (error) {{
                console.error('Failed to load directory:', error);
                document.getElementById('directoryContent').innerHTML = '<div class="error">Failed to load directory details</div>';
            }}
        }}

        // Render directory content
        function renderDirectoryContent(dirDetails) {{
            const container = document.getElementById('directoryContent');
            const sortBy = document.getElementById('sortSelect').value;
            const trackFilter = document.getElementById('trackFilter').value;

            let tracks = [...dirDetails.tracks];

            // Apply track filter
            if (trackFilter === 'mapped') {{
                tracks = tracks.filter(t => t.has_mapping);
            }} else if (trackFilter === 'unmapped') {{
                tracks = tracks.filter(t => !t.has_mapping);
            }}

            // Sort tracks
            tracks.sort((a, b) => {{
                switch (sortBy) {{
                    case 'size':
                        return b.size - a.size;
                    case 'duration':
                        return b.duration - a.duration;
                    case 'filename':
                    default:
                        return a.filename.localeCompare(b.filename);
                }}
            }});

            if (tracks.length === 0) {{
                container.innerHTML = '<div class="empty-state">No tracks match the current filters</div>';
                return;
            }}

            let html = '';
            tracks.forEach(track => {{
                const isSelected = currentTrack && currentTrack.path === track.path;
                const badgeClass = track.has_mapping ? 'badge-mapped' : 'badge-missing';
                const badgeText = track.has_mapping ? 'mapped' : 'missing tags';

                html += `<div class="track-item ${{isSelected ? 'selected' : ''}}" onclick="selectTrack('${{track.path}}')">
                    <div class="track-icon">🎵</div>
                    <div class="track-info">
                        <div class="track-filename">${{track.filename}}</div>
                        <div class="track-details">
                            ${{formatFileSize(track.size)}} • ${{formatDuration(track.duration)}}
                            <div class="track-badges">
                                <span class="badge ${{badgeClass}}">${{badgeText}}</span>
                            </div>
                        </div>
                    </div>
                </div>`;
            }});

            container.innerHTML = html;
        }}

        // Select a track
        function selectTrack(trackPath) {{
            if (!currentDirectory) return;

            currentTrack = currentDirectory.tracks.find(t => t.path === trackPath);
            updateDetailPanel();

            // Update track selection
            document.querySelectorAll('.track-item').forEach(item => {{
                item.classList.remove('selected');
            }});
            event.currentTarget.classList.add('selected');
        }}

        // Update breadcrumb
        function updateBreadcrumb(path) {{
            const breadcrumb = document.getElementById('breadcrumb');
            const parts = path.split('/');
            let currentPath = '';

            const links = parts.map((part, index) => {{
                currentPath += (index > 0 ? '/' : '') + part;
                const isLast = index === parts.length - 1;
                return isLast ? part : `<span onclick="navigateToPath('${{currentPath}}')">${{part}}</span>`;
            }});

            breadcrumb.innerHTML = links.join(' / ');
        }}

        // Update detail panel
        function updateDetailPanel() {{
            const header = document.getElementById('detailHeader');
            const container = document.getElementById('detailContent');

            if (!currentTrack) {{
                header.textContent = 'Detail Inspector';
                container.innerHTML = '<div class="empty-state">Select a track to view details</div>';
                return;
            }}

            header.textContent = `Track Details: ${{currentTrack.filename}}`;

            let html = `<div class="detail-section">
                <h4>Original Path</h4>
                <div class="detail-path">${{currentTrack.path}}</div>
            </div>`;

            if (currentTrack.expected_tags && Object.keys(currentTrack.expected_tags).length > 0) {{
                html += `<div class="detail-section">
                    <h4>Expected Tags</h4>
                    <table class="tag-table">
                        <thead>
                            <tr>
                                <th>Key</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>`;

                for (const [key, value] of Object.entries(currentTrack.expected_tags)) {{
                    html += `<tr>
                        <td class="tag-key">${{key}}</td>
                        <td class="tag-value">${{value}}</td>
                    </tr>`;
                }}

                html += `</tbody></table></div>`;
            }} else {{
                html += `<div class="detail-section">
                    <h4>Expected Tags</h4>
                    <div class="empty-state">No expected tags available</div>
                </div>`;
            }}

            html += `<div class="detail-section">
                <h4>Directory State</h4>
                <div>State: <strong>${{currentDirectory.state}}</strong></div>
                <div>Tracks: ${{currentDirectory.summary.audio_files}}</div>
                <div>Total Size: ${{formatFileSize(currentDirectory.summary.total_size)}}</div>
            </div>`;

            container.innerHTML = html;
        }}

        // Utility functions
        function formatFileSize(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }}

        function formatDuration(seconds) {{
            if (!seconds) return 'Unknown';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${{mins}}:${{secs.toString().padStart(2, '0')}}`;
        }}

        function navigateToPath(path) {{
            // This would require finding the directory by path
            console.log('Navigate to:', path);
        }}

        // Initialize on page load
        window.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>'''

    return html

def main():
    """Main entry point."""
    print("Generating HTML review interface (Strategy A)...")

    # Load the review bundle
    bundle_path = Path("review_bundle.json")
    if not bundle_path.exists():
        raise FileNotFoundError("review_bundle.json not found. Run generate_review_bundle.py first.")

    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    # Create output directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)

    # Generate directory tree index
    print("Generating directory tree index...")
    tree_data = build_directory_tree(bundle)
    with open(dist_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(tree_data, f, separators=(',', ':'))

    # Generate per-directory JSON files
    print("Generating per-directory JSON files...")
    dir_dir = dist_dir / "dir"
    dir_dir.mkdir(exist_ok=True)

    for dir_info in bundle["directory_tree"]:
        dir_path = dir_info["dir_path"]
        dir_id = create_stable_id(dir_path)

        details = build_directory_details(bundle, dir_path)
        with open(dir_dir / f"{dir_id}.json", 'w', encoding='utf-8') as f:
            json.dump(details, f, separators=(',', ':'))

    # Generate HTML
    print("Generating HTML interface...")
    html_content = generate_html(bundle)
    output_path = dist_dir / "real_corpus_review.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Generate manifest
    print("Generating manifest...")
    manifest = {
        "generated_at": bundle["_generated_at"],
        "input_hashes": bundle["input_file_hashes"],
        "output_hashes": {
            "index.json": compute_sha256(dist_dir / "index.json"),
            "real_corpus_review.html": compute_sha256(output_path),
        }
    }

    # Add directory JSON hashes
    for dir_info in bundle["directory_tree"]:
        dir_path = dir_info["dir_path"]
        dir_id = create_stable_id(dir_path)
        manifest["output_hashes"][f"dir/{dir_id}.json"] = compute_sha256(dir_dir / f"{dir_id}.json")

    with open(dist_dir / "manifest.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated files in {dist_dir}:")
    print(f"  - real_corpus_review.html ({len(html_content)} chars)")
    print(f"  - index.json ({len(json.dumps(tree_data, separators=(',', ':')))} chars)")
    print(f"  - {len(bundle['directory_tree'])} directory JSON files")
    print(f"  - manifest.json")

if __name__ == "__main__":
    main()
