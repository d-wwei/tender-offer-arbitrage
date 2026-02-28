---
name: tender-offer-arbitrage
description: "Scan, verify, and report tender offer arbitrage opportunities in the US stock market. Supports automated daily scanning, SEC filing verification, spread analysis, odd-lot detection, and multi-recipient email alerts."
version: "1.0.0"
---

# Tender Offer Arbitrage Scanner

An automated skill for discovering and analyzing tender offer arbitrage opportunities in the US equity market.

## Overview

This skill provides a complete pipeline:
1. **Scan** — Search SEC EDGAR and financial data sources for active tender offers
2. **Verify** — Download and parse official SEC filings to extract deal terms
3. **Report** — Generate a ranked Markdown report with spread analysis
4. **Notify** — Send the report to one or more email recipients
5. **Schedule** — Set up daily automated runs

## Prerequisites

Install Python dependencies:
```bash
cd scripts/
pip install -r requirements.txt
```

### Required API/Services
- **Internet access** — for SEC EDGAR, Yahoo Finance, web scraping
- **SMTP credentials** — for email notifications (Gmail App Password, or any SMTP server)

## Configuration

Copy and edit the config file:
```bash
cp config/config.example.json config/config.json
```

Edit `config/config.json` with your settings:

```jsonc
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",       // Use App Password for Gmail
    "from_address": "your-email@gmail.com",
    "recipients": [
      "recipient1@example.com",
      "recipient2@example.com"
    ]
  },
  "schedule": {
    "enabled": true,
    "run_time": "08:00",          // Local time (24h format)
    "timezone": "America/New_York"
  },
  "scan": {
    "min_spread_pct": 0.5,        // Minimum spread % to include
    "include_odd_lot_only": false, // If true, only show deals with odd-lot priority
    "max_days_to_expiry": 90      // Ignore offers expiring beyond this
  }
}
```

## Usage

### Full Pipeline (one command)
```bash
python3 scripts/run_pipeline.py --config config/config.json
```

### Individual Steps

**Step 1: Scan for active tender offers**
```bash
python3 scripts/scan_tender_offers.py --config config/config.json --output results/scan.json
```

**Step 2: Verify SEC filings for each opportunity**
```bash
python3 scripts/verify_filings.py --input results/scan.json --output results/verified.json
```

**Step 3: Generate report**
```bash
python3 scripts/generate_report.py --input results/verified.json --output results/report.md
```

**Step 4: Send email**
```bash
python3 scripts/send_email.py --config config/config.json --report results/report.md
```

You can also specify recipients on the command line:
```bash
python3 scripts/send_email.py --config config/config.json --report results/report.md \
  --to "user1@example.com,user2@example.com"
```

### Schedule Daily Runs
```bash
# Install a cron job for daily execution
python3 scripts/scheduler.py --install --config config/config.json

# Remove the cron job
python3 scripts/scheduler.py --uninstall

# Show current schedule
python3 scripts/scheduler.py --status
```

### Dry Run (no network, sample data)
```bash
python3 scripts/run_pipeline.py --dry-run
```

## Data Sources

| Source | Purpose |
|--------|---------|
| SEC EDGAR EFTS | Search for SC TO-I, SC TO-T, SC 14D-9 filings |
| SEC EDGAR Filing Pages | Download and parse tender offer documents |
| Yahoo Finance (yfinance) | Current stock prices, shares outstanding |
| InsideArbitrage.com | Cross-reference active tender offer list |

## Key Concepts

### Tender Offer Types
- **Issuer Bid (SC TO-I)**: Company buys back its own shares (e.g., DCBO, YEXT)
- **Third-Party Bid (SC TO-T)**: Another company acquires shares (e.g., GLDD, ACLX)
- **Dutch Auction**: Price range; final price determined by lowest price that fills the buyback
- **Fixed Price**: Single offer price for all shares

### Odd-Lot Priority
Many tender offers give priority to shareholders holding < 100 shares. Their shares are accepted in full before any proration is applied to larger holders. This is the key edge for small arbitrage positions.

### Spread Calculation
```
Gross Spread = (Offer Price - Current Price) / Current Price × 100%
Annualized = Gross Spread × (365 / Days to Expiry)
```

## Output Example

The generated report includes:
- Summary table of all active opportunities ranked by attractiveness
- Per-deal analysis: spread, odd-lot status, proration risk, key dates
- Risk factors and action items
- Timestamp and data source citations

## Agent Workflow

When an agent uses this skill, it should follow this workflow:

1. **Check config** — Verify `config/config.json` exists and has valid settings
2. **Run scan** — Execute `scan_tender_offers.py` to find active offers
3. **Verify filings** — Execute `verify_filings.py` to validate deal terms from SEC
4. **Generate report** — Execute `generate_report.py` to create the analysis
5. **Review report** — Read the generated Markdown and provide any additional commentary
6. **Send email** — Execute `send_email.py` if email is configured
7. **Log results** — Save scan history to `results/` directory for tracking

If running in scheduled mode, the agent should use `scheduler.py` to set up cron.
