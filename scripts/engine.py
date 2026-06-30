"""
Agent 辩论引擎核心
——不绑死任何底座，LLM 调用通过可插拔的 runner 注入
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
from dataclasses import dataclass, field

from roles import ROLES, select_roles


@dataclass
class DebateConfig:
    question: str
    roles: list[str] = field(default_factory=list)  # 不传则自动选择
    max_rounds: int = 3
    max_roles: int = 6

    def __post_init__(self):
        if not self.roles:
            self.roles = select_roles(self.question, self.max_roles)


@dataclass
class RoundMessage:
    """一轮辩论中的一条消息"""
    role: str
    role_name: str
    emoji: str
    content: str
    round_num: int


@dataclass
class DebateResult:
    """辩论最终输出——结构化结论"""
    question: str
    participants: list[str]
    total_rounds: int
    transcript: list[RoundMessage] = field(default_factory=list)

    # 结构化结论
    consensus: str = ""            # 共识结论
    conflicts: list[dict] = field(default_factory=list)  # 分歧点：[{topic, positions}]
    confidence: float = 0.0         # 综合置信度 0-1
    recommendation: str = ""        # 最终建议
    risk_items: list[str] = field(default_factory=list)  # 关键风险

    def to_markdown(self) -> str:
        """输出 Markdown 格式报告"""
        lines = [
            f"# 辩论结论报告",
            f"",
            f"**问题**：{self.question}",
            f"**参与方**：{' / '.join(self.participants)}",
            f"**辩论轮次**：{self.total_rounds} 轮",
            f"**综合置信度**：{self.confidence:.0%}",
            f"",
            f"---",
            f"",
            f"## 🏁 最终建议",
            f"",
            f"{self.recommendation}",
            f"",
            f"## ✅ 共识结论",
            f"",
            f"{self.consensus}",
            f"",
        ]

        if self.conflicts:
            lines.append("## ⚡ 核心分歧")
            lines.append("")
            for i, c in enumerate(self.conflicts, 1):
                lines.append(f"### 分歧 {i}：{c.get('topic', '未命名')}")
                lines.append("")
                for pos in c.get("positions", []):
                    lines.append(f"- **{pos.get('role', '?')}**：{pos.get('view', '')}")
                lines.append("")

        if self.risk_items:
            lines.append("## ⚠️ 关键风险")
            lines.append("")
            for r in self.risk_items:
                lines.append(f"- {r}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 📝 辩论实录")
        lines.append("")
        for msg in self.transcript:
            lines.append(f"### {msg.emoji} {msg.role_name}（第 {msg.round_num} 轮）")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "participants": self.participants,
            "total_rounds": self.total_rounds,
            "consensus": self.consensus,
            "conflicts": self.conflicts,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "risk_items": self.risk_items,
            "transcript": [
                {
                    "role": m.role,
                    "role_name": m.role_name,
                    "emoji": m.emoji,
                    "round": m.round_num,
                    "content": m.content,
                }
                for m in self.transcript
            ],
        }


class DebateEngine:
    """
    辩论引擎——与底座无关。

    用法：
        engine = DebateEngine(config)
        engine.set_runner(my_call_llm_function)
        result = engine.run()
        print(result.to_markdown())

    其中 my_call_llm_function 的签名：
        def runner(system_prompt: str, user_prompt: str) -> str
    """

    def __init__(self, config: DebateConfig):
        self.config = config
        self.result = DebateResult(
            question=config.question,
            participants=[ROLES[r]["name"] for r in config.roles],
            total_rounds=config.max_rounds,
        )
        self._runner: Optional[Callable[[str, str], str]] = None

    def set_runner(self, fn: Callable[[str, str], str],
                   judge_runner: Optional[Callable[[str, str], str]] = None):
        """注入 LLM 调用函数。judge_runner 可选：裁判用更强模型"""
        self._runner = fn
        self._judge_runner = judge_runner or fn

    def run(self) -> DebateResult:
        if self._runner is None:
            raise RuntimeError("请先调用 set_runner() 注入 LLM 调用函数")

        roles = self.config.roles
        transcript = self.result.transcript

        for round_num in range(1, self.config.max_rounds + 1):
            if round_num == 1:
                # Round 1: 各角色独立陈述，无彼此依赖 → 并行
                self._run_round1_parallel(roles, transcript)
            else:
                # Round 2+: 反驳需要看到对手本轮发言 → 顺序执行
                self._run_rebuttal_round(round_num, roles, transcript)

        # 最后一轮结束后，让裁判汇总
        self._synthesize(transcript)
        return self.result

    def _run_round1_parallel(self, roles: list[str],
                              transcript: list[RoundMessage]):
        """Round 1 并行：6 个角色同时发言，耗时约等于最慢那个"""

        def _speak(role_key: str) -> tuple[str, RoundMessage]:
            role_def = ROLES[role_key]
            user_prompt = self._round1_prompt(role_key)
            response = self._runner(role_def["system_prompt"], user_prompt)
            return role_key, RoundMessage(
                role=role_key,
                role_name=role_def["name"],
                emoji=role_def["emoji"],
                content=response,
                round_num=1,
            )

        # 并发调用所有角色，按角色原始顺序追加结果
        results: dict[str, RoundMessage] = {}
        with ThreadPoolExecutor(max_workers=len(roles)) as executor:
            futures = {executor.submit(_speak, r): r for r in roles}
            for future in as_completed(futures):
                key, msg = future.result()
                results[key] = msg

        for key in roles:
            transcript.append(results[key])

    def _run_rebuttal_round(self, round_num: int, roles: list[str],
                             transcript: list[RoundMessage]):
        """Round 2+: 顺序反驳——后来者能看到同轮先行者的论据"""
        round_context = self._build_round_context(round_num, transcript)

        for role_key in roles:
            role_def = ROLES[role_key]
            user_prompt = self._rebuttal_prompt(role_key, round_context)
            response = self._runner(role_def["system_prompt"], user_prompt)
            msg = RoundMessage(
                role=role_key,
                role_name=role_def["name"],
                emoji=role_def["emoji"],
                content=response,
                round_num=round_num,
            )
            transcript.append(msg)
            # 动态更新上下文——让下一个角色能看到刚才的发言
            round_context += (
                f"\n[{msg.emoji} {msg.role_name} 第{round_num}轮]:\n{msg.content}\n"
            )

    def _round1_prompt(self, role_key: str) -> str:
        role = ROLES[role_key]
        return f"""=== 辩论开始：第 1 轮（初始立场陈述）===

讨论问题：
{self.config.question}

你是{role['name']}。请从你的视角出发，阐述你对这个问题的初始立场和分析。

要求：
1. 明确你的核心观点
2. 用具体论据支撑，不要空泛
3. 控制在 300 字以内
4. 不需要回应其他人（第 1 轮每人独立陈述）"""

    def _rebuttal_prompt(self, role_key: str, context: str) -> str:
        role = ROLES[role_key]
        return f"""=== 辩论继续：新一轮 ===

讨论问题：
{self.config.question}

你是{role['name']}。以下是本轮辩论到此为止的全部发言：

{context}

请你：
1. 明确引用至少一位其他角色的具体论点进行反驳或补充
2. 如果是第二轮以后，指出之前辩论中被忽略的盲点
3. 如果你的立场因其他人的论点而有所调整，明确说明调整了什么
4. 控制在 400 字以内"""

    def _build_round_context(self, current_round: int,
                              transcript: list[RoundMessage]) -> str:
        """构建当前轮次的上下文——只给上一轮的内容，防止上下文爆炸"""
        parts = []
        for msg in transcript:
            if msg.round_num >= current_round - 1:  # 上一轮 + 本轮已有的
                parts.append(f"[{msg.emoji} {msg.role_name} 第{msg.round_num}轮]:\n{msg.content}\n")
        return "\n".join(parts) if parts else "（尚无发言）"

    def _synthesize(self, transcript: list[RoundMessage]):
        """裁判汇总——用 LLM 做结构化提取（使用 judge_runner，可能是更强的模型）"""
        runner = getattr(self, '_judge_runner', self._runner)
        if not runner:
            return

        full_context = "\n\n".join(
            f"[{msg.emoji} {msg.role_name} 第{msg.round_num}轮]: {msg.content}"
            for msg in transcript
        )

        judge_prompt = f"""你是一个辩论裁判。以下是一场关于「{self.config.question}」的完整辩论记录。

请分析并输出 JSON，格式如下：
{{
  "consensus": "各方达成共识的结论（如果有），没有则写'无明确共识'",
  "confidence": 0.75,
  "recommendation": "综合考虑所有论点后的最终建议，100字以内",
  "risk_items": ["关键风险1", "关键风险2"],
  "conflicts": [
    {{
      "topic": "分歧主题",
      "positions": [
        {{"role": "乐观派", "view": "观点简述"}},
        {{"role": "悲观派", "view": "观点简述"}}
      ]
    }}
  ]
}}

=== 辩论记录 ===
{full_context}

只输出 JSON，不要任何其他文字。"""

        response = runner(
            "你是一个公正的辩论裁判。你的任务是：阅读完整辩论记录，提取共识、分歧、置信度和最终建议。只输出 JSON。",
            judge_prompt,
        )

        # 解析裁判输出
        try:
            # 尝试清洗可能的 markdown 包裹
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
            data = json.loads(cleaned)
            self.result.consensus = data.get("consensus", "")
            self.result.confidence = data.get("confidence", 0.5)
            self.result.recommendation = data.get("recommendation", "")
            self.result.risk_items = data.get("risk_items", [])
            self.result.conflicts = data.get("conflicts", [])
        except (json.JSONDecodeError, KeyError) as e:
            # 解析失败：警告 + 保留原始文本（避免静默吞错）
            import logging
            logging.getLogger("stock_roundtable").warning(
                "⚠️ 裁判 JSON 解析失败 (%s)，回退到原始输出。前100字: %s",
                type(e).__name__, response[:100]
            )
            self.result.recommendation = response
            self.result.confidence = 0.5
