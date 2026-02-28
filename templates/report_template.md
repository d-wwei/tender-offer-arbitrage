# {{ report_title }}

> **生成时间**: {{ generated_at }}
> **扫描日期**: {{ scan_date }}
> **数据来源**: SEC EDGAR, Yahoo Finance, InsideArbitrage

---

## 📊 活跃套利机会总览

| 排名 | 股票 | 类型 | 要约价 | 当前价 | 价差 | 截止日 | Odd-Lot | 推荐度 |
|------|------|------|--------|--------|------|--------|---------|--------|
{% for deal in deals -%}
| {{ deal.rank }} | **{{ deal.ticker }}** | {{ deal.offer_type }} | ${{ deal.offer_price }} | ${{ deal.current_price }} | {{ deal.spread_pct }}% | {{ deal.expiry_date }} | {{ "✅" if deal.odd_lot_priority else "❌" }} | {{ deal.rating }} |
{% endfor %}

---

{% for deal in deals %}
## {{ deal.rank_emoji }} {{ deal.ticker }} ({{ deal.company_name }})

| 项目 | 详情 |
|------|------|
| **类型** | {{ deal.offer_type_detail }} |
| **要约价** | ${{ deal.offer_price }}/股 |
| **当前价** | ${{ deal.current_price }}/股 |
| **价差** | ${{ deal.spread_abs }}/股 ({{ deal.spread_pct }}%) |
| **回购/收购总额** | ${{ deal.total_value }} |
| **截止日** | {{ deal.expiry_date }} |
| **剩余天数** | {{ deal.days_remaining }}天 |
| **年化收益率** | {{ deal.annualized_return }}% |
| **Odd-Lot 优先** | {{ "✅ 是" if deal.odd_lot_priority else "❌ 否" }} |
| **SEC Filing** | [{{ deal.filing_id }}]({{ deal.filing_url }}) |

### 套利分析

{{ deal.analysis }}

### 风险因素

{% for risk in deal.risks -%}
- {{ risk }}
{% endfor %}

{% if deal.odd_lot_priority %}
### Odd-Lot 策略 (≤99股)

| 买入股数 | 成本 | 收入 | 毛利 | 收益率 |
|---------|------|------|------|--------|
| 99 | ${{ deal.odd_lot_cost_99 }} | ${{ deal.odd_lot_revenue_99 }} | ${{ deal.odd_lot_profit_99 }} | {{ deal.spread_pct }}% |
| 50 | ${{ deal.odd_lot_cost_50 }} | ${{ deal.odd_lot_revenue_50 }} | ${{ deal.odd_lot_profit_50 }} | {{ deal.spread_pct }}% |
{% endif %}

---

{% endfor %}

## 🎯 行动建议

{% for rec in recommendations -%}
{{ loop.index }}. {{ rec }}
{% endfor %}

---

> [!NOTE]
> 本报告由 Tender Offer Arbitrage Scanner 自动生成，仅供参考，不构成投资建议。
