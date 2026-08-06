from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30


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


def _strip_jats(text: str) -> str:
    """Crossref abstracts arrive as JATS XML-ish fragments (<jats:p> tags); strip tags, keep text."""
    import re

    without_tags = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_whitespace(without_tags)


def _extract_date(date_parts_container: dict | None) -> str:
    if not date_parts_container:
        return ""
    parts = date_parts_container.get("date-parts")
    if not parts or not parts[0]:
        return ""
    components = parts[0]
    year = components[0] if len(components) > 0 else None
    month = components[1] if len(components) > 1 else 1
    day = components[2] if len(components) > 2 else 1
    if year is None:
        return ""
    try:
        return f"{int(year):04d}-{int(month or 1):02d}-{int(day or 1):02d}"
    except (TypeError, ValueError):
        return ""


def _extract_authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author", []) or []:
        given = normalize_whitespace(author.get("given", ""))
        family = normalize_whitespace(author.get("family", ""))
        name = normalize_whitespace(f"{given} {family}")
        if name:
            authors.append(name)
        elif author.get("name"):
            authors.append(normalize_whitespace(author["name"]))
    return authors


def _extract_paper_id(item: dict) -> str:
    doi = item.get("DOI")
    if doi:
        return normalize_whitespace(doi).lower()
    url = item.get("URL")
    if url:
        return normalize_whitespace(url).lower()
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref /works payload into a list of PaperRecord.

    Records missing a stable id (DOI/URL) or a title are dropped since they
    cannot be reliably deduplicated or referenced downstream.
    """
    items = payload.get("message", {}).get("items", []) or []
    records: list[PaperRecord] = []

    for item in items:
        paper_id = _extract_paper_id(item)
        titles = item.get("title") or []
        title = normalize_whitespace(titles[0]) if titles else ""
        if not paper_id or not title:
            continue

        summary = _strip_jats(item.get("abstract", ""))
        authors = _extract_authors(item)
        categories = [normalize_whitespace(c) for c in item.get("subject", []) or [] if normalize_whitespace(c)]
        primary_category = categories[0] if categories else ""
        published = _extract_date(item.get("published") or item.get("published-print") or item.get("published-online"))
        updated = _extract_date(item.get("indexed") or item.get("deposited")) or published
        abs_url = normalize_whitespace(item.get("URL", ""))
        pdf_url = ""
        for link in item.get("link", []) or []:
            content_type = (link.get("content-type") or "").lower()
            if "pdf" in content_type:
                pdf_url = normalize_whitespace(link.get("URL", ""))
                break
        container_title = item.get("container-title") or []
        comment = normalize_whitespace(container_title[0]) if container_title else ""

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def _request_with_retry(url: str, params: dict) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            logger.warning("Crossref request attempt %d failed: %s", attempt, exc)
        else:
            if response.status_code == 200:
                return response
            if response.status_code in RETRYABLE_STATUS_CODES:
                logger.warning(
                    "Crossref request attempt %d got retryable status %d", attempt, response.status_code
                )
                last_exc = RuntimeError(f"Crossref returned status {response.status_code}")
            else:
                response.raise_for_status()

        if attempt < MAX_RETRIES:
            backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            time.sleep(backoff)

    raise RuntimeError(f"Crossref request failed after {MAX_RETRIES} attempts") from last_exc


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Call the Crossref API, persist the raw response, and parse it into records."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,published-print,"
        "published-online,indexed,deposited,URL,link,container-title",
    }

    response = _request_with_retry(CROSSREF_API_URL, params)
    payload = response.json()

    write_json(settings.paths.raw_api_response, payload)
    logger.info("Saved raw Crossref response to %s", settings.paths.raw_api_response)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [record.__dict__ for record in records])
    logger.info("Saved %d parsed raw records to %s", len(records), settings.paths.raw_records_json)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a previously saved raw records JSON snapshot and map it back to PaperRecord."""
    payload = read_json(path)
    return [PaperRecord(**item) for item in payload]
