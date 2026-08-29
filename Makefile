PY := .venv/bin/python

.PHONY: help up down logs init health smoke env clean

help:
	@echo "up      - start ParaBank and the PostgreSQL certification data store"
	@echo "down    - stop both containers"
	@echo "logs    - follow ParaBank logs"
	@echo "init    - provision the SUT (create ParaBank schema and demo data)"
	@echo "health  - verify the environment is READY to test"
	@echo "smoke   - run the Phase 1 smoke tests"
	@echo "env     - up, then init, then health, in order"
	@echo "clean   - remove caches and generated reports"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f parabank

init:
	$(PY) scripts/initialize_sut.py

health:
	$(PY) scripts/healthcheck.py

smoke:
	$(PY) -m pytest -m smoke -v

env: up init health

clean:
	rm -rf .pytest_cache reports allure-results
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
