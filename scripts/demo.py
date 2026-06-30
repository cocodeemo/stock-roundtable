"""
辩论引擎 Demo
——用 Hermes 当前配置的 LLM（taotoken.net）来跑完整辩论

用法：
    python3 demo.py "问题描述"
    python3 demo.py "问题" --model deepseek-v4-pro --rounds 3
"""

import sys
import os
import json

from engine import DebateEngine, DebateConfig
from roles import ROLES
from common import call_llm, parse_debate_args, log, DEFAULT_API_BASE


# ── LLM 配置 ──

API_BASE = os.environ.get("TAOTOKEN_API_BASE", DEFAULT_API_BASE)
API_KEY = os.environ.get("TAOTOKEN_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

DEBATE_MODEL = "deepseek-v4-pro"
JUDGE_MODEL = "deepseek-v4-pro"
MAX_TOKENS = 6000

# 辩论温度 0.7 保证观点多样性，裁判温度 0.3 保证 JSON 结构化输出稳定
DEBATE_TEMPERATURE = 0.7
JUDGE_TEMPERATURE = 0.3


def main():
    # 检查是否通过文件传入问题（避免命令行长度限制）
    question_file = None
    raw_argv = list(sys.argv[1:])
    i = 0
    while i < len(raw_argv):
        if raw_argv[i] == '--question-file' and i + 1 < len(raw_argv):
            question_file = raw_argv[i + 1]
            del raw_argv[i:i + 2]
            break
        i += 1

    # 解析参数（使用共享模块）
    if question_file and not raw_argv:
        raw_argv = ['(from file)']  # 确保 parse_debate_args 有内容
    args = parse_debate_args(raw_argv)
    question = args["question"]
    custom_roles = args["roles"]
    custom_model = args["model"]
    custom_rounds = args["rounds"]

    # 从文件读取完整问题
    if question_file:
        with open(question_file, 'r', encoding='utf-8') as f:
            question = f.read()

    if not question:
        log.info("用法: python3 demo.py '你的问题' [--roles role1,role2] [--model deepseek-v4-pro] [--rounds 3]")
        sys.exit(1)

    if custom_model:
        global DEBATE_MODEL, JUDGE_MODEL
        DEBATE_MODEL = custom_model
        JUDGE_MODEL = custom_model

    log.info("")
    log.info("%s", "=" * 60)
    log.info("  🎭 Agent 辩论复核框架 Demo")
    log.info("%s", "=" * 60)
    log.info("")
    log.info("📋 问题: %s", question)
    log.info("🤖 模型: %s", DEBATE_MODEL)
    log.info("🔄 轮次: %d 轮", custom_rounds)
    log.info("")

    # 1. 生成辩论角色
    config = DebateConfig(question=question, max_rounds=custom_rounds)
    if custom_roles:
        config.roles = custom_roles
    log.info("🎭 角色: %s", ', '.join(ROLES[r]['name'] + ROLES[r]['emoji'] for r in config.roles))
    log.info("🔄 辩论轮次: %d 轮", config.max_rounds)
    log.info("")

    # 2. 创建引擎 + 注入 runner
    engine = DebateEngine(config)

    # 辩论角色用较高温度（0.7），裁判用较低温度（0.3）保证 JSON 稳定
    debate_runner = lambda sp, up: call_llm(
        sp, up, api_key=API_KEY, api_base=API_BASE,
        model=DEBATE_MODEL, temperature=DEBATE_TEMPERATURE, max_tokens=MAX_TOKENS,
    )
    judge_runner = lambda sp, up: call_llm(
        sp, up, api_key=API_KEY, api_base=API_BASE,
        model=JUDGE_MODEL, temperature=JUDGE_TEMPERATURE, max_tokens=MAX_TOKENS,
    )

    engine.set_runner(debate_runner, judge_runner=judge_runner)

    # 3. 跑辩论
    log.info("⚔️  辩论开始...")
    log.info("")
    result = engine.run()

    # 4. 输出结果
    log.info("")
    log.info("%s", "=" * 60)
    log.info("  📊 辩论结果")
    log.info("%s", "=" * 60)
    log.info("")

    markdown = result.to_markdown()
    # Markdown 内容直接 print（非日志，是最终输出）
    print(markdown)

    # 5. 保存报告
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(script_dir, "last_debate_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    log.info("")
    log.info("💾 报告已保存: %s", report_path)

    json_path = os.path.join(script_dir, "last_debate_result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    log.info("💾 JSON 已保存: %s", json_path)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
