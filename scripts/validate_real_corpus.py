#!/usr/bin/env python3
"""
Manual validation script for real-world corpus testing.
Runs Resonance on actual music directories and captures human-readable output
for manual validation of matching decisions.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any


def run_resonance_command(cmd: List[str], cwd: Path) -> str:
    """Run a Resonance command and return its output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        return f"Command: {' '.join(cmd)}\nExit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return f"Command: {' '.join(cmd)}\nTIMEOUT: Command took longer than 5 minutes\n"
    except Exception as e:
        return f"Command: {' '.join(cmd)}\nERROR: {e}\n"


def analyze_directory(
    directory: Path, repo_root: Path, state_db: Path | None = None, cache_db: Path | None = None
) -> Dict[str, Any]:
    """Analyze a music directory with Resonance and capture results."""
    analysis = {
        "directory": str(directory),
        "exists": directory.exists(),
        "is_dir": directory.is_dir() if directory.exists() else False,
    }

    if not directory.exists() or not directory.is_dir():
        analysis["error"] = "Directory does not exist or is not a directory"
        return analysis

    # Count audio files
    audio_extensions = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".wav"}
    audio_files = []
    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
            audio_files.append(str(file_path.relative_to(directory)))

    analysis["audio_files"] = audio_files
    analysis["audio_count"] = len(audio_files)

    if not audio_files:
        analysis["error"] = "No audio files found in directory"
        return analysis

    # Run Resonance commands using the CLI entry point with proper argument passing
    def make_resonance_cmd(cmd_name, *args):
        cmd_args = ["resonance", cmd_name] + list(args)
        if state_db:
            cmd_args.extend(["--state-db", str(state_db)])
        # Only add cache-db for commands that support it (resolve, not scan)
        if cache_db and cmd_name in ["resolve"]:
            cmd_args.extend(["--cache-db", str(cache_db)])
        return [
            sys.executable,
            "-c",
            f"import sys; sys.argv = {cmd_args!r}; from resonance.cli import main; main()",
        ]

    # Change to the music library root (parent of the album directory)
    library_root = directory.parent
    album_name = directory.name

    analysis["library_root"] = str(library_root)
    analysis["album_name"] = album_name
    if state_db:
        analysis["state_db"] = str(state_db)
    if cache_db:
        analysis["cache_db"] = str(cache_db)

    # Run scan command (finds and analyzes the directory)
    # Note: scan command operates on the library root, not individual albums
    scan_cmd = make_resonance_cmd("scan", ".")
    analysis["scan_output"] = run_resonance_command(scan_cmd, library_root)

    # Run resolve command (shows matching candidates)
    resolve_cmd = make_resonance_cmd("resolve", ".")
    analysis["resolve_output"] = run_resonance_command(resolve_cmd, library_root)

    # For plan command, we need a dir_id, so we'll skip it for now unless we can get the dir_id from scan
    analysis["plan_note"] = (
        "Plan command requires dir_id from successful scan. Run 'resonance scan --state-db <db> <album>' first to get dir_id, then 'resonance plan --dir-id <id> --state-db <db> <album>'"
    )

    return analysis


def main():
    parser = argparse.ArgumentParser(
        description="Manually validate Resonance decisions on real music directories"
    )
    parser.add_argument(
        "directories",
        nargs="+",
        help="Music directories to analyze (can be album folders or artist folders)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file for JSON results (default: print to stdout)"
    )
    parser.add_argument(
        "--state-db",
        type=Path,
        help="Path to Resonance state database (will be created if it doesn't exist)",
    )
    parser.add_argument("--cache-db", type=Path, help="Path to Resonance cache database (optional)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Path to Resonance repository root",
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if not (repo_root / "pyproject.toml").exists():
        print(f"Error: {repo_root} does not appear to be the Resonance repository root")
        sys.exit(1)

    results = []
    for dir_path_str in args.directories:
        dir_path = Path(dir_path_str).resolve()

        print(f"Analyzing: {dir_path}", file=sys.stderr)

        # If it's a file, analyze its directory
        if dir_path.is_file():
            dir_path = dir_path.parent

        # If directory contains audio files directly, analyze it
        # Otherwise, find subdirectories that contain audio files
        audio_extensions = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".wav"}
        has_audio = any(dir_path.rglob(f"*{ext}") for ext in audio_extensions)

        if has_audio:
            analysis = analyze_directory(dir_path, repo_root, args.state_db, args.cache_db)
            results.append(analysis)
            print(f"Completed analysis of {dir_path}", file=sys.stderr)
        else:
            # Look for album subdirectories
            album_dirs = []
            for subdir in dir_path.iterdir():
                if subdir.is_dir():
                    if any(subdir.rglob(f"*{ext}") for ext in audio_extensions):
                        album_dirs.append(subdir)

            if album_dirs:
                print(
                    f"Found {len(album_dirs)} album directories, analyzing first few...",
                    file=sys.stderr,
                )
                for album_dir in album_dirs[:3]:  # Limit to first 3 albums
                    analysis = analyze_directory(album_dir, repo_root, args.state_db, args.cache_db)
                    results.append(analysis)
                    print(f"Completed analysis of {album_dir}", file=sys.stderr)
            else:
                print(f"No audio files found in {dir_path} or its subdirectories", file=sys.stderr)

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
