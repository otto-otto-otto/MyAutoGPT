---
name: persist-token-usage-in-postgres
overview: 添加 PostgreSQL 表持久化 token 用量，修复重启后 usage limit 归零的问题。Redis 继续做缓存，PostgreSQL 作数据源。
todos:
  - id: add-schema
    content: 在 schema.prisma 中 UserBalance 模型后添加 UserTokenUsage 表定义，运行 prisma generate 和 prisma migrate
    status: completed
  - id: add-persist-helper
    content: 在 rate_limit.py 中添加 _persist_token_usage() 函数（PostgreSQL UPSERT 双写）和 _read_token_usage_fallback() 函数（从 PostgreSQL 恢复当日/当周 token 用量）
    status: completed
    dependencies:
      - add-schema
  - id: modify-record
    content: 修改 record_token_usage()：在 Redis INCR 后异步调用 _persist_token_usage() 写入 PostgreSQL，使用 asyncio.create_task 确保不阻塞
    status: completed
    dependencies:
      - add-persist-helper
  - id: modify-read-status
    content: 修改 get_token_usage_status()：当 Redis 返回 0 时回退到 _read_token_usage_fallback()，取 max(redis, pg) 作为最终值并写回 Redis 缓存
    status: completed
    dependencies:
      - add-persist-helper
  - id: modify-read-check
    content: 修改 check_token_rate_limit()：当 Redis 返回 0 时回退到 _read_token_usage_fallback()，取 max(redis, pg) 判断是否超限
    status: completed
    dependencies:
      - add-persist-helper
  - id: verify-idempotent
    content: 验证重启恢复场景：模拟 Redis 清空后检查 get_token_usage_status() 是否正确从 PostgreSQL 恢复数据，以及双写不会产生重复计数
    status: completed
    dependencies:
      - modify-record
      - modify-read-status
      - modify-read-check
---

## 用户需求

后台每次重启后，token 使用量统计归零。需要实现持久化的 token 用量记录：

- 每位用户每天可用 **1,000,000 tokens**
- 每位用户每周可用 **5,000,000 tokens**
- 每次 LLM 调用消耗的 tokens 自动从对应窗口扣除
- 重启后计数器不丢失

## 核心功能

1. **PostgreSQL 持久化**：新增 `UserTokenUsage` 表作为 token 用量的权威数据源
2. **双写机制**：`record_token_usage()` 同时写入 Redis（快速读取）和 PostgreSQL（持久存储）
3. **回退读取**：`get_token_usage_status()` 和 `check_token_rate_limit()` 在 Redis 为空时自动从 PostgreSQL 恢复数据
4. **启动恢复**：重启后 Redis 为空，系统自动从 PostgreSQL 恢复计数器到 Redis
5. **向后兼容**：与现有 cost-based 微美元限速系统完全独立共存

## 技术方案

### 问题根因

Redis 集群在 docker-compose 中明确定义为 "cache-only, no volumes"，每次 `docker compose down/up` 或 Redis 重启都会清空 `copilot:token:*` 键。用户通过 `poetry run` 直接运行后端时同样没有 Redis 持久化。

### 解决方案：PostgreSQL 权威数据源  + Redis 读缓存

```
正常写入:  LLM调用 → record_token_usage()
                ├─ INCR Redis copilot:token:*
                └─ UPSERT PostgreSQL UserTokenUsage（异步，不阻塞）

正常读取:  get_token_usage_status() / check_token_rate_limit()
                ├─ GET Redis copilot:token:* → 有值直接返回
                └─ 值为 0 → SELECT PostgreSQL → 取 max(redis, pg) → 写回 Redis

重启恢复:  后端启动 → Redis 为空
                ├─ GET Redis copilot:token:* → None/0
                └─ SELECT PostgreSQL → 有值 → 返回 pg 值 + SET Redis
```

**关键设计决策**：读路径使用 `max(redis_value, postgres_value)` 确保任何情况下都不会低估实际用量（宁可多算不少算）。

### 数据库 Schema

```
model UserTokenUsage {
  userId    String
  window    String   // "daily" | "weekly"
  dateKey   String   // "2026-06-06" | "2026-W23"
  tokens    Int      @default(0)
  updatedAt DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@id([userId, window, dateKey])
  @@index([userId])
}
```

### 修改的文件

| 文件 | 修改内容 |
| --- | --- |
| `schema.prisma` (line 1391 后) | 新增 `UserTokenUsage` 模型 |
| `rate_limit.py` | 新增 `_persist_token_usage()` / `_read_token_usage_fallback()`；修改 `record_token_usage()`、`get_token_usage_status()`、check_token_rate_limit() |