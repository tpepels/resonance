#!/usr/bin/env python3
"""
Generate review_bundle.json for human review of corpus mappings.

This script deterministically merges the five corpus artifacts to create
a single review bundle that can be embedded in an HTML interface.

The review bundle is a release gate artifact that must be reproducible
and auditable. Any changes to the source files will be detected via
SHA256 hashes.
"""

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Corpus artifact files (V3.1 snapshot tests)
CORPUS_ARTIFACTS = [
    "tests/real_corpus/metadata.json",
    "tests/real_corpus/expected_state.json", 
    "tests/real_corpus/expected_layout.json",
    "tests/real_corpus/expected_tags.json",
    "tests/real_corpus/decisions.json"
]

def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_json_safe(file_path: Path) -> Dict[str, Any]:
    """Load JSON file safely with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load {file_path}: {e}")
        return {}

def extract_directory_tree(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract directory tree structure from metadata."""
    directories = []
    
    if 'files' not in metadata:
        return directories
    
    # Group files by directory
    dir_map = {}
    for file_info in metadata['files']:
        path = file_info['path']
        dir_path = str(Path(path).parent)
        
        if dir_path not in dir_map:
            dir_map[dir_path] = {
                'dir_path': dir_path,
                'files': [],
                'total_files': 0,
                'audio_files': 0,
                'total_size': 0,
                'has_cover_art': False,
                'has_extras': False
            }
        
        dir_info = dir_map[dir_path]
        dir_info['files'].append(file_info)
        dir_info['total_files'] += 1
        dir_info['total_size'] += file_info.get('size', 0)
        
        if file_info.get('is_audio', False):
            dir_info['audio_files'] += 1
        
        # Check for extras
        if 'cover' in path.lower() or 'front' in path.lower():
            dir_info['has_cover_art'] = True
        elif not file_info.get('is_audio', False):
            dir_info['has_extras'] = True
    
    # Convert to list and sort
    directories = list(dir_map.values())
    directories.sort(key=lambda d: d['dir_path'].lower())
    
    return directories

def create_review_bundle() -> Dict[str, Any]:
    """Create the complete review bundle."""
    
    # Verify all artifact files exist
    missing_files = []
    for artifact_path in CORPUS_ARTIFACTS:
        if not Path(artifact_path).exists():
            missing_files.append(artifact_path)
    
    if missing_files:
        raise FileNotFoundError(f"Missing corpus artifacts: {missing_files}")
    
    # Compute hashes of all input files
    file_hashes = {}
    for artifact_path in CORPUS_ARTIFACTS:
        file_path = Path(artifact_path)
        file_hashes[artifact_path] = compute_sha256(file_path)
    
    # Load all artifacts
    metadata = load_json_safe(Path(CORPUS_ARTIFACTS[0]))
    expected_state = load_json_safe(Path(CORPUS_ARTIFACTS[1]))
    expected_layout = load_json_safe(Path(CORPUS_ARTIFACTS[2]))
    expected_tags = load_json_safe(Path(CORPUS_ARTIFACTS[3]))
    decisions = load_json_safe(Path(CORPUS_ARTIFACTS[4]))
    
    # Extract directory tree
    directories = extract_directory_tree(metadata)
    
    # Create comprehensive track list for review
    tracks = []
    for file_info in metadata.get('files', []):
        if file_info.get('is_audio', False):
            track = {
                'original_path': file_info['path'],
                'file_size': file_info.get('size', 0),
                'is_audio': True,
                'audio_info': file_info.get('audio_info', {}),
                'permissions': file_info.get('permissions', ''),
            }
            tracks.append(track)
    
    # Create review bundle
    bundle = {
        '_format': 'corpus_review_bundle_v1',
        '_generated_at': datetime.now(timezone.utc).isoformat(),
        '_generation_info': {
            'generator': 'scripts/generate_review_bundle.py',
            'purpose': 'Human review interface for V4 corpus validation',
            'governance': 'V3.1 release gate artifact - do not modify V3.1 snapshots'
        },
        'input_file_hashes': file_hashes,
        'corpus_summary': {
            'total_files': metadata.get('_total_files', 0),
            'audio_files': metadata.get('_audio_files', 0),
            'source_path': metadata.get('_source_path', ''),
            'extraction_time': metadata.get('_extraction_time', ''),
            'total_directories': len(directories)
        },
        'directory_tree': directories,
        'tracks': tracks,
        'expected_outcomes': {
            'states': expected_state.get('states', {}),
            'summary': expected_state.get('summary', {}),
            'layout': expected_layout.get('files', []),
            'tags': expected_tags.get('tracks', []),
            'decisions': decisions.get('decisions', {})
        },
        'review_metadata': {
            'determinism_guarantee': 'SHA256 hashes of all input files recorded for audit',
            'offline_requirement': 'This bundle contains all data needed for offline review',
            'approval_invalidation': 'Approval becomes invalid if any input file hash changes',
            'governance_notes': 'V3.1 artifacts are frozen and must not be modified'
        }
    }
    
    return bundle

def main():
    """Main entry point."""
    print("Generating corpus review bundle...")
    
    try:
        bundle = create_review_bundle()
        
        # Write bundle to file
        output_path = Path("review_bundle.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Review bundle generated: {output_path}")
        print(f"  - {len(bundle['directory_tree'])} directories")
        print(f"  - {len(bundle['tracks'])} audio tracks")
        print(f"  - {bundle['corpus_summary']['total_files']} total files")
        print(f"  - Generated at: {bundle['_generated_at']}")
        
        # Print file hashes for audit trail
        print("\nInput file SHA256 hashes (for audit):")
        for path, hash_value in bundle['input_file_hashes'].items():
            print(f"  {path}: {hash_value}")
            
    except Exception as e:
        print(f"Error generating review bundle: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
