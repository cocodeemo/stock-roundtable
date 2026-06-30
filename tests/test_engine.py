"""engine.py 单元测试 —— 纯逻辑，不依赖网络"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import unittest
from engine import DebateConfig, DebateResult, RoundMessage, DebateEngine


class TestDebateConfig(unittest.TestCase):
    def test_default_config(self):
        config = DebateConfig(question="test?")
        self.assertEqual(config.question, "test?")
        self.assertEqual(config.max_rounds, 3)
        self.assertEqual(config.max_roles, 6)

    def test_custom_rounds(self):
        config = DebateConfig(question="test?", max_rounds=2)
        self.assertEqual(config.max_rounds, 2)

    def test_custom_roles(self):
        config = DebateConfig(question="股票投资?", roles=["graham", "buffett"])
        self.assertEqual(config.roles, ["graham", "buffett"])

    def test_auto_select_roles_stock_question(self):
        """股票相关问题时自动选择投资流派角色"""
        config = DebateConfig(question="要不要买入贵州茅台？")
        self.assertTrue(len(config.roles) >= 2)
        self.assertIn("graham", config.roles)

    def test_auto_select_roles_generic(self):
        """通用问题用辩论角色"""
        config = DebateConfig(question="要不要重构代码？")
        self.assertIn("optimist", config.roles)
        self.assertIn("pessimist", config.roles)


class TestDebateResult(unittest.TestCase):
    def setUp(self):
        self.result = DebateResult(
            question="test question?",
            participants=["乐观派", "悲观派"],
            total_rounds=2,
        )

    def test_empty_result(self):
        self.assertEqual(self.result.question, "test question?")
        self.assertEqual(len(self.result.participants), 2)
        self.assertEqual(self.result.total_rounds, 2)
        self.assertEqual(self.result.consensus, "")
        self.assertEqual(self.result.confidence, 0.0)

    def test_to_markdown(self):
        self.result.recommendation = "建议买入"
        self.result.consensus = "各方同意"
        self.result.confidence = 0.75
        md = self.result.to_markdown()
        self.assertIn("建议买入", md)
        self.assertIn("各方同意", md)
        self.assertIn("75%", md)
        self.assertIn("test question?", md)

    def test_to_markdown_with_conflicts(self):
        self.result.conflicts = [
            {"topic": "估值分歧", "positions": [
                {"role": "乐观", "view": "PE合理"},
                {"role": "悲观", "view": "PE过高"},
            ]},
        ]
        md = self.result.to_markdown()
        self.assertIn("估值分歧", md)
        self.assertIn("PE合理", md)
        self.assertIn("PE过高", md)

    def test_to_markdown_with_risks(self):
        self.result.risk_items = ["流动性风险", "政策风险"]
        md = self.result.to_markdown()
        self.assertIn("流动性风险", md)
        self.assertIn("政策风险", md)

    def test_to_dict(self):
        self.result.recommendation = "test rec"
        self.result.confidence = 0.5
        self.result.transcript.append(RoundMessage(
            role="optimist", role_name="乐观派", emoji="🟢",
            content="看好", round_num=1,
        ))
        d = self.result.to_dict()
        self.assertEqual(d["recommendation"], "test rec")
        self.assertEqual(d["confidence"], 0.5)
        self.assertEqual(len(d["transcript"]), 1)
        self.assertEqual(d["transcript"][0]["content"], "看好")

    def test_to_dict_empty_transcript(self):
        d = self.result.to_dict()
        self.assertEqual(len(d["transcript"]), 0)


class TestDebateEngineNoRunner(unittest.TestCase):
    """测试不涉及 LLM 调用的引擎逻辑"""

    def test_run_without_runner_raises(self):
        config = DebateConfig(question="test?", roles=["optimist", "pessimist"])
        engine = DebateEngine(config)
        with self.assertRaises(RuntimeError):
            engine.run()


class TestRoundMessage(unittest.TestCase):
    def test_create_message(self):
        msg = RoundMessage(
            role="optimist", role_name="乐观派", emoji="🟢",
            content="I think...", round_num=1,
        )
        self.assertEqual(msg.role, "optimist")
        self.assertEqual(msg.content, "I think...")
        self.assertEqual(msg.round_num, 1)


if __name__ == '__main__':
    unittest.main()
