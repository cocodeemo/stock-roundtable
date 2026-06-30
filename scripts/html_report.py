"""
辩论报告 HTML 渲染器
——把 DebateResult + 行情数据 → WorkBuddy 杂志级 HTML 报告

用法：
    from html_report import render_html
    html = render_html(result, stock_data={"snapshot": {...}, "date": "2026-06-26"})
    with open("report.html", "w") as f:
        f.write(html)
"""

import json, html
from datetime import datetime
from engine import DebateResult, RoundMessage

CSS = r"""
:root {
  --bg-primary: #F7F5F3; --bg-secondary: #FFFFFF; --bg-card: #FFFFFF;
  --bg-elevated: #FAFAF9; --bg-warm: #F5F2EE; --bg-dark: #2D2926;
  --text-primary: #2D2926; --text-secondary: #5C5652;
  --text-muted: #8A8480; --text-light: #A8A29E;
  --accent: #D97706; --accent-light: #FEF3C7; --accent-hover: #B45309;
  --border: #E5E2DE; --border-light: #F0EEEC;
  --red: #DC2626; --green: #059669; --gold: #D97706; --blue: #2563EB;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  background: var(--bg-primary); color: var(--text-primary);
  line-height: 1.8; font-size: 16px; -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 { font-family: inherit; font-weight: 600; letter-spacing: 0.02em; }

.section-head {
  max-width: 1100px; display: grid; grid-template-columns: 120px 1fr;
  gap: 32px; align-items: baseline; margin: 0 auto 48px; padding: 0 48px;
}
.section-num {
  font-size: 0.9rem; color: var(--accent); letter-spacing: 0.15em;
  border-top: 1px solid var(--accent); padding-top: 8px;
}
.section-title { font-size: 2rem; }
.section-lede { color: var(--text-muted); margin-top: 6px; font-size: 1rem; }
section { padding: 72px 0; }

/* Nav */
nav {
  position: sticky; top: 0; z-index: 100; height: 64px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 48px; background: rgba(247,245,243,0.85);
  backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-light);
}
.nav-logo { font-weight: 600; font-size: 1rem; }
.nav-links { display: flex; gap: 28px; }
.nav-links a { color: var(--text-secondary); font-size: 0.95rem; text-decoration: none; }
.nav-links a:hover { color: var(--accent); }

/* Hero */
.hero { max-width: 1100px; margin: 0 auto; padding: 96px 48px 48px; }
.kicker { color: var(--accent); font-size: 0.9rem; letter-spacing: 0.15em; font-weight: 500; margin-bottom: 24px; }
.hero h1 { font-size: 3rem; line-height: 1.25; margin-bottom: 24px; max-width: 900px; }
.hero-dek { max-width: 760px; font-size: 1.15rem; color: var(--text-secondary); line-height: 1.9; margin-bottom: 40px; }

/* Conclusion Card */
.conclusion-wrap { max-width: 1100px; margin: 0 auto; padding: 0 48px; }
.conclusion-card {
  padding: 40px 48px; background: var(--bg-card); border: 1px solid var(--border);
  border-left: 6px solid var(--accent); border-radius: 20px;
  box-shadow: 0 4px 28px rgba(217, 119, 6, 0.06);
}
.cc-question {
  font-size: 0.85rem; color: var(--text-muted); letter-spacing: 0.05em;
  margin-bottom: 8px; text-transform: uppercase;
}
.cc-question-text {
  font-size: 1.4rem; font-weight: 600; color: var(--text-primary);
  margin-bottom: 28px; padding-bottom: 24px; border-bottom: 1px dashed var(--border);
}
.cc-question-text::before { content: "「"; color: var(--accent); }
.cc-question-text::after { content: "」"; color: var(--accent); }

.cc-snapshot { margin-bottom: 32px; }
.cc-snapshot-label {
  font-size: 0.78rem; color: var(--text-muted); letter-spacing: 0.18em;
  font-weight: 600; margin-bottom: 14px; text-transform: uppercase;
}
.cc-snapshot-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--bg-elevated); border: 1px solid var(--border-light);
  border-radius: 12px; overflow: hidden;
}
.cc-snap-cell {
  padding: 16px 20px; border-right: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light); background: var(--bg-elevated);
}
.cc-snap-cell:nth-child(4n) { border-right: none; }
.cc-snap-cell:nth-last-child(-n+4) { border-bottom: none; }
.cc-snap-cell-label { font-size: 0.78rem; color: var(--text-muted); letter-spacing: 0.05em; margin-bottom: 6px; }
.cc-snap-cell-value { font-size: 1.4rem; font-weight: 600; color: var(--text-primary); font-variant-numeric: tabular-nums; line-height: 1.2; }
.cc-snap-cell-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; font-variant-numeric: tabular-nums; }
.cc-snap-up { color: var(--red); }
.cc-snap-down { color: var(--green); }

.cc-headline-label {
  font-size: 0.8rem; color: var(--accent); letter-spacing: 0.2em;
  font-weight: 600; margin-bottom: 14px; text-transform: uppercase;
}
.cc-headline {
  font-size: 1.15rem; font-weight: 500; color: var(--text-primary);
  letter-spacing: 0.01em; line-height: 1.75;
  margin-bottom: 32px; padding-bottom: 28px;
  border-bottom: 1px solid var(--border);
}
.cc-headline strong { font-weight: 700; }
.cc-headline em { font-style: normal; font-weight: 700; color: var(--red); }

/* Consensus block */
.cc-consensus {
  margin-bottom: 28px; padding: 20px 24px;
  background: var(--bg-warm); border-radius: 12px;
  border-left: 4px solid var(--blue);
}
.cc-consensus p {
  font-size: 1.05rem; color: var(--text-primary); line-height: 1.85; margin: 0;
}
.cc-consensus p strong { font-weight: 700; }

/* Data validation warnings */
.cc-validation {
  margin-bottom: 24px; padding: 16px 20px;
  background: #FEF2F2; border: 1px solid #FECACA;
  border-radius: 10px; font-size: 0.9rem;
}
.cc-validation-label {
  color: var(--red); font-weight: 700; font-size: 0.85rem;
  letter-spacing: 0.05em; margin-bottom: 6px;
}
.cc-validation-item {
  color: var(--text-secondary); padding: 2px 0; font-size: 0.85rem;
}

.cc-vote {
  display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  padding-top: 20px; border-top: 1px dashed var(--border);
}
.cc-vote-label { font-size: 0.85rem; color: var(--text-muted); letter-spacing: 0.05em; }
.cc-vote-tag {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 0.85rem; color: var(--text-secondary);
  padding: 4px 12px; background: var(--bg-elevated); border-radius: 999px;
  border: 1px solid var(--border-light);
}
.cc-vote-tag .dot { width: 8px; height: 8px; border-radius: 50%; }

/* Six-framework comparison */
.compare-table {
  width: 100%; border-collapse: collapse; margin: 24px 0;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 14px; overflow: hidden; font-variant-numeric: tabular-nums;
}
.compare-table th {
  background: var(--bg-warm); color: var(--text-muted);
  font-size: 0.82rem; padding: 12px 14px; text-align: center;
  letter-spacing: 0.04em; border-bottom: 2px solid var(--accent);
}
.compare-table td {
  padding: 10px 14px; text-align: center; border-bottom: 1px solid var(--border-light);
  font-size: 0.95rem;
}
.compare-table tr:last-child td { border-bottom: none; }
.compare-score { font-weight: 700; font-size: 1.1rem; }
.compare-score.high { color: var(--green); }
.compare-score.mid { color: var(--accent); }
.compare-score.low { color: var(--red); }
.compare-verdict {
  padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600;
}
.compare-verdict.buy { background: #DCFCE7; color: #166534; }
.compare-verdict.hold { background: #FEF3C7; color: #92400E; }
.compare-verdict.sell { background: #FEE2E2; color: #991B1B; }

/* Confidence bar */
.cc-confidence { margin-bottom: 28px; }
.cc-confidence-bar {
  height: 8px; background: var(--border-light); border-radius: 4px;
  margin-top: 8px; overflow: hidden;
}
.cc-confidence-fill {
  height: 100%; background: linear-gradient(90deg, var(--accent), var(--green));
  border-radius: 4px; transition: width 0.5s;
}

/* Voice Cards */
.voice-stack {
  max-width: 1100px; margin: 0 auto; padding: 0 48px;
  display: flex; flex-direction: column; gap: 24px;
}
.voice-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 16px; padding: 32px 36px; min-width: 0;
}
.voice-head {
  display: flex; align-items: center; gap: 12px;
  padding-bottom: 16px; margin-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}
.voice-emoji { width: 48px; height: 48px; border-radius: 50%;
  background: var(--bg-warm); display: flex; align-items: center;
  justify-content: center; font-size: 1.5rem; border: 2px solid var(--border);
}
.voice-name { font-weight: 600; font-size: 1.1rem; flex: 1; }
.voice-round { font-size: 0.8rem; color: var(--text-muted); }
.voice-card p { margin-bottom: 14px; line-height: 1.85; color: var(--text-secondary); }
.voice-card strong { color: var(--text-primary); font-weight: 600; }
.voice-card em { font-style: normal; font-weight: 600; color: var(--accent); }
.voice-card .pull-quote {
  border-left: 3px solid var(--accent); padding: 4px 0 4px 16px;
  margin: 16px 0; color: var(--text-secondary); font-style: italic;
}

/* ===== Score Visualization ===== */
.score-table {
  width: 100%; border-collapse: collapse; margin: 16px 0;
  background: var(--bg-elevated); border-radius: 12px;
  overflow: hidden; border: 1px solid var(--border-light);
}
.score-table th {
  background: var(--bg-warm); color: var(--text-muted);
  font-size: 0.82rem; font-weight: 500; padding: 10px 14px;
  text-align: left; letter-spacing: 0.04em;
}
.score-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
.score-table tr:last-child td { border-bottom: none; }
.score-bar-wrap { display: flex; align-items: center; gap: 8px; min-width: 120px; }
.score-bar {
  flex: 1; height: 6px; background: var(--border-light); border-radius: 3px; overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s; }
.score-bar-fill.high { background: var(--green); }
.score-bar-fill.mid { background: var(--accent); }
.score-bar-fill.low { background: var(--red); }
.score-value { font-weight: 600; font-size: 0.9rem; min-width: 36px; text-align: right; font-variant-numeric: tabular-nums; }
.score-total {
  display: flex; align-items: center; gap: 12px; padding: 16px 20px;
  background: var(--bg-warm); border-radius: 12px; margin: 12px 0;
  border: 2px solid var(--accent);
}
.score-total-label { font-size: 0.85rem; color: var(--text-muted); letter-spacing: 0.06em; }
.score-total-value { font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.score-total-grade {
  padding: 4px 14px; border-radius: 999px; font-size: 0.9rem; font-weight: 600;
}
.score-total-grade.top { background: #DCFCE7; color: #166534; }
.score-total-grade.good { background: #E0F2FE; color: #075985; }
.score-total-grade.ok { background: #FEF3C7; color: #92400E; }
.score-total-grade.bad { background: #FEE2E2; color: #991B1B; }
.score-total-grade.skip { background: #F3F4F6; color: #6B7280; }

.checklist { margin: 12px 0; }
.check-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 0;
  font-size: 0.95rem;
}
.check-pass { color: var(--green); font-weight: 600; }
.check-fail { color: var(--red); font-weight: 600; }
.check-warn { color: var(--accent); font-weight: 600; }

/* Risk Table */
.risk-wrap { max-width: 1100px; margin: 0 auto; padding: 0 48px; }
.risk-table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 16px; overflow: hidden; font-variant-numeric: tabular-nums;
}
.risk-table th, .risk-table td {
  padding: 18px 22px; text-align: left;
  border-bottom: 1px solid var(--border-light); vertical-align: top;
}
.risk-table tr:last-child td { border-bottom: none; }
.risk-table th {
  background: var(--bg-elevated); color: var(--text-muted);
  font-size: 0.85rem; font-weight: 500; letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* Disputes */
.dispute-stack { max-width: 1100px; margin: 0 auto; padding: 0 48px; display: flex; flex-direction: column; gap: 16px; }
.dispute-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 14px; padding: 24px 28px;
  display: grid; grid-template-columns: 56px 1fr; gap: 20px; align-items: baseline;
}
.dispute-num { font-size: 1.6rem; font-weight: 600; color: var(--accent); font-variant-numeric: tabular-nums; line-height: 1; opacity: 0.6; }
.dispute-body h4 { font-size: 1.1rem; margin-bottom: 8px; color: var(--text-primary); }
.dispute-body p { font-size: 0.98rem; line-height: 1.85; color: var(--text-secondary); margin: 0 0 8px; }

/* Footer */
footer { background: var(--bg-dark); color: var(--text-light); padding: 48px; text-align: center; margin-top: 72px; }
footer p { max-width: 680px; margin: 0 auto; font-size: 0.95rem; }
.footer-sub { margin-top: 16px; font-size: 0.8rem; color: var(--text-light); opacity: 0.7; }

@media (max-width: 900px) {
  .voice-stack, .risk-wrap, .dispute-stack, .conclusion-wrap { padding-left: 24px; padding-right: 24px; }
  .hero { padding-left: 24px; padding-right: 24px; }
  .conclusion-card { padding: 28px 24px; }
  .cc-headline { font-size: 1.05rem; line-height: 1.7; }
  .cc-snapshot-grid { grid-template-columns: repeat(2, 1fr); }
  .cc-snap-cell:nth-child(4n) { border-right: 1px solid var(--border-light); }
  .cc-snap-cell:nth-child(2n) { border-right: none; }
  .cc-snap-cell:nth-last-child(-n+4) { border-bottom: 1px solid var(--border-light); }
  .cc-snap-cell:nth-last-child(-n+2) { border-bottom: none; }
  .hero h1 { font-size: 2.2rem; }
  nav { padding: 0 24px; }
  .nav-links { display: none; }
  .voice-card { padding: 24px; }
  .dispute-card { padding: 20px; grid-template-columns: 1fr; gap: 8px; }
  .risk-table th, .risk-table td { padding: 14px 14px; }
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: #1A1817; --bg-secondary: #242220; --bg-card: #242220;
    --bg-elevated: #2D2A28; --bg-warm: #2D2A28; --bg-dark: #F5F2EE;
    --text-primary: #E5E2DE; --text-secondary: #B0ABA6;
    --text-muted: #8A8480; --text-light: #6B6560;
    --accent: #F59E0B; --accent-light: #78350F; --accent-hover: #FBBF24;
    --border: #3D3A36; --border-light: #33302D;
    --red: #F87171; --green: #34D399; --blue: #60A5FA;
  }
  .cc-validation { background: #2D1F1F; border-color: #5C2020; }
  .cc-consensus { background: #1F2A35; border-left-color: #60A5FA; }
  .score-total { background: #2D2A28; }
  .score-total-grade.top { background: #14532D; color: #86EFAC; }
  .score-total-grade.good { background: #1E3A5F; color: #93C5FD; }
  .score-total-grade.ok { background: #4A3500; color: #FDE68A; }
  .score-total-grade.bad { background: #5C2020; color: #FCA5A5; }
  .score-total-grade.skip { background: #2D2A28; color: #8A8480; }
  .compare-verdict.buy { background: #14532D; color: #86EFAC; }
  .compare-verdict.hold { background: #4A3500; color: #FDE68A; }
  .compare-verdict.sell { background: #5C2020; color: #FCA5A5; }
  .score-table { background: #2D2A28; }
  .score-table th { background: #242220; }
}
"""


def _shorten_question(q: str, max_len: int = 30) -> str:
    """缩短问题作为导航标题"""
    if len(q) <= max_len:
        return q
    return q[:max_len] + "…"


def _parse_transcript_to_voice_cards(transcript: list) -> str:
    """把辩论实录解析为 voice card HTML"""
    if not transcript:
        return '<p style="color:var(--text-muted);text-align:center;">暂无辩论记录</p>'

    # 按角色分组，每组可能有多个轮次
    cards = []
    for msg in transcript:
        content = msg.get("content", "")
        # Markdown → HTML → 可视化评分组件
        content_html = _visualize_scores(_simple_md_to_html(content))

        cards.append(f"""<article class="voice-card">
  <div class="voice-head">
    <div class="voice-emoji">{msg.get("emoji", "🎭")}</div>
    <div class="voice-name">{msg.get("role_name", "发言人")}</div>
    <div class="voice-round">第 {msg.get("round", 1)} 轮</div>
  </div>
  <div>{content_html}</div>
</article>""")

    return "\n".join(cards)


def _simple_md_to_html(text: str) -> str:
    """简易 Markdown → HTML 转换，含表格支持"""
    import re

    text = text.replace("\r\n", "\n")

    lines = text.split("\n")
    result = []
    in_list = False
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal table_rows, in_table
        if not table_rows:
            return
        bold_re = re.compile(r'\*\*(.+?)\*\*')
        html_rows = []
        for i, row in enumerate(table_rows):
            cells = [c.strip() for c in row.split('|')[1:-1]]
            tag = 'th' if i == 0 else 'td'
            html_cells = ''.join(
                '<{tag}>{cell}</{tag}>'.format(
                    tag=tag,
                    cell=bold_re.sub(r'<strong>\1</strong>', cell)
                )
                for cell in cells
            )
            html_rows.append('<tr>{}</tr>'.format(html_cells))
        result.append('<table>{}</table>'.format(''.join(html_rows)))
        table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        # 表格行检测
        is_table_row = bool(re.match(r'^\|.+\|$', stripped))
        is_separator = bool(re.match(r'^\|[\s\-:]+\|', stripped))
        is_code_fence = stripped.startswith('```')

        if is_code_fence:
            if in_table:
                flush_table()
            if in_list:
                result.append("</ul>")
                in_list = False
            continue

        if is_table_row and not is_separator:
            if not in_table:
                if in_list:
                    result.append("</ul>")
                    in_list = False
                in_table = True
            table_rows.append(stripped)
            continue
        elif is_separator and in_table:
            continue  # 跳过分隔行
        elif in_table:
            flush_table()

        # 空行
        if not stripped:
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append("")
            continue

        # 标题
        if stripped.startswith("### "):
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append(f'<h4>{stripped[4:]}</h4>')
            continue
        if stripped.startswith("## "):
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append(f'<h3>{stripped[3:]}</h3>')
            continue

        # 列表项
        if re.match(r'^[-*•]\s', stripped):
            if not in_list:
                result.append("<ul>")
                in_list = True
            item = re.sub(r'^[-*•]\s+', '', stripped)
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            result.append(f"<li>{item}</li>")
            continue

        # 引用
        if stripped.startswith("> "):
            if in_list:
                result.append("</ul>")
                in_list = False
            quote = stripped[2:]
            quote = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', quote)
            result.append(f'<div class="pull-quote">{quote}</div>')
            continue

        # 普通段落
        if in_list:
            result.append("</ul>")
            in_list = False
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        result.append(f"<p>{para}</p>")

    if in_list:
        result.append("</ul>")
    if in_table:
        flush_table()

    return "\n".join(result)


def _visualize_scores(html: str) -> str:
    """后处理：把评分相关内容变成可视化组件"""
    import re

    # 1. 总分行 → score-total 组件
    # 匹配: <p><strong>总分</strong>：... = <strong>32.5分</strong> → ❌ 平庸</p>
    total_re = re.compile(
        r'<p>(?:<strong>)?总分(?:</strong>)?[：:]\s*(.*?)\s*=\s*(?:<strong>)?([\d.]+)分(?:</strong>)?\s*→?\s*(.*?)</p>'
    )
    html = total_re.sub(
        lambda m: '<div class="score-total"><span class="score-total-label">综合评分</span>'
                  '<span class="score-total-value">{}</span>'
                  '<span class="score-total-grade {}">{}</span>'
                  '</div>'.format(
                      m.group(2),
                      _grade_class(float(m.group(2))),
                      m.group(3).strip() or _grade_label(float(m.group(2)))
                  ),
        html
    )

    # 2. 评分表格 → 带进度条的 score-table
    # 找 <table> 中含 "分数" 或 "评分" 或 "分值" 列头的表格

    def _add_bar_to_row(row_match):
        """给评分表格行添加进度条"""
        row = row_match.group(0)
        score_match = re.search(r'<td[^>]*>(?:<strong>)?([\d.]+)(?:</strong>)?</td>', row)
        if not score_match:
            return row
        score = float(score_match.group(1))
        bar_class = 'high' if score >= 70 else ('mid' if score >= 40 else 'low')
        bar_html = ('<div class="score-bar-wrap">'
                   '<span class="score-value">{}</span>'
                   '<div class="score-bar"><div class="score-bar-fill {}" style="width:{}%;"></div></div>'
                   '</div>').format(score, bar_class, min(score, 100))
        return re.sub(
            r'<td[^>]*>(?:<strong>)?[\d.]+(?:</strong>)?</td>',
            '<td>{}</td>'.format(bar_html),
            row,
            count=1
        )

    def convert_score_table(match):
        table_html = match.group(0)
        # 检查是否含分数列
        if not re.search(r'<th[^>]*>.*?(?:分数|评分|分值|得分).*?</th>', table_html):
            return table_html

        table_html = re.sub(r'<tr>(?!<th).*?</tr>', _add_bar_to_row, table_html)
        return table_html.replace('<table>', '<table class="score-table">')

    html = re.sub(r'<table>.*?</table>', convert_score_table, html, flags=re.DOTALL)

    # 3. ✅❌ 清单 → 可视化
    html = re.sub(
        r'<li>(✅|❌|⚠️)\s*(.*?)</li>',
        lambda m: f'<li><span class="check-{"pass" if m.group(1)=="✅" else ("fail" if m.group(1)=="❌" else "warn")}">{m.group(1)} {m.group(2)}</span></li>',
        html
    )

    # 4. 行内评分→高亮（如 "护城河30分" "PE 140倍 vs 15倍红线" "/100"）
    html = re.sub(
        r'(\d{1,3})\s*/\s*100\s*分?',
        r'<span style="font-weight:700;font-size:1.1em;">\1</span>/100分',
        html
    )
    html = re.sub(
        r'([\u4e00-\u9fff]{2,4})\s*[：:]\s*(\d{1,3})\s*分\b',
        r'<span class="inline-score">\1: <strong>\2</strong>分</span>',
        html
    )

    return html


def _build_comparison_table(transcript: list) -> str:
    """从辩论实录中提取分数，构建六框架对比表"""
    import re
    scores = {}

    for msg in transcript:
        name = msg.get("role_name", "")
        content = msg.get("content", "")
        if not name or not content:
            continue

        # 提取总分 —— 多段兜底
        m = None
        # 1. 标准的 "总分：XX/100" 格式
        m = re.search(r'总分[：:].*?([\d.]+)\s*/\s*100', content)
        # 2. "XX/100" 格式（独立一行）
        if not m:
            m = re.search(r'(?<!\d)([\d.]+)\s*/\s*100\s*(?:分|→)', content)
        # 3. "总分约XX分" "总分降至XX分" "总分仅仅XX"
        if not m:
            m = re.search(r'(?:总分|综合|加权).*?[\s：:]*(?:约|仅|降至|不及)?\s*([\d.]+)\s*分', content)
        # 4. "*总分*：**XX**/100" (bold Markdown)
        if not m:
            m = re.search(r'\*\*总分\*\*[：:]\s*\*?\*?([\d.]+)\*?\*?\s*/?\s*100', content)
        # 5. 表格最后一行最后一列是数字（兜底）
        _table_score = None
        if not m:
            for line in content.split('\n'):
                if re.match(r'^\|.*\|\s*$', line) and not re.match(r'^\|[\s\-:]+\|', line):
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    if len(cells) >= 2:
                        try:
                            # 最后一行最后单元格
                            last = cells[-1].replace('**', '').strip()
                            v = float(last)
                            if 0 < v <= 100:
                                _table_score = v
                                break
                        except ValueError:
                            # 倒数第二格（有时结论在最后一格）
                            if len(cells) > 2:
                                try:
                                    v = float(cells[-2].replace('**', '').strip())
                                    if 0 < v <= 100:
                                        _table_score = v
                                        break
                                except ValueError:
                                    pass

        score = None
        if m:
            score = float(m.group(1))
        elif _table_score is not None:
            score = float(_table_score)

        if score is not None:
            # 提取结论行 —— 优先找「结论：」或「结论」
            conclusion = ""
            for pattern in [r'结论[：:]\s*(.+?)(?:\n|$)', r'建议(.+?)(?:\n|$)']:
                cm = re.search(pattern, content)
                if cm:
                    conclusion = cm.group(1).strip()[:40]
                    break
            if not conclusion:
                # 从尾部找关键词所在行
                lines = content.split('\n')
                for kw in ['不持有', '不买', '避开', '回避', '远离', '卖出', '观望', '观察', '持有']:
                    for line in reversed(lines):
                        if kw in line:
                            conclusion = line.strip()[:50]
                            break
                    if conclusion:
                        break

            # 判定立场：先检查否定词
            verdict = 'sell'
            if any(kw in conclusion for kw in ['买', '持有', '值得']):
                if not any(n in conclusion for n in ['不持有', '不买', '不碰', '再谈']):
                    verdict = 'buy'
            if any(kw in conclusion for kw in ['观望', '观察', '等待', '再谈']):
                verdict = 'hold'
            # 低分不能是buy
            if score < 60 and verdict == 'buy':
                verdict = 'hold'
            if score < 40 and verdict != 'sell':
                verdict = 'sell'

            scores[name] = {'score': score, 'verdict': verdict, 'conclusion': conclusion[:40]}

    if len(scores) < 2:
        return ""

    rows = ""
    for name, data in scores.items():
        score = data['score']
        score_class = 'high' if score >= 60 else ('mid' if score >= 30 else 'low')
        verdict_class = data['verdict']
        verdict_label = {'buy': '看好', 'hold': '观望', 'sell': '看空'}.get(verdict_class, '？')

        rows += f"""<tr>
  <td style="text-align:left;font-weight:600;">{name}</td>
  <td><span class="compare-score {score_class}">{score:.0f}</span></td>
  <td><span class="compare-verdict {verdict_class}">{verdict_label}</span></td>
  <td style="text-align:left;font-size:0.85rem;color:var(--text-muted);">{data['conclusion']}</td>
</tr>"""

    return f"""<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:16px;padding:20px 28px;">
  <h4 style="margin-bottom:12px;color:var(--text-primary);">📊 六框架评分对比</h4>
  <table class="compare-table">
    <thead><tr><th style="text-align:left;">流派</th><th>评分</th><th>立场</th><th style="text-align:left;">结论</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def _grade_class(score: float) -> str:
    if score >= 75: return 'top'
    if score >= 60: return 'good'
    if score >= 40: return 'ok'
    if score >= 20: return 'bad'
    return 'skip'

def _grade_label(score: float) -> str:
    if score >= 75: return '🔥 顶级'
    if score >= 60: return '✅ 优质'
    if score >= 40: return '⚠️ 一般'
    if score >= 20: return '❌ 平庸'
    return '🚫 避开'


def _build_consensus_html(consensus: str) -> str:
    """渲染共识结论块"""
    if not consensus or consensus == '无明确共识':
        return ""
    return f"""<div class="cc-consensus">
  <div class="cc-headline-label">圆桌共识</div>
  <p>{consensus}</p>
</div>"""


def _build_validation_html(errors: list, warnings: list, skipped_roles: list = None) -> str:
    """渲染数据校验警告 & 自动跳过的角色"""
    if not errors and not warnings and not skipped_roles:
        return ""
    items = ""
    for e in errors:
        items += f'<div class="cc-validation-item">❌ {e}</div>'
    for w in warnings:
        items += f'<div class="cc-validation-item">⚠️ {w}</div>'
    if skipped_roles:
        items += '<div class="cc-validation-item" style="color:#f59e0b;">🔍 自动跳过: ' + ', '.join(skipped_roles) + '</div>'
    return f"""<div class="cc-validation">
  <div class="cc-validation-label">🔍 数据校验警告</div>
  {items}
</div>"""

def _render_snapshot(snapshot: dict) -> str:
    """渲染数据快照网格"""
    if not snapshot:
        return ""

    cells = ""
    for label, data in snapshot.items():
        value = data.get("value", "")
        sub = data.get("sub", "")
        sub_class = data.get("sub_class", "")
        cells += f"""<div class="cc-snap-cell">
  <div class="cc-snap-cell-label">{label}</div>
  <div class="cc-snap-cell-value">{value}</div>
  <div class="cc-snap-cell-sub {sub_class}">{sub}</div>
</div>"""

    return f"""<div class="cc-snapshot">
  <div class="cc-snapshot-label">当前关键数据</div>
  <div class="cc-snapshot-grid">{cells}
  </div>
</div>"""


def render_html(result: DebateResult, stock_data: dict = None) -> str:
    """
    渲染完整 HTML 报告

    Args:
        result: DebateResult 或 dict (from to_dict())
        stock_data: {"date": "2026-06-26", "snapshot": {...}, "title_prefix": "西藏矿业 · "}
    """
    # 兼容 dict 输入
    if isinstance(result, dict):
        d = result
    else:
        d = result.to_dict()

    stock_data = stock_data or {}
    date_str = stock_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    title_prefix = stock_data.get("title_prefix", "")
    display_title = html.escape(stock_data.get("display_title", d["question"]))  # 短标题，用于 Hero/导航
    short_q = _shorten_question(display_title)
    validation_errors = stock_data.get("validation_errors", [])
    validation_warnings = stock_data.get("validation_warnings", [])
    skipped_roles = stock_data.get("skipped_roles", [])

    # 快照
    snapshot_html = _render_snapshot(stock_data.get("snapshot", {}))

    # Voice cards
    voice_html = _parse_transcript_to_voice_cards(d.get("transcript", []))

    # 六框架对比表
    compare_html = _build_comparison_table(d.get("transcript", []))

    # 共识 & 建议
    recommendation = html.escape(d.get("recommendation", ""))
    consensus = d.get("consensus", "")
    confidence = d.get("confidence", 0.5)

    # 分歧
    conflicts_html = ""
    conflicts = d.get("conflicts", [])
    if conflicts:
        dispute_cards = ""
        for i, c in enumerate(conflicts, 1):
            positions_html = ""
            for pos in c.get("positions", []):
                positions_html += f"<p><strong>{pos.get('role', '?')}</strong>：{pos.get('view', '')}</p>"
            dispute_cards += f"""<article class="dispute-card">
  <div class="dispute-num">{i:02d}</div>
  <div class="dispute-body">
    <h4>{c.get('topic', '未命名分歧')}</h4>
    {positions_html}
  </div>
</article>"""

        conflicts_html = f"""
<section id="conflicts">
  <div class="section-head">
    <div class="section-num">03 · 分歧</div>
    <div>
      <div class="section-title">核心分歧</div>
      <div class="section-lede">各方未能达成一致的焦点问题</div>
    </div>
  </div>
  <div class="dispute-stack">
    {dispute_cards}
  </div>
</section>"""

    # 风险
    risk_items = d.get("risk_items", [])
    risk_html = ""
    if risk_items:
        rows = ""
        for i, r in enumerate(risk_items, 1):
            rows += f"""<tr>
  <td style="font-weight:600;width:60px;">{i:02d}</td>
  <td style="color:var(--text-secondary);line-height:1.85;">{r}</td>
</tr>"""

        risk_html = f"""
<section id="risks">
  <div class="section-head">
    <div class="section-num">04 · 风险</div>
    <div>
      <div class="section-title">关键风险清单</div>
      <div class="section-lede">辩论中识别出的主要风险因素</div>
    </div>
  </div>
  <div class="risk-wrap">
    <table class="risk-table">
      <thead><tr><th>#</th><th>风险描述</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>"""

    # 组装完整 HTML
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_prefix}圆桌辩论报告 · Hermes Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<nav>
  <a class="nav-logo">🎭 {title_prefix}圆桌辩论</a>
  <div class="nav-links">
    <a href="#conclusion">结论</a>
    <a href="#voices">视角</a>
    <a href="#conflicts">分歧</a>
    <a href="#risks">风险</a>
  </div>
</nav>

<section class="hero">
  <div class="kicker">ROUND TABLE · {date_str} · Hermes 多 Agent 辩论引擎</div>
  <h1>{display_title}</h1>
  <div class="hero-dek">{len(d.get("participants", []))} 位专家多轮交叉辩论——{d.get("total_rounds", 0)} 轮互相引用反驳，全方位审视，综合置信度 {confidence:.0%}</div>
</section>

<section id="conclusion">
  <div class="section-head">
    <div class="section-num">01 · 结论</div>
    <div><h2>圆桌怎么看</h2><p class="section-lede">多视角交叉验证后的综合判断</p></div>
  </div>
  <div class="conclusion-wrap">
    <div class="conclusion-card">

      <div class="cc-question">YOU ASKED</div>
      <div class="cc-question-text">{display_title}</div>

      {snapshot_html}

      {_build_validation_html(validation_errors, validation_warnings, skipped_roles)}

      <div class="cc-headline-label">圆桌综合视角</div>
      <div class="cc-headline">{recommendation}</div>

      {_build_consensus_html(consensus)}
      <div class="cc-confidence">
        <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:var(--text-muted);">
          <span>综合置信度</span><span>{confidence:.0%}</span>
        </div>
        <div class="cc-confidence-bar"><div class="cc-confidence-fill" style="width:{confidence*100:.0f}%;"></div></div>
      </div>

      <div class="cc-vote">
        <span class="cc-vote-label">参与方：</span>
        {''.join(f'<span class="cc-vote-tag"><span class="dot" style="background:var(--accent)"></span>{p}</span>' for p in d.get("participants", []))}
        <span class="cc-vote-tag"><span class="dot" style="background:var(--blue)"></span>{d.get("total_rounds", 0)} 轮辩论</span>
      </div>

    </div>
  </div>
</section>

<section id="voices">
  <div class="section-head">
    <div class="section-num">02 · 视角</div>
    <div>
      <div class="section-title">{len(d.get("participants", []))} 方怎么看</div>
      <div class="section-lede">每位从自己的角色立场独立诊断——想看完整推理的人来这里</div>
    </div>
  </div>
  <div class="voice-stack">
    {compare_html}
    {voice_html}
  </div>
</section>

{conflicts_html}

{risk_html}

<footer>
  <p>⚠️ 以上内容由 Hermes 多 Agent 辩论引擎自动生成，基于 AI 模型推理，仅供参考，不构成任何投资建议或专业决策依据。</p>
  <p class="footer-sub">Hermes Agent · Debate Engine · Generated {date_str}</p>
</footer>

</body>
</html>"""

    return full_html


if __name__ == "__main__":
    # 快速测试
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine import DebateResult, RoundMessage

    # 构造测试数据
    result = DebateResult(
        question="要不要继续持有西藏矿业(000762)和中矿资源(002738)？",
        participants=["乐观派", "悲观派", "行业技术派"],
        total_rounds=2,
        confidence=0.68,
        recommendation="西藏矿业保留底仓（成本优势是安全垫），中矿资源建议减仓50%以上（非洲矿成本偏高+双重压力）",
        consensus="锂盐价格处于历史低位但短期仍承压；新能源长期需求向上",
        conflicts=[
            {"topic": "锂价是否已见底", "positions": [
                {"role": "乐观派", "view": "产能正在出清，底部已近"},
                {"role": "悲观派", "view": "非洲矿+南美盐湖仍在放量，底部未到"}
            ]},
            {"topic": "现在该不该卖", "positions": [
                {"role": "乐观派", "view": "持有等待反转，此时退出是割在底部"},
                {"role": "悲观派", "view": "卖出回避不确定性，机会成本更低"}
            ]}
        ],
        risk_items=[
            "锂价继续下跌至6万以下——西藏矿业微利、中矿可能亏损",
            "非洲矿减产进度慢于预期——延长底部时间",
            "西藏矿业扎布耶二期扩产延期——有资源但产不出"
        ],
        transcript=[
            RoundMessage(role="optimist", role_name="🟢 乐观派", emoji="🟢", content="**核心观点：现在是底部区域，继续持有。**\n\n理由有三：\n- 碳酸锂从60万跌到7-8万，澳洲多个矿山已宣布减产，供给端正在出清\n- 西藏矿业扎布耶盐湖成本仅3-4万/吨，远低于矿石提锂\n- 新能源需求长期向上，储能需求爆发式增长\n\n**结论**：底部区域，继续持有。", round_num=1),
            RoundMessage(role="pessimist", role_name="🔴 悲观派", emoji="🔴", content="**核心观点：减仓或清仓，锂矿冬天还没过去。**\n\n反驳乐观派：\n- 你说\"底部\"可能是半山腰——2023年所有人说底了，2024年继续跌\n- 扎布耶海拔4400米，运输成本极高，扩产反复延期\n- 中矿资源市值388亿对应利润撑不住\n\n> 仓位管理比预测更重要——如果你现在空仓会买吗？不会就该卖。", round_num=1),
            RoundMessage(role="optimist", role_name="🟢 乐观派", emoji="🟢", content="**回应悲观派：\"割在最底部\"是典型的散户行为。**\n\n既然已经等了18个月，现在处于最难受阶段，此时退出是认知偏差。\n\n悲观派你说\"锂价还会跌\"——但底部在哪？7万说是半山腰，6万也可以说半山腰。无限悲观无法证伪。", round_num=2),
            RoundMessage(role="pessimist", role_name="🔴 悲观派", emoji="🔴", content="**回应乐观派：你这是锚定效应——锚定在买入成本上而非基本面。**\n\n如果今天手上是现金，你会买吗？不会就该卖。\n\n我同意技术派的部分判断：西藏矿业可以保留但也要减。A股锂矿板块整体走势高度同步，板块贝塔才是主导因素。", round_num=2),
        ]
    )

    html = render_html(result, stock_data={
        "date": "2026-06-26",
        "title_prefix": "锂矿持仓 · ",
        "snapshot": {
            "西藏矿业(000762)": {"value": "26.32", "sub": "-2.02%", "sub_class": "cc-snap-down"},
            "中矿资源(002738)": {"value": "53.79", "sub": "-4.36%", "sub_class": "cc-snap-down"},
            "市值(西藏矿业)": {"value": "137亿", "sub": ""},
            "市值(中矿资源)": {"value": "388亿", "sub": ""},
        }
    })

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 测试报告已生成: {out_path}")
