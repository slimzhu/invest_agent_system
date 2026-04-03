from __future__ import annotations

import re
from html import unescape


def clean_filing_text(raw_text: str) -> str:
    text = raw_text
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_between(
    text: str,
    start_patterns: list[str],
    end_patterns: list[str],
    max_len: int = 12000,
) -> str:
    lower_text = text.lower()

    start_idx = -1
    for sp in start_patterns:
        idx = lower_text.find(sp.lower())
        if idx != -1:
            start_idx = idx
            break

    if start_idx == -1:
        return ""

    end_idx = len(text)
    for ep in end_patterns:
        idx = lower_text.find(ep.lower(), start_idx + 20)
        if idx != -1:
            end_idx = min(end_idx, idx)

    snippet = text[start_idx:end_idx]
    return snippet[:max_len].strip()


def extract_mda_section(clean_text: str, form: str) -> str:
    form = form.upper().strip()

    if form == "10-K":
        return _extract_between(
            clean_text,
            start_patterns=[
                "management’s discussion and analysis of financial condition and results of operations",
                "management's discussion and analysis of financial condition and results of operations",
            ],
            end_patterns=[
                "quantitative and qualitative disclosures about market risk",
                "financial statements and supplementary data",
                "controls and procedures",
            ],
            max_len=10000,
        )

    if form == "10-Q":
        return _extract_between(
            clean_text,
            start_patterns=[
                "management’s discussion and analysis of financial condition and results of operations",
                "management's discussion and analysis of financial condition and results of operations",
            ],
            end_patterns=[
                "quantitative and qualitative disclosures about market risk",
                "controls and procedures",
                "part ii",
            ],
            max_len=8000,
        )

    return ""


def extract_segment_or_business_section(clean_text: str, form: str) -> str:
    form = form.upper().strip()

    if form == "10-K":
        return _extract_between(
            clean_text,
            start_patterns=[
                "business",
                "our business",
                "segments",
            ],
            end_patterns=[
                "risk factors",
                "properties",
                "legal proceedings",
            ],
            max_len=8000,
        )

    if form == "10-Q":
        return _extract_between(
            clean_text,
            start_patterns=[
                "results of operations",
                "segments",
            ],
            end_patterns=[
                "liquidity and capital resources",
                "controls and procedures",
            ],
            max_len=6000,
        )

    return ""


def compact_section(text: str, max_chars: int = 2500) -> str:
    return text[:max_chars].strip() if text else ""