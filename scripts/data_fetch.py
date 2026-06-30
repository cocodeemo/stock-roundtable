"""
数据获取模块
——行情、财务、公司信息、产业链背景的数据拉取
从 stock_debate.py 拆分，消除 main() 函数过长问题
"""

import re
import json
import math
import urllib.request
from datetime import datetime

from common import log, call_llm, retry_call, DEFAULT_API_BASE

# 预编译正则，避免每次调用重新解析
_QUOTE_LINE_RE = re.compile(r'="(.+)"')


# ── 1. 获取实时行情 ──

def fetch_stock_quote(code: str) -> dict:
    """从腾讯行情 API 拉取实时数据，支持 A 股和港股（带重试）"""
    # 判断交易所
    is_hk = False
    if len(code) == 6 and code.startswith(('6', '9')):
        full_code = f"sh{code}"
    elif len(code) == 6 and code.startswith(('0', '3')):
        full_code = f"sz{code}"
    else:
        # 港股：需要 hk 前缀，补齐 5 位
        is_hk = True
        padded = code.zfill(5)
        full_code = f"hk{padded}"

    url = f"https://qt.gtimg.cn/q={full_code}"

    def _do_fetch():
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.qq.com/'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
            return raw.decode('gbk', errors='replace')

    try:
        text = retry_call(_do_fetch, max_retries=2, base_delay=1.0)
    except Exception as e:
        log.error("行情获取失败: %s", e)
        return {}

    # 解析: v_sh688270="1~ST臻镭~688270~70.00~..."
    m = _QUOTE_LINE_RE.search(text)
    if not m:
        return {}

    fields = m.group(1).split('~')
    if len(fields) < 50:
        log.warning("数据字段不足 (got %d)", len(fields))
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
    kline_ok = False

    def _fetch_kline():
        """获取前复权 K 线"""
        kurl = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,,,250,qfq"
        req = urllib.request.Request(kurl, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com/'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    try:
        kd = retry_call(_fetch_kline, max_retries=2, base_delay=1.0)
        klines = kd.get('data', {}).get(full_code, {}).get('qfqday', [])
        if klines:
            real_high_52w = max(float(k[3]) for k in klines[-250:])
            real_low_52w = min(float(k[4]) for k in klines[-250:])
            kline_ok = True
    except Exception as e:
        log.warning("前复权K线获取失败（%s），将使用不除权的52周高低", e)

    # HK stocks use different field mapping
    if is_hk:
        market_cap = float(fields[44]) if fields[44] else 0
        if not market_cap:
            market_cap = float(fields[45]) if fields[45] else 0

    # 52 周高低：优先前复权，fallback 到不除权字段（需明确警告）
    fallback_52w = False
    if real_high_52w > 0 and real_low_52w > 0:
        high_52w = real_high_52w
        low_52w = real_low_52w
    else:
        high_52w = float(fields[47]) if fields[47] else 0
        low_52w = float(fields[48]) if fields[48] else 0
        if high_52w > 0 or low_52w > 0:
            fallback_52w = True
            log.warning(
                "⚠️ 52周高低使用不除权数据（fields[47/48]），可能与前复权有偏差。"
                "高: %.0f, 低: %.0f —— 用于格雷厄姆/龟龟防御型估值时请留意",
                high_52w, low_52w
            )

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
        'fallback_52w': fallback_52w,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }


# ── 2. 获取公司主营业务（动态背景）──

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
    except Exception as e:
        log.warning("⚠️ 公司信息获取模块异常（AKShare 可能未安装或版本不兼容）: %s", e)
        pass
    return ""


# ── 3. EastMoney 行情（交叉验证用）──

def fetch_eastmoney_quote(code: str) -> dict:
    """从东方财富 API 获取实时行情，用于交叉验证（带重试）"""
    # 沪市 1.xxx，深市 0.xxx
    if code.startswith(('6', '9')):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"

    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f58,f43,f46,f116,f117,f162,f163,f164,f165,f167"

    def _do_fetch():
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
                'pe_ttm': d.get('f164', 0) / 100 if d.get('f164') else 0,  # f164=TTM PE, f162=动态PE(不对齐)
                'pe_static': d.get('f163', 0) / 100 if d.get('f163') else 0,  # 静态PE(参考)
                'pe_dynamic': d.get('f162', 0) / 100 if d.get('f162') else 0,  # 动态PE(参考)
                'market_cap': d.get('f116', 0) / 1e8 if d.get('f116') else 0,
            }

    try:
        return retry_call(_do_fetch, max_retries=2, base_delay=1.0)
    except Exception as e:
        log.warning("EastMoney 行情获取失败: %s", e)
        return {}


# ── 4. 获取财务数据 ──

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
            if isinstance(v, float) and math.isnan(v): return 0
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
                        log.info("🔄 检测到送转股: %s %s (×%.1f)", ex_date, desc, factor)
        except Exception as e:
            log.warning("送转检测: %s", e)

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
            log.info("📐 每股数据已按 ×%.1f 除权调整（EPS/BPS/OCF）", split_factor)
        return fin
    except Exception as e:
        log.warning("财务数据获取失败: %s", e)
        return {}


# ── 5. 获取产业链格局（v4-pro 生成行业背景）──

def fetch_industry_context(quote: dict, fin: dict, api_key: str, api_base: str = None) -> str:
    """用 v4-pro 生成该股票的产业链位置、供需格局、竞争态势、近期催化"""
    if api_base is None:
        api_base = DEFAULT_API_BASE
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

    try:
        content = call_llm(
            "你是一个产业链研究分析师。用中文回答，简明扼要，只列事实。",
            prompt,
            api_key=api_key,
            api_base=api_base,
            model="deepseek-v4-pro",
            temperature=0.3,
            max_tokens=500,
            timeout=30,
            retries=2,
        )
        log.info("✅ 行业背景: %s...", content[:80])
        return content
    except Exception as e:
        log.warning("行业背景生成失败: %s", e)
        return ""
