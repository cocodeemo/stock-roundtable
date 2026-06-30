# Changelog

## v1.9.5 (2026-06-30) — 代码审查修复（5项）

- 🔴 交易所识别逻辑修复：`fetch_stock_quote()` 中 6-digit 深市代码正确识为 sz
- 🔴 `cfg` 作用域修复：`main()` 中 `try` 前初始化 `cfg=None`
- 🟠 `_parse()` NaN 处理：`math.isnan()` 检测
- 🟠 Google Fonts CDN 离线回退
- 🟡 LLM 输出 HTML 转义：`html.escape()` 防 XSS

## v1.9.4 (2026-06-29) — 代码审查修复（6项）

- 🔴 `cross_validate()` 残留 `pe_calc` 引用 → NameError 修复
- 🔴 `engine.py to_dict()` 丢失 emoji 字段 → voice card 修复
- 🔴 `filter_roles()` 真正返回 (roles, skipped) 元组 → HTML 琥珀色提示
- 🟠 `is_growth` 死代码激活 → 高增长股自动跳过格雷厄姆+龟龟
- 🟠 `fetch_industry_context()` + `demo.py` base_url 真正从 config.yaml 读取
- 🟡 `demo.py` ROLES 导入移至模块顶层

## v1.9.3 (2026-06-29) — macOS 兼容 + 数据校验收紧 + 仓库合并

- WSL 路径硬编码移除 → macOS/Linux/WSL 全兼容
- HTML 报告输出到 ~/Desktop/
- PE 交叉验证收紧：仅对比腾讯 vs 东财 TTM PE
- 阈值收紧：PE/市值偏差 >5% 警告，>10% 报错
- 合并 `cocodeemo/stock-analysis-skills` → `references/methodologies/`
- `.gitignore` 排除运行时产物

## v1.9.2 (2026-06-29) — 代码审查修复 + HTML 报告增强（9项）

- `filter_roles()` 死代码修复
- `fetch_industry_context()` 不再硬编码 URL → 从 config.yaml 读取
- `stock_debate.py` 新增 `--model` 参数
- `select_roles()` max_roles 5→6
- 重复 import 清理
- rounds 越界修正提示
- SKILL.md frontmatter 清理
- skill_view name 引用修正
- HTML 报告新增「自动跳过的角色」区块

## v1.9.1 (2026-06-29) — 数据三方交叉验证

- 新增 EastMoney API 作为第三数据源（PE、市值）
- `cross_validate()` 三源 PE 对比，偏差 >15% 报警
- 市值腾讯 vs 东财，偏差 >10% 报警

## v1.9.0 (2026-06-29) — 莫大角色重写 (v3.2)

- 新增「核心信念」段落
- 预期差重定义为"市场错判公司本质"
- 供给弹性新增"认证型壁垒"档
- 股价位置拆为空仓/已持有双情境
- 周期位置拆为产业链供给周期+企业盈利周期
- 打分铁律放宽为"可从公开事实推断"

## v1.8.0 (2026-06-29) — 产业链格局注入

- `build_question()` 前用 v4-pro 生成行业背景
- 解决「财务数据单维度绑架评分」问题

## v1.7.1 (2026-06-29) — 通用三情境

- 辩论问题从「是否值得持有」→「当前投资价值如何评估」
- 三个情境 + 动态关注点
- CSS tuple bug 修复

## v1.7.0 (2026-06-29) — 基础升级

- 模型升级为 deepseek-v4-pro，max_tokens 6000
- 支持 --model / --rounds
- 移除硬编码背景，动态获取公司信息
- 港股支持，API key yaml.safe_load
- HTML 共识展示、暗色模式、数据校验警告
