#!/usr/bin/env python3
"""
Pipeline Runner — Orchestrates the full scan → verify → report → email pipeline.
Single entry point for the complete workflow.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        logger.warning(f"Config not found: {config_path}, using defaults.")
        return {}
    with open(config_path, "r") as f:
        return json.load(f)


def run_pipeline(config_path: str = "config/config.json", dry_run: bool = False, skip_email: bool = False):
    """
    Run the full pipeline: scan → verify → report → email.
    """
    config = load_config(config_path)
    results_dir = config.get("output", {}).get("results_dir", "results")
    today = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(results_dir, today)
    os.makedirs(daily_dir, exist_ok=True)

    scan_output = os.path.join(daily_dir, "scan.json")
    verified_output = os.path.join(daily_dir, "verified.json")
    report_output = os.path.join(daily_dir, "report.md")

    logger.info("=" * 60)
    logger.info(f"🚀 Tender Offer Arbitrage Scanner — {today}")
    logger.info("=" * 60)

    # ── Step 1: Scan ──
    logger.info("")
    logger.info("📡 Step 1/4: Scanning for active tender offers...")
    logger.info("-" * 40)

    try:
        from scan_tender_offers import run_scan, load_config as load_scan_config
        deals = run_scan(config, dry_run=dry_run)
        scan_data = {
            "scan_date": datetime.now().isoformat(),
            "total_opportunities": len(deals),
            "deals": deals,
        }
        with open(scan_output, "w") as f:
            json.dump(scan_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"✅ Found {len(deals)} opportunities → {scan_output}")
    except Exception as e:
        logger.error(f"❌ Scan failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not deals:
        logger.info("No opportunities found. Pipeline complete.")
        return True

    # ── Step 2: Verify ──
    logger.info("")
    logger.info("🔍 Step 2/4: Verifying SEC filings...")
    logger.info("-" * 40)

    if dry_run:
        logger.info("⏭️  Skipping verification in dry-run mode.")
        verified_output = scan_output
    else:
        try:
            from verify_filings import verify_deal
            verified_deals = []
            for deal in deals:
                verified = verify_deal(deal)
                verified_deals.append(verified)
                status = verified.get("verification_status", "unknown")
                logger.info(f"   {deal.get('ticker', '?')}: {status}")

            verified_data = {
                "scan_date": scan_data["scan_date"],
                "verification_date": datetime.now().isoformat(),
                "total_opportunities": len(verified_deals),
                "deals": verified_deals,
            }
            with open(verified_output, "w") as f:
                json.dump(verified_data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"✅ Verification complete → {verified_output}")
        except Exception as e:
            logger.warning(f"⚠️ Verification step failed ({e}), continuing with unverified data...")
            verified_output = scan_output

    # ── Step 3: Generate Report ──
    logger.info("")
    logger.info("📝 Step 3/4: Generating report...")
    logger.info("-" * 40)

    try:
        from generate_report import render_report, load_deals
        data = load_deals(verified_output)
        template_path = str(SCRIPT_DIR.parent / "templates" / "report_template.md")
        report = render_report(data, template_path)
        with open(report_output, "w") as f:
            f.write(report)
        logger.info(f"✅ Report generated → {report_output}")
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ── Step 4: Send Email ──
    logger.info("")
    logger.info("📧 Step 4/4: Sending email...")
    logger.info("-" * 40)

    email_config = config.get("email", {})
    if skip_email or not email_config.get("recipients"):
        logger.info("⏭️  Email skipped (no recipients configured or --skip-email flag).")
    else:
        try:
            from send_email import send_email
            success = send_email(config, report_output)
            if success:
                logger.info("✅ Email sent successfully.")
            else:
                logger.warning("⚠️ Email sending failed — see logs above.")
        except Exception as e:
            logger.warning(f"⚠️ Email step failed: {e}")

    # ── Summary ──
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"✅ Pipeline complete! Results in: {daily_dir}/")
    logger.info(f"   📄 Scan data:   {scan_output}")
    logger.info(f"   🔍 Verified:    {verified_output}")
    logger.info(f"   📝 Report:      {report_output}")
    logger.info("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="Run the full tender offer arbitrage pipeline")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    parser.add_argument("--dry-run", action="store_true", help="Use sample data, skip verification")
    parser.add_argument("--skip-email", action="store_true", help="Skip email sending")
    args = parser.parse_args()

    # Add script dir to path for imports
    sys.path.insert(0, str(SCRIPT_DIR))

    success = run_pipeline(args.config, dry_run=args.dry_run, skip_email=args.skip_email)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
