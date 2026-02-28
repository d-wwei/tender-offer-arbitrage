#!/usr/bin/env python3
"""
Scheduler — Sets up daily cron jobs or launchd plists for automated pipeline execution.
Supports Linux (cron) and macOS (cron / launchd).
"""

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
PIPELINE_SCRIPT = SCRIPT_DIR / "run_pipeline.py"
CRON_MARKER = "# tender-offer-arbitrage-scanner"

LAUNCHD_PLIST_NAME = "com.tender-offer-scanner.daily"
LAUNCHD_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_PLIST_NAME}.plist"


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return json.load(f)


def get_python_path() -> str:
    """Get the full path to the Python interpreter."""
    return sys.executable


def parse_run_time(time_str: str) -> tuple:
    """Parse HH:MM format to (hour, minute)."""
    parts = time_str.strip().split(":")
    return int(parts[0]), int(parts[1])


# ─── Cron-based scheduling (Linux + macOS) ─────────────────────────

def install_cron(config_path: str, run_time: str = "08:00"):
    """Install a cron job for the pipeline."""
    hour, minute = parse_run_time(run_time)
    python = get_python_path()
    config_abs = os.path.abspath(config_path)
    pipeline = str(PIPELINE_SCRIPT)
    log_dir = SCRIPT_DIR.parent / "results" / "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = log_dir / "cron.log"

    cron_line = (
        f"{minute} {hour} * * 1-5 "  # Weekdays only (Mon-Fri)
        f"cd {SCRIPT_DIR.parent} && "
        f"{python} {pipeline} --config {config_abs} "
        f">> {log_file} 2>&1 "
        f"{CRON_MARKER}"
    )

    # Remove existing entry first
    _remove_cron_entry()

    # Add new entry
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"

        proc = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
        if proc.returncode == 0:
            logger.info(f"✅ Cron job installed: daily at {run_time} (weekdays)")
            logger.info(f"   Command: {cron_line}")
            logger.info(f"   Log: {log_file}")
        else:
            logger.error(f"❌ Failed to install cron: {proc.stderr}")
    except Exception as e:
        logger.error(f"❌ Error installing cron: {e}")


def _remove_cron_entry():
    """Remove existing tender offer scanner cron entry."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return

        lines = result.stdout.split("\n")
        filtered = [l for l in lines if CRON_MARKER not in l]
        new_crontab = "\n".join(filtered)

        subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
    except Exception:
        pass


def uninstall_cron():
    """Remove the cron job."""
    _remove_cron_entry()
    logger.info("✅ Cron job removed.")


def show_cron_status():
    """Show current cron status."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            print("No crontab found.")
            return

        lines = result.stdout.split("\n")
        scanner_lines = [l for l in lines if CRON_MARKER in l]
        if scanner_lines:
            print("✅ Tender Offer Scanner is scheduled:")
            for line in scanner_lines:
                print(f"   {line}")
        else:
            print("❌ No scheduled task found for Tender Offer Scanner.")
    except Exception as e:
        print(f"Error checking cron: {e}")


# ─── launchd-based scheduling (macOS) ──────────────────────────────

def install_launchd(config_path: str, run_time: str = "08:00"):
    """Install a macOS launchd plist for the pipeline."""
    hour, minute = parse_run_time(run_time)
    python = get_python_path()
    config_abs = os.path.abspath(config_path)
    pipeline = str(PIPELINE_SCRIPT)
    log_dir = SCRIPT_DIR.parent / "results" / "logs"
    os.makedirs(log_dir, exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCHD_PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{pipeline}</string>
        <string>--config</string>
        <string>{config_abs}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{SCRIPT_DIR.parent}</string>
    <key>StartCalendarInterval</key>
    <array>
        <!-- Monday through Friday -->
        <dict>
            <key>Weekday</key><integer>1</integer>
            <key>Hour</key><integer>{hour}</integer>
            <key>Minute</key><integer>{minute}</integer>
        </dict>
        <dict>
            <key>Weekday</key><integer>2</integer>
            <key>Hour</key><integer>{hour}</integer>
            <key>Minute</key><integer>{minute}</integer>
        </dict>
        <dict>
            <key>Weekday</key><integer>3</integer>
            <key>Hour</key><integer>{hour}</integer>
            <key>Minute</key><integer>{minute}</integer>
        </dict>
        <dict>
            <key>Weekday</key><integer>4</integer>
            <key>Hour</key><integer>{hour}</integer>
            <key>Minute</key><integer>{minute}</integer>
        </dict>
        <dict>
            <key>Weekday</key><integer>5</integer>
            <key>Hour</key><integer>{hour}</integer>
            <key>Minute</key><integer>{minute}</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>{log_dir}/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/launchd_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>"""

    # Unload existing plist if present
    uninstall_launchd(quiet=True)

    # Write plist
    os.makedirs(LAUNCHD_PLIST_PATH.parent, exist_ok=True)
    with open(LAUNCHD_PLIST_PATH, "w") as f:
        f.write(plist_content)

    # Load plist
    try:
        result = subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST_PATH)],
                                capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ launchd job installed: daily at {run_time} (weekdays)")
            logger.info(f"   Plist: {LAUNCHD_PLIST_PATH}")
            logger.info(f"   Logs: {log_dir}/")
        else:
            logger.error(f"❌ launchctl load failed: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ Error loading plist: {e}")


def uninstall_launchd(quiet: bool = False):
    """Remove the macOS launchd plist."""
    try:
        if LAUNCHD_PLIST_PATH.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST_PATH)],
                           capture_output=True, text=True)
            os.remove(LAUNCHD_PLIST_PATH)
            if not quiet:
                logger.info("✅ launchd job removed.")
        elif not quiet:
            logger.info("No launchd job found.")
    except Exception as e:
        if not quiet:
            logger.error(f"Error removing launchd job: {e}")


def show_launchd_status():
    """Show macOS launchd status."""
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        if LAUNCHD_PLIST_NAME in result.stdout:
            print(f"✅ Tender Offer Scanner is scheduled via launchd ({LAUNCHD_PLIST_NAME})")
            # Show details
            if LAUNCHD_PLIST_PATH.exists():
                print(f"   Plist: {LAUNCHD_PLIST_PATH}")
        else:
            print("❌ No launchd job found for Tender Offer Scanner.")
    except Exception as e:
        print(f"Error checking launchd: {e}")


def main():
    parser = argparse.ArgumentParser(description="Schedule daily tender offer scanning")
    parser.add_argument("--install", action="store_true", help="Install scheduled task")
    parser.add_argument("--uninstall", action="store_true", help="Remove scheduled task")
    parser.add_argument("--status", action="store_true", help="Show current schedule")
    parser.add_argument("--config", default="config/config.json", help="Path to config")
    parser.add_argument("--time", default=None, help="Override run time (HH:MM)")
    parser.add_argument("--use-launchd", action="store_true", help="Use macOS launchd instead of cron")
    args = parser.parse_args()

    is_mac = platform.system() == "Darwin"
    use_launchd = args.use_launchd or (is_mac and not args.install)

    if args.status:
        if is_mac:
            show_launchd_status()
        show_cron_status()
        return

    if args.uninstall:
        uninstall_cron()
        if is_mac:
            uninstall_launchd()
        return

    if args.install:
        config = load_config(args.config)
        schedule_config = config.get("schedule", {})
        run_time = args.time or schedule_config.get("run_time", "08:00")

        if use_launchd and is_mac:
            install_launchd(args.config, run_time)
        else:
            install_cron(args.config, run_time)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
