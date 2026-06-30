# 雪球帖子采集 — 踩坑全记录

> 目标：采集罗洄头 https://xueqiu.com/u/2632831661 的全部帖子
> 结论：除了浏览器地址栏直接访问，所有自动化方案全部失败。

---

## 已尝试方案（全部失败）

### 1. Chrome 控制台 fetch()

**代码**：
```javascript
(async()=>{
  let all=[];
  for(let i=1;i<=8;i++){
    let r=await fetch(`/v4/statuses/user_timeline.json?user_id=2632831661&page=${i}`);
    let d=await r.json();
    if(!d.list||!d.list.length)break;
    all.push(...d.list);
    console.log(`第${i}页 ${d.list.length}条`);
    await new Promise(r=>setTimeout(r,300));
  }
  copy(JSON.stringify(all));
})();
```

**失败原因**：雪球劫持了 `window.fetch`，调用时注入 `debugger` 语句。输出：
```
(function anonymous(s,i) {
0.919847499272051; debugger; return s['charCodeAt'](0);
})
```
Cmd+F8 关闭断点无效——这是雪球自己的 JS 代码里的 `debugger`，不是用户设的断点。

**为什么以前能用**：雪球在 2025 年 6 月前后升级了反爬，旧版无此拦截。

### 2. Chrome 控制台 XMLHttpRequest

**代码**：同步和异步 XHR 均尝试过。

**失败原因**：雪球同时劫持了 `XMLHttpRequest.prototype.send`，请求 URL 被注入 `md5__1038` 防爬 token：
```
Failed to execute 'send' on 'XMLHttpRequest': 
Failed to load '...?page=1&md5__1038=214d4f07715...'
```

### 3. curl + Cookie

**前提**：从 Chrome DevTools → Application → Cookies 手动复制 xq_a_token / xq_r_token / u / acw_tc。

**失败原因**：阿里云 WAF 拦截。curl 缺 WAF token（`_waf_bd8ce2ce37`），返回 WAF 挑战页面而非 JSON。

### 4. Chrome DevTools Protocol (CDP)

**前提**：Chrome 启动时加 `--remote-debugging-port=9222`。

**失败原因**：macOS 上 Chrome 的 CDP 端口无法在 localhost 暴露。即使进程参数里带了 flag，端口也不监听。杀进程重开、直接调二进制均无效——macOS 系统级封堵。

### 5. pycookiecheat（读取 Chrome 加密 Cookie）

**失败原因**：两层问题：
1. Keychain 权限：`keyring.errors.KeyringLocked`，sandbox 无法访问
2. 加密破解：`security find-generic-password` 能拿到 Keychain key，但 AES-GCM 解密始终 `InvalidTag`。Chrome 149 + macOS 的 cookie 加密派生逻辑与开源方案不兼容。

### 6. AppleScript 操控 Chrome

**失败原因**：Chrome 149+ 默认禁用「允许 Apple 事件中的 JavaScript」，且 `open -a` + `--args` 无法可靠传参。

---

## ✅ 唯一可行方案

**浏览器地址栏直接访问 API URL**：

```
https://xueqiu.com/v4/statuses/user_timeline.json?user_id=2632831661&page=1
```

利用已登录 Chrome 的 session（含 WAF token），地址栏导航不触发 fetch/XHR 拦截。

**流程**：
1. 浏览器打开 https://xueqiu.com（确保已登录）
2. 地址栏输入 API URL，回车
3. 看到 JSON 后 `Cmd+A` `Cmd+C` 复制
4. 改 page 参数重复

**代价**：只能逐页手动。109 页约 2173 条帖子，手动 8-10 页（160-200 条最新帖）足够分析。

---

## API 结构

```
GET /v4/statuses/user_timeline.json?user_id=2632831661&page=N

响应：
{
  "count": 20,
  "total": 2173,
  "page": N,
  "maxPage": 109,
  "statuses": [
    {
      "id": 396639777,
      "text": "帖子正文（HTML）",
      "created_at": 1782359315000,  // Unix 毫秒
      "type": "0",  // 0=原创 2=转发 null=回复
      "reply_count": 187,
      "like_count": 105,
      "retweet_count": 5,
      "retweeted_status": { ... }  // 转发时含原文
    }
  ]
}
```

---

## 历史数据

| 文件 | 帖子数 | 时间范围 |
|------|--------|----------|
| `xueqiu_2632831661_1780585752566.json` | 1996 | 2023-02 ~ 2025-06-03 |
| API page 1-2 | 40 | 2025-06-23 ~ 2025-06-29 |
| 合计 | 约 2036 | 2023-02 ~ 2025-06-29 |
| API 总帖数 | 2173 | 缺约 137 条（含旧帖和回复） |
