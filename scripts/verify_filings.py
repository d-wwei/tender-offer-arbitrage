#!/usr/bin/env python3
"""
SEC Filing Verifier — Downloads and parses tender offer documents from SEC EDGAR.
Extracts key terms: price, expiration, conditions, odd-lot rules, proration info.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "TenderOfferScanner/1.0 (contact@example.com)",
    "Accept": "text/html,application/xhtml+xml,application/json",
}

# Patterns to extract key terms from filing text
PATTERNS = {
    "offer_price": [
        r'\$\s*(\d+\.?\d*)\s*per\s*(common\s*)?share',
        r'purchase\s+price\s+of\s+\$\s*(\d+\.?\d*)',
        r'offer\s+price\s+of\s+\$\s*(\d+\.?\d*)',
        r'price\s+range\s+of\s+\$\s*(\d+\.?\d*)\s*to\s+\$\s*(\d+\.?\d*)',
    ],
    "expiry_date": [
        r'expir\w*\s+(?:on|at)\s+[\w\s,]*(\w+\s+\d{1,2},?\s+\d{4})',
        r'(?:expire|expiration|deadline).*?(\w+\s+\d{1,2},?\s+\d{4})',
        r'the\s+offer\s+will\s+expire\s+.*?(\w+\s+\d{1,2},?\s+\d{4})',
    ],
    "odd_lot": [
        r'odd[\s-]*lot',
        r'fewer\s+than\s+100\s+shares',
        r'less\s+than\s+100\s+shares',
        r'beneficial(?:ly)?\s+own(?:ing|s)?\s+(?:an\s+aggregate\s+of\s+)?fewer\s+than\s+100',
    ],
    "proration": [
        r'pro[\s-]*rat(?:a|ion|ed)',
        r'prorat(?:a|ion|ed)',
        r'proportional(?:ly)?\s+(?:reduce|adjust)',
    ],
    "total_value": [
        r'(?:up\s+to|aggregate)\s+(?:of\s+)?\$\s*(\d[\d,]*(?:\.\d+)?)\s*(?:million|billion)?',
        r'repurchas\w*\s+up\s+to\s+\$\s*(\d[\d,]*(?:\.\d+)?)',
    ],
    "conditions": [
        r'(?:condition|subject\s+to|contingent\s+upon)\s*[:.]?\s*([^.]+\.)',
    ],
}


def search_filing_on_edgar(ticker: str, filing_type: str = "SC TO-I") -> list:
    """Search EDGAR for a company's tender offer filings."""
    results = []
    try:
        # First, look up CIK by ticker
        cik_url = f"https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK={ticker}&type={filing_type.replace(' ', '+')}&dateb=&owner=include&count=10&search_text=&action=getcompany"
        resp = requests.get(cik_url, headers=HEADERS, timeout=30)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="tableFile2")
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        link_tag = cols[1].find("a")
                        filing_url = "https://www.sec.gov" + link_tag["href"] if link_tag else None
                        results.append({
                            "filing_type": cols[0].get_text(strip=True),
                            "description": cols[2].get_text(strip=True),
                            "filed_date": cols[3].get_text(strip=True),
                            "filing_url": filing_url,
                        })
    except Exception as e:
        logger.error(f"Error searching EDGAR for {ticker}: {e}")

    return results


def download_filing_text(filing_index_url: str) -> str:
    """Download the full text of a filing from its EDGAR index page."""
    try:
        resp = requests.get(filing_index_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        # Find the main document link (usually the .htm or .txt file)
        table = soup.find("table", class_="tableFile")
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    doc_type = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                    link = cols[2].find("a")
                    if link and (doc_type in ["SC TO-I", "SC TO-T", "SC 14D-9", ""] or
                                 link["href"].endswith((".htm", ".html", ".txt"))):
                        doc_url = "https://www.sec.gov" + link["href"]
                        doc_resp = requests.get(doc_url, headers=HEADERS, timeout=60)
                        if doc_resp.status_code == 200:
                            return doc_resp.text

        # Fallback: try to find any HTML document
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if href.endswith((".htm", ".html")) and "/Archives/" in href:
                doc_url = "https://www.sec.gov" + href if href.startswith("/") else href
                doc_resp = requests.get(doc_url, headers=HEADERS, timeout=60)
                if doc_resp.status_code == 200:
                    return doc_resp.text

    except Exception as e:
        logger.error(f"Error downloading filing: {e}")

    return ""


def extract_terms_from_text(text: str) -> dict:
    """Extract key tender offer terms from filing text using regex patterns."""
    # Clean HTML
    soup = BeautifulSoup(text, "html.parser")
    clean_text = soup.get_text(separator=" ", strip=True)

    terms = {
        "offer_prices": [],
        "expiry_dates": [],
        "has_odd_lot_priority": False,
        "has_proration": False,
        "total_values": [],
        "conditions": [],
        "raw_excerpts": {},
    }

    # Extract offer prices
    for pattern in PATTERNS["offer_price"]:
        matches = re.findall(pattern, clean_text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                terms["offer_prices"].extend([m for m in match if m])
            else:
                terms["offer_prices"].append(match)

    # Extract expiry dates
    for pattern in PATTERNS["expiry_date"]:
        matches = re.findall(pattern, clean_text, re.IGNORECASE)
        terms["expiry_dates"].extend(matches)

    # Detect odd-lot priority
    for pattern in PATTERNS["odd_lot"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            terms["has_odd_lot_priority"] = True
            # Extract context around the match
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 200)
                end = min(len(clean_text), match.end() + 200)
                terms["raw_excerpts"]["odd_lot_context"] = clean_text[start:end]
            break

    # Detect proration
    for pattern in PATTERNS["proration"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            terms["has_proration"] = True
            break

    # Extract total value
    for pattern in PATTERNS["total_value"]:
        matches = re.findall(pattern, clean_text, re.IGNORECASE)
        terms["total_values"].extend(matches)

    # Extract conditions
    for pattern in PATTERNS["conditions"]:
        matches = re.findall(pattern, clean_text, re.IGNORECASE)
        terms["conditions"].extend(matches[:5])  # Limit to 5

    # Deduplicate
    terms["offer_prices"] = list(set(terms["offer_prices"]))
    terms["expiry_dates"] = list(set(terms["expiry_dates"]))
    terms["total_values"] = list(set(terms["total_values"]))

    return terms


def verify_deal(deal: dict) -> dict:
    """
    Verify a deal by downloading and parsing its SEC filing.
    Updates the deal dict with verified information.
    """
    ticker = deal.get("ticker", "")
    filing_type = deal.get("filing_type", "SC TO-I")

    logger.info(f"Verifying {ticker} ({filing_type})...")

    # Search for filings
    filings = search_filing_on_edgar(ticker, filing_type)
    if not filings:
        # Try alternative filing type
        alt_type = "SC TO-T" if filing_type == "SC TO-I" else "SC TO-I"
        filings = search_filing_on_edgar(ticker, alt_type)

    if not filings:
        deal["verification_status"] = "no_filing_found"
        deal["verification_notes"] = f"No {filing_type} filing found on EDGAR for {ticker}"
        return deal

    # Use the most recent filing
    latest = filings[0]
    deal["filing_url"] = latest.get("filing_url", deal.get("filing_url"))
    deal["filing_date"] = latest.get("filed_date")

    # Download and parse filing text
    filing_text = ""
    if latest.get("filing_url"):
        filing_text = download_filing_text(latest["filing_url"])

    if not filing_text:
        deal["verification_status"] = "filing_not_downloadable"
        deal["verification_notes"] = "Filing found but could not download document text"
        return deal

    # Extract terms
    terms = extract_terms_from_text(filing_text)

    # Cross-reference with scanned data
    notes = []

    if terms["offer_prices"]:
        deal["verified_offer_prices"] = terms["offer_prices"]
        notes.append(f"Filing price(s): ${', $'.join(terms['offer_prices'])}")

    if terms["expiry_dates"]:
        deal["verified_expiry_dates"] = terms["expiry_dates"]
        notes.append(f"Filing expiry: {', '.join(terms['expiry_dates'])}")

    if terms["has_odd_lot_priority"]:
        deal["odd_lot_priority"] = True
        deal["odd_lot_verified"] = True
        notes.append("Odd-lot priority CONFIRMED in filing")
    else:
        if deal.get("odd_lot_priority"):
            notes.append("Odd-lot priority was expected but NOT found in filing text — manual check recommended")

    if terms["has_proration"]:
        deal["proration_confirmed"] = True
        notes.append("Proration provisions confirmed")

    if terms.get("raw_excerpts", {}).get("odd_lot_context"):
        deal["odd_lot_excerpt"] = terms["raw_excerpts"]["odd_lot_context"]

    deal["verification_status"] = "verified"
    deal["verification_notes"] = " | ".join(notes) if notes else "Filing parsed, no additional details extracted"
    deal["verified_conditions"] = terms.get("conditions", [])

    return deal


def main():
    parser = argparse.ArgumentParser(description="Verify tender offer filings from SEC EDGAR")
    parser.add_argument("--input", required=True, help="Input JSON from scan_tender_offers.py")
    parser.add_argument("--output", default=None, help="Output verified JSON file")
    parser.add_argument("--ticker", default=None, help="Verify only a specific ticker")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        scan_data = json.load(f)

    deals = scan_data.get("deals", [])
    verified_deals = []

    for deal in deals:
        if args.ticker and deal.get("ticker") != args.ticker:
            verified_deals.append(deal)
            continue
        verified = verify_deal(deal)
        verified_deals.append(verified)

    output = {
        "scan_date": scan_data.get("scan_date"),
        "verification_date": datetime.now().isoformat(),
        "total_opportunities": len(verified_deals),
        "deals": verified_deals,
    }

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Verified results saved to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
