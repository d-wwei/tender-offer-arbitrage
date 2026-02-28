#!/usr/bin/env python3
"""
Email Sender — Sends the arbitrage report to multiple recipients via SMTP.
Supports Gmail, custom SMTP servers, HTML + Markdown attachment.
"""

import argparse
import email.mime.multipart
import email.mime.text
import json
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load email configuration from JSON."""
    with open(config_path, "r") as f:
        return json.load(f)


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown to basic HTML for email body."""
    try:
        # Try using markdown library if available
        import markdown
        return markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    except ImportError:
        # Basic fallback conversion
        html = md_text
        # Headers
        import re
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        # Line breaks
        html = html.replace('\n\n', '</p><p>')
        html = html.replace('\n', '<br>')
        html = f"<html><body style='font-family: Arial, sans-serif;'><p>{html}</p></body></html>"
        return html


def send_email(
    config: dict,
    report_path: str,
    recipients: list = None,
    subject: str = None,
) -> bool:
    """
    Send the report via email.

    Args:
        config: Full config dict containing 'email' section
        report_path: Path to the Markdown report file
        recipients: Override recipient list (comma-separated or list)
        subject: Override email subject

    Returns:
        True if sent successfully
    """
    email_config = config.get("email", {})

    smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_config.get("smtp_port", 587)
    use_tls = email_config.get("use_tls", True)
    username = email_config.get("username")
    password = email_config.get("password")
    from_addr = email_config.get("from_address", username)
    from_name = email_config.get("from_name", "Tender Offer Scanner")

    # Determine recipients
    if recipients:
        if isinstance(recipients, str):
            to_list = [r.strip() for r in recipients.split(",")]
        else:
            to_list = recipients
    else:
        to_list = email_config.get("recipients", [])

    if not to_list:
        logger.error("No recipients specified. Set 'recipients' in config or use --to flag.")
        return False

    if not username or not password:
        logger.error("SMTP username and password are required in config.")
        return False

    # Read report
    with open(report_path, "r") as f:
        report_md = f.read()

    # Create email
    today = datetime.now().strftime("%Y-%m-%d")
    if not subject:
        subject = f"📊 要约收购套利日报 — {today}"

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject

    # HTML body (converted from Markdown)
    html_content = markdown_to_html(report_md)
    html_part = MIMEText(html_content, "html", "utf-8")

    # Alternative container for text/html
    alt = MIMEMultipart("alternative")
    text_part = MIMEText(report_md, "plain", "utf-8")
    alt.attach(text_part)
    alt.attach(html_part)
    msg.attach(alt)

    # Attach original Markdown file
    md_attachment = MIMEApplication(report_md.encode("utf-8"), Name=f"tender_offer_report_{today}.md")
    md_attachment["Content-Disposition"] = f'attachment; filename="tender_offer_report_{today}.md"'
    msg.attach(md_attachment)

    # Send
    try:
        logger.info(f"Connecting to {smtp_server}:{smtp_port}...")
        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)

        server.login(username, password)
        server.sendmail(from_addr, to_list, msg.as_string())
        server.quit()

        logger.info(f"✅ Report sent successfully to {len(to_list)} recipient(s): {', '.join(to_list)}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("❌ SMTP authentication failed. Check username/password. For Gmail, use App Password.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send arbitrage report via email")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--report", required=True, help="Path to Markdown report file")
    parser.add_argument("--to", default=None, help="Override recipients (comma-separated)")
    parser.add_argument("--subject", default=None, help="Override email subject")
    parser.add_argument("--dry-run", action="store_true", help="Print email details without sending")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.dry_run:
        email_config = config.get("email", {})
        recipients = args.to.split(",") if args.to else email_config.get("recipients", [])
        print(f"--- DRY RUN ---")
        print(f"SMTP Server: {email_config.get('smtp_server')}:{email_config.get('smtp_port')}")
        print(f"From: {email_config.get('from_name', 'Scanner')} <{email_config.get('from_address')}>")
        print(f"To: {', '.join(recipients)}")
        print(f"Subject: 📊 要约收购套利日报 — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"Report: {args.report}")
        print(f"Report size: {os.path.getsize(args.report)} bytes")
        return

    recipients = args.to.split(",") if args.to else None
    success = send_email(config, args.report, recipients=recipients, subject=args.subject)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
