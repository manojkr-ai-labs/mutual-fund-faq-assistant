"""Load and validate the Groww-only source catalog (Phase 2.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOSTS = frozenset({"groww.in", "www.groww.in"})
ALLOWED_PUBLISHERS = frozenset({"groww"})
ALLOWED_DOC_TYPES = frozenset({"scheme_page", "education", "process"})


class CatalogError(ValueError):
    """Invalid catalog entry or disallowed source."""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    doc_type: str
    source_url: str
    local_path: str
    publisher: str
    as_of: str
    retrieved_on: str
    scheme_id: str | None = None
    scheme_name: str | None = None
    category: str | None = None
    title: str | None = None
    fact_types: tuple[str, ...] = field(default_factory=tuple)

    def absolute_path(self, root: Path) -> Path:
        return (root / self.local_path).resolve()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_catalog_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "data" / "catalog" / "sources.json"


def source_host(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def is_allowlisted_url(url: str, host_allowlist: set[str] | frozenset[str] | None = None) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    hosts = host_allowlist or ALLOWED_HOSTS
    return source_host(url) in hosts


def assert_allowed_source(
    url: str,
    publisher: str,
    *,
    host_allowlist: set[str] | frozenset[str] | None = None,
) -> None:
    pub = (publisher or "").strip().lower()
    if pub not in ALLOWED_PUBLISHERS:
        raise CatalogError(f"publisher {publisher!r} is not allowed (must be groww)")
    if not is_allowlisted_url(url, host_allowlist):
        raise CatalogError(f"source URL is not an allowed Groww HTTPS URL: {url}")


def _host_allowlist_from_raw(raw: dict) -> frozenset[str]:
    listed = raw.get("host_allowlist") or ["groww.in"]
    hosts = {h.lower().lstrip(".") for h in listed}
    hosts.update(ALLOWED_HOSTS)
    extra = hosts - ALLOWED_HOSTS
    if extra:
        raise CatalogError(f"host_allowlist contains non-Groww hosts: {sorted(extra)}")
    return frozenset(hosts)


def _record(
    *,
    source_id: str,
    doc_type: str,
    source_url: str,
    local_path: str,
    publisher: str,
    as_of: str,
    retrieved_on: str,
    host_allowlist: frozenset[str],
    scheme_id: str | None = None,
    scheme_name: str | None = None,
    category: str | None = None,
    title: str | None = None,
    fact_types: tuple[str, ...] = (),
) -> SourceRecord:
    if doc_type not in ALLOWED_DOC_TYPES:
        raise CatalogError(f"unknown doc_type {doc_type!r} for {source_id}")
    if not local_path or Path(local_path).is_absolute() or ".." in Path(local_path).parts:
        raise CatalogError(f"local_path must be a relative path under the repo: {local_path!r}")
    assert_allowed_source(source_url, publisher, host_allowlist=host_allowlist)
    return SourceRecord(
        source_id=source_id,
        doc_type=doc_type,
        source_url=source_url,
        local_path=local_path.replace("\\", "/"),
        publisher=publisher.strip().lower(),
        as_of=as_of,
        retrieved_on=retrieved_on,
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        category=category,
        title=title,
        fact_types=fact_types,
    )


def identify_sources(raw: dict) -> list[SourceRecord]:
    """Turn catalog JSON into validated ingestible source records."""
    host_allowlist = _host_allowlist_from_raw(raw)
    catalog_publisher = (raw.get("publisher") or "groww").strip().lower()
    if catalog_publisher not in ALLOWED_PUBLISHERS:
        raise CatalogError(f"catalog publisher {catalog_publisher!r} is not allowed")

    records: list[SourceRecord] = []
    default_retrieved = raw.get("retrieved_on") or ""

    for scheme in raw.get("schemes") or []:
        records.append(
            _record(
                source_id=scheme["scheme_id"],
                doc_type=scheme.get("doc_type") or "scheme_page",
                source_url=scheme["source_url"],
                local_path=scheme["local_path"],
                publisher=scheme.get("publisher") or catalog_publisher,
                as_of=scheme.get("as_of") or "",
                retrieved_on=scheme.get("retrieved_on") or default_retrieved,
                host_allowlist=host_allowlist,
                scheme_id=scheme["scheme_id"],
                scheme_name=scheme.get("scheme_name"),
                category=scheme.get("category"),
                title=scheme.get("source_title") or scheme.get("scheme_name"),
            )
        )

    for page in raw.get("education") or []:
        url = page.get("url") or page.get("source_url")
        records.append(
            _record(
                source_id=page["id"],
                doc_type=page.get("doc_type") or "education",
                source_url=url,
                local_path=page["local_path"],
                publisher=page.get("publisher") or catalog_publisher,
                as_of=page.get("as_of") or "",
                retrieved_on=page.get("retrieved_on") or default_retrieved,
                host_allowlist=host_allowlist,
                title=page.get("title"),
            )
        )

    for page in raw.get("process") or []:
        url = page.get("url") or page.get("source_url")
        records.append(
            _record(
                source_id=page["id"],
                doc_type=page.get("doc_type") or "process",
                source_url=url,
                local_path=page["local_path"],
                publisher=page.get("publisher") or catalog_publisher,
                as_of=page.get("as_of") or "",
                retrieved_on=page.get("retrieved_on") or default_retrieved,
                host_allowlist=host_allowlist,
                title=page.get("title"),
                fact_types=tuple(page.get("fact_types") or ("process",)),
            )
        )

    ids = [r.source_id for r in records]
    if len(ids) != len(set(ids)):
        raise CatalogError("duplicate source_id in catalog")
    if not records:
        raise CatalogError("catalog contains no sources")
    return records


def allowlisted_urls(records: list[SourceRecord]) -> frozenset[str]:
    return frozenset(r.source_url for r in records)


def load_catalog(path: Path | None = None, *, root: Path | None = None) -> tuple[dict, list[SourceRecord]]:
    catalog_path = path or default_catalog_path(root)
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    return raw, identify_sources(raw)
