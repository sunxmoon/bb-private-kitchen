# 宝宝的私房菜馆 - 优化方案 v2.0

> 版本：v2.0 | 日期：2026-05-30
> 基于产品设计、架构技术、安全质量三个维度独立评审后的综合方案

---

## 评审综合结论

### 砍掉的方案（过度设计，评审否决）

| 方案 | 否决理由 |
|------|---------|
| Redis 速率限制/会话 | 家庭单进程内存足够，多一个组件多一份运维负担 |
| 异步 SQLAlchemy | 瓶颈在 AI 调用（120s），不在 DB，改写 380+ 行 CRUD 不值得 |
| Celery/RQ 任务队列 | 用 `asyncio.create_task` + 前端轮询替代 |
| WebSocket | HTMX polling 或 SSE 够用，WebSocket 运维复杂度过高 |
| API 版本管理 (/api/v1/) | SSR + HTMX 应用无独立前端消费者，无多版本并行需求 |
| PWA 离线缓存 | 家庭 Wi-Fi 环境无离线需求 |
| 多轮菜单/多会话 | 增加认知负担，单会话已满足核心场景 |
| OWASP ZAP 自动化渗透 | 企业级需求，内网应用 ROI 极低 |
| 密钥轮换方案 | 改 secret = 所有用户 session 失效，家庭场景无此需求 |
| 事务回滚测试隔离 | 当前 create_all/drop_all 方案更安全（SQLite savepoint 支持不完整） |

### 核心发现（原方案遗漏）

1. **登录枚举漏洞** — `auth.py` 分别返回 "用户不存在" 和 "密码错误"，可被枚举有效用户名
2. **最大体验痛点** — "看菜单"和"点餐"是两个独立页面，流程割裂（产品评审认定）
3. **datetime 无时区** — `crud.py` 中 `datetime.now()` 未用 timezone-aware，跨时区会出问题
4. **Dockerfile 版本未锁定** — `uv:latest` 导致构建不可复现

---

## 第一阶段：安全加固 + 核心体验（1-2周）

> 目标：消除安全风险，修复最大体验痛点

### 1.1 安全响应头中间件

**文件**: `app/main.py`
**工作量**: 30分钟

添加中间件，统一设置：
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy`（限制 style/script/font 来源）
- 生产环境额外 `Strict-Transport-Security`

**收益**: 从零防护到基础防护，一个中间件覆盖 5+ 个安全头

### 1.2 修复登录枚举漏洞

**文件**: `app/routers/auth.py`, `templates/login.html`
**工作量**: 10分钟

将 `/login` POST 的错误响应统一为 "用户名或密码错误"，不再区分用户不存在和密码错误。审计日志中仍记录具体失败原因（用于运维排查）。

**收益**: 防止用户名枚举攻击

### 1.3 生产环境错误处理

**文件**: `app/main.py`, `templates/error.html`
**工作量**: 15分钟

确认 `global_exception_handler` 不泄露栈信息；`error.html` 模板中生产环境隐藏技术细节，仅显示友好提示。

**收益**: 防止信息泄露

### 1.4 密码策略

**文件**: `app/schemas.py`, `app/routers/admin.py`
**工作量**: 20分钟

创建/修改密码时校验最小长度（8位）。默认密码 "666" 仅用于种子数据，不强制策略。

**收益**: 提升密码强度基线

### 1.5 Alembic 数据库迁移

**工作量**: 2-3小时

- 引入 Alembic，将 `main.py` 中的 4 个 `_migrate_*` 函数转换为版本化迁移脚本
- 移除 `main.py` 和 `seed_db.py` 中的内嵌迁移代码
- 初始迁移包含当前全部 schema
- `lifespan` 中改为 `alembic upgrade head`

**收益**: 消除最大技术债，支持版本追踪和回滚，消除多实例竞态风险

### 1.6 健康检查端点

**文件**: `app/main.py`, `Dockerfile`
**工作量**: 30分钟

- 新增 `GET /health`，检查 DB 连通性，AI 状态降级为可选（不阻塞容器健康）
- Dockerfile HEALTHCHECK 改为访问 `/health`（当前访问 `/login` 语义错误且污染日志）

**收益**: 语义正确的健康检查

### 1.7 修复 datetime 时区

**文件**: `app/crud.py`
**工作量**: 30分钟

将所有 `datetime.now()` 替换为 `datetime.now(timezone.utc)`。模型的 `server_default=func.now()` 保持不变（数据库时区）。

**收益**: 避免跨时区数据混乱

### 1.8 锁定 Dockerfile 版本

**文件**: `Dockerfile`
**工作量**: 5分钟

将 `ghcr.io/astral-sh/uv:latest` 替换为具体版本号（如 `0.6.0`）。

**收益**: 构建可复现

### 1.9 首页一键点餐（体验核心）

**文件**: `templates/index.html`, `app/routers/dishes.py`
**工作量**: 1小时

在菜品卡片上添加 "我要吃" 按钮，点击后跳转到点餐页并预选该菜品（URL 参数 `?dish_id=X`）。`order.html` 已有 URL 参数解析逻辑，只需确保跳转正确。

**收益**: 消除"看菜单"和"点餐"的流程割裂 — 产品评审认定的最大体验痛点

---

## 第二阶段：质量提升 + 功能增强（2-3周）

> 目标：提升代码质量和运维能力，增强核心功能

### 2.1 AI 客户端重试机制

**文件**: `app/ai_client.py`
**工作量**: 1小时

`_call_api` 方法添加指数退避重试（最多3次，间隔 2s/4s/8s），区分可重试错误（超时、5xx）和不可重试错误（4xx）。

**收益**: 提升 AI 菜谱生成成功率（当前仅有 120s 超时，无重试）

### 2.2 结构化日志

**文件**: `app/main.py`, 各 router
**工作量**: 2-3小时

引入 `structlog`，日志输出 JSON 格式，包含 request_id、user_id、action 等字段。替换现有 `logging.info` 调用。

**收益**: 可查询、可过滤的结构化日志，便于排查问题

### 2.3 连接池调优 + 静态文件缓存

**文件**: `app/database.py`, `app/main.py`
**工作量**: 30分钟

- SQLAlchemy 连接池参数：`pool_size=5, max_overflow=10, pool_recycle=3600`
- 静态文件添加 `Cache-Control: public, max-age=86400`（CSS/JS），上传图片 `max-age=3600`

**收益**: 减少 DB 连接开销，加速静态资源加载

### 2.4 点餐页展示当前订单摘要

**文件**: `templates/order.html`, `app/routers/orders.py`
**工作量**: 2小时

在点餐页顶部展示当前订单已有点餐项摘要，如"哥哥已点 红烧肉、姐姐已点 番茄蛋汤"。通过 HTMX polling（30秒）自动更新。

**收益**: 提升信息密度，避免重复点餐或遗漏

### 2.5 后端菜品搜索

**文件**: `app/routers/dishes.py`, `app/crud.py`, `templates/index.html`
**工作量**: 2小时

将前端 JS 过滤改为后端模糊匹配（`ILIKE`），支持分页。首页搜索框改为 HTMX 触发，输入时实时请求后端。

**收益**: 支持大数据量菜品搜索，前端过滤在菜品多时性能差

### 2.6 CI Pipeline

**新增**: `.github/workflows/ci.yml`
**工作量**: 2小时

- lint (ruff check)
- test (pytest --cov=app)
- coverage threshold (≥70%)
- 依赖安全扫描 (pip-audit)

**收益**: 代码质量自动化保障

### 2.7 菜品分类标签

**文件**: `app/models.py`, `app/schemas.py`, `app/crud.py`, `templates/index.html`
**工作量**: 3小时

Dish 模型新增 `category` 字段（如：荤菜/素菜/汤品/主食/甜品），首页按分类筛选，添加菜品时选择分类。

**收益**: 菜品多时提升浏览效率

---

## 第三阶段：产品完善 + 实时体验（3-4周）

> 目标：打磨细节，提升使用愉悦感

### 3.1 空状态引导

**文件**: `templates/index.html`, `templates/my_orders.html`
**工作量**: 1小时

- 首次使用无菜品时显示引导卡片 "添加第一道菜"
- 无订单时显示 "开始点餐" 引导
- 无历史记录时显示 "还没有点过菜，快去试试吧"

**收益**: 降低新用户认知门槛

### 3.2 最近常点 + 一键再来一份

**文件**: `app/crud.py`, `app/routers/orders.py`, `templates/order.html`
**工作量**: 2小时

- 点餐页新增"最近常点"区域，展示该用户历史点餐最多的 5 道菜，点击直接填入
- "我的订单"页面，已完成的订单项旁添加"再来一份"按钮

**收益**: 减少重复操作，提升复购效率

### 3.3 订单页自动刷新

**文件**: `templates/my_orders.html`
**工作量**: 30分钟

使用 HTMX `hx-trigger="every 10s"` 对订单列表进行轮询刷新，替代手动刷新。

**收益**: 多人协作时实时看到他人的点餐

### 3.4 SSE 实时推送

**文件**: `app/routers/orders.py`, `templates/my_orders.html`
**工作量**: 3-4小时

使用 Server-Sent Events 推送订单变更事件。HTMX 通过 `htmx:sse` 扩展接收。比 WebSocket 轻量，与现有 HTMX 架构天然契合。

**收益**: 订单变更即时感知，替代 polling

### 3.5 点餐成功反馈动画

**文件**: `templates/order.html`
**工作量**: 1小时

点餐提交后显示愉悦的成功动画（浮动餐具图标 + "点餐成功！"），1.5秒后跳转。

**收益**: 提升点餐仪式感和参与感，家庭场景中孩子会喜欢

### 3.6 无图菜品温和提示

**文件**: `templates/index.html`
**工作量**: 30分钟

对无图片的菜品卡片显示"缺一张美照"的柔和提示，引导家人拍照上传。有图菜品的点餐率显著高于无图。

**收益**: 引导完善菜品信息

---

## 时间线总览

```
第一阶段（1-2周）            第二阶段（2-3周）            第三阶段（3-4周）
┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐
│ 1.1 安全响应头       │    │ 2.1 AI 重试机制      │    │ 3.1 空状态引导       │
│ 1.2 登录枚举修复     │    │ 2.2 结构化日志       │    │ 3.2 最近常点         │
│ 1.3 生产错误处理     │    │ 2.3 连接池+缓存      │    │ 3.3 订单自动刷新     │
│ 1.4 密码策略         │    │ 2.4 订单摘要展示     │    │ 3.4 SSE 实时推送     │
│ 1.5 Alembic 迁移    │    │ 2.5 后端菜品搜索     │    │ 3.5 点餐成功动画     │
│ 1.6 健康检查         │    │ 2.6 CI Pipeline     │    │ 3.6 无图菜品提示     │
│ 1.7 datetime 时区   │    │ 2.7 菜品分类标签     │    │                     │
│ 1.8 Dockerfile 版本 │    │                     │    │                     │
│ 1.9 首页一键点餐     │    │                     │    │                     │
└────────────────────┘    └────────────────────┘    └────────────────────┘
```

## 工作量估算

| 阶段 | 预估工时 | 核心产出 |
|------|---------|---------|
| 第一阶段 | 8-10 小时 | 安全基线 + 核心体验修复 |
| 第二阶段 | 12-15 小时 | 质量保障 + 功能增强 |
| 第三阶段 | 8-10 小时 | 产品打磨 + 实时体验 |
| **总计** | **28-35 小时** | **约 3-4 周** |

## 评审 Agent 签核

| 角色 | 结论 | 关键意见 |
|------|------|---------|
| 产品设计 | 通过（附调整） | 最大痛点是流程割裂，PWA/多会话/WebSocket 砍掉 |
| 架构技术 | 通过（附调整） | Redis/Celery/async ORM 砍掉，SSE 替代 WebSocket |
| 安全质量 | 通过（附调整） | 登录枚举是关键发现，第三阶段安全措施过度砍掉 |
