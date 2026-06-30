"""
数据校验模块
——交叉验证与角色过滤，从 stock_debate.py 拆分
"""

from common import log


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
            log.info("✅ PE一致: 腾讯%.0fx vs 东财%.0fx", pe_tencent, pe_em)

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
            log.info("✅ 市值一致: 腾讯%.0f亿 vs 东财%.0f亿", mc_tencent, mc_em)

    # PE 极端值 / PS 极端值
    use_pe = pe_tencent or pe_em or 0
    if use_pe > 200:
        warnings.append(f'PE {use_pe:.0f}x 极端高估')
    if fin and fin.get('revenue', 0) > 0:
        ps = (mc_tencent or mc_em) / (fin['revenue'] / 1e8)
        if ps > 100:
            warnings.append(f'PS {ps:.0f}x 极高')

    # 52周前复权 fallback 提醒
    if quote.get('fallback_52w'):
        warnings.append('52周高低使用不除权数据，可能偏高')

    return errors, warnings


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

    if pe > 50:
        if 'shiji' in roles:
            roles.remove('shiji')
            skipped.append('🐢龟龟(PE>50，穿透回报率无意义)')

    # 高增长股天然不适合格雷厄姆和龟龟（防御型价值 / 高股息策略）
    if is_growth:
        if 'graham' in roles:
            roles.remove('graham')
            skipped.append('📐格雷厄姆(高增长股不适用)')
        if 'shiji' in roles:
            roles.remove('shiji')
            skipped.append('🐢龟龟(高增长股不适用)')

    if skipped:
        log.info("🔍 自动跳过: %s", ', '.join(skipped))
    return roles, skipped
