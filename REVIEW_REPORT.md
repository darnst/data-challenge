# Review Report: NRW-Datenpipeline (n8n)

**Reviewer:** Senior Data Engineer / Tech Lead  
**Datum:** 2026-04-27  
**Branch:** master  
**Reviewte Commits:** `4e20dca` bis HEAD

---

## Zusammenfassung

Der Werkstudent hat eine solide End-to-End-Pipeline abgeliefert, die die Kernaufgaben (Backfill + Daily, Quellenanalyse, Schema, Run-Reports, Fehlerklassen, Alerting) im Wesentlichen erfüllt. Echte Läufe sind nachweisbar und `make check` läuft ohne Fehler durch. Es gibt jedoch **einen kritischen Blocker**, der vor einem echten Produktiveinsatz behoben werden muss, sowie eine auffällige Dokumentations-Inkonsistenz beim LLM-Provider.

---

## 🟢 Pass — Gut umgesetzt

### Dateistruktur & Vollständigkeit
- Alle Pflicht-Deliverables vorhanden: `workflows/`, `schemas/`, `results/`, `README.md`, `requirements.txt`, `.env.example`, `Makefile`.
- Schema `schemas/enriched_legal_act.schema.json` geht deutlich über die Minimalvorgabe hinaus: vollständige JSON-Schema-Validierungsregeln, Enum-Prüfung für `jurisdiction` und `type`, `additionalProperties: false` auf beiden Ebenen — das ist produktionsreif.
- Bonus-Deliverables: `docs/quellenanalyse.md`, `scripts/gen_workflows.py`, `scripts/validate_output.py`, `scripts/fetch_sample.py`, `workflows/nrw_error_reporter.json`.

### Quellenanalyse (`docs/quellenanalyse.md`)
- Nachvollziehbare Begründung für recht.nrw.de als Primärquelle, inklusive Sitemap-Strategie, URL-Schema-Analyse (Datum-Slug-Format DDMMYYYY), und vollständigem Feldmapping.
- Sekundärquelle (OpenLegalData) korrekt als für NRW-Landesrecht ungeeignet eingestuft.
- Bekannte Einschränkungen (kein API, Layout-Änderungsrisiko, Rate-Limiting) transparent dokumentiert.

### Backfill-Workflow (`nrw_backfill.json`)
- **Pagination/Batching:** Iteriert alle Sitemaps dynamisch (zählt Einträge im Index-Sitemap, Fallback auf 47).
- **Deduplizierung:** `bySlug`-Map in der Sitemap-Verarbeitung — pro Slug wird nur die neueste Fassung (höchstes Datum ≤ heute) behalten.
- **Retry-Strategie:** 3 Versuche mit exponentiellem Backoff (1 s / 2 s), Differenzierung in `permanent` (4xx) vs. `transient` (Timeouts, 5xx).
- **Resume-Checkpoint:** `backfill_progress.txt` wird pro Dokument append-only fortgeschrieben; bei erneutem Start werden bereits verarbeitete Slugs übersprungen.
- **NDJSON-Akkumulator:** Schreibt während des Laufs in `_backfill_active.ndjson`, konvertiert am Ende zu einer finalen JSON-Datei — gute Crash-Recovery-Strategie.
- **Fehler-Records:** Abgebrochene und fehlgeschlagene Dokumente werden als `_error: true`-Einträge im NDJSON erfasst und im Report gezählt.

### Daily-Workflow (`nrw_daily_pipeline.json`)
- **Schedule-Trigger** mit Cron `0 6 * * *` (06:00 UTC) — korrekt eingebunden.
- **Checkpoint-Mechanismus:** `results/checkpoint.json` mit `lastRun`; Checkpoint wird nur aktualisiert wenn Fehlerquote < 50 %.
- **Idempotenz:** 2-Tage-Puffer (`lastmod >= since - 2 Tage`) schützt gegen Clock-Skew; mehrfacher Lauf am gleichen Tag produziert keine Duplikate solange das Downstream-System per `document_id` upsertet.
- **No-Changes-Kurzschluss:** Wenn die Sitemap keine Änderungen liefert, wird der Loop übersprungen.
- **Schritte klar erkennbar:** Fetch (`Fetch Changed Law URLs`) → Extract (`Fetch & Parse Law Page`) → Enrich (`Call Gemini`) → Compile (`Save Results & Update Checkpoint`).

### Run-Reports & Monitoring
- Alle geforderten Report-Felder vorhanden: `runId`, `mode`, `fetched`, `extracted`, `enriched`, `newDocuments`, `updatedDocuments`, `errors`, `topErrorReasons`.
- Alert-Node bei Fehlerquote > 10 % in beiden Workflows.
- **Separater Crash-Reporter-Workflow** (`nrw_error_reporter.json`) mit `errorTrigger`-Node — sendet Webhook bei unerwarteten Workflow-Abbrüchen. Das geht über die Anforderungen hinaus und ist eine gute Praxis.
- Echte Laufergebnisse nachweisbar: Backfill (10 Dokumente, 0 Fehler), Daily (16 Dokumente, 3 neu / 13 aktualisiert, 0 Fehler).

### Qualitätssicherung
- `scripts/validate_output.py`: Schema-Validierung per `jsonschema` + Datumsplausibilitäts-Checks (Format YYYY-MM-DD, Jahr 1800–2100, Kalender-Gültigkeit).
- `make check` läuft durch: `sample_records.json`, `run_report_example.json`, alle `backfill_*.json`, `daily_*.json` und `run_report_*` sind valide.
- `scripts/gen_workflows.py`: Workflows sind aus Python-Quellcode reproduzierbar generierbar — vermeidet Drift zwischen Doku und Implementierung.

### README
- Vollständige technische Dokumentation: Architektur, Schnellstart (< 30 Minuten realistisch), Idempotenz-Regeln, Fehlerklassen-Tabelle, alle Makefile-Targets erklärt.
- Offene Punkte transparent in einer Tabelle zusammengefasst.

---

## 🟡 Warnings — Funktioniert, entspricht aber nicht ganz den Best Practices

### W1 — LLM-Provider-Inkonsistenz in der Dokumentation
Die Dokumentation referenziert **drei verschiedene LLM-Provider** an drei verschiedenen Stellen:
- `README.md` → Anthropic / Claude (`claude-haiku-4-5-20251001`, `ANTHROPIC_API_KEY`)
- `docs/quellenanalyse.md` Zeile 123 → OpenAI GPT-4.1-mini
- Tatsächlich implementierte Workflows → **Google Gemini 2.5 Flash** (`googlePalmApi`-Credential)

Für sich allein wäre die Gemini-Implementierung völlig in Ordnung; das Problem ist, dass ein neuer Nutzer nach dem README `ANTHROPIC_API_KEY` eintragen und ein Anthropic-Credential anlegen würde — und dann feststellt, dass die Workflows ein `Google Gemini(PaLM) Api`-Credential erwarten. Das verhindert den Setup in < 30 Minuten.

### W2 — Hardcoded Credential-ID im Workflow-JSON
```json
"credentials": {
  "googlePalmApi": {
    "id": "xj3d4VdRweSxyQ7I",
    "name": "Google Gemini(PaLM) Api account"
  }
}
```
n8n ersetzt diese ID beim Import nicht automatisch. Nach dem Import in eine neue Instanz zeigt der `Call Gemini`-Node einen Credential-Fehler. Das ist n8n-spezifisches Verhalten, sollte aber explizit in der README unter Schritt 3 erwähnt werden: *„Credential nach Import neu verknüpfen: Backfill- und Daily-Workflow öffnen → Call Gemini-Node → Credential wählen."*

### W3 — Zone.Identifier-Dateien im Repository
Im `results/`-Verzeichnis liegen mehrere `*.json:Zone.Identifier`-Dateien (Windows-NTFS-Alternate-Data-Streams). Diese sind untracked, fehlen aber in `.gitignore`. Ein `git add results/` würde sie einschließen.

**Fix:** `.gitignore` ergänzen:
```
*:Zone.Identifier
```

### W4 — Redundante `.env/`-Unterordner-Struktur
Es existieren parallel:
- `.env.example` im Projekt-Root (korrekt)
- `.env/.env.example` als Unterordner (unklar, woher das kommt)

Der Unterordner sollte entfernt werden; er verursacht Verwirrung und ist laut `.gitignore` ohnehin nicht commited (`.env` ist excluded).

### W5 — `newDocuments`-Heuristik unzuverlässig
Der Report unterscheidet „neu" und „aktualisiert" per `entry_into_force_date >= lastRun`. Ein Gesetz von 2010 mit einer neuen Fassung 2026 würde als „neu" gezählt. Das ist im Code und in der README explizit als Limitation vermerkt — gut dokumentiert, aber ein Downstream-Konsument des Reports sollte darauf hingewiesen werden.

### W6 — `results/backfill_*.json` und `results/run_report_*_backfill.json` untracked
Der echte Backfill-Lauf liegt lokal vor, ist aber noch nicht committed. Die Abgabe profitiert davon, diese als Beweis zu committen — gerade weil der Backfill nur mit dem Limit-Node durchgelaufen ist (siehe Blocker unten).

---

## 🔴 Blocker / Fail — Muss vor Abgabe oder Produktiveinsatz behoben werden

### B1 — `Limit`-Node im Backfill (maxItems: 10) — KRITISCH
```json
{
  "parameters": { "maxItems": 10 },
  "name": "Limit",
  "type": "n8n-nodes-base.limit",
  ...
}
```
Dieser Node sitzt direkt zwischen `Fetch All Sitemap URLs` und `Loop: Process Laws` und begrenzt die Verarbeitung auf **10 Dokumente**. Ein echter Vollimport über alle ~47.000 NRW-Gesetze ist damit nicht möglich.

Es handelt sich offensichtlich um ein Test-Artefakt (typisch beim Entwickeln, um schnelle Iterationen zu ermöglichen), das vor der finalen Abgabe entfernt oder zumindest deaktiviert werden muss.

Der Backfill-Run-Report bestätigt das: `"fetched": 10, "newDocuments": 10` — exakt der Limit-Wert.

**Fix:** Den `Limit`-Node aus dem Workflow entfernen (oder auf `maxItems: 0` / sehr hohen Wert setzen und explizit kommentieren, wenn er bewusst für Demo-Zwecke drin bleiben soll). Danach `gen_workflows.py` anpassen und Workflow neu exportieren.

### B2 — LLM-Credential-Setup nicht end-to-end ausführbar
In Verbindung mit W1 und W2: Die Dokumentation beschreibt Anthropic, die Implementierung erwartet ein Google Gemini API-Credential, das nach dem Import manuell neu verknüpft werden muss. Ohne diesen Schritt bleibt `summary: null` und ein Nutzer weiß nicht warum. Das verletzt das Abnahmekriterium „Setup für Dritte in < 30 Minuten startbar".

Der Fix für B2 ist eine Ergänzung in der README (Setup-Schritt für Gemini-Credential), keine Code-Änderung — aber er ist erforderlich damit das Setup reproduzierbar ist.

---

## 📝 Action Items für den Werkstudenten

Klar priorisiert, wertschätzend gemeint — du hast gute Arbeit geleistet, hier sind die letzten Meter:

| Prio | Item | Datei(en) | Aufwand |
|------|------|-----------|---------|
| 🔴 1 | **`Limit`-Node aus `nrw_backfill.json` entfernen** (oder begründet dokumentieren). `gen_workflows.py` + Workflow-JSON aktualisieren. | `scripts/gen_workflows.py`, `workflows/nrw_backfill.json` | 15 min |
| 🔴 2 | **README auf Google Gemini aktualisieren**: Abschnitte über Anthropic/Claude ersetzen durch Gemini-Credential-Setup, Post-Import-Schritt „Credential neu verknüpfen" ergänzen. Zeile 123 in `docs/quellenanalyse.md` (OpenAI) korrigieren. | `README.md`, `docs/quellenanalyse.md`, `.env.example` | 30 min |
| 🟡 3 | **Zone.Identifier in `.gitignore`** aufnehmen: `*:Zone.Identifier` | `.gitignore` | 2 min |
| 🟡 4 | **`.env/`-Unterordner löschen** (redundant, verwirrend). | `.env/` | 2 min |
| 🟡 5 | **Backfill-Ergebnisse committen**: `git add results/backfill_2026-04-27T17-38-00.json results/run_report_2026-04-27T17-38-00_backfill.json` — als Beweis für den durchgelaufenen (eingeschränkten) Backfill. | `results/` | 5 min |
| 🟡 6 | **README-Hinweis ergänzen**: Nach dem Entfernen des Limit-Nodes: Laufzeit-Schätzung für echten Vollbackfill (~47 Sitemaps × ~1.000 Einträge × 1,2 s Delay = ca. 16 h) dokumentieren, damit Nutzer nicht nach 10 Minuten die Verbindung trennen. | `README.md` | 10 min |

---

## Gesamtbewertung

| Kriterium | Bewertung |
|-----------|-----------|
| Dateistruktur & Vollständigkeit | ✅ Erfüllt |
| Quellenanalyse & Feldmapping | ✅ Sehr gut |
| Backfill-Workflow (Logik) | ⚠️ Gut — Blocker: Limit-Node |
| Daily-Workflow | ✅ Erfüllt |
| Deduplizierung | ✅ Nachweisbar |
| Fehlerbehandlung & Retry | ✅ Gut |
| Idempotenz | ✅ Dokumentiert & implementiert |
| Monitoring / Alerting | ✅ Über Anforderungen hinaus |
| Run-Reports | ✅ Alle Felder vorhanden |
| Datenqualitätschecks | ✅ Schema + Datumsprüfung |
| Setup < 30 Minuten | ⚠️ Blockiert durch LLM-Doku-Inkonsistenz |
| `make check` | ✅ Grün |
