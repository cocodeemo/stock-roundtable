#!/usr/bin/env python3
"""
股票圆桌辩论 —— 自动抓取实时行情 + 注入辩论引擎 + 生成 HTML 报告

用法:
    python3 stock_debate.py 688270
    python3 stock_debate.py 000762        # 西藏矿业
    python3 stock_debate.py 00700         # 港股腾讯（自动识别）
    python3 stock_debate.py 688270 --rounds 3
"""

import sys
import os
import json
import tempfile
import subprocess
import time
from datetime import datetime

from common import log, load_hermes_config, DEFAULT_API_BASE
from data_fetch import (
    fetch_stock_quote,
    fetch_company_profile,
    fetch_eastmoney_quote,
    fetch_financial_data,
    fetch_industry_context,
)
from validation import cross_validate, filter_roles


# ── 构造带实时数据的辩论问题 ──

def build_question(quote: dict, fin: dict = None, company_profile: str = "", industry_context: str = "") -> str:
    """把实时数据注入问题，包含动态公司背景和产业链格局"""

    st_warning = ""
    if quote.get('is_st'):
        st_warning = "⚠️ 该股当前处于 ST（风险警示）状态。"

    fin_section = ""
    if fin and fin.get('revenue'):
        split_note = ""
        if fin.get('split_factor', 1) > 1:
            split_note = f"\n- ⚠️ 该股最近有送转股（除权后调整系数 ×{fin['split_factor']:.1f}），以上每股数据已做除权修正"

        fin_section = f"""
【最新财务数据 · {fin.get('report_date', '')}】{split_note}
- 营业总收入：{fin['revenue']/1e8:.2f}亿（同比{fin['revenue_yoy']:+.1f}%）
- 净利润：{fin['net_profit']/1e8:.2f}亿（同比{fin['net_profit_yoy']:+.1f}%）
- 毛利率：{fin['gross_margin']:.1f}% | 净利率：{fin['net_margin']:.1f}%
- EPS（除权后）：{fin['eps']:.4f}元 | 每股净资产（除权后）：{fin['bps']:.2f}元
- ROE：{fin['roe']:.1f}% | 资产负债率：{fin['debt_ratio']:.1f}%
- 经营现金流/股（除权后）：{fin['ocf_per_share']:.2f}元
- 应收账款周转天数：{fin['receivable_days']:.0f}天"""

    # 动态公司背景
    bg_section = ""
    if company_profile:
        bg_section = f"\n【公司主营业务】\n{company_profile}"
    else:
        bg_section = "\n【公司背景】\n请根据你的训练数据判断该公司的主营业务和行业属性。"

    # 产业链格局
    industry_section = ""
    if industry_context:
        industry_section = f"\n【产业链格局】\n{industry_context}"

    market_tag = "港股" if quote.get('is_hk') else "A股"

    # 动态关注点
    focus_points = ["估值是否合理？", "行业景气度如何？"]
    if fin and fin.get('revenue'):
        if fin['net_profit_yoy'] < -30:
            focus_points.append("利润大幅下滑的原因是什么？能否逆转？")
        if fin['debt_ratio'] > 50:
            focus_points.append(f"资产负债率{fin['debt_ratio']:.0f}%偏高，偿债压力如何？")
        if fin['receivable_days'] > 90:
            focus_points.append(f"应收账款周转{fin['receivable_days']:.0f}天，回款是否存在风险？")
    if quote.get('is_st'):
        focus_points.append("ST状态意味着什么风险？摘帽需要什么条件？")
    focus_str = "、".join(focus_points)

    q = f"""{quote['name']}({quote['code']})当前投资价值如何评估？

【实时行情 · {quote.get('date', '')} · {market_tag}】
- 最新价：{quote['price']}元
- 涨跌幅：{quote['change_pct']:+.2f}%
- 今日振幅：{quote['high']}-{quote['low']}
- PE(TTM)：{quote['pe_ttm']:.0f}倍
- 总市值：约{quote['market_cap']:.0f}亿
- 52周高低（前复权）：{quote['high_52w']}-{quote['low_52w']}
{st_warning}{fin_section}
{bg_section}
{industry_section}

请各角色从自己的框架出发进行分析，同时考虑三种情境：
- 尚未持有：现在是否值得买入？
- 已持有：应继续持有、加仓还是减仓？
- 无论哪种：现在的风险收益比如何？重点关注：{focus_str}。"""

    return q


# ── 构造 HTML 快照 ──

def build_snapshot(quote: dict, fin: dict = None, em: dict = None) -> dict:
    def fmt(v, unit=''):
        if isinstance(v, float):
            return f"{v:.2f}{unit}" if v else '-'
        return str(v) if v else '-'

    pct_class = 'cc-snap-up' if quote.get('change_pct', 0) >= 0 else 'cc-snap-down'

    snap = {
        f'{quote["name"]}({quote["code"]})': {
            'value': fmt(quote.get('price')),
            'sub': f'{quote.get("change_pct", 0):+.2f}%',
            'sub_class': pct_class,
        },
        'PE(TTM)': {
            'value': f'{quote.get("pe_ttm", 0):.0f}x',
            'sub': f'静态{em.get("pe_static", 0):.0f}x' if em and em.get('pe_static', 0) > 0 else '',
            'sub_class': '',
        },
        '总市值': {
            'value': f'{quote.get("market_cap", 0):.0f}亿',
            'sub': '',
            'sub_class': '',
        },
        '52周区间': {
            'value': f'{quote.get("high_52w", 0):.0f}',
            'sub': f'最低{quote.get("low_52w", 0):.0f}',
            'sub_class': '',
        },
    }

    if quote.get('is_st'):
        snap['⚠️ 风险警示'] = {
            'value': 'ST',
            'sub': '特别处理',
            'sub_class': 'cc-snap-up',
        }

    if fin and fin.get('revenue'):
        snap.update({
            '营收(最新期)': {
                'value': f'{fin["revenue"]/1e8:.2f}亿',
                'sub': f'同比{fin["revenue_yoy"]:+.0f}%',
                'sub_class': 'cc-snap-up' if fin['revenue_yoy'] > 0 else 'cc-snap-down',
            },
            '净利润': {
                'value': f'{fin["net_profit"]/1e8:.2f}亿',
                'sub': f'同比{fin["net_profit_yoy"]:+.0f}%',
                'sub_class': 'cc-snap-up' if fin['net_profit_yoy'] > 0 else 'cc-snap-down',
            },
            '毛利率/ROE': {
                'value': f'{fin["gross_margin"]:.0f}%',
                'sub': f'ROE {fin["roe"]:.1f}%',
                'sub_class': '',
            },
            '经营现金流/股': {
                'value': f'{fin["ocf_per_share"]:.2f}元',
                'sub': '负值=现金流出' if fin['ocf_per_share'] < 0 else '',
                'sub_class': 'cc-snap-down' if fin['ocf_per_share'] < 0 else '',
            },
        })

    return snap


# ── 主流程 ──

def main():
    # 解析 --rounds 参数（复用 common.parse_debate_args 的统一校验）
    custom_rounds = 2
    args = list(sys.argv[1:])
    code = None
    i = 0
    while i < len(args):
        if args[i] == '--rounds' and i + 1 < len(args):
            r = int(args[i + 1])
            custom_rounds = max(1, min(r, 3))
            i += 2
        else:
            code = args[i]
            i += 1

    if not code:
        log.info("用法: python3 stock_debate.py <股票代码> [--rounds 3]")
        log.info("示例: python3 stock_debate.py 688270")
        log.info("      python3 stock_debate.py 00700      # 港股")
        log.info("      python3 stock_debate.py 688270 --rounds 3")
        sys.exit(1)

    # 获取 API key 和 base URL（统一使用共享模块）
    cfg = load_hermes_config()
    api_key = cfg.get("api_key", "")
    api_base = cfg.get("api_base")

    if not api_key:
        log.error("未找到 API key（~/.hermes/config.yaml 或环境变量 TAOTOKEN_API_KEY）")
        sys.exit(1)

    # 拉行情
    log.info("📡 获取 %s 实时行情...", code)
    quote = fetch_stock_quote(code)
    if not quote or not quote.get('price'):
        log.error("行情数据获取失败，退出")
        sys.exit(1)

    log.info("   %s: %s元 | PE=%.0fx | 市值≈%.0f亿",
             quote['name'], quote['price'], quote['pe_ttm'], quote['market_cap'])
    if quote.get('is_st'):
        log.warning("   ⚠️ ST 风险警示股！")
    if quote.get('is_hk'):
        log.info("   🇭🇰 港股")

    # 拉 EastMoney 行情（交叉验证用）
    log.info("📡 获取 %s EastMoney 行情(交叉验证)...", code)
    em_quote = fetch_eastmoney_quote(code)

    # 拉公司背景
    log.info("📋 获取 %s 公司信息...", code)
    company_profile = fetch_company_profile(code)
    if company_profile:
        log.info("   ✅ 主营业务: %s...", company_profile[:80])
    else:
        log.warning("   ⚠️ 未获取到公司信息，LLM 将凭训练数据自行判断")

    # 拉财报
    log.info("📊 获取 %s 财务数据...", code)
    fin = fetch_financial_data(code)
    if fin:
        log.info("   %s: 营收%.2f亿(YoY%+.0f%%) 净利%.2f亿 毛利率%.0f%% ROE%.1f%%",
                 fin.get('report_date', ''),
                 fin['revenue']/1e8, fin['revenue_yoy'],
                 fin['net_profit']/1e8, fin['gross_margin'], fin['roe'])
    else:
        log.warning("   ⚠️ 未获取到财务数据，将仅使用行情数据")

    # ── 三方交叉验证 ──
    log.info("🔍 数据交叉验证...")
    validation_errors, validation_warnings = cross_validate(quote, fin, em_quote)

    # 送转股提醒
    if fin and fin.get('split_factor', 1) > 1:
        validation_warnings.append(f"送转股 ×{fin['split_factor']:.1f}，每股数据已除权")
        log.info("   🔄 送转股 ×%.1f", fin['split_factor'])

    # 52 周 K线
    if quote.get('high_52w', 0) > 0:
        log.info("   ✅ 52周区间: %.0f-%.0f（前复权）", quote['high_52w'], quote['low_52w'])

    if validation_errors:
        log.error("   ❌ 数据异常: %s", '; '.join(validation_errors))
    elif validation_warnings:
        log.warning("   ⚠️ 注意事项: %s", '; '.join(validation_warnings))
    else:
        log.info("   ✅ 数据校验通过（三方一致）")

    # 过滤角色
    roles, skipped_roles = filter_roles(quote, fin)
    roles_arg = ','.join(roles)
    log.info("   🎭 参与角色(%d): %s", len(roles), roles_arg)

    # 拉产业链格局
    industry_context = fetch_industry_context(quote, fin, api_key, api_base)

    # 构造问题
    question = build_question(quote, fin, company_profile, industry_context)
    log.info("")
    log.info("🎭 启动圆桌辩论（%d 轮）...", custom_rounds)
    log.info("")

    # 跑辩论
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 用临时文件传问题文本（避免 Windows 命令行长度截断）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', encoding='utf-8', delete=False) as tf:
        tf.write(question)
        question_file = tf.name

    log.info("⚔️  辩论后台运行中，请等待...")
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, 'demo.py', '--question-file', question_file,
             '--roles', roles_arg, '--rounds', str(custom_rounds)],
            capture_output=True, text=True, timeout=900,
            env={**os.environ, 'TAOTOKEN_API_KEY': api_key, 'OPENAI_API_KEY': api_key,
                 'TAOTOKEN_API_BASE': api_base or DEFAULT_API_BASE},
            cwd=script_dir,
        )
    finally:
        try:
            os.unlink(question_file)
        except OSError:
            pass

    elapsed = time.time() - t0
    log.info("⏱️  辩论耗时 %.1f 分钟", elapsed / 60)

    # 转发 demo.py 的输出
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        log.warning("STDERR: %s", result.stderr[:2000])

    if result.returncode != 0:
        log.error("辩论引擎退出码: %d", result.returncode)
        sys.exit(1)

    # 生成 HTML 报告
    log.info("")
    log.info("📄 生成 HTML 报告...")
    from html_report import render_html

    json_path = 'last_debate_result.json'
    with open(json_path, encoding='utf-8') as f:
        debate_result = json.load(f)

    # 清理角色名中的 emoji 前缀
    name = quote['name'].replace('*', '').replace('ST', '').strip()
    snapshot = build_snapshot(quote, fin, em_quote)
    date_str = quote.get('date', datetime.now().strftime('%Y-%m-%d'))
    display_title = f"{quote['name']}({code})投资价值评估"

    html = render_html(debate_result, stock_data={
        'date': date_str,
        'title_prefix': f'{name} · ',
        'display_title': display_title,
        'snapshot': snapshot,
        'validation_errors': validation_errors,
        'validation_warnings': validation_warnings,
        'skipped_roles': skipped_roles,
    })

    date_tag = datetime.now().strftime('%Y%m%d')
    desktop = os.path.expanduser('~/Desktop')
    os.makedirs(desktop, exist_ok=True)
    out_path = os.path.join(desktop, f'report_{name}_{code}_{date_tag}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    log.info("")
    log.info("✅ 报告已生成: %s", out_path)
    log.info("   文件大小: %d 字符", len(html))


if __name__ == '__main__':
    main()
