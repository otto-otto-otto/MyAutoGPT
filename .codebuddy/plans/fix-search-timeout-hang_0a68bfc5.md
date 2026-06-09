---
name: fix-search-timeout-hang
overview: 大幅缩短百度/搜狗搜索块的请求超时、减少重试次数、添加硬性时间上限，解决 8 分钟卡死问题。
todos:
  - id: baidu-timeout
    content: "【百度】_fetch_page: 30s→10s, connect 10→5; _fetch_page_content: 15s→8s, connect 8→4"
    status: completed
  - id: baidu-do-search
    content: "【百度】_do_search: 移除 _SEARCH_SEMAPHORE, 重试 3→1, 延迟线性→固定1s, 网络调用包 asyncio.wait_for(20)"
    status: completed
    dependencies:
      - baidu-timeout
  - id: baidu-enrich
    content: "【百度】_enrich_with_content: asyncio.gather 外包 asyncio.wait_for(15)"
    status: completed
    dependencies:
      - baidu-timeout
  - id: sogou-all
    content: 【搜狗】完全同上三处改动
    status: completed
    dependencies:
      - baidu-enrich
  - id: verify
    content: 验证导入无错误，确认 do_search time-bound ≤ 35s
    status: completed
    dependencies:
      - sogou-all
---

## 问题

修复 Brotli 解码后百度/搜狗搜索块运行 8 分钟挂死问题。

## 根因

1. `_fetch_page` timeout=30s × 3 retries = ~96s 单次搜索
2. `_fetch_page_content` timeout=15s × 10 URLs / 并发 3 ≈ 60s
3. `_SEARCH_SEMAPHORE(1)` 使多搜索块串行排队，3块 × 96s ≈ 300s → 8分钟
4. 之前 Brotli 报错"快速失败"掩盖了上述问题

## 修复目标

单搜索块总耗时 ≤ 35 秒必返回

## 修复方案

两个文件各 4 处改动：

### 文件 1: `baidu_search.py`

**改动 1** — `_fetch_page` (第 191 行)：降低超时

```
- timeout = aiohttp.ClientTimeout(total=30, connect=10)
+ timeout = aiohttp.ClientTimeout(total=10, connect=5)
```

**改动 2** — `_do_search` (第 38-172 行)：移除 Semaphore 排队 + 减少重试 + 硬超时

- 删除模块级 `_SEARCH_SEMAPHORE = asyncio.Semaphore(1)` (第 39 行)
- 删除 `_do_search` 内的 `async with _SEARCH_SEMAPHORE:` 包装
- 重试 `for attempt in range(3)` → `for attempt in range(1)`
- 延迟 `(attempt + 1) * 1.5` → `1.0`
- 整个网络搜索部分加 `asyncio.wait_for(..., timeout=20)` 硬上限

**改动 3** — `_fetch_page_content` (第 375 行)：降低获取超时

```
- timeout = aiohttp.ClientTimeout(total=15, connect=8)
+ timeout = aiohttp.ClientTimeout(total=8, connect=4)
```

**改动 4** — `_enrich_with_content` (第 334-355 行)：整体增强加硬上限

- `asyncio.gather(*tasks)` 外包 `asyncio.wait_for(..., timeout=15)`

### 文件 2: `sogou_search.py` — 完全相同的 4 处改动

### 关键代码变更细节

`_do_search` 重构后结构：

```python
async def _do_search(self, query, search_type, max_results):
    # 1. 缓存检查（不变）
    cached = await get_chinese_search_cache(query, engine="baidu")
    if cached is not None:
        return cached[:max_results], len(cached)

    # 2. 随机抖动
    await asyncio.sleep(random.uniform(0.1, 0.5))

    # 3. 硬超时 20s 保护
    try:
        return await asyncio.wait_for(
            self._do_search_impl(query, search_type, max_results),
            timeout=20,
        )
    except asyncio.TimeoutError:
        raise RuntimeError("Baidu search timed out after 20s")
```

新增内部方法 `_do_search_impl` 包含原网络调用+解析逻辑，只重试 1 次。

### 预期效果

| 阶段 | 修复前 | 修复后 |
| --- | --- | --- |
| _fetch_page | 30s × 3 = 90s | 10s × 1 = 10s |
| _do_search 硬超时 | 无 | 20s |
| _enrich_with_content | 15s × 10/3 ≈ 60s | 8s × 10/3 + 15s硬上限 ≈ 30s |
| Semaphore 排队 | N块 × 90s | 无 |
| **总计** | **最多 8 分钟** | **最多 35 秒** |