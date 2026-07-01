# 🎭 Stock Roundtable · v2.0.1

6 大投资流派圆桌辩论 —— 实时行情+财报+产业链格局，LLM 角色互相引用反驳，输出杂志级 HTML 报告。

> Multi-agent debate: 6 investment schools debate a stock with real-time data injection. Round 1 runs in parallel. Magazine-grade HTML output.

---

## 🎯 Demo

`demos/` 目录包含两个真实 HTML 报告示例（下载后浏览器打开即可查看）。均由 Hermes Agent 基于真实行情（腾讯 API）+ 财务数据（AKShare）进行两轮辩论后自动生成。

| 股票 | 看点 · Highlight |
|------|-----------------|
| [中际旭创 (300308)](demos/中际旭创_圆桌辩论报告.html) | AI 光模块龙头，多框架深度分裂 |
| [九丰能源 (605090)](demos/九丰能源_圆桌辩论报告.html) | LNG 贸易商，多框架一致看空 |

> 💡 GitHub 不渲染自定义 HTML，请下载后浏览器打开。<br>
> 💡 *Download the HTML and open in your browser. GitHub doesn't render custom HTML.*

---

## 🏛️ 六大流派

| 流派 | 来源 | 核心理念 |
|------|------|----------|
| 📐 **格雷厄姆** | 《聪明的投资者》 | 7 条量化硬标准：PE≤15 + PE×PB≤22.5 |
| 🏰 **巴菲特** | 《致股东的信》 | 护城河 × 伊索三问 × 安全边际 |
| 🔬 **费雪** | 《怎样选择成长股》 | 管理层质量 > 一切，15 条 checklist |
| ⚡ **笨韭** | B 站 24.9 万粉 UP 主 | 现象级事件 → 景气轮动 → 笨韭双击 |
| 📊 **莫大** | 雪球 2173 篇帖子 | 六维加权：预期差 × 不可替代 × 股价位置 |
| 🐢 **龟龟** | B 站 35 万粉 UP 主 | 穿透回报率 + 烟蒂股，先守后攻 |

完整方法论见 [`references/methodologies/`](references/methodologies/)。

---

## 🚀 快速开始

### 作为 Hermes Skill 使用

```bash
# 安装
hermes skills install https://raw.githubusercontent.com/cocodeemo/stock-roundtable/main/SKILL.md --name stock-roundtable

# 对话中使用
"分析一下九丰能源 605090"
```

Agent 会自动加载 6 大方法论，拉取实时数据，进行内联辩论并输出 HTML 报告。

### 作为 CLI 工具独立运行

```bash
# 依赖
pip install akshare pyyaml

# 配置 API key（taotoken.net 或其他 OpenAI 兼容接口）
# ~/.hermes/config.yaml 或环境变量 TAOTOKEN_API_KEY

# 运行
cd scripts/
python3 stock_debate.py 688268              # 华特气体
python3 stock_debate.py 688106              # 金宏气体
python3 stock_debate.py 688268 --rounds 3   # 3 轮辩论
python3 stock_debate.py 688268 --model deepseek-v4-pro  # 指定模型
```


### 数据链路

```
腾讯行情 API ──→ 价格 / PE / 市值 / 52周高低（前复权K线修正）
EastMoney API ──→ PE / 市值（交叉验证）
AKShare ────→ 财报 / 除权 / 主营业务
v4-pro ────→ 产业链格局（供给瓶颈 / 需求爆发 / 低估点）
                ↓
         三方交叉验证（PE偏差>5%警告/>10%报错 / 市值偏差>10%报错）
                ↓
         构造三情境辩论问题 → 6角色×2轮辩论 → 裁判汇总 → HTML
```

---

### 报告输出

报告保存到 `~/Desktop/report_<股票名>_<代码>_<日期>.html`，含六框架评分对比表、彩色进度条、数据校验警告、跳过角色提示。

---

## 📂 项目结构

```
stock-roundtable/
├── SKILL.md                         # Hermes Skill 主指南
├── scripts/
│   ├── stock_debate.py             # 主流程（一行命令全流程）
│   ├── data_fetch.py               # 数据采集（行情/财报/产业链）
│   ├── validation.py               # 交叉验证 + 角色过滤
│   ├── common.py                   # 公共模块（日志/配置/LLM调用）
│   ├── demo.py                     # LLM 辩论引擎入口
│   ├── engine.py                   # 核心辩论编排
│   ├── roles.py                    # 6 大流派角色定义
│   ├── html_report.py              # HTML 报告渲染
├── tests/                          # 单元测试（本地保留，不推送）
├── references/
│   ├── methodologies/               # 6 大投资方法论完整原文
│   │   ├── graham-methodology.md
│   │   ├── buffett-methodology.md
│   │   ├── fisher-methodology.md
│   │   ├── benjiu-methodology.md
│   │   ├── luohuitou-methodology.md
│   │   ├── shiji-methodology.md
└── demos/                           # HTML 报告示例
    ├── 中际旭创_圆桌辩论报告.html
    └── 九丰能源_圆桌辩论报告.html
```

---

## 🔍 数据校验

每次分析自动进行三方交叉验证：

| 检查项 | 数据源 | 阈值 |
|--------|--------|------|
| PE(TTM) | 腾讯 vs 东方财富 f164（TTM 口径） | 偏差 >10% 报错，>5% 警告 |
| PE(静态) | 东方财富 f163 | HTML 快照参考显示 |
| 总市值 | 腾讯 vs 东方财富 | 偏差 >10% 报错，>5% 警告 |
| 52 周高低 | 前复权 K 线修正 | 避免除权失真；K 线 API 不可用时 fallback 含除权风险 |
| 送转股 | AKShare 除权记录 | EPS/BPS/OCF 自动修正 |
| 产业链格局 | v4-pro 自动生成 | 供给瓶颈/需求爆发/低估点 |

---

## 🧠 智能角色过滤

并非所有流派都适用于每支股票。系统会根据数据特征自动跳过不适用的角色：

| 条件 | 跳过角色 | 原因 |
|------|---------|------|
| PE > 50 或 营收 < 50 亿 | 📐 格雷厄姆 | 7 条量化硬标准必挂 |
| PE > 50 | 🐢 龟龟 | 穿透回报率无意义 |
| 营收增速 >30% 且 毛利率 >50% | 📐 格雷厄姆 + 🐢 龟龟 | 高增长股不适用防御型策略 |

跳过的角色以琥珀色标注在 HTML 报告结论卡中。

---

## ⚙️ 平台支持

| 平台 | 状态 |
|------|------|
| macOS | ✅ 主力开发环境 |
| Linux | ✅ 已验证 |
| Windows | ⚠️ 未测试 |

---

<p align="center">
  <sub>
    ⚠️ 报告由 AI 自动生成，仅供参考，不构成投资建议。<br>
    ⚠️ <em>AI-generated reports for reference only. Not investment advice.</em>
  </sub>
</p>
