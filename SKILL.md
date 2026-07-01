---
name: stock-roundtable
description: "股票圆桌辩论——6 大投资流派（格雷厄姆/巴菲特/费雪/笨韭/莫大/龟龟）同时分析一支股票，自动抓行情+财报+除权调整，输出 WorkBuddy 同款 HTML 报告。"
version: 2.0.0
author: Agent + 大哥
license: MIT
platforms: [linux, macos]
notes: |
    v2.0.0 (2026-07-01) — 方法论驱动重构：roles.py 从 methodology 文件动态加载，删通用辩论角色，methodology 文件修复+精简。详见 CHANGELOG.md。
metadata:
  hermes:
    tags: [multi-agent, debate, decision-making, ai-orchestration]
---

# 🎭 Stock Roundtable

6 大投资流派圆桌辩论 —— 一条命令，自动抓行情+财报+产业链格局，输出杂志级 HTML 报告。

## 🏛️ 六大流派

| 角色 | 来源 | 核心理念 |
|------|------|----------|
| 📐 **格雷厄姆** | 《聪明的投资者》 | 7 条量化硬标准：PE≤15 + PE×PB≤22.5 |
| 🏰 **巴菲特** | 《致股东的信》 | 护城河 × 伊索三问 × 安全边际 |
| 🔬 **费雪** | 《怎样选择成长股》 | 管理层质量 > 一切 |
| ⚡ **笨韭** | B 站 24.9 万粉 UP 主 | 现象级事件 → 景气轮动 → 笨韭双击 |
| 📊 **莫大** | 雪球 2173 篇帖子 | 六维加权：供给约束 > 业绩增长 |
| 🐢 **龟龟** | B 站 35 万粉 UP 主 | 穿透回报率 + 烟蒂股，先守后攻 |

完整方法论见 [`references/methodologies/`](references/methodologies/)。莫大真实氦气仓位框架见 [`references/moda-helium-thesis.md`](references/moda-helium-thesis.md)。

## 🚀 快速开始

### Hermes Skill

```bash
hermes skills install https://raw.githubusercontent.com/cocodeemo/stock-roundtable/main/SKILL.md --name stock-roundtable
```

对话中说 "分析一下华特气体 688268"，Agent 自动加载 6 大方法论，拉取实时数据并输出 HTML 报告。

### CLI 独立运行

```bash
pip install akshare                                     # 可选：深度财务分析
cd scripts/
python3 stock_debate.py 688268                          # 华特气体
python3 stock_debate.py 688268 --rounds 3               # 3 轮辩论
python3 stock_debate.py 688268 --model deepseek-v4-pro  # 指定模型
```

报告输出到 `~/Desktop/report_<股票名>_<代码>_<日期>.html`。

### 数据链路

```
腾讯行情 ──→ 价格 / PE / 市值 / 52周高低（前复权K线修正）
EastMoney ──→ PE / 市值（交叉验证）
AKShare ───→ 财报 / 除权 / 主营业务
v4-pro ────→ 产业链格局（供给瓶颈 / 需求爆发 / 低估点）
              ↓
       三方交叉验证（PE偏差>5%警告/>10%报错 / 市值偏差>10%报错）
              ↓
       三情境辩论问题 → 6角色×2轮辩论 → 裁判汇总 → HTML 报告
```

## ✨ 核心功能

### 智能角色过滤

| 条件 | 跳过角色 | 原因 |
|------|---------|------|
| PE > 50 或 营收 < 50 亿 | 📐 格雷厄姆 | 7 条硬标准必挂 |
| PE > 100 且 ROE < 5% | 🐢 龟龟 | 穿透回报率必为 0 |
| 营收 YoY > 30% 且 毛利率 > 50% | 📐 + 🐢 | 高增长股不适合防御型策略 |

跳过的角色以琥珀色标注在 HTML 结论卡中。

### 三方交叉验证

| 检查项 | 数据源 | 阈值 |
|--------|--------|------|
| PE(TTM) | 腾讯 vs 东方财富 TTM PE | 偏差 >5% 警告，>10% 报错 |
| 总市值 | 腾讯 vs 东方财富 | 偏差 >10% 报错 |
| 52 周高低 | 前复权 K 线修正 | 避免除权失真 |
| 送转股 | AKShare 除权记录 | EPS/BPS/OCF 自动修正 |
| 产业链格局 | v4-pro 自动生成 | 供给瓶颈/需求爆发/低估点 |

### HTML 报告模块

- 结论卡 — 数据快照 + 裁判建议 + 置信度 + 共识 + 数据校验警告 + 跳过角色提示
- 六框架评分对比表 — 自动从辩论实录提取分数和立场
- 视角卡 — 每个角色一条 voice card，评分表自动可视化（彩色进度条）
- 分歧卡 + 风险表
- 暗色模式自动适配

### 辩论问题格式（通用三情境）

```
{股票名}({代码})当前投资价值如何评估？

【实时行情】...【财务数据】...【公司背景】...【产业链格局】...

请各角色从自己的框架出发进行分析，同时考虑三种情境：
- 尚未持有：现在是否值得买入？
- 已持有：应继续持有、加仓还是减仓？
- 无论哪种：现在的风险收益比如何？
```

## 🎯 Demo

`demos/` 目录包含真实案例的 HTML 报告（下载后浏览器打开）：

| Demo | 股票 | 看点 |
|------|------|------|
| [中际旭创](demos/中际旭创_圆桌辩论报告.html) | AI 光模块龙头 | 六框架深度分裂（费雪 82 vs 格雷厄姆 0） |
| [九丰能源](demos/九丰能源_圆桌辩论报告.html) | LNG 贸易商 | 六框架一致看空（均分 39） |

## 📂 项目结构

```
stock-roundtable/
├── SKILL.md                        # Hermes Skill 主指南
├── scripts/
│   ├── stock_debate.py             # 一行命令全流程
│   ├── demo.py                     # LLM 辩论引擎入口
│   ├── engine.py                   # 核心辩论编排
│   ├── roles.py                    # 6 大流派角色定义
│   └── html_report.py             # HTML 报告渲染
├── references/
│   ├── methodologies/              # 6 大投资方法论原文
│   ├── moda-helium-thesis.md       # 莫大真实氦气仓位框架
│   └── html-report-format-pitfalls.md
└── demos/                          # HTML 报告示例
```

## ⚠️ 关键 Pitfalls

- **数据准确性优先于分析质量**：腾讯 API `fields[39]=PE, [45]=市值, [47/48]=52周高低(不除权)`，索引错了所有数据全废。52 周高低必须用前复权 K 线（`fqkline/get?param=,day,,,250,qfq`）替代。
- **送转股除权**：送转股除权日后，AKShare 每股数据不会自动反映。必须通过 `stock_dividend_cninfo()` 检测，对 EPS/BPS/OCF 做除法调整。NaN 处理：`if sg and sg==sg`。
- **交易所识别**：深市代码是 6 位（000762），不能用 `len(code)==5` 判断港股——会误把深市当港股。正确：`len(code)==6 and code[0] in '69' → sh`；`len(code)==6 and code[0] in '03' → sz`；其余 → hk。
- **辩论问题不能诱导错误方向**：旧版 `build_question()` 硬编码了"军工电子"背景和"ST状态意味着什么风险？"。已修复为动态生成公司背景和关注点——只在该股真正 ST 时才提 ST。
- **产业链格局必须聚焦供需矛盾**：v4-pro 生成行业背景时，提示词应聚焦"核心产品哪个存在供给瓶颈？市场低估了什么？"，而非面面俱到的行业概述。聚焦型输出能显著提升辩论质量（验证：莫大费雪各涨 30+ 分）。
- **角色 prompt 必须有强制输出格式**：每个投资流派的 prompt 末尾必须有固定评分表格模板，否则 LLM 在 Round 2 只互相引用不打分，HTML 报告中无可视化分数。
- **已修复的常见 bug**：CSS 字符串尾部逗号→tuple（`"""` 后无逗号）；`html` 变量名遮盖 import；`cfg` 作用域 NameError（`try` 前初始化 `cfg=None`）；`_parse()` NaN 传播（`math.isnan()` 检测）。
- **LLM 训练数据过时**：deepseek-v4-pro 训练截止 2023，不知道当前股价/PE/财报。必须提前抓实时数据注入问题，否则角色会编造假数字互相打架。
- **报告交付必须附带文件路径**：给用户时直接在回复中写出绝对路径（如 `~/Desktop/report_华特气体_688268_20260629.html`），不要只给 Markdown 链接。
- **Round 2 HTML 格式兼容性**：LLM 在第二轮常产出非标准表格（`旧分/新分/调整` 列头、数字后带尾随文本如 `**30** (下调10分)`、`综合评分：XX/100` 等格式）。`html_report.py` 已做 4 项修复来兜底这些情况，详见 [`references/html-report-format-pitfalls.md`](references/html-report-format-pitfalls.md)。

---

<p align="center">
  <sub>⚠️ 报告由 AI 自动生成，仅供参考，不构成投资建议。</sub>
</p>
