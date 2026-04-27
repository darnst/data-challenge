# Quellenanalyse: NRW-Rechtsdokumente

## Ergebnis

Die primäre und vollständigste Quelle für NRW-Landesrecht ist **recht.nrw.de** selbst.
Das Portal wurde am 04.02.2026 neu aufgesetzt und nutzt seitdem eine moderne URL-Struktur.
Ein direktes API existiert nicht — der Zugriff erfolgt über Sitemaps + HTML-Scraping.

---

## Quelle 1: recht.nrw.de (Primärquelle, empfohlen)

### URL-Struktur

```
https://recht.nrw.de/lrgv/{typ}/{datum}-{slug}/
```

| Typ-Segment        | Bedeutung               | Ziel-`type`              |
|--------------------|-------------------------|--------------------------|
| `gesetz`           | Formelles Gesetz        | `law`                    |
| `rechtsverordnung` | Rechtsverordnung        | `regulation`             |
| `bekanntmachung`   | Bekanntmachung          | `announcement`           |

Das Datum im URL-Segment entspricht dem Tag, ab dem diese Fassung gilt (`entry_into_force_date`).

**Beispiel:**
```
https://recht.nrw.de/lrgv/gesetz/01012026-landesbesoldungsgesetz-lbesg-nrw/
                                  ^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                  gültig ab  stabiler Slug (law identifier)
```

Jedes Gesetz hat **mehrere Fassungen** (historisch + aktuell). Alle Fassungen teilen denselben Slug ohne Datum.

### Sitemaps (Zugangsstrategie für Backfill und Daily)

```
https://recht.nrw.de/sitemap.xml                   ← Index (47 Sub-Sitemaps)
https://recht.nrw.de/sitemap/page/{1..47}/sitemap.xml
```

- 47 Sitemaps × ~1.000 Einträge = ca. **47.000 URLs** gesamt (inkl. historischer Fassungen)
- Jeder Eintrag enthält `<lastmod>` (ISO 8601) → ideal für Change-Detection
- `changefreq` der meisten Gesetze: `yearly`

**Für Backfill:** Alle 47 Sitemaps iterieren, `/lrgv/`-URLs extrahieren, nach Slug gruppieren, je Slug nur neueste Fassung behalten.

**Für Daily:** Sitemaps fetchen, nur Einträge mit `lastmod >= letzte_run_zeit` verarbeiten.

### GV.NRW (neue Ausgaben)

```
https://recht.nrw.de/gvnrw/{jahr}-{nummer}
```

Beispiel: `https://recht.nrw.de/gvnrw/2026-2` → GV. NRW. 2026 Nr. 2 vom 27.01.2026

Listet alle in einer Ausgabe veröffentlichten Rechtsakte. Nützlich als sekundärer Feed für neue Gesetze.

### Verfügbare Metadaten pro Gesetzesseite

| Seitenfeld               | Beschreibung                                         |
|--------------------------|------------------------------------------------------|
| `<h1>` / Breadcrumb      | Vollständiger Titel                                  |
| Abkürzung                | Kurzbezeichnung (z.B. `LBesG NRW`)                   |
| Ausfertigungsdatum       | Datum der Ausfertigung                               |
| „Gültig ab"              | Inkrafttretungsdatum dieser Fassung (= URL-Datum)    |
| GV-Fundstelle            | `GV. NRW. YYYY S. NNN` → Veröffentlichungsdatum      |
| Letzte Änderung          | GV-Verweis + Datum                                   |
| Fassungen-Liste          | Links zu allen historischen Versionen                |
| PDF-Download             | `/system/files/pdf/...` statische Datei              |

**Kein JSON-LD, kein strukturiertes Markup** — reines HTML-Scraping erforderlich.

### Beispiel: Abruf eines Gesetzes

```
GET https://recht.nrw.de/lrgv/gesetz/01012026-landesbesoldungsgesetz-lbesg-nrw/

Extrahierte Daten:
  Titel:                Besoldungsgesetz für das Land NRW (LBesG NRW)
  Abkürzung:            LBesG NRW
  Ausfertigungsdatum:   14.06.2016
  Gültig ab:            01.01.2026
  GV-Fundstelle:        GV. NRW. 2025 S. 1068
  Versionen:            31 historische Fassungen
```

---

## Quelle 2: OpenLegalData API (Sekundär, nicht NRW-spezifisch)

**URL:** `https://de.openlegaldata.io/api/law_books/?jurisdiction=nrw`

Befund: Die 1.112 als `jurisdiction=nrw` markierten Bücher sind **Bundesgesetze** (z.B. HGB, AAppO),
keine NRW-Landesgesetze. Für NRW-Landesrecht daher **nicht geeignet**.

Nützlich als Fallback für Bundesrecht-Kontext (Verweise in NRW-Gesetzen auf Bundesgesetze).

---

## Feldmapping: recht.nrw.de → EnrichedDocument

### `legal_act`

| Quellenfeld                          | Zielfeld                  | Transformationsregel                                                    |
|--------------------------------------|---------------------------|-------------------------------------------------------------------------|
| URL-Slug ohne Datum                  | `document_id`             | `{slug}` aus URL-Pfad, z.B. `landesbesoldungsgesetz-lbesg-nrw`         |
| `<h1>` Titel                         | `title`                   | Direktübertragung                                                       |
| Abkürzung auf Seite                  | `abbreviation`            | Direktübertragung, z.B. `LBesG NRW`                                    |
| Abkürzung                            | `title_short`             | Gleich wie `abbreviation`                                               |
| URL (vollständige Seiten-URL)        | `url`                     | `https://recht.nrw.de/lrgv/{typ}/{datum}-{slug}/`                      |
| Datum im URL-Segment                 | `entry_into_force_date`   | Aus URL: `01012026` → `2026-01-01`                                      |
| Ausfertigungsdatum (HTML)            | `enactment_date`          | Parse `DD.MM.YYYY` → `YYYY-MM-DD`                                       |
| GV-Fundstelle (HTML)                 | `publication_date`        | Parse `GV. NRW. YYYY S. NNN` → Datum per GV-Ausgaben-Lookup            |
| Letzte Änderung (HTML)               | `last_amendment_date`     | Parse Datum aus Änderungshistorie                                       |
| `de_nw`                              | `jurisdiction`            | Fest                                                                    |
| URL-Typ-Segment                      | `type`                    | `gesetz`→`law`, `rechtsverordnung`→`regulation`, `bekanntmachung`→`announcement` |
| `legal_act`                          | `entity_type`             | Fest (Standard)                                                         |
| `true`                               | `is_in_force`             | Nur aktuelle Fassungen werden verarbeitet                               |
| `de`                                 | `language`                | Fest                                                                    |
| LLM-generiert (Titel + Paragraphen) | `summary`                 | Google Gemini 2.5 Flash, Prompt: 3-Satz-Zusammenfassung (Gegenstand, Adressaten, Rechtsfolgen) |

### `legal_act_relations`

Verweise zwischen Gesetzen (z.B. „ändert § 5 des SchulG NRW") sind **im Fließtext** der Paragraphen enthalten.
Für Phase 1 werden Relationen **nicht extrahiert** (zu aufwändig für n8n-Code-Nodes).
Können in einer späteren Version per LLM aus dem Volltext gewonnen werden.

---

## Bekannte Einschränkungen

| Problem                              | Auswirkung              | Mitigation                                                   |
|--------------------------------------|-------------------------|--------------------------------------------------------------|
| Kein direktes API                    | HTML-Scraping nötig     | n8n HTTP Request + Code Node zum Parsen                      |
| Seitenlayout kann sich ändern        | Parser bricht           | Selektoren dokumentieren, Monitoring einbauen                |
| `lastmod` nicht immer taggenau       | Daily könnte etwas verpassen | Puffer: `lastmod >= heute - 2 Tage`                  |
| Historische Fassungen in Sitemaps    | Doppelte Verarbeitung   | Slug-Deduplizierung, nur neueste Fassung behalten            |
| Kein `is_in_force`-Flag auf Seite    | Aufgehobene Gesetze     | Aufgehobene Gesetze haben keine aktuelle Fassung; prüfen via Textstempel „aufgehoben" |
| Summary erfordert LLM               | Kosten beim Backfill    | Backfill: optional / nur für Stichprobe; Daily: immer        |
| Rate-Limiting unbekannt              | Mögliche Blockierung    | Delay 1–2 s zwischen Requests                               |

---

## Empfohlene Architektur

```
Backfill:
  Sitemap 1..47
    → Alle /lrgv/ URLs extrahieren
    → Gruppenbildung: slug (= URL ohne Datum-Präfix)
    → Je Gruppe: neueste URL (höchstes Datum ≤ heute) = aktuelle Fassung
    → Seite fetchen + HTML parsen
    → LLM Summary (optional)
    → EnrichedDocument speichern

Daily:
  Sitemap 1..47
    → Nur Einträge mit lastmod ≥ gestern
    → Seite fetchen + HTML parsen
    → LLM Summary
    → Upsert (neu oder update per document_id)
    → Run-Report
```
