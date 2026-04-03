typecheck:
	python -m mypy resonance

lint:
	python -m ruff check resonance

lint-fix:
	python -m ruff check resonance --fix

test-v1:
	pytest -m pipeline_v1

test-v2:
	pytest -m pipeline_v2

format:
	python -m ruff format resonance

corpus-extract:
	@echo "==> Extracting corpus metadata from real filesystem"
	@echo "    This updates tests/real_corpus/metadata.json from disk"
	@./scripts/extract_real_corpus.sh /tmp/corpus_extraction 2>/dev/null || echo "Extraction failed - check script and permissions"
	@python3 scripts/corpus_summary.py
	@echo "==> Corpus extraction complete!"

corpus-decide:
	@echo "==> Running REAL Resonance corpus decision workflow (authoritative, network required)"
	@echo "    This processes the full corpus using live provider APIs, records your decisions,"
	@echo "    and regenerates all expected outputs and review artifacts."
	@echo ""
	@if [ ! -f "tests/real_corpus/metadata.json" ]; then \
		echo "ERROR: tests/real_corpus/metadata.json missing. Run 'make corpus-extract' first."; \
		exit 1; \
	fi
	@echo "    Checking for required credentials..."
	@if [ -z "$$ACOUSTID_API_KEY" ]; then \
		echo "ERROR: ACOUSTID_API_KEY environment variable required (get from https://acoustid.org/)"; \
		exit 1; \
	fi
	@if [ -z "$$DISCOGS_TOKEN" ]; then \
		echo "ERROR: DISCOGS_TOKEN environment variable required (get from https://www.discogs.com/settings/developers)"; \
		exit 1; \
	fi
	@echo "    Counting directories in corpus..."
	@python3 -c "import json; data=json.load(open('tests/real_corpus/metadata.json')); audio_dirs=set(); [audio_dirs.add(f['path'].rsplit('/',1)[0]) for f in data['files'] if f.get('is_audio',False)]; print(f'Found {len(audio_dirs)} directories with audio files to process')"
	@echo ""
	@echo "    INTERACTIVE DECISION RECORDING:"
	@echo "    - You will be prompted for each unresolved directory"
	@echo "    - Type: number to select release, 's' to jail, 'mb:ID' or 'dg:ID' for custom IDs"
	@echo "    - Your decisions will be recorded to tests/real_corpus/prompt_replay.json"
	@echo "    - Press Ctrl+C to abort (replay file won't be saved)"
	@echo ""
	python3 scripts/corpus_decide_real_interactive.py
	@echo ""
	@echo "    REGENERATING REVIEW ARTIFACTS..."
	@echo "    Generating review bundle..."
	python3 scripts/generate_review_bundle.py
	@echo "    Generating HTML interface..."
	python3 scripts/generate_review_interface.py
	@echo ""
	@echo "==> Authoritative corpus decision complete!"
	@echo "    Next: Run 'make corpus-review' to inspect results"

corpus-review:
	@echo "==> Serving Resonance corpus review interface (read-only)"
	@echo "    Open: http://localhost:8080/real_corpus_review.html"
	@echo "    This serves the generated review interface for human inspection"
	@echo "    No files are modified - purely observational"
	@python3 -m http.server -d dist 8080

# Advanced/Offline workflow (hidden from primary docs)
corpus-decide-offline:
	@echo "==> ADVANCED: Running DETERMINISTIC offline corpus workflow"
	@echo "    This uses recorded decisions without network calls (for testing/reproduction)"
	@if [ ! -f "tests/real_corpus/metadata.json" ]; then \
		echo "ERROR: tests/real_corpus/metadata.json missing. Run 'make corpus-extract' first."; \
		exit 1; \
	fi
	@if [ ! -f "tests/real_corpus/prompt_replay.json" ]; then \
		echo "ERROR: tests/real_corpus/prompt_replay.json missing. Run 'make corpus-decide' first."; \
		exit 1; \
	fi
	@echo "    Processing ALL directories in metadata.json and regenerating review artifacts..."
	python3 scripts/corpus_decide.py
	@echo "    Generating review bundle..."
	python3 scripts/generate_review_bundle.py
	@echo "    Generating HTML interface..."
	python3 scripts/generate_review_interface.py
	@echo "==> Offline corpus decision complete!"

quality: lint typecheck

.PHONY: typecheck lint lint-fix format quality corpus-extract corpus-decide corpus-review
