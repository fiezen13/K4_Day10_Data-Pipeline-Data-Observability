from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging
import re
import time
import html
from typing import Any

import requests

from core.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_html(text: str | None) -> str:
    if text is None or text == "":
        return ""
    # If crossref returned a list, join into a single string
    if isinstance(text, list):
        text = " ".join(str(x) for x in text if x is not None)
    # ensure we operate on a string
    text = str(text)
    # Crossref may return abstracts with XML/HTML tags (e.g. <jats:p> …)
    text = html.unescape(text)
    # remove tags
    text = re.sub(r"<[^>]+>", "", text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_date(item: dict[str, Any]) -> str:
    # Crossref date objects typically have 'date-parts': [[YYYY, MM, DD]]
    if not item:
        return ""
    for key in ("published-print", "published-online", "issued", "created", "deposited"):
        if key in item and item[key] and isinstance(item[key], dict):
            dp = item[key].get("date-parts")
            if dp and isinstance(dp, list) and len(dp) > 0 and len(dp[0]) > 0:
                parts = dp[0]
                return "-".join(str(p) for p in parts)
    # fallback: if caller passed a direct dict with date-parts
    dp = item.get("date-parts") if isinstance(item, dict) else None
    if dp and isinstance(dp, list) and len(dp) > 0 and len(dp[0]) > 0:
        return "-".join(str(p) for p in dp[0])
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref API payload -> list[PaperRecord].

    The function is permissive: missing fields become empty strings/lists.

    TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.

    """
    items = payload.get("message", {}).get("items", []) if isinstance(payload, dict) else []
    records: list[PaperRecord] = []

    for it in items:
        # paper id: prefer DOI
        doi = it.get("DOI") or it.get("doi") or ""
        paper_id = doi.strip()

        # title: Crossref returns list
        title_list = it.get("title") or []
        title = title_list[0].strip() if isinstance(title_list, list) and title_list else ""

        # abstract/summary
        abstract = _clean_html(it.get("abstract") or it.get("subtitle") or "")

        # authors
        authors = []
        for a in it.get("author") or []:
            given = (a.get("given") or "").strip()
            family = (a.get("family") or "").strip()
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
            elif given:
                authors.append(given)
        # subjects/categories
        subjects = it.get("subject") or []
        categories = [s for s in subjects if isinstance(s, str)]
        primary_category = categories[0] if categories else ""

        # dates
        published = ""
        updated = ""
        # try common fields
        published = _format_date({
            "published-print": it.get("published-print"),
            "published-online": it.get("published-online"),
            "issued": it.get("issued"),
        })
        # updated -> deposited or created
        updated = _format_date({
            "deposited": it.get("deposited"),
            "created": it.get("created"),
        })

        # links: abs_url from URL, pdf from link entries
        abs_url = it.get("URL") or it.get("url") or ""
        pdf_url = ""
        for link in it.get("link") or []:
            if not isinstance(link, dict):
                continue
            content_type = (link.get("content-type") or "").lower()
            if "pdf" in content_type or link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL") or link.get("url") or pdf_url
        # sometimes 'link' entries use 'URL' or 'URL' all caps

        # comment/notes
        comment = _clean_html(it.get("note") or it.get("short-container-title") or "")

        record = PaperRecord(
            paper_id=paper_id,
            title=title,
            summary=abstract,
            authors=authors,
            categories=categories,
            primary_category=primary_category,
            published=published,
            updated=updated,
            abs_url=abs_url,
            pdf_url=pdf_url,
            comment=comment,
        )

        # basic validation: require either DOI or title
        if not record.paper_id and not record.title:
            log.debug("Skipping item without id/title: %s", it)
            continue

        records.append(record)

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Call Crossref API, save raw response and parsed records.

    Writes two files (creating parents as needed):
    - settings.paths.raw_api_response : the full API JSON response
    - settings.paths.raw_records_json : JSON list of parsed records (dicts)
    
    TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    api_url = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    headers = {"User-Agent": "data-observability-lab/0.1 (mailto:student@example.com)"}

    session = requests.Session()
    backoff = 1
    max_attempts = 5
    resp_json: dict | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            log.debug("Crossref request attempt %s params=%s", attempt, params)
            r = session.get(api_url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                resp_json = r.json()
                break
            if r.status_code in {429, 503}:
                log.warning("Crossref returned %s, backing off %s seconds", r.status_code, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Request failed (attempt %s): %s", attempt, exc)
            time.sleep(backoff)
            backoff *= 2
            continue

    if resp_json is None:
        raise RuntimeError("Failed to fetch Crossref API after retries")

    # persist raw API response
    raw_path: Path = settings.paths.raw_api_response
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("w", encoding="utf-8") as fh:
        json.dump(resp_json, fh, ensure_ascii=False, indent=2)

    # parse
    records = parse_crossref_payload(resp_json)

    # persist parsed records as JSON (list of dicts)
    raw_records_path: Path = settings.paths.raw_records_json
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_records_path.open("w", encoding="utf-8") as fh:
        json.dump([r.__dict__ for r in records], fh, ensure_ascii=False, indent=2)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load JSON snapshot written by fetch_source_records and map to PaperRecord.

    Expects a list of dict-like records with keys matching PaperRecord fields.

    TODO(student): doc JSON snapshot va map thanh `PaperRecord`.
    """
    if not path.exists():
        raise FileNotFoundError(f"Raw records file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    records: list[PaperRecord] = []
    for rec in data:
        # tolerate missing keys
        records.append(
            PaperRecord(
                paper_id=rec.get("paper_id", ""),
                title=rec.get("title", ""),
                summary=rec.get("summary", ""),
                authors=rec.get("authors", []) or [],
                categories=rec.get("categories", []) or [],
                primary_category=rec.get("primary_category", ""),
                published=rec.get("published", ""),
                updated=rec.get("updated", ""),
                abs_url=rec.get("abs_url", ""),
                pdf_url=rec.get("pdf_url", ""),
                comment=rec.get("comment", ""),
            )
        )
    return records
