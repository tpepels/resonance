#!/usr/bin/env python3
"""
Simple HTML interface generator.
"""

import json
from pathlib import Path

def main():
    """Generate HTML interface."""
    # Load bundle
    with open('review_bundle.json', 'r') as f:
        bundle = json.load(f)
    
    # Create dist directory
    Path('dist').mkdir(exist_ok=True)
    
    # Generate simple HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Resonance Corpus Review</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 20px; border-radius: 8px; }}
        .controls {{ margin: 20px 0; }}
        .directory {{ border: 1px solid #ddd; margin: 10px 0; padding: 10px; border-radius: 4px; }}
        .track {{ background: #f9f9f9; margin: 5px 0; padding: 8px; border-left: 3px solid #4CAF50; }}
        .btn {{ background: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }}
        .notes {{ width: 100%; height: 60px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Resonance V4 - Corpus Review Interface</h1>
        <p>Generated: {bundle['_generated_at']}</p>
        <p>Total Files: {bundle['corpus_summary']['total_files']} | Audio Tracks: {bundle['corpus_summary']['audio_files']} | Directories: {bundle['corpus_summary']['total_directories']}</p>
    </div>
    
    <div class="controls">
        <input type="text" id="search" placeholder="Search paths..." onkeyup="filterDirectories()">
        <select id="stateFilter" onchange="filterDirectories()">
            <option value="">All States</option>
            <option value="APPLIED">APPLIED</option>
            <option value="JAILED">JAILED</option>
            <option value="PENDING">PENDING</option>
        </select>
        <button class="btn" onclick="exportNotes()">Export Notes</button>
        <button class="btn" onclick="approve()">Approve Corpus</button>
    </div>
    
    <div id="directories"></div>

    <script>
        const BUNDLE = {json.dumps(bundle, separators=(',', ':'))};
        let notes = {{}};
        let filteredDirs = BUNDLE.directory_tree;
        
        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }}
        
        function getState(dirPath) {{
            const states = BUNDLE.expected_outcomes.states;
            return states[dirPath] ? states[dirPath].state || 'APPLIED' : 'PENDING';
        }}
        
        function renderDirectories() {{
            const container = document.getElementById('directories');
            container.innerHTML = '';
            
            filteredDirs.forEach((dir, index) => {{
                const state = getState(dir.dir_path);
                const html = `
                    <div class="directory">
                        <h3>${{dir.dir_path}}</h3>
                        <p><strong>State:</strong> ${{state}} | <strong>Files:</strong> ${{dir.total_files}} | <strong>Tracks:</strong> ${{dir.audio_files}} | <strong>Size:</strong> ${{formatBytes(dir.total_size)}}</p>
                        ${{dir.has_cover_art ? '<p>🎨 Cover Art</p>' : ''}}
                        ${{dir.has_extras ? '<p>📄 Extras</p>' : ''}}
                        <div>
                            <h4>Audio Tracks:</h4>
                            ${{dir.files.filter(f => f.is_audio).map(track => `
                                <div class="track">
                                    <strong>${{track.path}}</strong><br>
                                    Size: ${{formatBytes(track.size)}} | Duration: ${{track.audio_info.duration || 0}}s | Perms: ${{track.permissions}}
                                </div>
                            `).join('')}}
                        </div>
                        <textarea class="notes" placeholder="Review notes..." onchange="saveNote('${{dir.dir_path}}', this.value)">${{notes[dir.dir_path] || ''}}</textarea>
                    </div>
                `;
                container.innerHTML += html;
            }});
        }}
        
        function filterDirectories() {{
            const search = document.getElementById('search').value.toLowerCase();
            const stateFilter = document.getElementById('stateFilter').value;
            
            filteredDirs = BUNDLE.directory_tree.filter(dir => {{
                const matchesSearch = !search || dir.dir_path.toLowerCase().includes(search);
                const matchesState = !stateFilter || getState(dir.dir_path) === stateFilter;
                return matchesSearch && matchesState;
            }});
            
            renderDirectories();
        }}
        
        function saveNote(path, note) {{
            notes[path] = note;
        }}
        
        function exportNotes() {{
            const data = {{
                _format: 'corpus_review_notes_v1',
                _exported_at: new Date().toISOString(),
                notes: notes,
                summary: {{
                    total_directories: filteredDirs.length,
                    with_notes: Object.keys(notes).length
                }}
            }};
            
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'CORPUS_REVIEW_NOTES.json';
            a.click();
        }}
        
        function approve() {{
            const name = prompt('Enter your name to approve the corpus:');
            if (!name) return;
            
            const data = {{
                _format: 'corpus_approval_v1',
                _approved_at: new Date().toISOString(),
                reviewer_name: name,
                input_file_hashes: BUNDLE.input_file_hashes,
                review_metadata: {{
                    total_directories_reviewed: filteredDirs.length,
                    total_tracks: BUNDLE.corpus_summary.audio_files
                }}
            }};
            
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'CORPUS_APPROVAL.json';
            a.click();
        }}
        
        // Initialize
        renderDirectories();
    </script>
</body>
</html>"""
    
    # Write file
    with open('dist/real_corpus_review.html', 'w') as f:
        f.write(html)
    
    print("✓ Simple HTML interface generated: dist/real_corpus_review.html")
    print(f"  - {len(bundle['directory_tree'])} directories")
    print(f"  - {len(bundle['tracks'])} tracks")

if __name__ == "__main__":
    main()
