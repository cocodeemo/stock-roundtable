#!/usr/bin/env python3
"""
B站视频 AI 总结 — 完整 ASR 链路（自动超时重试 + 进度可见）

用法: python3 bilibili-ai-summary.py <BVID或B站链接> [--model tiny|base]
默认: tiny（快），追求质量用 --model base

依赖: pip install faster-whisper curl_cffi
      ffmpeg 系统自带
      国内需设 HF_ENDPOINT=https://hf-mirror.com
"""
import os, sys, re, hashlib, time, json, subprocess

# === 关键：进度输出到 stderr（永远无缓冲，后台也可见）===
# stdout 保留给最终数据输出，stderr 用于进度日志
# 这样无论是否 python -u / PYTHONUNBUFFERED，进度都实时可见

# 国内用户必设 HF 镜像
if 'HF_ENDPOINT' not in os.environ:
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from curl_cffi import requests

# ============================================================
# 工具函数
# ============================================================

def log(msg: str) -> None:
    """带时间戳的进度输出 → stderr（无缓冲，后台实时可见）"""
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr, flush=True)

def extract_bvid(url_or_bvid: str) -> str:
    m = re.search(r'(BV[a-zA-Z0-9]{10})', url_or_bvid)
    if not m:
        raise ValueError(f"无法提取 BVID: {url_or_bvid}")
    return m.group(1)

def download_with_retry(session, url: str, out_path: str,
                         short_timeout: int = 120,
                         long_timeout: int = 600) -> bool:
    """
    下载文件，先短超时尝试，失败自动切长超时。
    如果两次 curl_cffi 都失败，保留部分下载的文件供 curl -C 续传。
    返回 True/False。
    """
    headers = {'Referer': 'https://www.bilibili.com/',
               'Origin': 'https://www.bilibili.com'}

    for attempt, timeout in enumerate([short_timeout, long_timeout], 1):
        try:
            log(f"  下载尝试 {attempt}/2 (timeout={timeout}s)...")
            resp = session.get(url, headers=headers,
                              impersonate='chrome131', timeout=timeout)
            with open(out_path, 'wb') as f:
                f.write(resp.content)
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            log(f"  下载完成: {size_mb:.1f} MB")
            return True
        except Exception as e:
            partial = os.path.exists(out_path) and os.path.getsize(out_path)
            partial_str = f" (已收 {partial/1024:.0f}KB)" if partial else ""
            log(f"  尝试 {attempt} 失败: {type(e).__name__}{partial_str}")
            if attempt == 1:
                log(f"  切换到长超时 ({long_timeout}s) 重试...")
            else:
                log(f"  curl_cffi 两次均失败，将用 curl -C 续传")
    return False

# ============================================================
# 核心流程
# ============================================================

def get_audio_url(bvid: str) -> tuple:
    """返回 (session, audio_url, title, duration_sec, cid)"""
    session = requests.Session()

    # 1. 获取视频信息 + cid
    log("步骤1/5: 获取视频元数据...")
    resp = session.get(
        f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
        headers={'Referer': 'https://www.bilibili.com/'},
        impersonate='chrome131', timeout=15
    )
    data = resp.json()['data']
    title = data['title']
    duration = data['duration']
    cid = data['cid']
    log(f"  标题: {title}")
    log(f"  UP主: {data['owner']['name']} | 时长: {duration//60}:{duration%60:02d} | cid={cid}")

    # 2. WBI 签名密钥
    log("步骤2/5: 获取 WBI 签名密钥...")
    resp = session.get('https://api.bilibili.com/x/web-interface/nav',
                       impersonate='chrome131', timeout=10)
    wbi = resp.json()['data']['wbi_img']
    img_key = wbi['img_url'].split('/')[-1].split('.')[0]
    sub_key = wbi['sub_url'].split('/')[-1].split('.')[0]
    mixin = (img_key + sub_key)[:32]
    log(f"  mixin: {mixin[:8]}...")

    # 3. 获取音频流 (playurl 旧版 API)
    log("步骤3/5: 获取音频流 URL...")
    wts = int(time.time())
    to_sign = f'bvid={bvid}&cid={cid}&qn=0&fnver=0&fnval=4048&wts={wts}{mixin}'
    w_rid = hashlib.md5(to_sign.encode()).hexdigest()

    resp = session.get(
        f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}'
        f'&qn=0&fnver=0&fnval=4048&wts={wts}&w_rid={w_rid}',
        headers={'Referer': f'https://www.bilibili.com/video/{bvid}/'},
        impersonate='chrome131', timeout=15
    )
    dash = resp.json()['data'].get('dash', {})
    audio_list = dash.get('audio', [])

    if not audio_list:
        # fallback: 不带 WBI 签名
        log("  WBI 签名无音频，尝试 fallback...")
        resp2 = requests.get(
            f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}'
            f'&qn=0&fnver=0&fnval=16',
            headers={'Referer': f'https://www.bilibili.com/video/{bvid}/'},
            impersonate='chrome131', timeout=15
        )
        audio_list = resp2.json()['data'].get('dash', {}).get('audio', [])

    if not audio_list:
        raise RuntimeError("无法获取音频流——该视频可能无音频或需会员")

    best = sorted(audio_list, key=lambda a: a.get('bandwidth', 0), reverse=True)[0]
    log(f"  音频码率: {best.get('bandwidth', 0)//1000}kbps")
    return session, best['baseUrl'], title, duration, cid

def download_and_convert(session, audio_url: str, bvid: str) -> str:
    """下载音频 → 转 WAV，返回 WAV 路径"""
    out_dir = '/tmp/bilibili-summary'
    os.makedirs(out_dir, exist_ok=True)
    m4s_path = f'{out_dir}/{bvid}.m4s'
    wav_path = f'{out_dir}/{bvid}.wav'

    # 下载（带自动超时重试）
    log("步骤4/5: 下载音频（自动超时重试）...")
    if not download_with_retry(session, audio_url, m4s_path):
        # 最后的兜底：curl 原生下载 + 断点续传
        log("  curl_cffi 失败，尝试 curl -C 续传（最多 900s）...")
        rc = os.system(
            f'curl -L -C - --max-time 900 --retry 3 --retry-delay 5 '
            f'-H "Referer: https://www.bilibili.com/" '
            f'-H "Origin: https://www.bilibili.com" '
            f'-o "{m4s_path}" "{audio_url}" 2>/dev/null'
        )
        if rc != 0 or not os.path.exists(m4s_path) or os.path.getsize(m4s_path) < 1000:
            raise RuntimeError("音频下载失败，所有重试均已耗尽")

    # 转 WAV
    log("  转 WAV (16kHz mono)...")
    subprocess.run([
        'ffmpeg', '-y', '-i', m4s_path,
        '-ar', '16000', '-ac', '1', '-f', 'wav', wav_path
    ], capture_output=True, check=True, timeout=60)
    wav_mb = os.path.getsize(wav_path) / (1024 * 1024)
    log(f"  WAV 完成: {wav_mb:.1f} MB")

    # 清理 m4s
    os.remove(m4s_path)
    return wav_path

def transcribe_audio(wav_path: str, model_size: str = 'tiny') -> str:
    """faster-whisper 转写"""
    from faster_whisper import WhisperModel

    log(f"步骤5/5: ASR 转写 (faster-whisper {model_size})...")
    if model_size == 'tiny':
        log("  (tiny 模型，约 1:10 实时比，请耐心等待)")
    else:
        log("  (base 模型，约 1:4 实时比，请耐心等待)")

    model = WhisperModel(model_size, device='cpu', compute_type='int8')
    start = time.time()
    segments, info = model.transcribe(
        wav_path, language='zh', vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    log(f"  检测语言: {info.language} (置信度: {info.language_probability:.2f})")

    lines = []
    last_report = 0
    for seg in segments:
        lines.append(f"[{seg.start:.1f}s-{seg.end:.1f}s] {seg.text.strip()}")
        # 每 30 秒报告一次进度
        now = time.time()
        if now - last_report > 30:
            log(f"  进度: {seg.start:.0f}s / ... ({len(lines)} 段)")
            last_report = now

    full_text = '\n'.join(lines)
    elapsed = time.time() - start
    log(f"  转写完成: {len(lines)} 段, {len(full_text)} 字符, 耗时 {elapsed:.0f}s "
        f"(实时比 1:{elapsed/max(seg.end,1):.0f})")

    # 清理 WAV
    os.remove(wav_path)
    return full_text

# ============================================================
# 入口
# ============================================================

def main():
    model_size = 'tiny'
    args = [a for a in sys.argv[1:] if not a.startswith('--model')]
    for a in sys.argv[1:]:
        if a.startswith('--model'):
            model_size = a.split('=', 1)[1] if '=' in a else sys.argv[sys.argv.index(a)+1]

    if len(args) < 1:
        print("用法: python3 bilibili-ai-summary.py <BVID或B站链接> [--model tiny|base]")
        sys.exit(1)

    bvid = extract_bvid(args[0])
    out_dir = '/tmp/bilibili-summary'
    out_path = f'{out_dir}/{bvid}.txt'
    os.makedirs(out_dir, exist_ok=True)

    try:
        # 获取音频流
        session, audio_url, title, duration, cid = get_audio_url(bvid)

        # 下载 + 转 WAV
        wav_path = download_and_convert(session, audio_url, bvid)

        # ASR 转写
        transcript = transcribe_audio(wav_path, model_size)

        # 保存
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(f"【视频标题】{title}\n")
            f.write(f"【UP主】略 | 时长: {duration//60}:{duration%60:02d}\n")
            f.write(f"【转写方式】faster-whisper {model_size}\n")
            f.write(f"{'='*60}\n\n")
            f.write(transcript)

        log(f"\n✅ 完成！转录文本: {out_path}")
        log(f"   总字符: {len(transcript)}")

    except Exception as e:
        log(f"\n❌ 失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
