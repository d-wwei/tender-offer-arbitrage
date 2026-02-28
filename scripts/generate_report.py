#!/usr/bin/env python3
"""
Report Generator — Takes scan/verified JSON and produces a formatted Markdown report.
Uses Jinja2 templates for flexible output formatting.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"


def load_deals(input_path: str) -> dict:
    """Load deals from scan/verified JSON."""
    with open(input_path, "r") as f:
        return json.load(f)


def generate_recommendations(deals: list) -> list:
    """Generate action recommendations based on deals."""
    recs = []
    urgent = [d for d in deals if d.get("days_remaining", 999) <= 14 and d.get("spread_pct", 0) > 1]
    odd_lot = [d for d in deals if d.get("odd_lot_priority") and d.get("spread_pct", 0) > 0]
    full_acq = [d for d in deals if "Full" in d.get("offer_type", "") and d.get("spread_pct", 0) > 0]

    if urgent:
        tickers = ", ".join([d["ticker"] for d in urgent])
        recs.append(f"🔴 **紧急行动**: {tickers} — 距截止日不足14天，需立即决定是否参与")

    if odd_lot:
        for d in odd_lot:
            profit = d.get("odd_lot_profit_99", 0)
            recs.append(
                f"⭐ **{d['ticker']} Odd-Lot 套利**: 买入≤99股 (成本 ~${d.get('odd_lot_cost_99', 0):.0f})，"
                f"预期利润 ~${profit:.0f} ({d.get('spread_pct', 0)}%)"
            )

    if full_acq:
        for d in full_acq:
            recs.append(
                f"📊 **{d['ticker']} 并购套利**: 价差 {d.get('spread_pct', 0)}%，"
                f"预计 {d.get('days_remaining', '?')} 天完成"
            )

    if not recs:
        recs.append("目前没有发现高确定性的套利机会，建议继续观察。")

    recs.append("💡 确认您的券商支持参与美股 tender offer（如 Interactive Brokers、Schwab）")
    recs.append("⚠️ 以上分析仅供参考，不构成投资建议。请进行独立研究。")

    return recs


def render_report(data: dict, template_path: str = None) -> str:
    """Render the report using Jinja2 template."""
    deals = data.get("deals", [])
    recommendations = generate_recommendations(deals)

    context = {
        "report_title": "🔍 要约收购套利机会扫描报告",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_date": data.get("scan_date", datetime.now().isoformat()),
        "deals": deals,
        "recommendations": recommendations,
    }

    if template_path and os.path.exists(template_path):
        template_dir = os.path.dirname(template_path)
        template_name = os.path.basename(template_path)
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template(template_name)
        return template.render(**context)
    else:
        # Fallback: generate report without template
        return _generate_fallback_report(context)


def _generate_fallback_report(ctx: dict) -> str:
    """Generate report without Jinja2 template as fallback."""
    lines = []
    lines.append(f"# {ctx['report_title']}")
    lines.append("")
    lines.append(f"> **生成时间**: {ctx['generated_at']}")
    lines.append(f"> **扫描日期**: {ctx['scan_date']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## 📊 活跃套利机会总览")
    lines.append("")
    lines.append("| 排名 | 股票 | 类型 | 要约价 | 当前价 | 价差 | 截止日 | Odd-Lot | 推荐度 |")
    lines.append("|------|------|------|--------|--------|------|--------|---------|--------|")

    for deal in ctx["deals"]:
        odd = "✅" if deal.get("odd_lot_priority") else "❌"
        lines.append(
            f"| {deal.get('rank', '-')} | **{deal.get('ticker', '?')}** | "
            f"{deal.get('offer_type', '?')} | ${deal.get('offer_price', '?')} | "
            f"${deal.get('current_price', '?')} | {deal.get('spread_pct', '?')}% | "
            f"{deal.get('expiry_date', '?')} | {odd} | {deal.get('rating', '?')} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-deal details
    for deal in ctx["deals"]:
        lines.append(f"## {deal.get('rank_emoji', '')} {deal.get('ticker', '?')} ({deal.get('company_name', '?')})")
        lines.append("")
        lines.append("| 项目 | 详情 |")
        lines.append("|------|------|")
        lines.append(f"| **类型** | {deal.get('offer_type_detail', deal.get('offer_type', '?'))} |")
        lines.append(f"| **要约价** | ${deal.get('offer_price', '?')}/股 |")
        lines.append(f"| **当前价** | ${deal.get('current_price', '?')}/股 |")
        lines.append(f"| **价差** | {deal.get('spread_pct', '?')}% (${deal.get('spread_abs', '?')}/股) |")
        lines.append(f"| **截止日** | {deal.get('expiry_date', '?')} ({deal.get('days_remaining', '?')}天) |")
        lines.append(f"| **年化收益率** | {deal.get('annualized_return', '?')}% |")
        odd_str = "✅ 已确认" if deal.get("odd_lot_verified") else ("✅ 是" if deal.get("odd_lot_priority") else "❌ 否")
        lines.append(f"| **Odd-Lot 优先** | {odd_str} |")
        if deal.get("verification_status"):
            lines.append(f"| **验证状态** | {deal.get('verification_status')} |")
        lines.append("")

        # Analysis
        if deal.get("analysis"):
            lines.append("### 分析")
            lines.append("")
            lines.append(deal["analysis"])
            lines.append("")

        # Risks
        if deal.get("risks"):
            lines.append("### 风险因素")
            lines.append("")
            for risk in deal["risks"]:
                lines.append(f"- {risk}")
            lines.append("")

        # Odd-lot table
        if deal.get("odd_lot_priority") and deal.get("odd_lot_cost_99"):
            lines.append("### Odd-Lot 策略 (≤99股)")
            lines.append("")
            lines.append("| 买入股数 | 成本 | 收入 | 毛利 | 收益率 |")
            lines.append("|---------|------|------|------|--------|")
            lines.append(
                f"| 99 | ${deal.get('odd_lot_cost_99', 0):.2f} | "
                f"${deal.get('odd_lot_revenue_99', 0):.2f} | "
                f"${deal.get('odd_lot_profit_99', 0):.2f} | {deal.get('spread_pct', 0)}% |"
            )
            lines.append(
                f"| 50 | ${deal.get('odd_lot_cost_50', 0):.2f} | "
                f"${deal.get('odd_lot_revenue_50', 0):.2f} | "
                f"${deal.get('odd_lot_profit_50', 0):.2f} | {deal.get('spread_pct', 0)}% |"
            )
            lines.append("")

        # Verification notes
        if deal.get("verification_notes"):
            lines.append("### 验证信息")
            lines.append("")
            lines.append(f"> {deal['verification_notes']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Recommendations
    lines.append("## 🎯 行动建议")
    lines.append("")
    for i, rec in enumerate(ctx["recommendations"], 1):
        lines.append(f"{i}. {rec}")
    lines.append("")

    lines.append("> **免责声明**: 本报告由自动化工具生成，仅供参考，不构成投资建议。")

    return "\n".join(lines)


def generate_sample_report() -> str:
    """Generate a sample report using built-in sample data."""
    from scan_tender_offers import SAMPLE_DEALS, calculate_spread, generate_risk_analysis, rank_deals

    deals = []
    for deal in SAMPLE_DEALS:
        deal = calculate_spread(deal)
        deal["risks"] = generate_risk_analysis(deal)
        from scan_tender_offers import _generate_analysis_text
        deal["analysis"] = _generate_analysis_text(deal)
        deals.append(deal)

    deals = rank_deals(deals)

    data = {
        "scan_date": datetime.now().isoformat(),
        "deals": deals,
    }

    return render_report(data, str(TEMPLATE_DIR / "report_template.md"))


def main():
    parser = argparse.ArgumentParser(description="Generate arbitrage report from scan data")
    parser.add_argument("--input", default=None, help="Input JSON from scan/verify step")
    parser.add_argument("--output", default=None, help="Output Markdown report path")
    parser.add_argument("--template", default=str(TEMPLATE_DIR / "report_template.md"), help="Jinja2 template path")
    parser.add_argument("--sample", action="store_true", help="Generate sample report")
    args = parser.parse_args()

    if args.sample:
        report = generate_sample_report()
    else:
        if not args.input:
            print("Error: --input is required (or use --sample for demo)", file=sys.stderr)
            sys.exit(1)
        data = load_deals(args.input)
        report = render_report(data, args.template)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
