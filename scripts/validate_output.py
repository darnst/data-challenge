#!/usr/bin/env python3
"""Validate backfill/daily output against enriched_legal_act.schema.json."""
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_FILE = ROOT / "schemas" / "enriched_legal_act.schema.json"
RESULTS_DIR = ROOT / "results"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_FIELDS = [
    "enactment_date", "entry_into_force_date",
    "last_amendment_date", "publication_date", "validity_date",
]


def check_date(value: str, field: str, doc_id: str) -> str | None:
    if not DATE_RE.match(value):
        return f"{doc_id}.{field}: invalid format {value!r} (expected YYYY-MM-DD)"
    y, m, d = int(value[:4]), int(value[5:7]), int(value[8:10])
    if not (1800 <= y <= 2100):
        return f"{doc_id}.{field}: year {y} out of range [1800, 2100]"
    try:
        _date(y, m, d)
    except ValueError:
        return f"{doc_id}.{field}: invalid calendar date {value!r}"
    return None


def quality_check(docs: list[dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors = hard failures; warnings = quality issues."""
    errors: list[str] = []
    warnings: list[str] = []
    for doc in docs:
        la = doc.get("legal_act", {})
        doc_id = la.get("document_id", "?")
        # Date plausibility (hard error — format is deterministic)
        for field in DATE_FIELDS:
            val = la.get(field)
            if val is not None:
                msg = check_date(val, field, doc_id)
                if msg:
                    errors.append(msg)
        # Non-empty content: textContent is not persisted in EnrichedDocument (interim scraping field),
        # so we check title as a proxy. Null = <h1> parser missed or page had no title.
        if la.get("title") is None:
            warnings.append(f"{doc_id}: title is null")
    return errors, warnings


def validate_file(path: Path, schema: dict) -> list[str]:
    docs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(docs, list):
        return [f"{path.name}: root must be an array"]
    errors = []
    for i, doc in enumerate(docs):
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as e:
            errors.append(f"doc[{i}] ({doc.get('legal_act', {}).get('document_id', '?')}): {e.message}")
    return errors


def main():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

    output_files = (
        sorted(RESULTS_DIR.glob("backfill_*.json"))
        + sorted(RESULTS_DIR.glob("daily_*.json"))
        + ([RESULTS_DIR / "sample_daily.json"] if (RESULTS_DIR / "sample_daily.json").exists() else [])
    )
    if not output_files:
        print("No backfill_*.json, daily_*.json or sample_daily.json found in results/")
        sys.exit(1)

    all_ok = True
    for bf in output_files:
        schema_errs = validate_file(bf, schema)
        if schema_errs:
            print(f"FAIL {bf.name}: {len(schema_errs)} schema error(s)")
            for e in schema_errs[:5]:
                print(f"  {e}")
            all_ok = False
            continue

        docs = json.loads(bf.read_text())
        q_errors, q_warnings = quality_check(docs)

        if q_errors:
            print(f"FAIL {bf.name}: {len(docs)} docs, {len(q_errors)} quality error(s)")
            for e in q_errors[:5]:
                print(f"  ERROR: {e}")
            all_ok = False
        elif q_warnings:
            print(f"WARN {bf.name}: {len(docs)} docs valid — {len(q_warnings)} warning(s)")
            for w in q_warnings[:5]:
                print(f"  WARN: {w}")
        else:
            print(f"OK   {bf.name}: {len(docs)} docs, all valid")

    # Run report checks
    for rr in sorted(RESULTS_DIR.glob("run_report_*.json")):
        if "example" in rr.name:
            continue
        report = json.loads(rr.read_text())
        required = {"runId", "mode", "fetched", "extracted", "enriched",
                    "newDocuments", "updatedDocuments", "errors", "topErrorReasons"}
        missing = required - set(report.keys())
        if missing:
            print(f"FAIL {rr.name}: missing keys {missing}")
            all_ok = False
        elif not isinstance(report["errors"], int):
            print(f"FAIL {rr.name}: errors must be int, got {type(report['errors'])}")
            all_ok = False
        else:
            print(f"OK   {rr.name}: {report}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
