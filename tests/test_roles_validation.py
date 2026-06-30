"""roles.py 和 validation.py 单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import unittest
from roles import ROLES, ROLES_DEBATE, STOCK_INVESTMENT_ROLES, select_roles
from validation import filter_roles, cross_validate


class TestRoles(unittest.TestCase):
    def test_all_stock_roles_defined(self):
        """6 大投资流派必须全部定义"""
        for role in STOCK_INVESTMENT_ROLES:
            self.assertIn(role, ROLES)
            self.assertIn("name", ROLES[role])
            self.assertIn("system_prompt", ROLES[role])
            self.assertGreater(len(ROLES[role]["system_prompt"]), 100,
                               f"{role} 的 system_prompt 太短")

    def test_debate_roles(self):
        self.assertIn("optimist", ROLES_DEBATE)
        self.assertIn("pessimist", ROLES_DEBATE)
        self.assertIn("skeptic", ROLES_DEBATE)

    def test_stock_role_keys(self):
        """所有股票角色键名不含空格，无 emoji"""
        for role in STOCK_INVESTMENT_ROLES:
            self.assertNotIn(" ", role, f"{role} 不应含空格")
            self.assertEqual(role, role.lower())

    def test_select_roles_stock_keywords(self):
        """股票关键词触发投资流派"""
        result = select_roles("是否应该买入贵州茅台？")
        self.assertTrue(len(result) >= 2)
        # 股票问题应该返回投资流派，不是通用辩论角色
        self.assertNotEqual(result[0], "optimist")

    def test_select_roles_technical(self):
        """技术关键词触发技术派"""
        result = select_roles("K8s部署方案选型？")
        self.assertIn("technologist", result)

    def test_select_roles_generic(self):
        """通用问题有两个默认 + skeptic"""
        result = select_roles("今天天气怎么样？")
        self.assertIn("optimist", result)
        self.assertIn("pessimist", result)
        # 至少 2 个角色
        self.assertGreaterEqual(len(result), 2)


class TestFilterRoles(unittest.TestCase):
    def test_high_pe_filters_graham_and_shiji(self):
        """PE>50 跳过格雷厄姆和龟龟"""
        quote = {"pe_ttm": 80, "market_cap": 500}
        roster, skipped = filter_roles(quote)
        self.assertNotIn("graham", roster)
        self.assertNotIn("shiji", roster)
        self.assertGreaterEqual(len(skipped), 2)

    def test_low_pe_keeps_all(self):
        """低PE保留所有角色"""
        quote = {"pe_ttm": 15, "market_cap": 1000}
        fin = {"revenue": 100e8, "revenue_yoy": 10, "gross_margin": 40}
        roster, skipped = filter_roles(quote, fin)
        self.assertIn("graham", roster)
        self.assertIn("shiji", roster)
        self.assertEqual(len(skipped), 0)

    def test_growth_stock_filters(self):
        """高增长股过滤格雷厄姆和龟龟"""
        quote = {"pe_ttm": 30, "market_cap": 500}
        fin = {"revenue": 200e8, "revenue_yoy": 50, "gross_margin": 60}
        roster, skipped = filter_roles(quote, fin)
        self.assertNotIn("graham", roster)
        self.assertNotIn("shiji", roster)

    def test_small_revenue_filters_graham(self):
        """营收<50亿过滤格雷厄姆"""
        quote = {"pe_ttm": 10, "market_cap": 100}
        fin = {"revenue": 30e8, "revenue_yoy": 5, "gross_margin": 30}
        roster, skipped = filter_roles(quote, fin)
        self.assertNotIn("graham", roster)


class TestCrossValidate(unittest.TestCase):
    def test_perfect_match(self):
        """完全一致不应报错"""
        quote = {"pe_ttm": 20, "market_cap": 500}
        em = {"pe_ttm": 20, "market_cap": 500}
        errors, warnings = cross_validate(quote, {}, em)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_pe_deviation_warning(self):
        """PE 偏差 5%-10% 警告"""
        quote = {"pe_ttm": 20, "market_cap": 500}
        em = {"pe_ttm": 21.5, "market_cap": 500}  # ~7.5% 偏差
        errors, warnings = cross_validate(quote, {}, em)
        self.assertEqual(len(errors), 0)
        self.assertGreater(len(warnings), 0)

    def test_pe_deviation_error(self):
        """PE 偏差 >10% 报错"""
        quote = {"pe_ttm": 20, "market_cap": 500}
        em = {"pe_ttm": 24, "market_cap": 500}  # 20% 偏差
        errors, warnings = cross_validate(quote, {}, em)
        self.assertGreater(len(errors), 0)

    def test_missing_em_data(self):
        """EastMoney 无数据时不报错"""
        quote = {"pe_ttm": 20, "market_cap": 500}
        errors, warnings = cross_validate(quote, {}, {})
        self.assertEqual(len(errors), 0)

    def test_extreme_pe_warning(self):
        """PE>200 警告"""
        quote = {"pe_ttm": 250, "market_cap": 100}
        em = {"pe_ttm": 250, "market_cap": 100}
        errors, warnings = cross_validate(quote, {}, em)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any("极端高估" in w for w in warnings))


if __name__ == '__main__':
    unittest.main()
