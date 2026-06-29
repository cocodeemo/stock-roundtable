# Stock Analysis Skills

六个投资方法论 + 一个主控 Skill，全部百分制，可交叉对比。

## 结构

```
stock-analysis.md          ← 主控：说「分析 XX」自动跑六框架
├── graham-methodology.md  ← 格雷厄姆：防御型价值。7条硬标准（PE≤15, PB≤1.5）
├── fisher-methodology.md  ← 费雪：成长股投资。管理层+成长空间+竞争优势
├── buffett-methodology.md ← 巴菲特：伟大企业。护城河+伊索三问+安全边际
├── luohuitou-methodology.md ← 莫大：物理瓶颈。矿权/牌照/进口资质/技术壁垒
├── benjiu-methodology.md  ← 笨韭：景气投机。现象级事件→行业拐点
└── shiji-methodology.md   ← 史诗级韭菜：古典价值。穿透回报率+真资产
```

## 投资光谱

```
便宜就行 ←——————————————————→ 成长潜力
格雷厄姆   史诗韭菜   巴菲特   费雪    笨韭
(PE/PB)  (穿透回报) (护城河) (管理层) (景气)

莫大 —— 独立于光谱之外，只买物理瓶颈
```

## 框架速查

| 框架 | 核心问题 | 一票否决项 | 来源 |
|---|---|---|---|
| 格雷厄姆 | 便宜吗？安全吗？ | PE>15 / PE×PB>22.5 | 聪明的投资者 |
| 费雪 | 管理层靠谱吗？成长多大？ | 管理层诚信有问题 | 怎样选择成长股 |
| 巴菲特 | 护城河够宽吗？价格合理？ | 用杠杆 / 看不懂 | 20个Skill合集 |
| 史诗级韭菜 | 公司给我发多少钱？ | 不产生正自由现金流 | 12集B站字幕 |
| 笨韭 | 现象级事件在哪？ | 单边下跌无催化剂 | 92集B站字幕 |
| 莫大 | 物理上绕得开吗？ | 品牌/渠道型壁垒 | 1996篇雪球帖 |

## 安装

```bash
git clone https://github.com/cocodeemo/stock-analysis-skills.git
cp *.md ~/.hermes/skills/finance/
```

## 用法

加载 `stock-analysis` skill 后，说「分析 贵州茅台」自动跑六个框架输出对比。
