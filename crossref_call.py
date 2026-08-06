import logging
import traceback

from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records

logging.basicConfig(level=logging.INFO)

def safe_str(s):
    if s is None:
        return ''
    return str(s).encode('ascii', errors='backslashreplace').decode('ascii')

try:
    settings = load_settings()
    print("Settings source_query:", settings.source_query)
    records = fetch_source_records(settings)
    print("Fetched", len(records), "records")
    if records:
        r = records[0]
        print("First title (safe):", safe_str(r.title))
        print("First authors (safe):", [safe_str(a) for a in r.authors])
    recs2 = load_raw_records(settings.paths.raw_records_json)
    print("Loaded from file:", len(recs2), "records")
except Exception as e:
    traceback.print_exc()
    print('ERROR:', e)