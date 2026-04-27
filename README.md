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

1. **Initialer Vollaufbau des Datasets (Natürlich nur angedeutet: wie bekämen wir Vollständigkeit hin, WENN wir das jetzt durchlaufen ließen?)** 
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

## Idempotenz- und Fehlerklassen-Regeln

### Idempotenz (Daily-Workflow)

Der Daily-Workflow ist idempotent: Mehrfaches Ausloesen am selben Tag erzeugt keine doppelten Dokumente.

- **Mechanismus:** `results/checkpoint.json` speichert `lastRun` (ISO-Datum). Beim naechsten Lauf werden
  nur Sitemaps-Eintraege verarbeitet, deren `lastmod ≥ lastRun - 2 Tage`.
- **Re-Run gleicher Tag:** `lastRun = today` wurde bereits gesetzt. Der Lauf verarbeitet erneut alle
  Dokumente mit `lastmod >= today - 2 Tage` und schreibt eine neue `daily_*.json`. Keine neuen
  Seiteneffekte, solange das Downstream-System Upserts per `document_id` macht.
- **Manueller Re-Run:** `results/checkpoint.json` loeschen oder `lastRun` zuruecksetzen, um alle Aenderungen
  seit einem frueheren Datum erneut zu verarbeiten.

### Fehlerklassen

| Klasse       | Beispiele              | Verhalten                                                  |
|--------------|------------------------|------------------------------------------------------------|
| **Transient** | Timeout, 5xx           | 3 Versuche mit exponentiellem Backoff (1s, 2s)            |
| **Permanent** | 404, 403               | Sofortiger Abbruch, Fehler-Record in NDJSON + Report       |
| **Abgebrochen** | Aufgehobenes Gesetz  | Eintrag mit `reason: abrogated` im Report, nicht im Output |

Bei Fehlerquote > 10 % sendet der `Send Alert`-Node einen POST-Request an `ALERT_WEBHOOK_URL` (falls gesetzt).

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

### 1. Repo und Python-Umgebung
```bash
git clone <repo-url> && cd data-challenge
make setup          # erstellt .venv und installiert requirements.txt
```

### 2. n8n starten

**Option A – npx (kein Docker noetig):**
```bash
npx n8n
```

**Option B – Docker:**
```bash
docker run -it --rm -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  n8nio/n8n
```

n8n laeuft dann unter `http://localhost:5678`.

### 3. Credentials und Variablen in n8n setzen

#### API-Keys: immer in n8n Credentials, nie in `.env`

> ⚠️ **Wichtig:** API-Keys gehoeren **ausschliesslich** in n8n's verschluesselten Credential-Speicher —
> **nicht** in `.env`, **nicht** als n8n Variable.  
> Code-Nodes haben seit n8n v1.0 keinen Zugriff auf OS-Umgebungsvariablen (`process.env`).  
> n8n Variables (`$vars`) sind fuer unkritische Konfigurationswerte, nicht fuer Secrets.

**Google Gemini API-Key (fuer LLM-Enrichment, optional):**

1. In n8n: **Settings → Credentials → Add Credential → Google Gemini(PaLM) API**
2. API-Key eintragen und speichern
3. Nach dem Import der Workflows: in `nrw_backfill.json` und `nrw_daily_pipeline.json` den **"Call Gemini"-Node** oeffnen → Credential-Feld → das eben angelegte Credential auswaehlen
4. Ohne Credential bleibt `summary: null` — der Workflow laeuft trotzdem sauber durch

#### n8n Variables (keine Secrets)

In n8n: **Settings → Variables** – folgende Werte anlegen (Name exakt wie angegeben):

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `RESULTS_DIR` | nein | Absoluter Pfad fuer Ausgabedateien. Leer = `~/.n8n/nrw-results` |
| `ALERT_WEBHOOK_URL` | nein | Webhook-URL fuer Alerts bei Fehlerquote > 10 % und bei Workflow-Abbruch |

### 4. Workflows importieren und konfigurieren

In n8n: **Workflows → Import from File** — alle drei Dateien importieren:

| Datei | Beschreibung | Nach Import |
|---|---|---|
| `workflows/nrw_error_reporter.json` | **Zuerst importieren.** Fängt unerwartete Workflow-Abbrüche ab und sendet Crash-Alert an `ALERT_WEBHOOK_URL`. | Wird automatisch aktiviert (`active: true`). |
| `workflows/nrw_backfill.json` | Einmaliger Vollimport aller NRW-Gesetze. | Workflow-Settings öffnen → **"Error Workflow"** → `nrw_error_reporter` auswaehlen. Danach manuell starten. |
| `workflows/nrw_daily_pipeline.json` | Taeglich 06:00 UTC, verarbeitet Aenderungen seit letztem Lauf. | Workflow-Settings öffnen → **"Error Workflow"** → `nrw_error_reporter` auswaehlen. Danach Workflow aktivieren (Toggle oben rechts). |

> **Monitoring & Alerting:** Zwei Mechanismen greifen ineinander:
> - **Fehlerquote > 10 %** im selben Lauf: `Send Alert`-Node in Backfill und Daily sendet POST an `ALERT_WEBHOOK_URL`.
> - **Unerwarteter Workflow-Abbruch** (Node-Crash, n8n-Fehler): `nrw_error_reporter` faengt den Fehler via `errorTrigger` ab und sendet ebenfalls POST an `ALERT_WEBHOOK_URL`.
> - Beide Alerts enthalten `workflow`, `runId`/`executionId`, `errorMessage` und betroffenen Node.
> - Ohne `ALERT_WEBHOOK_URL` werden Fehler nur in den n8n-Execution-Logs sichtbar.

### 5. Ergebnis pruefen
```bash
make check          # validiert sample_records.json + alle backfill_*.json / daily_*.json
```

Beispielformat: `results/sample_records.json`, `results/run_report_example.json`.

### 6. Vor Abgabe
- Workflows in n8n ggf. anpassen und als JSON re-exportieren
- `make generate-workflows` regeneriert die Workflow-JSONs aus `scripts/gen_workflows.py`
- Offene Punkte dokumentieren, PR mit Testhinweisen erstellen

### Makefile-Targets im Ueberblick
| Target | Beschreibung |
|---|---|
| `make setup` | venv erstellen + requirements installieren |
| `make check` | JSON-Validierung + Qualitaetschecks |
| `make fetch-sample` | Echtdaten-Sample von recht.nrw.de fetchen |
| `make generate-workflows` | Workflow-JSONs aus gen_workflows.py regenerieren |
| `make start-n8n` | Startbefehle anzeigen |
| `make run-backfill` | Anleitung Backfill-Workflow |
| `make run-daily` | Anleitung Daily-Workflow |

Freue mich sehr auf deine Ergebnisse!
NM

## Offene Punkte und bekannte Limitierungen

| Punkt | Status | Naechste Schritte (Phase 2) |
|---|---|---|
| `legal_act_relations` leer | Bewusst ausgelassen: Verweise liegen im Fliesstext, zu aufwaendig fuer n8n-Code-Nodes | LLM-Extraktion aus Volltext (z. B. GPT-4 mit strukturiertem Output) |
| `summary` nur mit Gemini-Key | Ohne Google-Gemini-Credential bleibt `summary: null` | Credential in n8n anlegen (Settings → Credentials → Google Gemini(PaLM) API); Modell: `gemini-2.5-flash` |
| Rate-Limiting recht.nrw.de | Unbekannt; 1,2 s Delay zwischen Requests eingebaut | Fehlermonitoring; ggf. Delay erhoehen bei gehaeuften 429-Antworten |
| Historische Fassungen | Nur aktuelle Fassung (hoechstes Datum &le; heute) wird verarbeitet | Versionierung: alle Fassungen mit `entity_type: consolidated_act` speichern |
| `publication_date` | Aus GV-Fundstelle geparst; nicht immer vorhanden (kein standardisiertes Feld) | Lookup-Tabelle GV-NRW-Ausgaben (Jahrgang + Nummer → Erscheinungsdatum) |
| Volltext-Speicherung | Volltext wird nur waehrend der n8n-Ausfuehrung zwischengespeichert, nicht persistiert | Volltext in separatem Feld oder Datei ablegen fuer spaetere Nachverarbeitung |