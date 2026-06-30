"""stock_debate.py 纯逻辑单元测试（不依赖网络）"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import unittest
from stock_debate import build_question, build_snapshot


class TestBuildQuestion(unittest.TestCase):
    def setUp(self):
        self.quote = {
            'name': '测试股票', 'code': '000001',
            'price': 25.50, 'change_pct': 3.2,
            'high': 26.0, 'low': 24.8,
            'pe_ttm': 18, 'market_cap': 500,
            'high_52w': 35.0, 'low_52w': 15.0,
            'is_st': False, 'is_hk': False,
            'date': '2026-06-30',
        }

    def test_basic_question(self):
        q = build_question(self.quote)
        self.assertIn("000001", q)
        self.assertIn("测试股票", q)
        self.assertIn("25.5", q)
        self.assertIn("A股", q)

    def test_with_financial_data(self):
        fin = {
            'report_date': '2025Q4',
            'revenue': 200e8, 'revenue_yoy': 15.0,
            'net_profit': 30e8, 'net_profit_yoy': 10.0,
            'gross_margin': 45.0, 'net_margin': 15.0,
            'eps': 2.5, 'bps': 15.0,
            'roe': 16.7, 'debt_ratio': 35.0,
            'ocf_per_share': 3.0, 'receivable_days': 60,
            'split_factor': 1.0,
        }
        q = build_question(self.quote, fin)
        self.assertIn("200.00亿", q)
        self.assertIn("30.00亿", q)
        self.assertIn("ROE", q)

    def test_st_warning(self):
        self.quote['is_st'] = True
        self.quote['name'] = '*ST测试'
        q = build_question(self.quote)
        self.assertIn("ST", q)
        self.assertIn("风险警示", q)

    def test_hk_stock(self):
        self.quote['is_hk'] = True
        q = build_question(self.quote)
        self.assertIn("港股", q)

    def test_with_company_profile(self):
        q = build_question(self.quote, company_profile="半导体芯片设计公司")
        self.assertIn("半导体芯片设计公司", q)

    def test_with_industry_context(self):
        q = build_question(self.quote, industry_context="AI芯片需求爆发")
        self.assertIn("AI芯片需求爆发", q)

    def test_dynamic_focus_points(self):
        """高负债 + 利润下滑触发额外关注点"""
        fin = {
            'report_date': '2025Q4',
            'revenue': 200e8, 'revenue_yoy': 5.0,
            'net_profit': 10e8, 'net_profit_yoy': -35.0,
            'gross_margin': 30.0, 'net_margin': 5.0,
            'eps': 1.0, 'bps': 10.0,
            'roe': 10.0, 'debt_ratio': 60.0,
            'ocf_per_share': 0.5, 'receivable_days': 120,
            'split_factor': 1.0,
        }
        q = build_question(self.quote, fin)
        self.assertIn("利润大幅下滑", q)
        self.assertIn("偿债压力", q)
        self.assertIn("回款", q)


class TestBuildSnapshot(unittest.TestCase):
    def setUp(self):
        self.quote = {
            'name': '测试', 'code': '000001',
            'price': 25.50, 'change_pct': 3.2,
            'pe_ttm': 18, 'market_cap': 500,
            'high_52w': 35.0, 'low_52w': 15.0,
            'is_st': False,
        }

    def test_basic_snapshot(self):
        snap = build_snapshot(self.quote)
        self.assertIn("测试(000001)", snap)
        self.assertIn("PE(TTM)", snap)
        self.assertIn("总市值", snap)
        self.assertEqual(snap["测试(000001)"]["sub_class"], "cc-snap-up")

    def test_down_pct(self):
        self.quote['change_pct'] = -2.5
        snap = build_snapshot(self.quote)
        self.assertEqual(snap["测试(000001)"]["sub_class"], "cc-snap-down")

    def test_st_warning_in_snapshot(self):
        self.quote['is_st'] = True
        snap = build_snapshot(self.quote)
        self.assertIn("⚠️ 风险警示", snap)

    def test_financial_in_snapshot(self):
        fin = {
            'revenue': 100e8, 'revenue_yoy': 20.0,
            'net_profit': 15e8, 'net_profit_yoy': -5.0,
            'gross_margin': 40.0, 'roe': 12.0,
            'ocf_per_share': 1.5,
        }
        snap = build_snapshot(self.quote, fin)
        self.assertIn("营收(最新期)", snap)
        self.assertIn("净利润", snap)
        # 净利润同比为负 → sub_class 应为 cc-snap-down
        self.assertEqual(snap["净利润"]["sub_class"], "cc-snap-down")


if __name__ == '__main__':
    unittest.main()
