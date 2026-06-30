# 数据采集工具包

从雪球/B站等平台采集投资分析师的原始发言数据，用于后续方法论蒸馏。

---

## 工具清单

| 脚本 | 用途 | 源平台 | 依赖 |
|------|------|--------|------|
| `xueqiu-scraper.py` | 采集雪球用户所有帖子 | 雪球 | Playwright + Chromium |
| `bilibili-asr.py` | 下载B站视频音频并转文字 | B站 | curl_cffi + faster-whisper + ffmpeg |

---

## 快速开始

### 环境准备

```bash
# 雪球采集依赖
pip install playwright
playwright install chromium

# B站采集依赖
pip install faster-whisper curl_cffi
# ffmpeg 系统自带

# 国内用户必设（HuggingFace 模型下载）
export HF_ENDPOINT=https://hf-mirror.com
```

### 采集雪球帖子

```bash
# 基本用法（莫大用户ID）
python3 xueqiu-scraper.py <雪球用户ID>

# 带参数
python3 xueqiu-scraper.py <用户ID> \
  --max-pages 100 \
  --out output.json \
  --extract-text

# 调试模式（看浏览器）
python3 xueqiu-scraper.py <用户ID> --no-headless
```

**获取用户ID**：打开雪球用户主页，URL中的数字
- 例：`https://xueqiu.com/u/4244594694` → ID为 `4244594694`

**首次使用**需要手动在弹出浏览器中登录雪球（支持手机号/微信/微博），登录态会保存到 `~/.xueqiu-scraper-profile/`，后续自动复用。

**原理**：雪球 API 有阿里云 WAF 保护（md5 token 绑定 session），直接 HTTP 请求会被 403。本脚本使用真实浏览器拦截页面自动发出的 API 响应，避开 WAF。

### 采集B站视频字幕/音频

```bash
# 基本用法
python3 bilibili-asr.py <BVID或B站链接>

# 高质量模式（更准但更慢）
python3 bilibili-asr.py <BVID> --model base

# 示例
python3 bilibili-asr.py BV1xx411c7mD
```

**原理**：优先尝试 CC 字幕 → 无字幕时下载音频流 → faster-whisper ASR 转写。输出带时间戳的纯文本文件。

**注意事项**：
- B站 API 需 `curl_cffi` + `impersonate=chrome131` 绕过 WAF
- `playurl`（旧版API）比 `player/wbi/v2`（新版）更稳定返回音频
- 音频下载内置超时退避（120s→600s）+ curl 续传兜底
- 默认 tiny 模型（快），追求质量用 `--model base`

---

## 输出格式

### 雪球

采集后得到两类文件：

- `*.json` — 原始 API 响应（含所有元数据）
- `*.txt` — 纯文本提取（`--extract-text`，过滤短回复/去HTML）

```
--- 2025-03-15 14:30 (转发:128 回复:45 赞:952) ---
这篇文章讲的是铜矿供给的逻辑...

--- 2025-03-12 09:15 (转发:67 回复:23 赞:431) ---
预期差的本质不是"跌多了"，而是市场对某个事实的定价不足...
```

### B站

输出文件：`/tmp/bilibili-summary/{BVID}.txt`

```
【视频标题】某某赛道还能不能买？
【UP主】笨笨的韭菜 | 时长: 22:15
【转写方式】faster-whisper tiny
============================================================

[0.0s-5.2s] 今天跟大家聊一下白酒行业的最新情况
[5.2s-12.8s] 首先看产量数据，2024年全国白酒产量继续下滑...
```

---

## 与其他模块的关系

```
data-collection/          ← 当前工具包（采集原始数据）
    ↓
方法论蒸馏                 ← investment-methodology-distillation
    ↓
methodology/*.md          ← 方法论 SKILL 文件（评分框架）
    ↓
stock-analysis            ← 六框架联合分析引擎
```

采集到的帖子/字幕数据 → 用 AI 蒸馏出投资框架 → 生成可复用的方法论 Skill → 喂给分析引擎打分。

---

## 已知限制

- 雪球：阿里云 WAF 不定期更新规则，需更新 Playwright 版本。翻页加载依赖无限滚动触发，大帖子量（1000+）可能需要多次运行
- B站：绝大多数视频无 CC 字幕（API 不返回 AI 字幕），必须走 ASR。tiny 模型约 1:10 实时比（20 分钟视频 ≈ 3 分钟处理）
- 两个工具均需国内网络环境访问源站
