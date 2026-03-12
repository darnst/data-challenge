# Aufgabenstellung Werkstudent: NRW-Datensatz und Daily Pipeline (mit n8n)

## Kontext
Wir bauen einen belastbaren Datenprozess fuer Rechtsdokumente aus Nordrhein-Westfalen (NRW).  
Ziel ist ein reproduzierbares, erweiterbares Setup, das ein moeglichst vollstaendiges Dataset aufbaut und danach taeglich neue bzw. geaenderte Dokumente verarbeitet.

## Rahmenbedingungen
- **Technologie der Wahl (explizit): `n8n`**
- Sprache der Dokumentation: Deutsch (Code und technische Bezeichner koennen Englisch sein)
- Fokus: Stabilitaet, Nachvollziehbarkeit, Wartbarkeit

## Ziel der Aufgabenstellung
Implementiere einen End-to-End-Workflow in `n8n` fuer NRW-Rechtsquellen mit zwei Betriebsmodi:

1. **Initialer Vollaufbau des Datasets (muss nicht vollständig gelaufen sein)** 
2. **Daily Update Pipeline**

Wir interessieren uns ausschließlich für Gesetze, die in Kraft sind.

## Konkrete Aufgaben

### 1) Quellenanalyse und Datenmodell
- Identifiziere relevante NRW-Quellen (z. B. Amtsblatt/Gesetzesportale/APIs/RSS, falls verfuegbar).
- Dokumentiere Feldmapping Quelle -> Zieldatenmodell (siehe `schemas/enriched_legal_act.schema.json`).

### 2) Vollstaendiges Dataset aufbauen (Backfill)
- Implementiere einen `n8n`-Workflow fuer den initialen Datenaufbau.
- Anforderungen:
  - Pagination/Batching fuer grosse Datenmengen
  - Deduplizierung (z. B. ueber `legal_act.document_id` + `legal_act.entity_type`)
  - Robuste Fehlerbehandlung mit Retry-Strategie
  - Checkpoints/Resume-Moeglichkeit bei Abbruch
- Ergebnis: reproduzierbarer Vollimport mit nachvollziehbarem Laufprotokoll.

### 3) Daily Fetch / Extract / Enrich
- Implementiere einen taeglichen `n8n`-Workflow (Scheduler/Cron in `n8n`), der:
  1. neue/geaenderte Dokumente erkennt (`fetch`)
  2. strukturierte Inhalte extrahiert (`extract`)
  3. Metadaten mit LLM anreichert (`enrich`)
- Definiere klare Regeln fuer:
  - Idempotenz (mehrfaches Laufen ohne doppelte Seiteneffekte)
  - Fehlerklassen (temporar vs. permanent)
  - Monitoring/Alerting (mindestens bei Laufabbruch und hoher Fehlerquote)

### 4) Qualitaet und Nachvollziehbarkeit
- Fuehre minimale Datenqualitaetschecks ein:
  - Pflichtfelder vorhanden
  - Plausible Datumswerte
  - Nicht-leere Inhalte bei erfolgreich verarbeiteten Dokumenten
- Stelle pro Lauf einen Report bereit:
  - Anzahl fetched/extracted/enriched
  - Anzahl Fehler + Top-Fehlergruende
  - Anzahl neuer vs. aktualisierter Dokumente

## Zielmodell (`enriched`) als Vorgabe
Das Zielmodell soll explizit im Repository liegen, damit klar ist, wie das Endergebnis aussieht.

Beispiel (`schemas/enriched_legal_act.schema.json`):

```json
{
  "legal_act": {
    "document_id": "string",
    "jurisdiction": "de_nw",
    "title": "string|null",
    "summary": "string|null",
    "publication_date": "YYYY-MM-DD|null",
    "entity_type": "legal_act|consolidated_act"
  },
  "legal_act_relations": [
    {
      "source_document_id": "string",
      "target_document_id": "string",
      "relation_type": "string",
      "concerned_sections": [
        {
          "subdivision_concerned": "string",
          "comment": "string|null"
        }
      ]
    }
  ]
}
```

## Erwartete Deliverables (Minimal)
- `README.md` als zentrale Aufgabenstellung + technische Doku
- Exportierte `n8n`-Workflows (`.json`)
- Ergebnisse als JSON-Dateien im Repo (z. B. `results/*.json`)
- Abgabe als Pull Request

## Abnahmekriterien
- Backfill laeuft reproduzierbar durch (oder dokumentiert sauber, wo Quellen blockieren).
- Daily-Workflow laeuft automatisiert und ist idempotent.
- Deduplizierung funktioniert sichtbar.
- Fehler sind nachvollziehbar geloggt und in Reports sichtbar.
- Setup ist fuer Dritte in < 30 Minuten startbar.

## Schnellstart fuer Werkstudenten (von 0)
1. Repository auschecken und in den Projektordner wechseln.
2. Python-Umgebung aufsetzen und Dependencies installieren:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Umgebungsvariablen anlegen:
   - `.env.example` nach `.env` kopieren
   - benoetigte Werte eintragen (mindestens Quellen + optional LLM Key)
4. `n8n` lokal starten und Workflows importieren:
   - `workflows/nrw_backfill.json`
   - `workflows/nrw_daily_pipeline.json`
5. Ergebnis- und Reportformat anhand von:
   - `results/sample_records.json`
   - `results/run_report_example.json`
6. Vor Abgabe sicherstellen:
   - Workflows exportiert und aktualisiert
   - offene Punkte dokumentiert
   - PR mit Testhinweisen erstellt

### Optionaler Komfort via Makefile
- `make setup` erstellt lokale venv und installiert `requirements.txt`.
- `make check` validiert die JSON-Beispieldateien auf gueltiges JSON.
- `make run-backfill` und `make run-daily` zeigen die vorgesehenen Startpunkte in `n8n`.

Freue mich sehr auf deine Ergebnisse!
NM