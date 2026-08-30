PY := .venv/bin/python

.PHONY: PY  help up down logs init health smoke docs env clean reset newman

help:
	@echo "up      - start ParaBank and the PostgreSQL certification data store"
	@echo "down    - stop both containers"
	@echo "logs    - follow ParaBank logs"
	@echo "init    - provision the SUT (create ParaBank schema and demo data)"
	@echo "health  - verify the environment is READY to test"
	@echo "smoke   - run the Phase 1 smoke tests"
	@echo "docs    - regenerate all generated documentation"
	@echo "reset   - wipe and reseed ParaBank demo data"
	@echo "newman  - run the Postman collection headlessly"
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

docs:
	$(PY) scripts/generate_requirements_doc.py
	$(PY) scripts/generate_test_cases_doc.py
	$(PY) scripts/generate_rtm.py

env: up init health

clean:
	rm -rf .pytest_cache reports allure-results
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
reset:
	$(PY) scripts/reset_sut_data.py

newman:
	newman run postman/northline.postman_collection.json \
	  -e postman/northline.local.postman_environment.json \
	  --reporters cli,junit \
	  --reporter-junit-export reports/newman-junit.xml
