PYTHON ?= python3
VENV_DIR ?= .venv

.PHONY: setup install check generate-workflows fetch-sample start-n8n run-backfill run-daily

setup:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt

install:
	pip install -r requirements.txt

check:
	@test -d $(VENV_DIR) || (echo "ERROR: .venv fehlt. Bitte zuerst 'make setup' ausfuehren." && exit 1)
	$(VENV_DIR)/bin/python3 -m json.tool results/sample_records.json > /dev/null
	$(VENV_DIR)/bin/python3 -m json.tool results/run_report_example.json > /dev/null
	$(VENV_DIR)/bin/python3 scripts/validate_output.py

generate-workflows:
	$(VENV_DIR)/bin/python3 scripts/gen_workflows.py

fetch-sample:
	$(VENV_DIR)/bin/python3 scripts/fetch_sample.py

start-n8n:
	@echo "n8n starten (npx):  npx n8n"
	@echo "n8n starten (Docker): docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n"
	@echo "Danach: http://localhost:5678"
	@echo "Umgebungsvariablen in n8n: Settings → Environment Variables (aus .env.example)"

run-backfill:
	@echo "1. n8n starten: make start-n8n"
	@echo "2. workflows/nrw_backfill.json importieren (n8n UI → Workflows → Import)"
	@echo "3. Workflow manuell starten."

run-daily:
	@echo "1. n8n starten: make start-n8n"
	@echo "2. workflows/nrw_daily_pipeline.json importieren"
	@echo "3. Workflow aktivieren (Toggle oben rechts) — laeuft dann taeglich um 06:00 UTC."
