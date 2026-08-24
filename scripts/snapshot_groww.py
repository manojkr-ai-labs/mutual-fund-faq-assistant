"""Snapshot Groww scheme / education / process pages for Phase 1 corpus.

Saves HTML under data/raw/ and writes data/catalog/sources.json.
Does not crawl other hosts. Re-run to refresh snapshots.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CATALOG_PATH = ROOT / "data" / "catalog" / "sources.json"
TODAY = date.today().isoformat()
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCHEMES = [
    {
        "scheme_id": "hdfc-mid-cap-direct-growth",
        "scheme_name": "HDFC Mid Cap Fund — Direct Growth",
        "category": "mid-cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "local_path": "data/raw/schemes/hdfc-mid-cap-direct-growth.html",
    },
    {
        "scheme_id": "hdfc-small-cap-direct-growth",
        "scheme_name": "HDFC Small Cap Fund — Direct Growth",
        "category": "small-cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        "local_path": "data/raw/schemes/hdfc-small-cap-direct-growth.html",
    },
    {
        "scheme_id": "hdfc-gold-etf-fof-direct-growth",
        "scheme_name": "HDFC Gold ETF Fund of Fund — Direct Plan Growth",
        "category": "gold-etf-fof",
        "source_url": "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
        "local_path": "data/raw/schemes/hdfc-gold-etf-fof-direct-growth.html",
    },
    {
        "scheme_id": "hdfc-large-cap-direct-growth",
        "scheme_name": "HDFC Large Cap Fund — Direct Growth",
        "category": "large-cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "local_path": "data/raw/schemes/hdfc-large-cap-direct-growth.html",
    },
    {
        "scheme_id": "hdfc-elss-tax-saver-direct-growth",
        "scheme_name": "HDFC ELSS Tax Saver Fund — Direct Plan Growth",
        "category": "elss",
        "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
        "local_path": "data/raw/schemes/hdfc-elss-tax-saver-direct-growth.html",
    },
]

EDUCATION = [
    {
        "id": "groww-types-of-mutual-funds",
        "title": "Types of Mutual Fund in India",
        "url": "https://groww.in/p/types-of-mutual-funds",
        "local_path": "data/raw/education/types-of-mutual-funds.html",
    },
    {
        "id": "groww-mutual-funds-hub",
        "title": "Groww Mutual Funds",
        "url": "https://groww.in/mutual-funds",
        "local_path": "data/raw/education/mutual-funds-hub.html",
    },
]

PROCESS = [
    {
        "id": "groww-capital-gains-report",
        "title": "How to download capital gain report",
        "url": "https://groww.in/help/mutual-funds/mf-others/how-to-download-capital-gain-report--50",
        "local_path": "data/raw/process/how-to-download-capital-gain-report.html",
        "fact_types": ["process", "capital_gains"],
    },
    {
        "id": "groww-transaction-history",
        "title": "Where can I get the transaction history",
        "url": "https://groww.in/help/my-account/ma-others/where-can-i-get-the-transaction-history",
        "local_path": "data/raw/process/transaction-history.html",
        "fact_types": ["process", "statement"],
    },
    {
        "id": "groww-elss-tax-statement",
        "title": "How to download tax statement for ELSS",
        "url": "https://groww.in/help/mutual-funds/order/how-to-download-tax-statement--for-elss--77",
        "local_path": "data/raw/process/elss-tax-statement.html",
        "fact_types": ["process", "elss_statement"],
    },
]


def fetch_html(url: str) -> str:
    if not url.startswith("https://groww.in/"):
        raise ValueError(f"refusing non-Groww URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned {response.status}")
        return response.read().decode("utf-8", "replace")


def save_html(relative_path: str, html: str) -> Path:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def extract_next_data(html: str) -> dict | None:
    marker = 'id="__NEXT_DATA__"'
    start = html.find(marker)
    if start < 0:
        return None
    gt = html.find(">", start)
    end = html.find("</script>", gt)
    if gt < 0 or end < 0:
        return None
    return json.loads(html[gt + 1 : end])


def normalize_as_of(nav_date: str | None) -> str:
    if not nav_date:
        return TODAY
    text = str(nav_date).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return TODAY


def lock_in_present(lock_in: dict) -> bool:
    return any((lock_in.get(key) or 0) > 0 for key in ("years", "months", "days"))


def scheme_facts(html: str) -> dict:
    payload = extract_next_data(html) or {}
    mf = payload.get("props", {}).get("pageProps", {}).get("mfServerSideData") or {}
    lock_in = mf.get("lock_in") or {}
    return_stats = (mf.get("return_stats") or [{}])[0]
    as_of = normalize_as_of(mf.get("nav_date"))
    return {
        "scheme_name_on_page": mf.get("scheme_name"),
        "plan_type": mf.get("plan_type"),
        "nav_date": mf.get("nav_date"),
        "as_of": as_of,
        "expense_ratio": mf.get("expense_ratio"),
        "exit_load": mf.get("exit_load"),
        "min_sip_investment": mf.get("min_sip_investment"),
        "min_investment_amount": mf.get("min_investment_amount"),
        "riskometer": return_stats.get("risk") or mf.get("nfo_risk"),
        "benchmark": mf.get("benchmark") or mf.get("benchmark_name"),
        "lock_in": lock_in,
        "coverage": {
            "expense_ratio": mf.get("expense_ratio") not in (None, ""),
            "exit_load": bool(mf.get("exit_load")),
            "min_sip": mf.get("min_sip_investment") not in (None, ""),
            "riskometer": bool(return_stats.get("risk") or mf.get("nfo_risk")),
            "benchmark": bool(mf.get("benchmark") or mf.get("benchmark_name")),
            "lock_in": lock_in_present(lock_in),
        },
    }


def assert_groww(url: str) -> None:
    if "://groww.in/" not in url:
        raise ValueError(f"catalog URL is not groww.in: {url}")


def main() -> None:
    schemes_out = []
    for scheme in SCHEMES:
        assert_groww(scheme["source_url"])
        print(f"fetch {scheme['scheme_id']} ...")
        html = fetch_html(scheme["source_url"])
        save_html(scheme["local_path"], html)
        facts = scheme_facts(html)
        coverage = facts["coverage"]
        missing = [key for key, ok in coverage.items() if not ok]
        # lock-in is required only for ELSS; other schemes may have empty/zero lock-in
        if scheme["category"] != "elss":
            missing = [key for key in missing if key != "lock_in"]
        if missing:
            print(f"  WARNING missing facts: {missing}")
        else:
            print(f"  ok TER={facts['expense_ratio']} load={facts['exit_load']!r} sip={facts['min_sip_investment']} risk={facts['riskometer']!r} bench={facts['benchmark']!r} lock_in={facts['lock_in']}")
        schemes_out.append(
            {
                "scheme_id": scheme["scheme_id"],
                "scheme_name": scheme["scheme_name"],
                "category": scheme["category"],
                "source_url": scheme["source_url"],
                "source_title": f"Groww — {scheme['scheme_name']}",
                "local_path": scheme["local_path"],
                "publisher": "groww",
                "doc_type": "scheme_page",
                "as_of": facts["as_of"],
                "retrieved_on": TODAY,
                "facts": {
                    "expense_ratio": facts["expense_ratio"],
                    "exit_load": facts["exit_load"],
                    "min_sip_investment": facts["min_sip_investment"],
                    "riskometer": facts["riskometer"],
                    "benchmark": facts["benchmark"],
                    "lock_in": facts["lock_in"],
                },
                "coverage": coverage,
            }
        )

    education_out = []
    for page in EDUCATION:
        assert_groww(page["url"])
        print(f"fetch education {page['id']} ...")
        html = fetch_html(page["url"])
        save_html(page["local_path"], html)
        education_out.append(
            {
                "id": page["id"],
                "title": page["title"],
                "url": page["url"],
                "local_path": page["local_path"],
                "publisher": "groww",
                "doc_type": "education",
                "as_of": TODAY,
                "retrieved_on": TODAY,
            }
        )

    process_out = []
    for page in PROCESS:
        assert_groww(page["url"])
        print(f"fetch process {page['id']} ...")
        try:
            html = fetch_html(page["url"])
        except urllib.error.HTTPError as exc:
            print(f"  WARNING {page['url']} -> HTTP {exc.code}")
            continue
        save_html(page["local_path"], html)
        process_out.append(
            {
                "id": page["id"],
                "title": page["title"],
                "url": page["url"],
                "local_path": page["local_path"],
                "publisher": "groww",
                "doc_type": "process",
                "fact_types": page["fact_types"],
                "as_of": TODAY,
                "retrieved_on": TODAY,
            }
        )

    catalog = {
        "publisher": "groww",
        "host_allowlist": ["groww.in"],
        "retrieved_on": TODAY,
        "schemes": schemes_out,
        "education": education_out,
        "process": process_out,
        "coverage_checklist": {
            "expense_ratio": [s["scheme_id"] for s in schemes_out if s["coverage"]["expense_ratio"]],
            "exit_load": [s["scheme_id"] for s in schemes_out if s["coverage"]["exit_load"]],
            "min_sip": [s["scheme_id"] for s in schemes_out if s["coverage"]["min_sip"]],
            "riskometer": [s["scheme_id"] for s in schemes_out if s["coverage"]["riskometer"]],
            "benchmark": [s["scheme_id"] for s in schemes_out if s["coverage"]["benchmark"]],
            "elss_lock_in": [
                s["scheme_id"]
                for s in schemes_out
                if s["category"] == "elss" and s["coverage"]["lock_in"]
            ],
            "gold_fof_present": any(s["category"] == "gold-etf-fof" for s in schemes_out),
            "process_pages": [p["id"] for p in process_out],
            "education_pages": [p["id"] for p in education_out],
        },
    }
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {CATALOG_PATH}")


if __name__ == "__main__":
    main()
