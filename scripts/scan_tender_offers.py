#!/usr/bin/env python3
"""
Tender Offer Scanner — Scans SEC EDGAR and financial sources for active tender offers.
Outputs structured JSON with spread calculations and odd-lot detection.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

try:
    import yfinance as yf
except ImportError:
    yf = None
    logging.warning("yfinance not installed — stock price lookups will be skipped.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_API_URL = "https://efts.sec.gov/LATEST/search-index"

# SEC EDGAR Full-Text Search API
EDGAR_SEARCH_API = "https://efts.sec.gov/LATEST/search-index"

HEADERS = {
    "User-Agent": "TenderOfferScanner/1.0 (contact@example.com)",
    "Accept": "application/json",
}

# Sample data for dry-run mode
SAMPLE_DEALS = [
    {
        "ticker": "YEXT",
        "company_name": "Yext, Inc.",
        "offer_type": "Issuer Bid (Dutch Auction)",
        "offer_type_detail": "Modified Dutch Auction — Issuer repurchase",
        "offer_price": "5.75-6.50",
        "offer_price_low": 5.75,
        "offer_price_high": 6.50,
        "current_price": 5.68,
        "total_value": "180,000,000",
        "total_value_num": 180000000,
        "expiry_date": "2026-03-12",
        "filing_type": "SC TO-I",
        "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=yext&CIK=&type=SC+TO-I&dateb=&owner=include&count=10",
        "filing_id": "SC TO-I (Yext)",
        "odd_lot_priority": True,
        "odd_lot_threshold": 100,
        "shares_outstanding": 117600000,
        "market_cap": 668000000,
        "conditions": ["No minimum tender condition for issuer bid"],
        "status": "active",
    },
    {
        "ticker": "DCBO",
        "company_name": "Docebo Inc.",
        "offer_type": "Issuer Bid (Fixed Price)",
        "offer_type_detail": "Fixed Price Substantial Issuer Bid",
        "offer_price": "20.40",
        "offer_price_low": 20.40,
        "offer_price_high": 20.40,
        "current_price": 17.05,
        "total_value": "60,000,000",
        "total_value_num": 60000000,
        "expiry_date": "2026-03-10",
        "filing_type": "SC TO-I",
        "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=docebo&CIK=&type=SC+TO-I&dateb=&owner=include&count=10",
        "filing_id": "SC TO-I (Docebo)",
        "odd_lot_priority": True,
        "odd_lot_threshold": 100,
        "shares_outstanding": 28750000,
        "market_cap": 490000000,
        "conditions": ["Intercap Equity may participate to maintain ownership %"],
        "status": "active",
    },
    {
        "ticker": "LE",
        "company_name": "Lands' End, Inc.",
        "offer_type": "Third-Party (Partial)",
        "offer_type_detail": "Third-Party partial acquisition by WHP Global",
        "offer_price": "45.00",
        "offer_price_low": 45.00,
        "offer_price_high": 45.00,
        "current_price": 17.40,
        "total_value": "100,000,000",
        "total_value_num": 100000000,
        "expiry_date": "2026-03-26",
        "filing_type": "SC TO-T",
        "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=lands+end&CIK=&type=SC+TO-T&dateb=&owner=include&count=10",
        "filing_id": "SC TO-T (Lands' End / WHP)",
        "odd_lot_priority": False,
        "odd_lot_threshold": 100,
        "shares_outstanding": 31000000,
        "market_cap": 539000000,
        "conditions": ["JV transaction must close first", "Only acquiring ~7% of shares"],
        "status": "active",
    },
    {
        "ticker": "GLDD",
        "company_name": "Great Lakes Dredge & Dock Corp.",
        "offer_type": "Third-Party (Full Acquisition)",
        "offer_type_detail": "All-cash acquisition by Saltchuk Resources",
        "offer_price": "17.00",
        "offer_price_low": 17.00,
        "offer_price_high": 17.00,
        "current_price": 16.91,
        "total_value": "1,200,000,000",
        "total_value_num": 1200000000,
        "expiry_date": "2026-06-30",
        "filing_type": "SC TO-T",
        "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=great+lakes+dredge&CIK=&type=SC+TO-T&dateb=&owner=include&count=10",
        "filing_id": "SC TO-T (GLDD / Saltchuk)",
        "odd_lot_priority": False,
        "odd_lot_threshold": 100,
        "shares_outstanding": 66000000,
        "market_cap": 1116000000,
        "conditions": ["Regulatory approval required", "Majority tender condition"],
        "status": "active",
    },
    {
        "ticker": "ACLX",
        "company_name": "Arcellx, Inc.",
        "offer_type": "Third-Party (Full Acquisition)",
        "offer_type_detail": "All-cash acquisition by Gilead Sciences + $5 CVR",
        "offer_price": "115.00",
        "offer_price_low": 115.00,
        "offer_price_high": 115.00,
        "current_price": 115.00,
        "total_value": "7,800,000,000",
        "total_value_num": 7800000000,
        "expiry_date": "2026-06-30",
        "filing_type": "SC TO-T",
        "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=arcellx&CIK=&type=SC+TO-T&dateb=&owner=include&count=10",
        "filing_id": "SC TO-T (ACLX / Gilead)",
        "odd_lot_priority": False,
        "odd_lot_threshold": 100,
        "shares_outstanding": 67800000,
        "market_cap": 7797000000,
        "conditions": ["Regulatory approval", "$5 CVR contingent on anito-cel sales >= $6B by 2029"],
        "status": "active",
    },
]


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}, using defaults.")
        return {"scan": {"min_spread_pct": 0.5, "max_days_to_expiry": 90, "exclude_debt_offers": True}}
    with open(config_path, "r") as f:
        return json.load(f)


def _extract_ticker_from_display(display_name: str):
    """Extract ticker symbol from EDGAR display_names like 'Company Name  (TICKER)  (CIK XXX)'."""
    if not display_name:
        return None
    # Match 1-5 uppercase letters in parentheses, but not CIK patterns
    matches = re.findall(r'\(([A-Z]{1,5})\)', display_name)
    for m in matches:
        if m != "CIK":
            return m
    return None


def _clean_company_name(display_name: str):
    """Extract clean company name from EDGAR display_names."""
    if not display_name:
        return "Unknown"
    # Remove (TICKER) and (CIK XXXX) parts
    name = re.sub(r'\s*\([A-Z]{1,5}\)\s*', ' ', display_name)
    name = re.sub(r'\s*\(CIK\s*\d+\)\s*', '', name)
    return name.strip() or "Unknown"


def search_edgar_filings(filing_types: list = None, days_back: int = 60) -> list:
    """
    Search SEC EDGAR for recent tender offer filings.
    Uses the EDGAR full-text search system (EFTS).
    Returns deduplicated list by CIK, with tickers extracted from display_names.
    """
    if filing_types is None:
        filing_types = ["SC TO-I", "SC TO-T"]

    results = []
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    seen_ciks = {}  # CIK -> most recent filing

    for ftype in filing_types:
        try:
            search_url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": '"%s"' % ftype,
                "forms": ftype,
                "dateRange": "custom",
                "startdt": date_from,
                "enddt": datetime.now().strftime("%Y-%m-%d"),
            }

            resp = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "hits" in data and "hits" in data["hits"]:
                    for hit in data["hits"]["hits"]:
                        source = hit.get("_source", {})
                        display = (source.get("display_names", [""])[0]
                                   if source.get("display_names") else "")
                        ciks = source.get("ciks", [])
                        cik = ciks[0] if ciks else None

                        # Extract ticker from display_names
                        ticker = _extract_ticker_from_display(display)
                        company_name = _clean_company_name(display)

                        # Build filing URL
                        file_id = hit.get("_id", "")
                        accession = file_id.split(":")[0] if ":" in file_id else ""
                        if accession and cik:
                            cik_clean = cik.lstrip("0") or "0"
                            acc_clean = accession.replace("-", "")
                            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{accession}-index.htm"
                        else:
                            filing_url = None

                        entry = {
                            "filing_type": ftype,
                            "company_name": company_name,
                            "ticker": ticker,
                            "filed_date": source.get("file_date"),
                            "filing_url": filing_url,
                            "cik": cik,
                            "filing_id": f"{ftype} ({ticker or company_name})",
                        }

                        # Dedup by CIK — keep most recent
                        key = cik or company_name
                        if key not in seen_ciks:
                            seen_ciks[key] = entry
                        else:
                            existing_date = seen_ciks[key].get("filed_date", "")
                            new_date = entry.get("filed_date", "")
                            if new_date > existing_date:
                                seen_ciks[key] = entry

            else:
                logger.warning(f"EDGAR search returned status {resp.status_code} for {ftype}")

        except Exception as e:
            logger.error(f"Error searching EDGAR for {ftype}: {e}")

    results = list(seen_ciks.values())

    # If EFTS failed, try fallback
    if not results:
        logger.info("EFTS returned no results, trying EDGAR company search...")
        results = _search_edgar_company_filings(filing_types, days_back)

    return results


def _search_edgar_company_filings(filing_types: list, days_back: int) -> list:
    """Fallback: search EDGAR via company filing search."""
    results = []
    for ftype in filing_types:
        try:
            url = (f"https://www.sec.gov/cgi-bin/browse-edgar?"
                   f"action=getcompany&type={ftype.replace(' ', '+')}"
                   f"&dateb=&owner=include&count=40&search_text=&action=getcompany")
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", class_="tableFile2")
                if table:
                    rows = table.find_all("tr")[1:]
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 5:
                            results.append({
                                "filing_type": ftype,
                                "company_name": cols[1].get_text(strip=True),
                                "ticker": None,
                                "filed_date": cols[3].get_text(strip=True),
                                "filing_url": ("https://www.sec.gov" + cols[1].find("a")["href"]
                                               if cols[1].find("a") else None),
                                "cik": cols[0].get_text(strip=True),
                            })
        except Exception as e:
            logger.error(f"Error in fallback EDGAR search for {ftype}: {e}")
    return results


def scrape_insidearbitrage() -> list:
    """Scrape InsideArbitrage.com for active tender offer list."""
    deals = []
    try:
        url = "https://www.insidearbitrage.com/tender-offers/"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 6:
                        deals.append({
                            "ticker": cols[0].get_text(strip=True),
                            "company_name": cols[1].get_text(strip=True),
                            "offer_price": cols[2].get_text(strip=True),
                            "expiry_date": cols[3].get_text(strip=True),
                            "filing_type": cols[4].get_text(strip=True) if len(cols) > 4 else "Unknown",
                        })
        else:
            logger.warning(f"InsideArbitrage returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Could not scrape InsideArbitrage: {e}")
    return deals


def get_stock_price(ticker: str):
    """Fetch current stock price and key data via yfinance."""
    if yf is None:
        return None
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1d")
        current_price = hist["Close"].iloc[-1] if not hist.empty else info.get("currentPrice") or info.get("previousClose")
        return {
            "current_price": round(float(current_price), 2) if current_price else None,
            "shares_outstanding": info.get("sharesOutstanding"),
            "market_cap": info.get("marketCap"),
            "name": info.get("shortName") or info.get("longName"),
        }
    except Exception as e:
        logger.warning(f"Could not fetch price for {ticker}: {e}")
        return None


def calculate_spread(deal: dict) -> dict:
    """Calculate spread metrics for a deal."""
    current = deal.get("current_price")
    offer_high = deal.get("offer_price_high")
    offer_low = deal.get("offer_price_low")

    if not current or not offer_high:
        return deal

    spread_abs = round(offer_high - current, 2)
    spread_pct = round((offer_high - current) / current * 100, 2)

    # Handle low end for Dutch auctions
    spread_abs_low = round(offer_low - current, 2) if offer_low != offer_high else spread_abs
    spread_pct_low = round((offer_low - current) / current * 100, 2) if offer_low != offer_high else spread_pct

    # Days to expiry
    try:
        expiry = dateparser.parse(deal.get("expiry_date", ""))
        days_remaining = max((expiry - datetime.now()).days, 1)
    except Exception:
        days_remaining = 30

    annualized = round(spread_pct * 365 / days_remaining, 1) if days_remaining > 0 else 0

    deal.update({
        "spread_abs": spread_abs,
        "spread_pct": spread_pct,
        "spread_abs_low": spread_abs_low,
        "spread_pct_low": spread_pct_low,
        "days_remaining": days_remaining,
        "annualized_return": annualized,
    })

    # Odd-lot calculations
    if deal.get("odd_lot_priority"):
        for qty in [99, 50]:
            deal[f"odd_lot_cost_{qty}"] = round(current * qty, 2)
            deal[f"odd_lot_revenue_{qty}"] = round(offer_high * qty, 2)
            deal[f"odd_lot_profit_{qty}"] = round((offer_high - current) * qty, 2)

    return deal


def rank_deals(deals: list) -> list:
    """Rank deals by attractiveness (spread × odd-lot priority × time)."""
    for deal in deals:
        # Score: higher = better
        score = 0
        spread = deal.get("spread_pct", 0)
        days = deal.get("days_remaining", 999)

        if spread > 0:
            score += spread * 10
        if deal.get("odd_lot_priority"):
            score += 50
        if days <= 30:
            score += 20
        elif days <= 60:
            score += 10

        # Penalize partial acquisitions (high proration risk)
        if "Partial" in deal.get("offer_type", ""):
            score -= 30

        # Penalize zero/negative spread
        if spread <= 0:
            score -= 50

        deal["score"] = score

    deals.sort(key=lambda d: d.get("score", 0), reverse=True)

    rank_emojis = ["⭐1", "⭐2", "🥉", "4", "5", "6", "7", "8", "9", "10"]
    for i, deal in enumerate(deals):
        deal["rank"] = i + 1
        deal["rank_emoji"] = rank_emojis[i] if i < len(rank_emojis) else str(i + 1)
        stars = min(5, max(1, int(deal["score"] / 20)))
        deal["rating"] = "⭐" * stars

    return deals


def generate_risk_analysis(deal: dict) -> list:
    """Generate risk factors for a deal."""
    risks = []
    spread = deal.get("spread_pct", 0)

    if spread < 0:
        risks.append("⚠️ 负价差 — 当前股价高于要约价")
    if spread > 20:
        risks.append("⚠️ 价差异常大 — 可能反映高proration风险或条件性风险")

    if "Partial" in deal.get("offer_type", ""):
        risks.append("🔴 部分收购 — 严重的proration风险")
    if not deal.get("odd_lot_priority"):
        risks.append("⚠️ 无odd-lot优先权 — 所有股东按比例缩减")

    conditions = deal.get("conditions", [])
    for cond in conditions:
        risks.append(f"📋 条件: {cond}")

    days = deal.get("days_remaining", 0)
    if days > 60:
        risks.append("⏳ 等待时间较长 — 资金占用成本增加")
    if days <= 5:
        risks.append("⚡ 即将截止 — 时间紧迫，可能来不及操作")

    risks.append("📉 要约可能被撤回或修改")

    return risks


def run_scan(config: dict, dry_run: bool = False) -> list:
    """
    Main scanning function. Combines multiple data sources.
    """
    if dry_run:
        logger.info("Running in dry-run mode with sample data...")
        deals = SAMPLE_DEALS.copy()
    else:
        logger.info("Scanning SEC EDGAR for active tender offer filings...")
        edgar_results = search_edgar_filings(
            filing_types=config.get("scan", {}).get("filing_types", ["SC TO-I", "SC TO-T"]),
            days_back=config.get("scan", {}).get("max_days_to_expiry", 90),
        )
        logger.info(f"Found {len(edgar_results)} EDGAR filings.")

        logger.info("Scraping InsideArbitrage for active tender offers...")
        ia_results = scrape_insidearbitrage()
        logger.info(f"Found {len(ia_results)} InsideArbitrage listings.")

        # Merge and deduplicate
        deals = _merge_sources(edgar_results, ia_results)

        # Enrich with stock prices
        for deal in deals:
            ticker = deal.get("ticker")
            if ticker:
                price_data = get_stock_price(ticker)
                if price_data:
                    deal["current_price"] = price_data.get("current_price") or deal.get("current_price")
                    deal["shares_outstanding"] = price_data.get("shares_outstanding") or deal.get("shares_outstanding")
                    deal["market_cap"] = price_data.get("market_cap") or deal.get("market_cap")
                    if not deal.get("company_name"):
                        deal["company_name"] = price_data.get("name")

    # Calculate spreads
    for deal in deals:
        deal = calculate_spread(deal)
        deal["risks"] = generate_risk_analysis(deal)
        deal["analysis"] = _generate_analysis_text(deal)

    # Filter by config
    min_spread = config.get("scan", {}).get("min_spread_pct", 0)
    max_days = config.get("scan", {}).get("max_days_to_expiry", 90)
    odd_lot_only = config.get("scan", {}).get("include_odd_lot_only", False)

    filtered = []
    for deal in deals:
        # If deal has no spread data (offer price unknown), still include it for verification
        has_spread = deal.get("spread_pct") is not None
        if has_spread and deal.get("spread_pct", 0) < min_spread and min_spread > 0:
            logger.info(f"Skipping {deal.get('ticker')} — spread {deal.get('spread_pct')}% < {min_spread}%")
            continue
        if has_spread and deal.get("days_remaining", 999) > max_days:
            continue
        if odd_lot_only and not deal.get("odd_lot_priority"):
            continue
        if not has_spread:
            deal["needs_verification"] = True
            deal["offer_type"] = deal.get("offer_type", "Pending Verification")
            deal["offer_type_detail"] = deal.get("offer_type_detail", "Details pending — needs SEC filing review")
        filtered.append(deal)

    # Rank
    ranked = rank_deals(filtered)
    logger.info(f"Scan complete. {len(ranked)} opportunities found.")
    return ranked


def _merge_sources(edgar_results: list, ia_results: list) -> list:
    """Merge results from EDGAR and InsideArbitrage, deduplicating."""
    merged = {}

    # EDGAR results keyed by CIK or ticker
    for result in edgar_results:
        ticker = result.get("ticker")
        cik = result.get("cik")
        key = ticker or cik or result.get("company_name")
        if key:
            # Skip entries without tickers (private funds, etc)
            if not ticker:
                continue
            if key not in merged:
                merged[key] = result
            else:
                # Supplement with newer data
                for k, v in result.items():
                    if v and not merged[key].get(k):
                        merged[key][k] = v

    # InsideArbitrage results
    for result in ia_results:
        ticker = result.get("ticker")
        if ticker and ticker not in merged:
            merged[ticker] = result
        elif ticker and ticker in merged:
            for k, v in result.items():
                if v and not merged[ticker].get(k):
                    merged[ticker][k] = v

    logger.info(f"Merged to {len(merged)} unique public-company deals.")
    return list(merged.values())


def _generate_analysis_text(deal: dict) -> str:
    """Generate human-readable analysis for a deal."""
    ticker = deal.get("ticker", "Unknown")
    spread = deal.get("spread_pct", 0)
    odd_lot = deal.get("odd_lot_priority", False)
    offer_type = deal.get("offer_type", "")
    days = deal.get("days_remaining", 0)

    lines = []

    if spread > 10 and odd_lot:
        lines.append(f"**{ticker} 是一个优质的 odd-lot 套利机会。** 价差 {spread}%，odd-lot 持有者（<100股）免受 proration。")
    elif spread > 5 and odd_lot:
        lines.append(f"{ticker} 提供中等价差 ({spread}%)，odd-lot 优先权增加确定性。")
    elif spread > 0:
        lines.append(f"{ticker} 存在正价差 ({spread}%)，但需注意 proration 和条件风险。")
    else:
        lines.append(f"{ticker} 当前价差极小或为负 ({spread}%)，套利空间有限。")

    if "Dutch Auction" in offer_type:
        lines.append("Dutch Auction 机制下，最终清算价取决于认购情况，可能高于最低价。建议以最高价提交。")
    if "Partial" in offer_type:
        lines.append("**注意：这是部分收购，proration 风险极高。** 大部分股份可能不被接受。")
    if days <= 14:
        lines.append(f"距截止日仅剩 {days} 天，需立即行动。")

    return " ".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scan for tender offer arbitrage opportunities")
    parser.add_argument("--config", default="config/config.json", help="Path to config file")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--dry-run", action="store_true", help="Use sample data (no network)")
    args = parser.parse_args()

    config = load_config(args.config)
    deals = run_scan(config, dry_run=args.dry_run)

    output = {
        "scan_date": datetime.now().isoformat(),
        "total_opportunities": len(deals),
        "deals": deals,
    }

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Results saved to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
