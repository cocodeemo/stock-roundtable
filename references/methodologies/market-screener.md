---
name: market-screener
version: 1.0.0
description: >
  三框架量化选股器。从全市场按格雷厄姆、史诗级韭菜、巴菲特的量化标准
  自动筛选候选池。需配合 akshare 使用。
metadata:
  hermes:
    tags: [stock-screener, quantitative, multi-framework]
    dependencies: [akshare, pandas]
trigger_keywords:
  - 选股
  - 筛选
  - 池子
  - 候选
  - 全市场
---

# 三框架量化选股器

三个可量化的框架合并成一个筛选脚本。数据来源：akshare（A股全市场日频更新）。

---

## 框架一：格雷厄姆防御型

| 标准 | 阈值 |
|---|---|
| PE（TTM） | ≤ 15 |
| PB | ≤ 1.5 |
| PE × PB | ≤ 22.5 |
| 市值 | ≥ 50 亿 |
| 排除 | 银行、保险、ST、退市 |

**适合找**：极度便宜、有安全边际的股票。

---

## 框架二：史诗级韭菜（真资产+高分红）

| 标准 | 阈值 |
|---|---|
| 股息率 | ≥ 3% |
| PE | ≤ 25 |
| 市值 | ≥ 50 亿 |
| 自由现金流 | 正（排除烧钱企业） |

**适合找**：给你持续吐钱的「真资产」。

---

## 框架三：巴菲特（护城河+安全边际）

| 标准 | 阈值 |
|---|---|
| ROE | ≥ 15%（5年均值更好） |
| PE | ≤ 25 |
| 资产负债率 | ≤ 50%（低杠杆） |
| 市值 | ≥ 100 亿 |

**适合找**：有护城河、管理层靠谱的优质企业。

---

## 使用方式

```bash
pip3 install akshare pandas
python3 market_screener.py
```

输出三个候选池，分别标注通过哪个框架。同一只股票通过多个框架 = 高共识度。

---

## 融合评分

如果一只股票同时通过多个框架，合并打分：

| 通过框架数 | 共识度 |
|---|---|
| 3 个全过 | 🔥🔥🔥 三代宗师共识 |
| 2 个 | ✅✅ 双框架认可 |
| 1 个 | ⚠️ 单一框架 |

---

## 脚本

```python
# market_screener.py — 三框架选股器
import akshare as ak
import pandas as pd

df = ak.stock_a_indicator_lg()

# 预处理
df = df[df['pe'] > 0]
df = df[~df['name'].str.contains('银行|保险|太保|ST|退市|农商')]
df['pe_x_pb'] = df['pe'] * df['pb']

# 框架一：格雷厄姆
g = df[(df['pe'] <= 15) & (df['pb'] <= 1.5) & (df['pe_x_pb'] <= 22.5)]
g['graham'] = True

# 框架二：史诗韭菜
s = df[(df['dividend_yield'] >= 3.0) & (df['pe'] <= 25)]
s['shiji'] = True

# 框架三：巴菲特
b = df[(df['roe'] >= 15) & (df['pe'] <= 25) & (df['debt_to_equity'] <= 0.5)]
b['buffett'] = True

# 合并输出
merged = df.copy()
merged['graham'] = merged.index.isin(g.index)
merged['shiji'] = merged.index.isin(s.index)
merged['buffett'] = merged.index.isin(b.index)
merged['score'] = merged[['graham','shiji','buffett']].sum(axis=1)

# 按共识度排序输出
result = merged[merged['score'] >= 1][['code','name','pe','pb','dividend_yield','roe','score']]
result = result.sort_values('score', ascending=False)

print("=== 三框架共识 ===")
print(f"🔥🔥🔥 三框架全过: {len(result[result['score']==3])} 只")
print(f"✅✅ 双框架: {len(result[result['score']==2])} 只")
print(f"⚠️ 单一框架: {len(result[result['score']==1])} 只")

print("\n--- 三框架全过 ---")
print(result[result['score']==3].to_string())

print("\n--- 双框架 ---")
print(result[result['score']==2].head(20).to_string())
```
