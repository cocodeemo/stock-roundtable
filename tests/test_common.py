"""common.py 单元测试 —— 纯逻辑，不依赖网络"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import unittest
import tempfile
from common import parse_debate_args, load_hermes_config


class TestParseDebateArgs(unittest.TestCase):
    def test_question_only(self):
        result = parse_debate_args(["test question?"])
        self.assertEqual(result["question"], "test question?")
        self.assertEqual(result["rounds"], 2)
        self.assertIsNone(result["roles"])

    def test_question_with_spaces(self):
        result = parse_debate_args(["这是", "一个", "问题"])
        self.assertEqual(result["question"], "这是 一个 问题")

    def test_rounds(self):
        result = parse_debate_args(["test", "--rounds", "3"])
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(result["question"], "test")

    def test_rounds_clamped(self):
        """--rounds 限制在 1-3"""
        result = parse_debate_args(["test", "--rounds", "5"])
        self.assertEqual(result["rounds"], 3)
        result = parse_debate_args(["test", "--rounds", "0"])
        self.assertEqual(result["rounds"], 1)

    def test_roles(self):
        result = parse_debate_args(["--roles", "graham,buffett", "question here"])
        self.assertEqual(result["roles"], ["graham", "buffett"])
        self.assertEqual(result["question"], "question here")

    def test_model(self):
        result = parse_debate_args(["--model", "gpt-4", "test?"])
        self.assertEqual(result["model"], "gpt-4")

    def test_all_args(self):
        result = parse_debate_args([
            "股票分析问题", "--roles", "graham,fisher",
            "--model", "deepseek-v4", "--rounds", "2"
        ])
        self.assertEqual(result["question"], "股票分析问题")
        self.assertEqual(result["roles"], ["graham", "fisher"])
        self.assertEqual(result["model"], "deepseek-v4")
        self.assertEqual(result["rounds"], 2)

    def test_empty_argv(self):
        result = parse_debate_args([])
        self.assertEqual(result["question"], "")
        self.assertIsNone(result["roles"])

    def test_invalid_rounds(self):
        """--rounds abc 忽略"""
        result = parse_debate_args(["test", "--rounds", "abc"])
        self.assertEqual(result["rounds"], 2)


class TestLoadHermesConfig(unittest.TestCase):
    def test_nonexistent_file(self):
        """不存在的配置文件返回空"""
        result = load_hermes_config("/nonexistent/path/config.yaml")
        self.assertEqual(result["api_key"], "")
        self.assertIsNone(result["api_base"])

    def test_regex_fallback_yaml(self):
        """正则解析 YAML 格式的 api_key"""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_hermes_config.yaml')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write("api_key: sk-test-key-12345\n")
            f.write("some_other: value\n")
            f.flush()
            os.fsync(f.fileno())

        try:
            result = load_hermes_config(tmp_path)
            self.assertIn("sk-test-key-12345", result.get("api_key", ""),
                          f"Got: {result}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_regex_fallback_quoted(self):
        """正则解析带引号的 api_key"""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_hermes_quoted.yaml')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('api_key: "sk-test-quoted"\n')
            f.flush()
            os.fsync(f.fileno())

        try:
            result = load_hermes_config(tmp_path)
            self.assertIn("sk-test-quoted", result.get("api_key", ""),
                          f"Got: {result}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main()
