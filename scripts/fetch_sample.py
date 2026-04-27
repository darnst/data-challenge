#!/usr/bin/env python3
"""
Fetch a small sample of real NRW laws from recht.nrw.de.
Produces results/backfill_{ts}.json and results/run_report_{ts}.json.
"""
import json
import os
import re
import time
from datetime import datetime, date, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://recht.nrw.de"
_env_dir = os.environ.get("RESULTS_DIR")
RESULTS_DIR = Path(_env_dir).resolve() if _env_dir else Path(__file__).parent.parent / "results"
SAMPLE_SIZE = int(os.environ.get("SAMPLE_SIZE", "0")) or None  # None = no limit (full backfill)
DELAY = 1.2
MAX_RETRIES = 3

TYPE_MAP = {"gesetz": "law", "rechtsverordnung": "regulation", "bekanntmachung": "announcement"}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (NRW-Gesetze-Fetcher/1.0)"})


def get(url: str) -> str:
    """Fetch URL with retry and exponential backoff. 4xx = permanent (no retry), 5xx = transient."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return r.text
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise  # 4xx permanent — no retry
            last_exc = e  # 5xx transient — retry
        except Exception as e:
            last_exc = e
        if attempt < MAX_RETRIES:
            time.sleep(2 ** (attempt - 1))
    raise last_exc  # type: ignore[misc]


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def parse_de_date(s: str) -> str | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"


def ddmmyyyy_to_iso(date_str: str) -> str:
    """Convert DDMMYYYY → YYYY-MM-DD."""
    return f"{date_str[4:8]}-{date_str[2:4]}-{date_str[:2]}"


def parse_law_page(url: str, doc_type: str, entry_date: str, slug: str) -> dict:
    try:
        html = get(url)
    except Exception as e:
        error_type = "permanent" if isinstance(e, requests.HTTPError) else "transient"
        return {"_fetchError": str(e), "_errorType": error_type, "documentId": slug, "url": url}

    time.sleep(DELAY)

    strip = lambda s: re.sub(r"\s+", " ", strip_tags(s)).strip()

    # Skip abrogated laws — CSS class only; freetext has false positives in amendment laws
    if re.search(r'<[^>]+class="[^"]*aufgehoben[^"]*"', html, re.I):
        return {"_abrogated": True, "documentId": slug, "url": url}

    # Title from <h1>
    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
    title = strip(m.group(1)) if m else None

    # Abbreviation
    abbr = None
    m = re.search(r"<dt[^>]*>\s*Abk.rzung\s*</dt>\s*<dd[^>]*>([^<]{1,60})</dd>", html, re.I)
    if m:
        abbr = m.group(1).strip()

    # Enactment date
    enactment_date = None
    m = re.search(r"<dt[^>]*>\s*Ausfertigungsdatum\s*</dt>\s*<dd[^>]*>\s*(\d{2}\.\d{2}\.\d{4})", html, re.I)
    if m:
        enactment_date = parse_de_date(m.group(1))

    # Last amendment date
    last_amendment_date = None
    m = re.search(r"zuletzt\s+ge[äa]ndert[\s\S]{0,300}?(\d{2}\.\d{2}\.\d{4})", html, re.I)
    if m:
        last_amendment_date = parse_de_date(m.group(1))

    # Publication date from GV-Fundstelle
    publication_date = None
    m = re.search(r"Fundstelle[\s\S]{0,300}?(\d{2}\.\d{2}\.\d{4})", html, re.I)
    if m:
        publication_date = parse_de_date(m.group(1))

    # Body text
    m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, re.I) or \
        re.search(r"<article[^>]*>([\s\S]*?)</article>", html, re.I)
    text_content = strip(m.group(1))[:2500] if m else strip(html)[:2500]

    return {
        "documentId": slug,
        "slug": slug,
        "docType": doc_type,
        "url": url,
        "entryDate": entry_date,
        "title": title,
        "abbreviation": abbr,
        "enactmentDate": enactment_date,
        "lastAmendmentDate": last_amendment_date,
        "publicationDate": publication_date,
        "legalType": TYPE_MAP.get(doc_type, "law"),
        "textContent": text_content,
    }


def build_enriched_doc(law: dict) -> dict:
    la = law
    return {
        "legal_act": {
            "document_id": la["documentId"],
            "jurisdiction": "de_nw",
            "entity_type": "legal_act",
            "is_in_force": True,
            "language": "de",
            "url": la.get("url"),
            "canonical_source_url": la.get("url"),
            "fallback_text_url": None,
            "title": la.get("title"),
            "title_short": la.get("abbreviation"),
            "abbreviation": la.get("abbreviation"),
            "type": la.get("legalType"),
            "summary": None,
            "entry_into_force_date": la.get("entryDate"),
            "enactment_date": la.get("enactmentDate"),
            "last_amendment_date": la.get("lastAmendmentDate"),
            "validity_date": None,
            "publication_date": la.get("publicationDate"),
        },
        "legal_act_relations": [],
    }


def get_sitemap_count() -> int:
    try:
        xml = get(f"{BASE}/sitemap.xml")
        count = len(re.findall(r"<sitemap>", xml))
        return count if count > 0 else 47
    except Exception:
        return 47


def fetch_sample_laws(n: int | None = SAMPLE_SIZE) -> tuple[list, int]:
    today = date.today().isoformat()
    by_slug: dict[str, dict] = {}
    sitemap_count = get_sitemap_count()

    limit_str = "unlimited" if n is None else str(n)
    print(f"Fetching sitemaps (index: {sitemap_count} sitemaps, limit: {limit_str})...")
    for page in range(1, sitemap_count + 1):
        url = f"{BASE}/sitemap/page/{page}/sitemap.xml"
        try:
            xml = get(url)
        except Exception as e:
            print(f"  Sitemap {page} failed: {e}")
            continue

        for blk_m in re.finditer(r"<url>([\s\S]*?)</url>", xml):
            blk = blk_m.group(1)
            loc_m = re.search(r"<loc>([^<]+)</loc>", blk)
            if not loc_m:
                continue
            loc = loc_m.group(1).strip()
            if "/lrgv/" not in loc:
                continue
            m = re.search(r"/lrgv/([^/]+)/(\d{8})-([^/]+)/?$", loc)
            if not m:
                continue
            doc_type, date_str, slug = m.groups()
            # URL date format is DDMMYYYY
            entry_date = ddmmyyyy_to_iso(date_str)
            if entry_date > today:
                continue
            # Keep latest version per slug (compare ISO dates, not raw DDMMYYYY strings)
            if slug not in by_slug or by_slug[slug]["entryDate"] < entry_date:
                lmod_m = re.search(r"<lastmod>([^<]+)</lastmod>", blk)
                by_slug[slug] = {
                    "url": loc,
                    "lastmod": lmod_m.group(1).strip() if lmod_m else None,
                    "docType": doc_type,
                    "dateStr": date_str,
                    "entryDate": entry_date,
                    "slug": slug,
                    "documentId": slug,
                }

        collected = len(by_slug)
        print(f"  Sitemap {page}: {collected} unique slugs so far")
        if n is not None and collected >= n:
            break
        time.sleep(0.6)

    candidates = list(by_slug.values())[:n]  # [:None] returns all
    print(f"Selected {len(candidates)} laws to fetch")
    return candidates, len(by_slug)


def main():
    RESULTS_DIR.mkdir(exist_ok=True)

    candidates, total_unique = fetch_sample_laws(SAMPLE_SIZE)

    documents = []
    error_reasons: dict[str, int] = {}
    for i, law_meta in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {law_meta['slug']}")
        parsed = parse_law_page(
            law_meta["url"],
            law_meta["docType"],
            law_meta["entryDate"],
            law_meta["slug"],
        )
        if "_fetchError" in parsed:
            print(f"  ERROR ({parsed.get('_errorType')}): {parsed['_fetchError']}")
            reason = f"http_error_{parsed.get('_errorType', 'transient')}"
            error_reasons[reason] = error_reasons.get(reason, 0) + 1
            continue
        if parsed.get("_abrogated"):
            print(f"  SKIPPED: abrogated")
            error_reasons["abrogated"] = error_reasons.get("abrogated", 0) + 1
            continue
        doc = build_enriched_doc(parsed)
        documents.append(doc)
        print(f"  title={parsed['title']!r}  abbr={parsed['abbreviation']!r}  pub={parsed.get('publicationDate')!r}")

    total_errors = sum(error_reasons.values())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_file = RESULTS_DIR / f"backfill_{ts}.json"
    out_file.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "runId": f"backfill_{ts}",
        "mode": "backfill",
        "fetched": len(documents) + total_errors,
        "extracted": len(documents),
        "enriched": 0,
        "newDocuments": len(documents),
        "updatedDocuments": 0,
        "errors": total_errors,
        "topErrorReasons": [{"reason": r, "count": c} for r, c in sorted(error_reasons.items(), key=lambda x: -x[1])],
    }
    report_file = RESULTS_DIR / f"run_report_{ts}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone: {len(documents)} docs → {out_file.name}")
    print(f"Report → {report_file.name}")
    print(f"(Note: {total_unique} unique slugs across sitemaps; sample={SAMPLE_SIZE})")


if __name__ == "__main__":
    main()
