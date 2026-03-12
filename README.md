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
- Dokumentiere Feldmapping Quelle -> Zieldatenmodell (siehe )

### 2) Vollstaendiges Dataset aufbauen (Backfill)
- Implementiere einen `n8n`-Workflow fuer den initialen Datenaufbau.
- Anforderungen:
  - Pagination/Batching fuer grosse Datenmengen
  - Deduplizierung (z. B. ueber `documentId` + `version`)
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
  "documentId": "string",
  "title": "string",
  "jurisdiction": "NRW",
  "publicationDate": "YYYY-MM-DD",
  "effectiveDate": "YYYY-MM-DD|null",
  "url": "string",
  "language": "de|en",
  "version": "string|null",
  "source": "string",
  "text": "string",
  "enriched": {
    "summary": "string",
    "keywords": ["string"],
    "topics": ["string"]
  }
}
```

## Erwartete Deliverables (Minimal)
- `README.md` als zentrale Aufgabenstellung + technische Doku
- Exportierte `n8n`-Workflows (`.json`)
- Zielmodell fuer `enriched` (JSON Schema oder klar dokumentiertes Beispiel)
- Ergebnisse als JSON-Dateien im Repo (z. B. `results/*.json`)
- Kurze Liste mit Limitierungen/Offenen Punkten
- Abgabe als Pull Request

## Abnahmekriterien
- Backfill laeuft reproduzierbar durch (oder dokumentiert sauber, wo Quellen blockieren).
- Daily-Workflow laeuft automatisiert und ist idempotent.
- Deduplizierung funktioniert sichtbar.
- Fehler sind nachvollziehbar geloggt und in Reports sichtbar.
- Setup ist fuer Dritte in < 30 Minuten startbar.
---

## Was in ein leeres Repo rein soll (ausreichend)
Ja, dein Vorschlag reicht in der Praxis aus. Lege in ein neues, leeres Repository mindestens diese Struktur:

```text
nrw-legal-pipeline/
  README.md
  .env.example
  .gitignore
  schemas/
    enriched_legal_act.schema.json
  workflows/
    nrw_backfill.json
    nrw_daily_pipeline.json
  results/
    sample_records.json
    run_report_example.json
```

### Inhaltsempfehlungen
- `README.md`: Aufgabenstellung, Schnellstart, Setup, Ausfuehrung (Backfill + Daily), Betriebsnotizen.
- `.env.example`: benoetigte Variablen (Quellen-URLs, API-Keys, Zielsystem, Alerting).
- `schemas/enriched_legal_act.schema.json`: Zielstruktur fuer das Enrichment.
- `workflows/*.json`: Exportierte `n8n`-Workflows fuer direkten Import.
- `results/*.json`: erzeugte Ergebnisdateien + Beispielreport.

## LLM-Vorgabe
- LLM ist frei waehlbar.
- Optional kann ein `OPENAI_API_KEY` bereitgestellt werden, falls fuer Enrichment benoetigt.
- Entscheidung und Begruendung kurz im `README.md` dokumentieren.

## Hinweis fuer den Kandidaten
Die Umsetzung soll **explizit mit `n8n`** erfolgen.  
Wenn zusaetzliche Tools verwendet werden, muessen sie den `n8n`-Workflow ergaenzen (nicht ersetzen).

## Abgabe
- Ergebnis als Pull Request mit:
  - kurzer Zusammenfassung der Umsetzung
  - Hinweisen zum Testen
  - offenen Punkten / bekannten Grenzen
