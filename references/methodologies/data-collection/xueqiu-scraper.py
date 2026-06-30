#!/usr/bin/env python3
"""
雪球用户帖子采集器

通过 Playwright 拦截雪球 API 响应来采集指定用户的所有帖子，
避开阿里云 WAF 对直接 API 调用的拦截。

用法:
    python3 xueqiu-scraper.py <user_id> [--max-pages N] [--out FILE]

示例:
    python3 xueqiu-scraper.py 1234567890 --max-pages 100 --out luohuitou_posts.json

依赖:
    pip install playwright
    playwright install chromium

原理:
    雪球对 API 调用有阿里云 WAF 保护（md5 token 绑定 session）。
    直接 curl/requests 会被 403。本脚本用真实浏览器（Playwright Chromium）
    访问雪球用户主页，拦截页面自动发出的 API 请求的响应，从中提取帖子数据。

    首次运行需要手动登录雪球获取 cookie（脚本会自动保存到 Chrome profile）。
    后续运行复用登录态，无需重复登录。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ============================================================
# 配置
# ============================================================

PROFILE_DIR = Path.home() / ".xueqiu-scraper-profile"
OUT_DIR = Path.home() / ".xueqiu-scraper-output"
INTERCEPT_PATTERN = "**/v4/statuses/user_timeline.json*"

# ============================================================
# 核心逻辑
# ============================================================

def install_playwright_browser():
    """确保 Chromium 已安装"""
    import subprocess
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch()
        return True
    except Exception:
        print("[setup] 安装 Chromium (仅首次)...")
        subprocess.run(["playwright", "install", "chromium"], check=True)
        return True


def scrape_user_timeline(
    user_id: str,
    max_pages: int = 100,
    out_file: Optional[str] = None,
    headless: bool = True,
):
    """
    采集指定雪球用户的所有帖子。

    Args:
        user_id: 雪球用户 ID（数字字符串）
        max_pages: 最大翻页数
        out_file: 输出文件路径（默认: ~/.xueqiu-scraper-output/{user_id}.json）
        headless: 是否无头模式（默认 True）
    """
    from playwright.sync_api import sync_playwright

    if out_file is None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_file = str(OUT_DIR / f"{user_id}.json")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    all_statuses = []
    intercepted_pages = 0
    should_stop = False

    with sync_playwright() as p:
        print(f"[launch] 启动 Chromium (headless={headless})...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        # ---- 拦截 API 响应 ----
        def handle_response(response):
            nonlocal intercepted_pages, should_stop
            if INTERCEPT_PATTERN.replace("**", "") in response.url:
                try:
                    data = response.json()
                    statuses = data.get("list", []) or data.get("statuses", [])
                    if statuses:
                        intercepted_pages += 1
                        print(f"[page {intercepted_pages}] 截获 {len(statuses)} 条帖子", end="")
                        # 去重添加
                        existing_ids = {s["id"] for s in all_statuses}
                        new_count = 0
                        for s in statuses:
                            if s["id"] not in existing_ids:
                                all_statuses.append(s)
                                new_count += 1
                        print(f" → 新增 {new_count} 条 (累计 {len(all_statuses)})")

                        if new_count == 0:
                            print("[stop] 无新数据，停止翻页")
                            should_stop = True

                        if intercepted_pages >= max_pages:
                            print(f"[stop] 达到最大页数 {max_pages}")
                            should_stop = True
                except Exception as e:
                    print(f"[warn] 解析响应失败: {e}")

        page.on("response", handle_response)

        # ---- 打开用户主页 ----
        target_url = f"https://xueqiu.com/u/{user_id}"
        print(f"[navigate] 打开 {target_url}")
        page.goto(target_url, wait_until="networkidle", timeout=30000)

        # ---- 检查是否需要登录 ----
        if "login" in page.url or " Login " in page.content():
            print("\n⚠️  需要登录雪球账号！")
            print("   请在浏览器中完成登录（手机号/微信/微博均可）")
            print("   登录成功后脚本会自动继续...")
            page.wait_for_url(f"**/u/{user_id}**", timeout=120000)
            print("[auth] 登录成功！")

        # ---- 等待帖子列表加载 ----
        time.sleep(3)

        # ---- 自动翻页 ----
        print("[scroll] 开始滚动加载...")
        last_height = 0
        timeout_start = time.time()

        while not should_stop:
            # 滚动到底部
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

            # 检查是否到底
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                # 再等一等，可能还在加载
                time.sleep(2)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("[stop] 页面已到底")
                    break
            last_height = new_height

            # 超时保护（30分钟）
            if time.time() - timeout_start > 1800:
                print("[stop] 超时（30分钟）")
                break

        context.close()

    # ---- 保存结果 ----
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_statuses, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共采集 {len(all_statuses)} 条帖子")
    print(f"   输出文件: {out_file}")

    # ---- 统计摘要 ----
    if all_statuses:
        dates = [s.get("created_at", 0) for s in all_statuses if s.get("created_at")]
        if dates:
            from datetime import datetime
            earliest = datetime.fromtimestamp(min(dates) / 1000).strftime("%Y-%m-%d")
            latest = datetime.fromtimestamp(max(dates) / 1000).strftime("%Y-%m-%d")
            print(f"   时间范围: {earliest} ~ {latest}")

        # 按类型统计
        types = {}
        for s in all_statuses:
            t = s.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        print(f"   帖子类型: {types}")

        # 总字符数
        total_chars = sum(
            len(s.get("title", "") or "") + len(s.get("description", "") or "") + len(s.get("text", "") or "")
            for s in all_statuses
        )
        print(f"   总字符数: {total_chars:,}")

    return all_statuses


def extract_text_posts(statuses: list, min_chars: int = 50) -> list:
    """
    从原始 JSON 中提取纯文本帖子，过滤短回复。

    Args:
        statuses: scrape_user_timeline 返回的原始数据
        min_chars: 最小字符数，低于此值的短帖被过滤

    Returns:
        列表，每项为 {"id": ..., "created_at": ..., "text": ..., "retweet_count": ..., "reply_count": ...}
    """
    from datetime import datetime

    results = []
    for s in statuses:
        # 提取文本
        text = (s.get("title") or "") + "\n" + (s.get("description") or "") + "\n" + (s.get("text") or "")
        text = text.strip()

        # 去除 HTML 标签
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < min_chars:
            continue

        ts = s.get("created_at", 0)
        if ts > 1e12:  # 毫秒
            ts = ts / 1000

        results.append({
            "id": s["id"],
            "created_at": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "unknown",
            "text": text,
            "retweet_count": s.get("retweet_count", 0),
            "reply_count": s.get("reply_count", 0),
            "like_count": s.get("like_count", 0),
            "type": s.get("type", ""),
        })

    return results


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="雪球用户帖子采集器 (Playwright intercept 模式)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 采集莫大（罗洄头）的所有帖子
  python3 xueqiu-scraper.py 4244594694 --max-pages 100 --out luohuitou.json

  # 采集后提取纯文本
  python3 xueqiu-scraper.py 4244594694 --max-pages 100 --extract-text

  # 非无头模式（调试用，能看到浏览器）
  python3 xueqiu-scraper.py 4244594694 --no-headless

寻找用户 ID:
  打开雪球用户主页，URL 中的数字就是 user_id。
  例如: https://xueqiu.com/u/4244594694 → user_id = 4244594694
        """,
    )
    parser.add_argument("user_id", help="雪球用户 ID（数字）")
    parser.add_argument("--max-pages", type=int, default=100, help="最大翻页数 (默认: 100)")
    parser.add_argument("--out", dest="out_file", help="输出 JSON 文件路径")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（调试用）")
    parser.add_argument("--extract-text", action="store_true", help="额外输出纯文本版本 (*.txt)")
    parser.add_argument("--min-chars", type=int, default=50, help="文本提取的最小字符数 (默认: 50)")

    args = parser.parse_args()

    # 安装检查
    install_playwright_browser()

    # 采集
    statuses = scrape_user_timeline(
        user_id=args.user_id,
        max_pages=args.max_pages,
        out_file=args.out_file,
        headless=not args.no_headless,
    )

    # 提取纯文本
    if args.extract_text and statuses:
        texts = extract_text_posts(statuses, min_chars=args.min_chars)
        txt_path = (args.out_file or str(OUT_DIR / f"{args.user_id}.json")).replace(".json", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for t in texts:
                f.write(f"--- {t['created_at']} (转发:{t['retweet_count']} 回复:{t['reply_count']} 赞:{t['like_count']}) ---\n")
                f.write(t["text"] + "\n\n")
        print(f"   纯文本: {txt_path} ({len(texts)} 条, 过滤掉了 {len(statuses) - len(texts)} 条短帖)")


if __name__ == "__main__":
    main()
