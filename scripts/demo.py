"""
辩论引擎 Demo
——用 Hermes 当前配置的 LLM（taotoken.net）来跑完整辩论

用法：
    python3 stock_debate.py 或 demo.py "问题描述"
    python3 stock_debate.py 或 demo.py "K8s 集群要不要从 1.34 升级到 1.35？"
    python3 stock_debate.py 或 demo.py "问题" --model deepseek-v4-pro --rounds 3
"""

import sys
import os
import json
import urllib.request
import urllib.error

from engine import DebateEngine, DebateConfig
from roles import ROLES

# ── LLM Runner：封装对 taotoken.net 的调用 ──

API_BASE = os.environ.get("TAOTOKEN_API_BASE", "https://taotoken.net/api/v1")
API_KEY = os.environ.get("TAOTOKEN_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

DEBATE_MODEL = "deepseek-v4-pro"   # 辩论用 pro 模型，保证深度
JUDGE_MODEL = "deepseek-v4-pro"    # 裁判也用 pro，保证 JSON 结构化输出质量
MAX_TOKENS = 6000                  # 投资流派完整评分表需要 4000-6000 tokens


def call_llm(system_prompt: str, user_prompt: str,
             model: str = None, max_tokens: int = None) -> str:
    """调用 LLM，返回纯文本响应"""
    if not API_KEY:
        raise RuntimeError("请设置 TAOTOKEN_API_KEY 环境变量")

    payload = {
        "model": model or DEBATE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens or MAX_TOKENS,
    }

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 错误 {e.code}: {body[:500]}")
    except Exception as e:
        raise RuntimeError(f"调用失败: {e}")


def main():
    # ── 解析参数 ──
    custom_roles = None
    custom_model = None
    custom_rounds = 2
    args = list(sys.argv[1:])
    question_parts = []
    i = 0
    while i < len(args):
        if args[i] == '--roles' and i + 1 < len(args):
            custom_roles = args[i + 1].split(',')
            i += 2
        elif args[i] == '--model' and i + 1 < len(args):
            custom_model = args[i + 1]
            i += 2
        elif args[i] == '--rounds' and i + 1 < len(args):
            custom_rounds = int(args[i + 1])
            if custom_rounds < 1:
                custom_rounds = 1
            elif custom_rounds > 3:
                custom_rounds = 3
            i += 2
        else:
            question_parts.append(args[i])
            i += 1
    question = " ".join(question_parts)

    if not question:
        print("用法: python3 demo.py '你的问题' [--roles role1,role2] [--model deepseek-v4-pro] [--rounds 3]")
        sys.exit(1)

    # 应用模型
    global DEBATE_MODEL, JUDGE_MODEL
    if custom_model:
        DEBATE_MODEL = custom_model
        JUDGE_MODEL = custom_model

    print(f"\n{'='*60}")
    print(f"  🎭 Agent 辩论复核框架 Demo")
    print(f"{'='*60}")
    print(f"\n📋 问题: {question}")
    print(f"🤖 模型: {DEBATE_MODEL}")
    print(f"🔄 轮次: {custom_rounds} 轮\n")

    # 1. 生成辩论角色
    config = DebateConfig(question=question, max_rounds=custom_rounds)
    if custom_roles:
        config.roles = custom_roles
    print(f"🎭 角色: {', '.join(ROLES[r]['name'] + ROLES[r]['emoji'] for r in config.roles)}")
    print(f"🔄 辩论轮次: {config.max_rounds} 轮\n")

    # 2. 创建引擎 + 注入 runner
    engine = DebateEngine(config)

    # 裁判用 JUDGE_MODEL（可能比辩论模型更强），辩论角色用 DEBATE_MODEL
    debate_runner = lambda sp, up: call_llm(sp, up, model=DEBATE_MODEL, max_tokens=MAX_TOKENS)
    judge_runner = lambda sp, up: call_llm(sp, up, model=JUDGE_MODEL, max_tokens=MAX_TOKENS)

    # 引擎支持分离的 runner：普通轮次用 debate_runner，裁判用 judge_runner
    engine.set_runner(debate_runner, judge_runner=judge_runner)

    # 3. 跑辩论
    print("⚔️  辩论开始...\n")
    result = engine.run()

    # 4. 输出结果
    print(f"\n{'='*60}")
    print(f"  📊 辩论结果")
    print(f"{'='*60}\n")

    markdown = result.to_markdown()
    print(markdown)

    # 5. 保存报告（使用脚本所在目录，兼容 macOS/Linux/WSL）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(script_dir, "last_debate_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"\n💾 报告已保存: {report_path}")

    # 也保存 JSON
    json_path = os.path.join(script_dir, "last_debate_result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"💾 JSON 已保存: {json_path}")


if __name__ == "__main__":
    # 确保当前目录在 sys.path（当前目录已在 stock_debate.py 中 cd 到 scripts/）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
