#!/usr/bin/env python3
"""
股票圆桌辩论 —— 自动抓取实时行情 + 注入辩论引擎 + 生成 HTML 报告

用法:
    python3 stock_debate.py 688270
    python3 stock_debate.py 000762        # 西藏矿业
    python3 stock_debate.py 00700         # 港股腾讯（自动识别）
    python3 stock_debate.py 688270 --rounds 3
"""

import sys, os, re, json, urllib.request, subprocess, time
from datetime import datetime

# ── 1. 获取实时行情 ──

def fetch_stock_quote(code: str) -> dict:
    """从腾讯行情 API 拉取实时数据，支持 A 股和港股"""
    # 判断交易所
    is_hk = False
    if code.startswith(('6', '9')):
        full_code = f"sh{code}"
    elif len(code) == 5 and code.startswith(('0', '3')):
        full_code = f"sz{code}"
    else:
        # 港股：需要 hk 前缀，补齐 5 位
        is_hk = True
        padded = code.zfill(5)
        full_code = f"hk{padded}"

    url = f"https://qt.gtimg.cn/q={full_code}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com/'
    })

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
            # 腾讯 API 返回 GBK 编码
            text = raw.decode('gbk', errors='replace')
    except Exception as e:
        print(f"❌ 行情获取失败: {e}")
        return {}

    # 解析: v_sh688270="1~ST臻镭~688270~70.00~..."
    m = re.search(r'="(.+)"', text)
    if not m:
        return {}

    fields = m.group(1).split('~')
    if len(fields) < 50:
        print(f"⚠️ 数据字段不足 (got {len(fields)})")
        return {}

    # 腾讯行情 API 字段索引
    name = fields[1]
    price = float(fields[3]) if fields[3] else 0
    prev_close = float(fields[4]) if fields[4] else 0
    change = float(fields[31]) if fields[31] else 0
    change_pct = float(fields[32]) if fields[32] else 0
    high = float(fields[33]) if fields[33] else 0
    low = float(fields[34]) if fields[34] else 0
    volume = int(fields[6]) if fields[6] else 0
    pe_ttm = float(fields[39]) if fields[39] else 0        # 动态市盈率
    market_cap = float(fields[45]) if fields[45] else 0     # 总市值(亿)

    # ── 拉 前复权 K 线取真实 52 周高低 ──
    real_high_52w = 0
    real_low_52w = 0
    # 两个端点轮流尝试
    endpoints = [
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,,,250,qfq",
        f"https://qt.gtimg.cn/q={full_code}",  # fallback
    ]
    kline_ok = False
    for kurl in endpoints:
        if kline_ok:
            break
        try:
            if 'fqkline' in kurl:
                with urllib.request.urlopen(urllib.request.Request(kurl, headers={
                    'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com/'
                }), timeout=10) as resp:
                    kd = json.loads(resp.read())
                    klines = kd.get('data', {}).get(full_code, {}).get('qfqday', [])
                    if klines:
                        real_high_52w = max(float(k[3]) for k in klines[-250:])
                        real_low_52w = min(float(k[4]) for k in klines[-250:])
                        kline_ok = True
        except Exception:
            continue

    # HK stocks use different field mapping
    if is_hk:
        # 港股 PE 在 fields[39]、市值不同（fields[44]=市值，单位可能不同）
        market_cap = float(fields[44]) if fields[44] else 0
        if not market_cap:
            market_cap = float(fields[45]) if fields[45] else 0

    high_52w = real_high_52w if real_high_52w else float(fields[47]) if fields[47] else 0
    low_52w = real_low_52w if real_low_52w else float(fields[48]) if fields[48] else 0

    # ST 检测
    is_st = 'ST' in name or '*ST' in name

    return {
        'code': code,
        'name': name,
        'price': price,
        'prev_close': prev_close,
        'change': change,
        'change_pct': change_pct,
        'high': high,
        'low': low,
        'volume': volume,
        'pe_ttm': pe_ttm,
        'high_52w': high_52w,
        'low_52w': low_52w,
        'market_cap': market_cap,
        'is_st': is_st,
        'is_hk': is_hk,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }


# ── 1.5 获取公司主营业务（动态背景）──

def fetch_company_profile(code: str) -> str:
    """通过 AKShare 获取公司主营业务描述，失败返回空"""
    try:
        import akshare as ak
        # 尝试个股信息
        try:
            info = ak.stock_individual_info_em(symbol=code)
            if info is not None and not info.empty:
                for _, row in info.iterrows():
                    if '主营' in str(row.get('item', '')):
                        biz = str(row.get('value', ''))
                        if biz and len(biz) > 10:
                            return biz[:200]
        except Exception:
            pass

        # 备选：公司概况
        try:
            profile = ak.stock_profile_cninfo(symbol=code)
            if profile is not None and not profile.empty:
                biz = str(profile.iloc[0].get('主营业务', ''))
                if biz and len(biz) > 10:
                    return biz[:200]
        except Exception:
            pass
    except Exception:
        pass
    return ""


# ── 1.6 EastMoney 行情（交叉验证用）──

def fetch_eastmoney_quote(code: str) -> dict:
    """从东方财富 API 获取实时行情，用于交叉验证"""
    # 沪市 1.xxx，深市 0.xxx
    if code.startswith(('6', '9')):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"

    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f58,f43,f46,f44,f45,f47,f48,f50,f51,f52,f116,f117,f162,f167,f168,f169,f170,f171"
    import json, urllib.request
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            d = data.get('data', {})
            if not d:
                return {}
            return {
                'name': d.get('f58', ''),
                'price': d.get('f43', 0) / 100 if d.get('f43') else 0,
                'pe_ttm': d.get('f162', 0) / 100 if d.get('f162') else 0,  # PE(TTM) ×100存储
                'market_cap': d.get('f116', 0) / 1e8 if d.get('f116') else 0,  # 总市值(元→亿)
            }
    except Exception:
        return {}


def cross_validate(quote: dict, fin: dict, em: dict) -> tuple:
    """三方交叉验证：腾讯行情 vs EastMoney（两源TTM PE对比）"""
    errors, warnings = [], []
    pe_tencent = quote.get('pe_ttm', 0)
    pe_em = em.get('pe_ttm', 0)

    # PE 两源对比（均为 TTM 口径，偏差>5%警告，>10%报错）
    if pe_tencent > 0 and pe_em > 0:
        pe_diff = abs(pe_tencent - pe_em) / min(pe_tencent, pe_em)
        if pe_diff > 0.10:
            errors.append(f'PE偏差{pe_diff:.0%}（腾讯{pe_tencent:.0f}x vs 东财{pe_em:.0f}x）')
        elif pe_diff > 0.05:
            warnings.append(f'PE轻微偏差{pe_diff:.0%}（腾讯{pe_tencent:.0f}x vs 东财{pe_em:.0f}x）')
        else:
            print(f"   ✅ PE一致: 腾讯{pe_tencent:.0f}x vs 东财{pe_em:.0f}x")

    # 市值对比（偏差>5%警告，>10%报错）
    mc_tencent = quote.get('market_cap', 0)
    mc_em = em.get('market_cap', 0)
    if mc_tencent > 0 and mc_em > 0:
        mc_diff = abs(mc_tencent - mc_em) / min(mc_tencent, mc_em)
        if mc_diff > 0.10:
            errors.append(f'市值偏差{mc_diff:.0%}（腾讯{mc_tencent:.0f}亿 vs 东财{mc_em:.0f}亿）')
        elif mc_diff > 0.05:
            warnings.append(f'市值轻微偏差{mc_diff:.0%}（腾讯{mc_tencent:.0f}亿 vs 东财{mc_em:.0f}亿）')
        else:
            print(f"   ✅ 市值一致: 腾讯{mc_tencent:.0f}亿 vs 东财{mc_em:.0f}亿")

    # PE 极端值 / PS 极端值
    use_pe = pe_tencent or pe_em or 0
    if use_pe > 200:
        warnings.append(f'PE {use_pe:.0f}x 极端高估')
    if fin and fin.get('revenue', 0) > 0:
        ps = (mc_tencent or mc_em) / (fin['revenue'] / 1e8)
        if ps > 100:
            warnings.append(f'PS {ps:.0f}x 极高')

    return errors, warnings


# ── 1.6 获取产业链格局（v4-pro 生成行业背景）──

def fetch_industry_context(quote: dict, fin: dict, api_key: str, api_base: str = None) -> str:
    """用 v4-pro 生成该股票的产业链位置、供需格局、竞争态势、近期催化"""
    if api_base is None:
        api_base = "https://taotoken.net/api/v1"
    name = quote.get('name', '')
    code = quote.get('code', '')

    fin_text = ""
    if fin and fin.get('revenue'):
        fin_text = f"""
营收{fin['revenue']/1e8:.1f}亿(同比{fin['revenue_yoy']:+.0f}%)
净利{fin['net_profit']/1e8:.2f}亿(同比{fin['net_profit_yoy']:+.0f}%)
毛利率{fin['gross_margin']:.0f}% ROE{fin['roe']:.1f}%"""

    prompt = f"""{name}({code})的核心竞争优势和最大风险分别是什么？重点分析：

1. 核心产品中哪个存在供给瓶颈（如资源稀缺/进口依赖/产能受限）？
2. 下游哪个需求正在爆发式增长（如AI/半导体/新能源）？
3. 是否受益于国产替代/制裁/供应链重构？
4. 市场可能低估了什么？

回答简明扼要（200字以内），聚焦最关键的供需矛盾点，不要面面俱到。只列事实不评价估值。

{fin_text}"""

    import json, urllib.request
    try:
        payload = {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": "你是一个产业链研究分析师。用中文回答，简明扼要，只列事实。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 500,
        }
        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            print(f"   ✅ 行业背景: {content[:80]}...")
            return content
    except Exception as e:
        print(f"   ⚠️ 行业背景生成失败: {e}")
        return ""


# ── 2. 获取财务数据 ──

def fetch_financial_data(code: str) -> dict:
    """通过 AKShare 获取最新财务数据，自动检测送转股并调整每股数据"""
    try:
        import akshare as ak
        df = ak.stock_financial_abstract_ths(symbol=code, indicator='按报告期')
        if df is None or df.empty:
            return {}

        recent = df.tail(3)
        latest = recent.iloc[-1].to_dict()
        prev = recent.iloc[-2].to_dict() if len(recent) >= 2 else {}

        def _parse(v):
            if v is None: return 0
            if isinstance(v, (int, float)): return v
            s = str(v).replace(',', '').replace('%', '')
            if '亿' in s: return float(s.replace('亿', '')) * 1e8
            if '万' in s: return float(s.replace('万', '')) * 1e4
            try: return float(s)
            except ValueError: return 0

        # 检测最新送转股
        split_factor = 1.0
        try:
            div_df = ak.stock_dividend_cninfo(symbol=code)
            if div_df is not None and not div_df.empty:
                latest_report = latest.get('报告期', '')
                for _, row in div_df.iterrows():
                    ex_date = str(row.get('除权日', ''))
                    if ex_date <= latest_report:
                        continue
                    sg = row.get('送股比例', 0)
                    zz = row.get('转增比例', 0)
                    sg = float(sg) if sg and sg == sg else 0
                    zz = float(zz) if zz and zz == zz else 0
                    factor = 1 + (sg + zz) / 10
                    if factor > 1:
                        split_factor *= factor
                        desc = row.get('实施方案分红说明', '')
                        print(f"   🔄 检测到送转股: {ex_date} {desc} (×{factor:.1f})")
        except Exception as e:
            print(f"   ⚠️ 送转检测: {e}")

        fin = {
            'report_date': latest.get('报告期', ''),
            'revenue': _parse(latest.get('营业总收入')),
            'revenue_yoy': float(str(latest.get('营业总收入同比增长率', '0')).replace('%', '')),
            'net_profit': _parse(latest.get('净利润')),
            'net_profit_yoy': float(str(latest.get('净利润同比增长率', '0')).replace('%', '')),
            'gross_margin': float(str(latest.get('销售毛利率', '0')).replace('%', '')),
            'net_margin': float(str(latest.get('销售净利率', '0')).replace('%', '')),
            'eps': float(str(latest.get('基本每股收益', '0'))) / split_factor,
            'bps': float(str(latest.get('每股净资产', '0'))) / split_factor,
            'roe': float(str(latest.get('净资产收益率', '0')).replace('%', '')),
            'ocf_per_share': float(str(latest.get('每股经营现金流', '0'))) / split_factor,
            'debt_ratio': float(str(latest.get('资产负债率', '0')).replace('%', '')),
            'receivable_days': float(str(latest.get('应收账款周转天数', '0'))),
            'prev_revenue': _parse(prev.get('营业总收入')) if prev else 0,
            'prev_net_profit': _parse(prev.get('净利润')) if prev else 0,
            'split_factor': split_factor,
        }
        if split_factor > 1:
            print(f"   📐 每股数据已按 ×{split_factor:.1f} 除权调整（EPS/BPS/OCF）")
        return fin
    except Exception as e:
        print(f"   ⚠️ 财务数据获取失败: {e}")
        return {}


# ── 3. 构造带实时数据的辩论问题 ──

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


# ── 4. 构造 HTML 快照 ──

def build_snapshot(quote: dict, fin: dict = None) -> dict:
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
            'sub': '',
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


# ── 5. 角色过滤 ──

def filter_roles(quote: dict, fin: dict = None) -> tuple[list[str], list[str]]:
    """根据股票特征过滤不合适的投资流派，返回 (roles, skipped)"""
    from roles import STOCK_INVESTMENT_ROLES
    roles = list(STOCK_INVESTMENT_ROLES)
    skipped = []

    pe = quote.get('pe_ttm', 0)
    is_growth = False

    if fin:
        rev_yoy = fin.get('revenue_yoy', 0)
        gross_margin = fin.get('gross_margin', 0)
        if rev_yoy > 30 and gross_margin > 50:
            is_growth = True

    if pe > 50 or (fin and fin.get('revenue', 0) < 50e8):
        if 'graham' in roles:
            roles.remove('graham')
            skipped.append('📐格雷厄姆(PE/营收不达标)')

    if pe > 100 and (not fin or fin.get('roe', 0) < 5):
        if 'shiji' in roles:
            roles.remove('shiji')
            skipped.append('🐢龟龟(无分红+超高PE)')

    # 高增长股天然不适合格雷厄姆和龟龟（防御型价值 / 高股息策略）
    if is_growth:
        if 'graham' in roles:
            roles.remove('graham')
            skipped.append('📐格雷厄姆(高增长股不适用)')
        if 'shiji' in roles:
            roles.remove('shiji')
            skipped.append('🐢龟龟(高增长股不适用)')

    if skipped:
        print(f"   🔍 自动跳过: {', '.join(skipped)}")
    return roles, skipped


# ── 6. 主流程 ──

def main():
    # 解析 --rounds 参数
    custom_rounds = 2
    args = list(sys.argv[1:])
    code = None
    i = 0
    while i < len(args):
        if args[i] == '--rounds' and i + 1 < len(args):
            custom_rounds = int(args[i + 1])
            if custom_rounds < 1:
                custom_rounds = 1
            elif custom_rounds > 3:
                custom_rounds = 3
            i += 2
        else:
            code = args[i]
            i += 1

    if not code:
        print("用法: python3 stock_debate.py <股票代码> [--rounds 3]")
        print("示例: python3 stock_debate.py 688270")
        print("      python3 stock_debate.py 00700      # 港股")
        print("      python3 stock_debate.py 688270 --rounds 3")
        sys.exit(1)

    # 获取 API key（用 yaml.safe_load 而非正则）
    try:
        import yaml
        with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
            cfg = yaml.safe_load(f)
        api_key = ""
        # 尝试多层读取
        if isinstance(cfg, dict):
            # 1. 顶层 api_key/key/token
            for key in ['api_key', 'key', 'token']:
                if key in cfg and cfg[key]:
                    api_key = str(cfg[key])
                    break
            # 2. providers dict（旧格式）
            if not api_key and 'providers' in cfg:
                providers = cfg['providers']
                if isinstance(providers, dict):
                    for p in providers.values():
                        if isinstance(p, dict) and p.get('api_key'):
                            api_key = str(p['api_key'])
                            break
                elif isinstance(providers, list):
                    for p in providers:
                        if isinstance(p, dict) and p.get('api_key'):
                            api_key = str(p['api_key'])
                            break
            # 3. custom_providers list（常见格式）
            if not api_key and 'custom_providers' in cfg:
                cp = cfg['custom_providers']
                if isinstance(cp, list):
                    for p in cp:
                        if isinstance(p, dict) and p.get('api_key'):
                            api_key = str(p['api_key'])
                            break
                elif isinstance(cp, dict):
                    for p in cp.values():
                        if isinstance(p, dict) and p.get('api_key'):
                            api_key = str(p['api_key'])
                            break
            # 4. delegation.api_key
            if not api_key and 'delegation' in cfg:
                dk = cfg['delegation'].get('api_key', '') if isinstance(cfg['delegation'], dict) else ''
                if dk:
                    api_key = str(dk)
    except Exception:
        # fallback 到正则（兼容旧配置格式）
        with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
            raw = f.read()
        m = re.search(r'api_key:\s*["\']?([^"\'\n\s]+)["\']?', raw)
        api_key = m.group(1) if m else ""

    if not api_key:
        print("❌ 未找到 API key")
        sys.exit(1)

    # 提取 api_base（与 api_key 读取方式一致）
    api_base = None
    try:
        if isinstance(cfg, dict):
            for key in ['api_base', 'base_url']:
                if key in cfg and cfg[key]:
                    api_base = str(cfg[key])
                    break
            if not api_base and 'custom_providers' in cfg:
                cp = cfg['custom_providers']
                items = cp if isinstance(cp, list) else cp.values()
                for p in items:
                    if isinstance(p, dict) and p.get('base_url'):
                        api_base = str(p['base_url'])
                        break
            if not api_base and 'providers' in cfg:
                for p in cfg['providers'].values():
                    if isinstance(p, dict) and p.get('base_url'):
                        api_base = str(p['base_url'])
                        break
    except Exception:
        pass

    # 拉行情
    print(f"📡 获取 {code} 实时行情...")
    quote = fetch_stock_quote(code)
    if not quote or not quote.get('price'):
        print("❌ 行情数据获取失败，退出")
        sys.exit(1)

    print(f"   {quote['name']}: {quote['price']}元 | PE={quote['pe_ttm']:.0f}x | 市值≈{quote['market_cap']:.0f}亿")
    if quote.get('is_st'):
        print("   ⚠️ ST 风险警示股！")
    if quote.get('is_hk'):
        print("   🇭🇰 港股")

    # 拉 EastMoney 行情（交叉验证用）
    print(f"📡 获取 {code} EastMoney 行情(交叉验证)...")
    em_quote = fetch_eastmoney_quote(code)

    # 拉公司背景
    print(f"📋 获取 {code} 公司信息...")
    company_profile = fetch_company_profile(code)
    if company_profile:
        print(f"   ✅ 主营业务: {company_profile[:80]}...")
    else:
        print("   ⚠️ 未获取到公司信息，LLM 将凭训练数据自行判断")

    # 拉财报
    print(f"📊 获取 {code} 财务数据...")
    fin = fetch_financial_data(code)
    if fin:
        print(f"   {fin.get('report_date','')}: 营收{fin['revenue']/1e8:.2f}亿(YoY{fin['revenue_yoy']:+.0f}%) 净利{fin['net_profit']/1e8:.2f}亿 毛利率{fin['gross_margin']:.0f}% ROE{fin['roe']:.1f}%")
    else:
        print("   ⚠️ 未获取到财务数据，将仅使用行情数据")

    # ── 三方交叉验证（腾讯 + AKShare + EastMoney）──
    print(f"🔍 数据交叉验证...")
    validation_errors, validation_warnings = cross_validate(quote, fin, em_quote)

    # 送转股提醒
    if fin and fin.get('split_factor', 1) > 1:
        validation_warnings.append(f"送转股 ×{fin['split_factor']:.1f}，每股数据已除权")
        print(f"   🔄 送转股 ×{fin['split_factor']:.1f}")

    # 52 周 K线
    if quote.get('high_52w', 0) > 0:
        print(f"   ✅ 52周区间: {quote['high_52w']:.0f}-{quote['low_52w']:.0f}（前复权）")

    if validation_errors:
        print(f"   ❌ 数据异常: {'; '.join(validation_errors)}")
    elif validation_warnings:
        print(f"   ⚠️ 注意事项: {'; '.join(validation_warnings)}")
    else:
        print(f"   ✅ 数据校验通过（三方一致）")

    # 过滤角色
    roles, skipped_roles = filter_roles(quote, fin)
    roles_arg = ','.join(roles)
    print(f"   🎭 参与角色({len(roles)}): {roles_arg}")

    # 拉产业链格局
    industry_context = fetch_industry_context(quote, fin, api_key, api_base)

    # 构造问题
    question = build_question(quote, fin, company_profile, industry_context)
    print(f"\n🎭 启动圆桌辩论（{custom_rounds} 轮）...\n")

    # 跑辩论
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 用 background=True + wait 模式，用户可看到进度
    print("⚔️  辩论后台运行中，请等待...")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, 'demo.py', question, '--roles', roles_arg, '--rounds', str(custom_rounds)],
        capture_output=True, text=True, timeout=900,
        env={**os.environ, 'TAOTOKEN_API_KEY': api_key, 'OPENAI_API_KEY': api_key,
             'TAOTOKEN_API_BASE': api_base or 'https://taotoken.net/api/v1'},
    )

    elapsed = time.time() - t0
    print(f"⏱️  辩论耗时 {elapsed/60:.1f} 分钟")

    print(result.stdout)
    if result.stderr:
        print("⚠️ STDERR:", result.stderr[:2000])

    if result.returncode != 0:
        print(f"❌ 辩论引擎退出码: {result.returncode}")
        sys.exit(1)

    # 生成 HTML 报告
    print("\n📄 生成 HTML 报告...")
    from html_report import render_html

    json_path = 'last_debate_result.json'
    with open(json_path, encoding='utf-8') as f:
        debate_result = json.load(f)

    # 清理角色名中的 emoji 前缀
    name = quote['name'].replace('*', '').replace('ST', '').strip()
    snapshot = build_snapshot(quote, fin)
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

    print(f"\n✅ 报告已生成: {out_path}")
    print(f"   文件大小: {len(html)} 字符")


if __name__ == '__main__':
    main()
