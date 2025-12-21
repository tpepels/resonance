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

quality: lint typecheck

.PHONY: typecheck lint lint-fix format quality
