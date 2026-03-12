PYTHON ?= python3
VENV_DIR ?= .venv

.PHONY: setup install check run-backfill run-daily

setup:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt

install:
	pip install -r requirements.txt

check:
	python -m json.tool results/sample_records.json > /dev/null
	python -m json.tool results/run_report_example.json > /dev/null

run-backfill:
	@echo "Importiere workflows/nrw_backfill.json in n8n und starte den Workflow dort."

run-daily:
	@echo "Importiere workflows/nrw_daily_pipeline.json in n8n und aktiviere den Cron Trigger."
