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

corpus-decide-offline:
	@echo "==> Running DETERMINISTIC offline corpus workflow (cached/review tooling path)"
	@if [ ! -f "tests/real_corpus/metadata.json" ]; then \
		echo "ERROR: tests/real_corpus/metadata.json missing. Run 'make corpus-extract' first."; \
		exit 1; \
	fi
	@echo "    Counting directories in corpus..."
	@python3 -c "import json; data=json.load(open('tests/real_corpus/metadata.json')); audio_dirs=set(); [audio_dirs.add(f['path'].rsplit('/',1)[0]) for f in data['files'] if f.get('is_audio',False)]; print(f'Found {len(audio_dirs)} directories with audio files to process')"
	@echo "    Processing ALL directories in metadata.json and regenerating review artifacts..."
	python3 scripts/corpus_decide.py
	@echo "    Generating review bundle..."
	python3 scripts/generate_review_bundle.py
	@echo "    Generating HTML interface..."
	python3 scripts/generate_review_interface.py
	@echo "==> Offline corpus decision complete!"

corpus-decide-real-interactive:
	@echo "==> Running REAL Resonance workflow INTERACTIVELY (network calls + recording)"
	@if [ ! -f "tests/real_corpus/metadata.json" ]; then \
		echo "ERROR: tests/real_corpus/metadata.json missing. Run 'make corpus-extract' first."; \
		exit 1; \
	fi
	@echo "    Checking for required credentials..."
	@if [ -z "$$ACOUSTID_API_KEY" ]; then \
		echo "ERROR: ACOUSTID_API_KEY environment variable required for real workflow"; \
		exit 1; \
	fi
	@if [ -z "$$DISCOGS_TOKEN" ]; then \
		echo "ERROR: DISCOGS_TOKEN environment variable required for real workflow"; \
		exit 1; \
	fi
	@echo "    This will record your decisions to tests/real_corpus/prompt_replay.json"
	@echo "    You will be prompted interactively for each unresolved directory"
	@echo "    Press Ctrl+C to abort without saving replay file"
	python3 scripts/corpus_decide_real_interactive.py

corpus-decide-real-replay:
	@echo "==> Running REAL Resonance workflow with REPLAY (network calls + replay validation)"
	@if [ ! -f "tests/real_corpus/metadata.json" ]; then \
		echo "ERROR: tests/real_corpus/metadata.json missing. Run 'make corpus-extract' first."; \
		exit 1; \
	fi
	@if [ ! -f "tests/real_corpus/prompt_replay.json" ]; then \
		echo "ERROR: tests/real_corpus/prompt_replay.json missing. Run 'make corpus-decide-real-interactive' first."; \
		exit 1; \
	fi
	@echo "    Checking for required credentials..."
	@if [ -z "$$ACOUSTID_API_KEY" ]; then \
		echo "ERROR: ACOUSTID_API_KEY environment variable required for real workflow"; \
		exit 1; \
	fi
	@if [ -z "$$DISCOGS_TOKEN" ]; then \
		echo "ERROR: DISCOGS_TOKEN environment variable required for real workflow"; \
		exit 1; \
	fi
	@echo "    Counting directories in corpus..."
	@python3 -c "import json; data=json.load(open('tests/real_corpus/metadata.json')); audio_dirs=set(); [audio_dirs.add(f['path'].rsplit('/',1)[0]) for f in data['files'] if f.get('is_audio',False)]; print(f'Found {len(audio_dirs)} directories with audio files to process')"
	@echo "    Processing ALL directories in metadata.json using REAL provider APIs with replay..."
	python3 scripts/corpus_decide_real_replay.py
	@echo "    Generating review bundle..."
	python3 scripts/generate_review_bundle.py
	@echo "    Generating HTML interface..."
	python3 scripts/generate_review_interface.py
	@echo "==> Real corpus decision with replay complete!"

corpus-review:
	@echo "==> Serving corpus review interface"
	@echo "    Open: http://localhost:8080/real_corpus_review.html"
	@python3 -m http.server -d dist 8080

quality: lint typecheck

.PHONY: typecheck lint lint-fix format quality corpus-extract corpus-decide corpus-review
