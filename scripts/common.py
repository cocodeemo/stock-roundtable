"""
共享模块：LLM 调用、参数解析、配置读取、日志、重试
——供 stock_debate.py 和 demo.py 共用，消除重复代码
"""

import sys
import os
import json
import re
import time
import logging
import urllib.request
import urllib.error


# ── 日志 ──

def setup_logging(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """统一日志配置：INFO 级别、带时间戳、模块名"""
    logger = logging.getLogger(name or __name__)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger

# 模块级 logger，其他模块可 import 使用
log = setup_logging("stock_roundtable")

# ── 默认 API 配置（全局唯一入口，避免散落硬编码）──
DEFAULT_API_BASE = "https://taotoken.net/api/v1"
DEFAULT_MODEL = "deepseek-v4-pro"


# ── 重试 ──

def retry_call(
    fn,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    logger: logging.Logger = None,
    **kwargs,
):
    """
    指数退避重试封装。
    fn: 可调用对象
    max_retries: 最多重试次数（含首次，共 max_retries+1 次）
    base_delay: 首次重试等待秒数
    backoff: 退避倍数
    """
    _log = logger or log
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (backoff ** attempt)
                _log.warning("第 %d 次调用失败: %s，%.1fs 后重试...", attempt + 1, e, delay)
                time.sleep(delay)
            else:
                _log.error("已重试 %d 次，最终失败: %s", max_retries, e)
    raise last_error


# ── LLM 调用 ──

def call_llm(
    system_prompt: str,
    user_prompt: str,
    api_key: str = None,
    api_base: str = None,
    model: str = "deepseek-v4-pro",
    temperature: float = 0.7,
    max_tokens: int = 6000,
    timeout: int = 180,
    retries: int = 3,
) -> str:
    """调用 OpenAI 兼容 API，返回纯文本响应（支持重试）"""
    api_key = api_key or os.environ.get(
        "TAOTOKEN_API_KEY", os.environ.get("OPENAI_API_KEY", "")
    )
    if not api_key:
        raise RuntimeError("请设置 TAOTOKEN_API_KEY 环境变量或传入 api_key 参数")
    api_base = api_base or os.environ.get(
        "TAOTOKEN_API_BASE", DEFAULT_API_BASE
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    def _do_call():
        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    try:
        return retry_call(_do_call, max_retries=retries, base_delay=1.0, backoff=2.0)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 错误 {e.code}: {body[:500]}")
    except Exception as e:
        raise RuntimeError(f"调用失败: {e}")


# ── 参数解析 ──

def parse_debate_args(argv: list = None) -> dict:
    """解析通用辩论参数：--rounds, --model, --roles, 剩余为 question"""
    if argv is None:
        argv = list(sys.argv[1:])

    result = {"question": "", "roles": None, "model": None, "rounds": 2}
    parts = []
    i = 0
    while i < len(argv):
        if argv[i] == "--roles" and i + 1 < len(argv):
            result["roles"] = argv[i + 1].split(",")
            i += 2
        elif argv[i] == "--model" and i + 1 < len(argv):
            result["model"] = argv[i + 1]
            i += 2
        elif argv[i] == "--rounds" and i + 1 < len(argv):
            try:
                r = int(argv[i + 1])
                if r < 1:
                    r = 1
                elif r > 3:
                    r = 3
                result["rounds"] = r
            except ValueError:
                pass
            i += 2
        else:
            parts.append(argv[i])
            i += 1

    result["question"] = " ".join(parts)
    return result


# ── 配置读取 ──

def load_hermes_config(config_path: str = None) -> dict:
    """
    从 ~/.hermes/config.yaml 读取 API key 和 base_url。
    优先使用 yaml.safe_load，失败时回退到正则解析。
    返回 {"api_key": str, "api_base": str or None}
    """
    if config_path is None:
        config_path = os.path.expanduser("~/.hermes/config.yaml")

    cfg = {}
    result = {"api_key": "", "api_base": None}

    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    # ── 提取 api_key ──
    if cfg:
        for key in ["api_key", "key", "token"]:
            if key in cfg and cfg[key]:
                result["api_key"] = str(cfg[key])
                break
        if not result["api_key"]:
            for section in ["providers", "custom_providers"]:
                if section in cfg:
                    items = cfg[section]
                    if isinstance(items, dict):
                        items = items.values()
                    for p in items:
                        if isinstance(p, dict) and p.get("api_key"):
                            result["api_key"] = str(p["api_key"])
                            break
                if result["api_key"]:
                    break
        if not result["api_key"] and "delegation" in cfg:
            dk = cfg.get("delegation", {})
            if isinstance(dk, dict) and dk.get("api_key"):
                result["api_key"] = str(dk["api_key"])

    # fallback 到正则（纯文本解析，不依赖 yaml）
    if not result["api_key"]:
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = f.read()
            # 匹配 api_key: <value>，value 不包含空白和引号
            m = re.search(r'api_key\s*:\s*["\']?(\S+)["\']?', raw)
            if m:
                result["api_key"] = m.group(1).strip()
        except Exception:
            pass

    # ── 提取 api_base ──
    if isinstance(cfg, dict):
        for key in ["api_base", "base_url"]:
            if key in cfg and cfg[key]:
                result["api_base"] = str(cfg[key])
                break
        if not result["api_base"]:
            for section in ["custom_providers", "providers"]:
                if section in cfg:
                    items = cfg[section]
                    if isinstance(items, dict):
                        items = items.values()
                    for p in items:
                        if isinstance(p, dict) and p.get("base_url"):
                            result["api_base"] = str(p["base_url"])
                            break
                if result["api_base"]:
                    break

    return result
