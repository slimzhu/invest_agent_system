from __future__ import annotations

from typing import Any

from app.config import settings
from app.utils.http_utils import get_json_with_resilience, get_text_with_resilience


def _sec_headers() -> dict[str, str]:
    return {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def normalize_cik(cik: str) -> str:
    return "".join(ch for ch in str(cik) if ch.isdigit()).zfill(10)


def get_sec_company_submissions(cik: str) -> dict[str, Any]:
    cik_num = normalize_cik(cik)
    url = f"https://data.sec.gov/submissions/CIK{cik_num}.json"

    data = get_json_with_resilience(
        url,
        headers=_sec_headers(),
        timeout=30,
        retries=2,
        use_proxy=False,   # SEC 不走代理
    )

    if isinstance(data, dict) and data.get("_error"):
        return {
            "source_name": "sec_submissions",
            "enabled": False,
            "cik": cik_num,
            "error": data["_error"],
            "filings": {},
        }

    return {
        "source_name": "sec_submissions",
        "enabled": True,
        "cik": cik_num,
        "company_name": data.get("name", ""),
        "tickers": data.get("tickers", []),
        "sic": data.get("sic", ""),
        "sic_description": data.get("sicDescription", ""),
        "filings": data.get("filings", {}),
    }


def get_sec_company_facts(cik: str) -> dict[str, Any]:
    cik_num = normalize_cik(cik)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_num}.json"

    data = get_json_with_resilience(
        url,
        headers=_sec_headers(),
        timeout=30,
        retries=2,
        use_proxy=False,   # SEC 不走代理
    )

    if isinstance(data, dict) and data.get("_error"):
        return {
            "source_name": "sec_company_facts",
            "enabled": False,
            "cik": cik_num,
            "error": data["_error"],
            "facts": {},
        }

    return {
        "source_name": "sec_company_facts",
        "enabled": True,
        "cik": cik_num,
        "entity_name": data.get("entityName", ""),
        "facts": data.get("facts", {}),
    }


def build_filing_document_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_no_padding = str(int(normalize_cik(cik)))
    accession_no_dashes = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_padding}/{accession_no_dashes}/{primary_document}"


def extract_recent_filings(
    submissions_data: dict[str, Any],
    forms_filter: list[str] | None = None,
    max_items: int = 12,
) -> list[dict[str, Any]]:
    recent = submissions_data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    primary_doc_descriptions = recent.get("primaryDocDescription", [])

    result: list[dict[str, Any]] = []
    cik = submissions_data.get("cik", "")
    company_name = submissions_data.get("company_name", "")

    for i in range(len(forms)):
        form = forms[i] if i < len(forms) else ""
        if forms_filter and form not in forms_filter:
            continue

        accession_number = accession_numbers[i] if i < len(accession_numbers) else ""
        primary_document = primary_documents[i] if i < len(primary_documents) else ""
        filing_date = filing_dates[i] if i < len(filing_dates) else ""
        description = primary_doc_descriptions[i] if i < len(primary_doc_descriptions) else ""

        filing_url = ""
        if cik and accession_number and primary_document:
            filing_url = build_filing_document_url(cik, accession_number, primary_document)

        result.append(
            {
                "company_name": company_name,
                "form": form,
                "filing_date": filing_date,
                "accession_number": accession_number,
                "primary_document": primary_document,
                "description": description,
                "filing_url": filing_url,
            }
        )

        if len(result) >= max_items:
            break

    return result


def fetch_filing_text(filing_url: str) -> str:
    return get_text_with_resilience(
        filing_url,
        headers={"User-Agent": settings.SEC_USER_AGENT},
        timeout=35,
        retries=2,
        use_proxy=False,
    )

def _fact_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    fy = item.get("fy") or 0
    filed = item.get("filed") or ""
    end = item.get("end") or ""
    frame = item.get("frame") or ""
    form = item.get("form") or ""
    return (fy, filed, end, frame, form)


def _pick_latest_fact_value(units_block: dict[str, Any]) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    latest_key: tuple[Any, ...] | None = None

    for values in units_block.values():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            key = _fact_sort_key(item)
            if latest_key is None or key > latest_key:
                latest_key = key
                latest = item

    return latest


def extract_key_company_facts(company_facts_data: dict[str, Any]) -> dict[str, Any]:
    if not company_facts_data.get("enabled"):
        return {
            "entity_name": "",
            "key_facts": {},
        }

    us_gaap = company_facts_data.get("facts", {}).get("us-gaap", {})

    wanted = {
        "Revenue": "Revenues",
        "NetIncomeLoss": "NetIncomeLoss",
        "Assets": "Assets",
        "OperatingCashFlow": "NetCashProvidedByUsedInOperatingActivities",
        "Capex": "PaymentsToAcquirePropertyPlantAndEquipment",
        "GrossProfit": "GrossProfit",
    }

    extracted: dict[str, Any] = {}

    for label, gaap_key in wanted.items():
        fact_block = us_gaap.get(gaap_key, {})
        units = fact_block.get("units", {})
        extracted[label] = _pick_latest_fact_value(units)

    return {
        "entity_name": company_facts_data.get("entity_name", ""),
        "key_facts": extracted,
    }
