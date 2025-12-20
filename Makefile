typecheck:
	python -m mypy resonance

lint:
	python -m ruff check resonance

lint-fix:
	python -m ruff check resonance --fix

format:
	python -m ruff format resonance

quality: lint typecheck

.PHONY: typecheck lint lint-fix format quality
