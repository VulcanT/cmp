.PHONY: setup test lint run daily-dry db-up

setup:
	python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check . && ruff format --check . && mypy src

run:
	uvicorn cmp.app:app --reload --port 8000

daily-dry:
	CMP_MODE=dry_run CMP_FIXTURES=1 python -m cmp.pipeline --date yesterday

db-up:
	docker compose up -d db
