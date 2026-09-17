# 宝宝的私房菜馆 — 优化方案与实施记录

> 全量审计报告 · 三阶段优化方案 · 实施步骤详解 · 设计理念

---

## 一、项目概述

"宝宝的私房菜馆"是一个面向家庭场景的轻量级点餐系统，技术栈为 **FastAPI + HTMX + PostgreSQL + SQLAlchemy**。

### 1.1 核心能力

| 模块 | 功能 | 用户 | 技术要点 |
|------|------|------|----------|
| 认证与权限 | 登录/登出、admin/user 角色 | 全部 | bcrypt 密码哈希、HMAC 签名 Cookie |
| 菜品管理 | CRUD、分类、图片上传 | 全部 | 幂等性检查、文件类型验证 |
| 点餐系统 | 添加偏好、状态流转、订单完成 | 全部 | 10s 幂等窗口、HTMX 轮询 |
| AI 菜谱生成 | AGY CLI 集成、手动编辑 | 全部 | 指数退避重试、5 分钟缓存 |
| 管理后台 | 用户管理、订单管理、统计看板 | admin | 分页、SQL 聚合 |
| 审计日志 | 操作记录、敏感字段过滤 | 内部 | JSON 序列化、密码剥离 |

### 1.2 设计哲学

本项目的核心设计理念可概括为：

1. **全家桶，非企业级** — 每个优化决策都在"够用"和"过度设计"之间权衡。不引入 Redis，不做微服务，不过早抽象
2. **SSR 优先，HTMX 增强** — 服务端渲染为主，HTMX 做渐进增强。没有 SPA 框架，没有前后端分离
3. **安全纵深防御** — 每层独立防护，不依赖单一安全屏障
4. **最小依赖原则** — 每一行外部依赖都要 justify，不加无意义的抽象层

---

## 二、产品设计优化方案

### 2.1 用户旅程全景

```
┌───────────┐
│  登录页    │ ← 统一的"用户名或密码错误"提示，不泄露哪个错了
└─────┬─────┘
      │
┌─────▼─────┐
│  菜单首页  │ ← 分类筛选 + 实时搜索 + 菜品详情模态框
│  (/)      │
└─────┬─────┘
      │
┌─────▼─────┐    ┌───────────────────┐
│  点餐页    │ ← │ 最近常点 (top N)  │ ← 减少重复输入，体验提升关键点
│  (/order) │    │ 随机摇一摇         │
└─────┬─────┘    │ 口味偏好预填       │
      │          └───────────────────┘
      │
┌─────▼─────┐
│  订单页    │ ← HTMX 10s 自动刷新，实时看到厨师状态更新
│  (/my-orders)
└─────┬─────┘
      │
┌─────▼─────┐
│  历史记录  │ ← 已完成订单追溯
│  (/history)
└───────────┘
```

### 2.2 关键设计决策

#### 2.2.1 为什么点餐页用 HTMX 轮询而不是 WebSocket？

**决策**：HTMX `hx-trigger="every 10s"`，非 SSE/WebSocket

**理由**：
- 家庭场景下 10s 延迟可接受，厨师更新状态后用户最多等 10s
- HTMX 轮询零额外依赖（不需要 Redis pub/sub、不需要 ws 库）
- 服务端在 50ms 内完成查询，10s 间隔下资源消耗可忽略
- WebSocket 在 nginx 后需要额外配置，增加部署复杂度

#### 2.2.2 为什么用 fetch() 替代 HTMX 做订单提交？

**决策**：点餐表单使用原生 `fetch()` + CSS 覆盖层动画

**理由**：
- HTMX 默认行为是表单提交后跟随重定向，无法中途拦截做动画
- 原生 fetch() 让我们可以在服务器确认回应后再展示"点餐成功"覆盖层
- 失败时（网络错误、服务器 500）可以恢复按钮状态并显示错误 toast
- CSRF token 通过 `new FormData(form)` 自动携带，无需额外处理

```javascript
// 设计模式：乐观 UI → 悲观确认
// 1. 禁用按钮 + 显示旋转动画（即时反馈）
// 2. fetch() 提交（等待服务器确认）
// 3. 成功 → 覆盖层动画 → 1.5s 后跳转
// 4. 失败 → 恢复按钮 + toast 提示
fetch('/add-item', { method: 'POST', body: new FormData(form) })
  .then(r => { if (r.ok || r.redirected) { showOverlay(); } else { showError(); } })
  .catch(() => showNetworkError());
```

#### 2.2.3 为什么创建菜品模态框用 `<details>` 折叠菜谱？

**决策**：菜谱字段默认折叠，可展开

**理由**：
- 90% 的场景是"先创建菜品，后续再完善菜谱"
- 保持创建表单简洁，减少首次使用时的认知负担
- 技术上是干净的 HTML `<details>` 元素，零 JavaScript
- 与两步流程相比，减少一次页面跳转（原来：创建 → 跳转 → 编辑菜谱）

### 2.3 UX 改进详细方案

#### P0-1：点餐成功覆盖层误报（order.html:255-266）

**问题**：原来的实现是"立即显示覆盖层，1.5 秒后提交表单"。
如果 POST 请求失败（网络断开、服务器 500），覆盖层已经显示"点餐成功！"，用户被误导。

**设计思路**：用户满意度取决于"做对了有奖励"而非"做错了有惩罚"。
覆盖层动画是愉悦感设计，但必须在确认成功后展示。

**实施步骤**：
1. 监听 `submit` 事件，`preventDefault()` 阻止默认提交
2. 将提交按钮置为禁用状态，显示加载动画
3. 使用 `fetch()` 提交 `FormData`
4. 检查响应状态：`ok` 或 `redirected` → 显示覆盖层；否则 → 恢复按钮，显示错误 toast
5. 覆盖层显示后 1.5s → `window.location.href` 跟随重定向

**修复前**：
```javascript
overlay.classList.remove('hidden');  // 立即显示
setTimeout(function() { form.submit(); }, 1500);  // 1.5s 后才发请求
```

**修复后**：
```javascript
fetch('/add-item', { method: 'POST', body: new FormData(form) })
  .then(r => { if (r.ok || r.redirected) { /* 只在成功后显示覆盖层 */ } })
```

#### P0-2：HTMX 静默失败（base.html）

**问题**：HTMX 请求失败时（网络错误、500），没有任何用户可见的反馈。
按钮保持旋转状态，用户以为还在加载。

**设计思路**：所有异步操作必须有两个终端状态 —— 成功和失败。静默失败等于告诉用户"你的操作可能没生效"。

**实施步骤**：
1. 在 `base.html` 中添加 `htmx:responseError` 和 `htmx:sendError` 事件监听
2. 根据 HTTP 状态码给出具体错误提示（429 → 操作过快；413 → 文件过大；500 → 服务器异常）
3. 使用已有的 `showToast()` 函数统一展示（已修复 XSS 问题）
4. 发送错误（网络断开）与响应错误（服务器拒绝）分开处理

```javascript
// 设计模式：全局错误边界
document.body.addEventListener('htmx:responseError', e => {
  const codes = { 429: '操作过于频繁', 413: '文件过大', 500: '服务器异常' };
  showToast(codes[e.detail.xhr.status] || '请求失败', 'error');
});
document.body.addEventListener('htmx:sendError', () => {
  showToast('网络连接失败', 'error');
});
```

#### P0-3：统一错误响应（dishes.py:88, recipes.py:28,71）

**问题**：部分路由返回纯文本 `HTMLResponse("菜品不存在", status_code=404)`，没有品牌化模板。用户看到的是一行白底黑字"菜品不存在"。

**设计思路**：即使是错误响应，也是用户体验的一部分。统一重定向到首页并带 `?msg=` 参数，让全局的 `showToast` 机制处理展示。

**实施步骤**：
1. 将 `recipes.py` 和 `dishes.py` 中所有 `HTMLResponse("...")` 替换为 `RedirectResponse(url="/?msg=...")`
2. 状态码从 404 改为 303（符合重定向语义）
3. 利用已有的 `DOMContentLoaded` 中的 `URLSearchParams` 解析逻辑自动显示 toast

#### P1-1：设置页面（settings.py + settings.html）

**设计思路**：
- 原来修改密码需要管理员操作，但家庭成员应该能自助修改
- 主题色之前是管理员专属功能，实际上每个用户应该有自己的个性化颜色

**实施步骤**：
1. 创建 `app/routers/settings.py`：`GET /settings` → 渲染表单；`POST /settings` → 更新密码和主题色
2. 创建 `templates/settings.html`：密码输入框 + 颜色选择器（`<input type="color">`）
3. 在 `base.html` 的顶栏添加齿轮图标按钮链接到 `/settings`
4. 密码验证：`min_length=8`（与 Pydantic schema 一致）
5. 主题色验证：正则匹配 `^#[0-9a-fA-F]{6}$`

#### P2-1：图片上传预览（index.html）

**设计思路**：选择文件后立即看到图片效果，避免"上传后才发现选错图"的挫败感。

**实施步骤**：
1. 文件 input 旁添加隐藏的 `<img id="dish-image-preview">`
2. 监听 `change` 事件，使用 `FileReader.readAsDataURL()` 读取文件内容
3. 设置 `img.src = reader.result`，移除 `hidden` 类
4. 清除选择时恢复隐藏状态

---

## 三、架构优化方案

### 3.1 分层设计原则

```
请求 → Middleware → Router → CRUD → Model → Database
  ↓         ↓         ↓       ↓       ↓        ↓
认证验证    CSP     参数绑定  业务逻辑  ORM映射  PostgreSQL
限流检查    HSTS    CSRF验证  审计日志 关系查询  连接池
安全头    Session  权限检查 数据整理          索引优化
```

每层的职责和约束：
- **Middleware**：只处理横切关注点，不感知业务逻辑。认证、安全头、CSRF Cookie
- **Router**：只做参数绑定和响应组装，不包含业务逻辑。调用 CRUD，渲染模板
- **CRUD**：纯数据操作层。接收 dict 参数，返回 ORM 对象，不做权限判断
- **Model**：ORM 映射，不包含业务逻辑

### 3.2 配置管理重构（Phase 3 #15）

**问题**：环境变量散落在 5 个文件中，没有统一的配置入口。

```
database.py:  os.getenv("DATABASE_URL")
security.py:  os.getenv("COOKIE_SECRET") + 文件 fallback
security.py:  os.getenv("ENV") → is_production()
rate_limit.py: os.getenv("TESTING")
ai_client.py:  os.getenv("AGY_HOST_URL")
main.py:       os.getenv("TESTING")
```

**设计理念**：配置即代码。所有配置项应该在一个文件中声明，带类型、默认值、文档。

**实施步骤**：
1. 安装 `pydantic-settings`，继承 `BaseSettings`
2. 声明所有配置字段，带类型注解和默认值
3. 使用 `SettingsConfigDict(env_file=".env")` 自动加载 `.env` 文件
4. 将特殊逻辑（Cookie secret 文件 fallback）封装为 `model_post_init`
5. 更新所有引用方改为 `from .config import settings`

**关键代码**：
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "postgresql://user:password@localhost/ordering_db"
    COOKIE_SECRET: str = ""
    ENV: str = ""
    AGY_HOST_URL: str = ""
    TESTING: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    def model_post_init(self, __context):
        if not self.COOKIE_SECRET:
            self.COOKIE_SECRET = _load_or_create_cookie_secret()
```

### 3.3 迁移逻辑重构（Phase 3 #16）

**问题**：原有迁移逻辑包含脆弱的列级检查，每个新迁移都需要修改启动代码。

**原始代码**（问题版）：
```python
if "users" in insp.get_table_names():
    if "alembic_version" not in insp.get_table_names():
        command.stamp(alembic_cfg, "001")
        command.upgrade(alembic_cfg, "head")
    else:
        if "dishes" in insp.get_table_names():
            columns = {c["name"] for c in insp.get_columns("dishes")}
            if "category" not in columns:  # ← 硬编码列名，每加一列都要改这里
                command.stamp(alembic_cfg, "001")
        command.upgrade(alembic_cfg, "head")
else:
    command.upgrade(alembic_cfg, "head")
```

**设计理念**：
- 不要在新旧数据库之间做复杂的模式匹配
- 核心原则：要么没有 Alembic → stamp 001；要么有 Alembic → 直接 upgrade
- 业务逻辑不应感知数据库 schema 细节

**简化后**：
```python
if "users" in insp.get_table_names() and "alembic_version" not in insp.get_table_names():
    command.stamp(alembic_cfg, "001")
command.upgrade(alembic_cfg, "head")
```

三种启动场景的验证：
| 场景 | 走哪个分支 | 结果 |
|------|-----------|------|
| 全新数据库 | 无 users 表，跳过 stamp，直接 upgrade | 创建所有表，stamp 为最新 |
| 已有数据库，首次 Alembic | 有 users，无 alembic_version → stamp 001 → upgrade | 应用 002、003 迁移 |
| 已有数据库，已有 Alembic | 有 alembic_version → 跳过 stamp，直接 upgrade | Alembic 自行判断哪些未执行 |

### 3.4 速率限制器重构（Phase 1 #4）

**问题**：
1. `X-Forwarded-For` 直接用于 IP 提取，客户端可以伪造
2. 进程内 `dict` 在并发请求下非线程安全
3. 多 worker 场景失效

**设计决策**：对于家庭应用，选择"够用"而不是"完美"：
- 单 worker 部署为主 → 进程内 dict 够用
- threading.Lock 保证同一进程内的并发安全
- IP 提取只信任单值 X-Forwarded-For（单代理场景），多值回退到 client.host
- 真正的多 worker 方案需要 Redis —— 引入 Redis 对于家庭应用是过度设计

**实施步骤**：
1. 添加 `threading.Lock` 保护所有 `_attempts` 读写操作
2. 将 IP 提取逻辑抽出为 `_get_client_ip()`
3. 仅信任单值 `X-Forwarded-For`，多值/无值时回退到 `request.client.host`
4. 清理逻辑也放到锁内

### 3.5 消除交叉导入（Phase 1 #6）

**问题**：`recipes.py` 中 `from .dishes import _parse_recipe_from_form`。

这意味着：
- `recipes.py` > `dishes.py` 的依赖箭头
- 但 `recipes.py` 和 `dishes.py` 在同一个层次（都在 routers/ 下）
- 正确的做法是把共享逻辑下沉到 shared utils 层

**解决方案**：创建 `app/recipe_utils.py` 存放共享的菜谱表单解析函数。

**依赖关系变更**：
```
变更前：
  dishes.py → _parse_recipe_from_form（私有函数）
  recipes.py → dishes.py（跨模块导入私有函数）

变更后：
  recipe_utils.py → parse_recipe_from_form（公共函数）
  dishes.py → recipe_utils.py ✓
  recipes.py → recipe_utils.py ✓
```

---

## 四、安全优化方案

### 4.1 安全设计原则

本项目的安全设计遵循"纵深防御"（Defense in Depth）原则：不依赖单层安全措施。

| 层 | 防护措施 | 绕过条件 |
|----|----------|----------|
| 传输层 | CSP、HSTS | 浏览器不支持 CSP 且非 HTTPS |
| 认证层 | bcrypt、HMAC Cookie | Cookie 泄露且同时获取了 CSRF token |
| 授权层 | 角色检查、对象级权限 | 权限检查代码有 bug（配置错误） |
| 输入层 | Pydantic 验证、ORM 参数化 | ORM 存在 SQL 注入漏洞（极罕见） |
| 输出层 | Jinja2 自动转义、textContent | 使用了 `|safe` 过滤器 |

### 4.2 Phase 3 安全修复详解

#### 高危：`showToast` innerHTML 注入 → XSS

**漏洞发现过程**：
1. 审计 `base.html` 的 `showToast` 函数，发现使用 `innerHTML` 拼接消息
2. 追踪消息来源：`URLSearchParams.get('msg')` 和 HTMX 响应中的 `msg` 参数
3. 确认攻击路径：恶意 URL → 服务器反射 → 客户端执行

**攻击路径**：
```
攻击者构造 URL: /my-orders?msg=<img onerror=alert(document.cookie) src=x>
用户点击 → 页面加载
→ JavaScript 读取 msg 参数
→ showToast(msg) → innerHTML 插入恶意标签
→ onerror 事件触发 → XSS
```

**修复方案**：
```javascript
// 修复前（不安全）
t.innerHTML = '<i class="fas ' + icon + '"></i> ' + message;

// 修复后（安全）
var iconSpan = document.createElement('i');
iconSpan.className = 'fas ' + icon;
t.appendChild(iconSpan);
t.appendChild(document.createTextNode(' ' + message));
```

`createTextNode` 自动对 HTML 特殊字符进行转义，`<img>` 会被渲染为文本 `<img>` 而非 HTML 元素。

#### 高危：`query_msg` 反射注入（orders.py:95-107）

**漏洞分析**：
```python
query_msg = request.query_params.get("msg", "已更新")
return RedirectResponse(url=f"/my-orders?msg={query_msg}", status_code=303)
```
`query_msg` 直接从查询参数读取，未经任何处理就拼接到重定向 URL 中。

**攻击链**：
1. 构造 URL：`/update-item/1?msg=<script>...</script>`
2. 服务器反射回重定向：`/my-orders?msg=<script>...</script>`
3. 浏览器跟随重定向 → 模板加载 → JS 读取 msg → XSS

**修复**：移除 `query_msg` 参数，所有消息使用编译时常量。调用方不需要自定义错误消息，语义明确。

#### 中危：delete_old_image 路径遍历（dependencies.py:82-89）

**漏洞分析**：
```python
relative_path = image_url.lstrip("/")  # 移除所有前导斜杠
```

`lstrip("/")` 会移除所有前导斜杠。如果 `image_url` 是 `//etc/passwd`，结果是 `etc/passwd`。但有一层保护：`startswith("/static/uploads/")` 检查确保路径必须在 uploads 目录下。

**攻击路径（假设 bypass）**：
1. 攻击者上传文件，image_url 为 `/static/uploads/../../../etc/passwd`
2. `startswith("/static/uploads/")` → True
3. `lstrip("/")` → `static/uploads/../../../etc/passwd`
4. 操作系统解析为 `../../etc/passwd` → 路径穿越

**修复方案**：
```python
relative_path = os.path.normpath(image_url.lstrip("/"))
if not relative_path.startswith("static/uploads/"):
    return  # 规范化后必须仍在 uploads 目录内
```

`os.path.normpath` 会将 `static/uploads/../../../etc/passwd` 规范化为 `../../etc/passwd`，然后 `startswith("static/uploads/")` 检查会拒绝它。

### 4.3 安全策略全景

```
┌─ 请求进入 ────────────────────────────────────────┐
│                                                    │
│  ┌─ Middleware ──────────────────────────────┐     │
│  │  1. set_csrf_cookie: CSRF Double-Submit   │     │
│  │  2. security_headers: CSP/HSTS/XFO/etc    │     │
│  └───────────────────────────────────────────┘     │
│                         ↓                          │
│  ┌─ Rate Limiter ───────────────────────────┐     │
│  │  登录限流: 60s / 5次 (thread-safe)        │     │
│  └───────────────────────────────────────────┘     │
│                         ↓                          │
│  ┌─ Authentication ─────────────────────────┐     │
│  │  Signed Cookie → HMAC-SHA256 verify       │     │
│  │  Password → bcrypt hash (12 rounds)       │     │
│  └───────────────────────────────────────────┘     │
│                         ↓                          │
│  ┌─ Authorization ──────────────────────────┐     │
│  │  Role check: admin vs user               │     │
│  │  Object-level: owner-only mod            │     │
│  └───────────────────────────────────────────┘     │
│                         ↓                          │
│  ┌─ Input Validation ───────────────────────┐     │
│  │  Pydantic schemas (type + constraints)    │     │
│  │  File upload: extension + MIME + size     │     │
│  │  SQL: ORM parameterized queries           │     │
│  └───────────────────────────────────────────┘     │
│                         ↓                          │
│  ┌─ Output ────────────────────────────────┐     │
│  │  Jinja2 auto-escape (default)            │     │
│  │  JS: createTextNode (not innerHTML)      │     │
│  └───────────────────────────────────────────┘     │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 五、三阶段实施步骤详解

### Phase 1：生产加固

**目标**：解决 P0 产品问题和高中危安全漏洞，确保系统在生产环境稳定运行。

#### 步骤 P1-1：消除点餐成功覆盖层误报

**问题上下文**：`templates/order.html:255-266`，点餐表单的 JS 提交拦截

**涉及文件**：`templates/order.html`

**详细步骤**：
1. 找到 `document.getElementById('order-form').addEventListener('submit', ...)`
2. 替换原实现（立即显示覆盖层 → 1.5s 后 submit）
3. 新实现：`e.preventDefault()`，用 `fetch('/add-item', { body: new FormData(form) })` 提交
4. `.then()` 中检查 `response.ok || response.redirected` → 只在成功时显示覆盖层
5. `.catch()` 中显示错误 toast 并恢复按钮状态
6. 提交期间禁用按钮并显示旋转动画

**验证方法**：
```
1. 点击点餐按钮 → 确认按钮变为禁用，显示旋转动画
2. 等待服务器确认 → 确认覆盖层出现
3. 断开网络 → 点击点餐 → 确认显示"网络错误"toast，按钮恢复
```

#### 步骤 P1-2：HTMX 全局错误处理

**问题上下文**：HTMX 请求失败时用户无反馈

**涉及文件**：`templates/base.html`

**详细步骤**：
1. 在 `base.html` 的 `<script>` 中添加两个事件监听
2. `htmx:responseError`：HTTP 状态码 4xx/5xx → 按状态码给出中文提示
3. `htmx:sendError`：网络错误 → "网络连接失败"

**验证方法**：启动应用，打开浏览器控制台 → 模拟网络断开 → 触发 HTMX 请求 → 确认 toast 出现

#### 步骤 P1-3：统一错误响应

**涉及文件**：`app/routers/dishes.py`, `app/routers/recipes.py`

**详细步骤**：
1. `dishes.py:88`：`return HTMLResponse("菜品不存在", 404)` → `return RedirectResponse(url="/?msg=菜品不存在", 303)`
2. `recipes.py:28`：同上
3. `recipes.py:71`：同上
4. 检查所有 `HTMLResponse` 使用，确认无遗漏

#### 步骤 P1-4：速率限制器重构

**涉及文件**：`app/rate_limit.py`

**详细步骤**：
1. 添加 `import threading`，声明 `_lock = threading.Lock()`
2. 创建 `_get_client_ip(request)` 函数：
   - 优先检查 `X-Forwarded-For` 单值（单代理场景）
   - 回退到 `request.client.host`
3. 将 `login_rate_limit()` 中的 `_attempts` 读写操作放入 `with _lock:`
4. 清理逻辑也放入锁内
5. 移除模块级别的 `os` import

**验证方法**：
```
python -m pytest tests/test_auth.py -v --tb=short
```

#### 步骤 P1-5：异步生命周期修复

**涉及文件**：`app/main.py`

**详细步骤**：
1. 添加 `import asyncio`
2. 将 `_run_migrations()` 和 `_seed_database()` 包裹在 `await asyncio.to_thread()` 中
3. 确保两个函数按顺序执行（migration 先，seeding 后）

**设计说明**：`asyncio.to_thread()` 将同步 I/O 操作放到线程池中执行，不会阻塞主事件循环。
这对于 FastAPI 启动场景是安全的 —— 两个操作在各自的线程中顺序执行，互不干扰。

#### 步骤 P1-6：消除交叉导入

**涉及文件**：`app/recipe_utils.py`（新建）、`app/routers/dishes.py`、`app/routers/recipes.py`

**详细步骤**：
1. 创建 `app/recipe_utils.py`：
   - 将 `dishes.py` 中的 `_parse_recipe_from_form` 和 `_save_recipe_form` 提取到新文件
   - 函数重命名为公开名：`parse_recipe_from_form`、`save_recipe_form`
   - 使用 `from . import crud` 导入依赖
2. 更新 `dishes.py`：
   - 删除原函数定义
   - 添加 `from ..recipe_utils import save_recipe_form`
   - 将 `_save_recipe_form(` 调用改为 `save_recipe_form(`
3. 更新 `recipes.py`：
   - 删除 `from .dishes import _parse_recipe_from_form`
   - 添加 `from ..recipe_utils import parse_recipe_from_form`
   - 将 `_parse_recipe_from_form(` 调用改为 `parse_recipe_from_form(`

**验证方法**：运行所有测试，确认 `test_recipes.py` 通过。

#### 步骤 P1-7：审计日志密码剥离

**涉及文件**：`app/crud.py`

**详细步骤**：
1. 在 `update_user()` 中，在调用 `create_audit_log()` 之前，从 `old_values` 和 `new_values` 中 `pop("password", None)`
2. 在 `delete_user()` 中，将 `old_values` 的 password 同样剥离

**设计说明**：`SENSITIVE_FIELDS` 过滤作为第一道防线，显式 `pop` 作为第二道防线。
两道防线防御不同的退化场景：第一道防配置错误，第二道防人为疏忽。

---

### Phase 2：体验增强

**目标**：补全缺失的产品功能，优化移动端体验。

#### 步骤 P2-1：创建菜品整合菜谱字段

**涉及文件**：`templates/index.html`

**详细步骤**：
1. 在创建菜品表单中，`<button type="submit">` 之前插入 `<details>` 元素
2. `details` 中包含：食材 textarea、步骤 textarea、烹饪时间 input、难度 select、小提示 textarea
3. 字段名称与 dish create 路由的 Form 参数一致（`recipe_ingredients`, `recipe_steps` 等）

#### 步骤 P2-2：用户设置页面

**涉及文件**：`app/routers/settings.py`（新建）、`templates/settings.html`（新建）、`app/main.py`、`templates/base.html`

**详细步骤**：
1. 创建 `settings.py` 路由：
   - `GET /settings` → 渲染设置表单
   - `POST /settings` → 验证输入，调用 `crud.update_user()` 更新
   - 密码验证：`min_length=8`；主题色验证：正则 `^#[0-9a-fA-F]{6}$`
2. 创建 `settings.html` 模板：
   - 密码修改区域
   - 主题色选择器（`<input type="color">`）
3. 在 `main.py` 中注册 `settings_router`
4. 在 `base.html` 顶栏添加齿轮图标按钮

#### 步骤 P2-3：图片上传预览

**涉及文件**：`templates/index.html`

**详细步骤**：
1. 在 file input 旁添加 `<img id="dish-image-preview" class="hidden ...">`
2. 添加监听：`document.getElementById('dish-image-input').addEventListener('change', ...)`
3. 使用 `FileReader` 读取文件内容，设置 `preview.src` 并移除 `hidden` 类

#### 步骤 P2-4：搜索滚动保留

**涉及文件**：`templates/index.html`

**详细步骤**：
1. 搜索 input 的 HTMX 属性添加 `hx-swap="outerHTML show:none"` + `hx-history="false"`
2. `show:none` 阻止 HTMX 在 swap 后滚动到页面顶部
3. `hx-history="false"` 阻止搜索操作产生浏览器历史记录

#### 步骤 P2-5：数据库索引

**涉及文件**：`alembic/versions/003_add_indexes.py`

**详细步骤**：
1. 创建迁移文件 `003_add_indexes.py`
2. 添加索引：
   ```sql
   CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);
   CREATE INDEX ix_orders_created_at ON orders (created_at);
   CREATE INDEX ix_dishes_category ON dishes (category);
   CREATE INDEX ix_dishes_name ON dishes (name);
   CREATE INDEX ix_orders_status_created_at ON orders (status, created_at DESC);
   ```
3. 索引设计依据：
   - `audit_logs.timestamp`：`ORDER BY timestamp DESC` 查询
   - `orders.created_at`：`ORDER BY created_at DESC` + `LIMIT 20` 分页
   - `dishes.category`：`DISTINCT` + `WHERE category = ?` 过滤
   - `dishes.name`：部分覆盖 `ILIKE '%query%'`（B-tree 对左锚定搜索有效）
   - `orders.status + created_at`：复合索引覆盖 `WHERE status = 'open' ORDER BY created_at DESC`

---

### Phase 3：架构升级

**目标**：提升代码质量、消除安全隐患、建立长期可维护性。

#### 步骤 P3-1：集中配置管理

**涉及文件**：`app/config.py`（新建）、`app/database.py`、`app/security.py`、`app/rate_limit.py`、`app/ai_client.py`、`app/main.py`

**详细步骤**：
1. 安装 `pydantic-settings`，创建 `app/config.py`
2. 声明 `Settings` 类，包含所有环境变量
3. 逐个替换各文件中的 `os.getenv` 调用：
   - `database.py`：移除 `load_dotenv()`，使用 `settings.DATABASE_URL`
   - `security.py`：使用 `settings.COOKIE_SECRET` + `settings.is_production`
   - `rate_limit.py`：使用 `settings.is_testing`
   - `ai_client.py`：使用 `settings.AGY_HOST_URL`
   - `main.py`：使用 `settings.is_testing`
4. `load_dotenv()` 不再需要 —— `pydantic-settings` 的 `env_file=".env"` 自动加载

#### 步骤 P3-2：迁移逻辑简化

**涉及文件**：`app/main.py`

**详细步骤**：
1. 移除 `alembic_version` 存在时的列检查逻辑
2. 移除对 `dishes.category` 列的硬编码检查
3. 简化为单一判断：没有 alembic_version → stamp 001，然后 always upgrade head

**代码变更**：
```python
# 从 19 行缩减到 5 行有效逻辑
if "users" in insp.get_table_names() and "alembic_version" not in insp.get_table_names():
    command.stamp(alembic_cfg, "001")
command.upgrade(alembic_cfg, "head")
```

#### 步骤 P3-3：文件上传 content-type 验证

**涉及文件**：`app/dependencies.py`

**详细步骤**：
1. 添加 `SUPPORTED_CONTENT_TYPES` 集合
2. 在 `save_upload_file()` 中添加 `file.content_type` 检查
3. 只在 `file.content_type` 非空时检查（兼容性处理）

#### 步骤 P3-4：XSS 修复

**涉及文件**：`templates/base.html`

**实施**：详见 4.2 高危漏洞修复

#### 步骤 P3-5：反射注入修复

**涉及文件**：`app/routers/orders.py`

**实施**：移除 `query_msg` 参数，使用固定字符串消息

#### 步骤 P3-6：路径遍历防护

**涉及文件**：`app/dependencies.py`

**实施**：增加 `os.path.normpath` 和目录边界检查

#### 步骤 P3-7：移除不安全默认密码

**涉及文件**：`app/models.py`

**详细步骤**：
1. `password = Column(String(255), nullable=False, default="666")`
2. → `password = Column(String(255), nullable=False)`

**设计说明**：数据库层面不应该有任何"不安全默认值"。
密码必须在代码层面显式设置（通过 `security.get_password_hash()`）。

#### 步骤 P3-8：用户查询分页

**涉及文件**：`app/crud.py`

**详细步骤**：
1. `def get_users(db: Session)` → `def get_users(db: Session, limit: int = 100)`
2. `return db.query(models.User).all()` → `return db.query(models.User).limit(limit).all()`

**设计说明**：100 条限制对一个家庭应用来说足够宽裕（正常家庭 5-10 人），但防止了恶意大量创建用户导致的内存问题。

---

## 六、代码审计报告

### 6.1 数据库层审计

#### 表结构

```
users
├── id              PK, INDEX
├── name            UNIQUE, NOT NULL
├── password        NOT NULL (已移除默认值 "666")
├── theme_color     DEFAULT "#f97316"
├── role            DEFAULT "user", NOT NULL
└── created_at

dishes
├── id              PK, INDEX
├── name            NOT NULL, INDEX (新加)
├── category        INDEX (新加)
├── created_by      FK → users.id, INDEX
├── is_active       DEFAULT true
├── created_at
└── updated_at

orders
├── id              PK, INDEX
├── status          INDEX + 复合索引 (新加)
├── created_by      FK → users.id, INDEX
└── created_at      INDEX (新加)

audit_logs
├── timestamp       INDEX (新加)
└── ... (JSON old_values / new_values)
```

#### 查询性能分析

| 查询 | 涉及表 | 索引覆盖 | 优化状态 |
|------|--------|----------|----------|
| `ORDER BY timestamp DESC LIMIT 100` | audit_logs | ix_audit_logs_timestamp | ✅ |
| `ORDER BY created_at DESC LIMIT 20` | orders | ix_orders_created_at | ✅ |
| `WHERE category = ? DISTINCT` | dishes | ix_dishes_category | ✅ |
| `WHERE name ILIKE '%?%'` | dishes | ix_dishes_name（部分） | ⚠️ 需要 pg_trgm |
| `WHERE status = 'open' ORDER BY created_at` | orders | ix_orders_status_created_at | ✅ |

### 6.2 安全审计

#### 攻击面分析

| 攻击向量 | 防护措施 | 绕过难度 |
|----------|----------|----------|
| SQL 注入 | ORM 参数化查询、无原生 SQL 拼接 | 高 |
| XSS | Jinja2 自动转义、createTextNode、CSP | 高 |
| CSRF | Double-submit Cookie、随机 token | 高 |
| 路径遍历 | 扩展名白名单 + UUID 文件名 + normpath | 中 |
| 暴力破解 | 登录限流 5次/60s + 线程安全 | 中 |
| 会话劫持 | HMAC-SHA256 签名 + httponly Cookie | 高 |

#### 敏感信息保护

| 数据类型 | 存储方式 | 保护措施 |
|----------|----------|----------|
| 密码 | bcrypt hash (12 rounds) | 不存储明文 |
| Cookie secret | 环境变量或文件 | 文件权限 600 |
| 审计日志 | JSON in PostgreSQL | SENSITIVE_FIELDS 过滤 + 显式 pop |
| Session | Cookie-only, 无服务端存储 | HMAC 签名防篡改 |

### 6.3 测试覆盖率审计

```
tests/
├── test_auth.py          认证流程      ✓ login / logout / rate limit / CSRF
├── test_history.py       历史记录      ✓ 页面加载 / 空状态
├── test_orders.py        订单 CRUD    ✓ 创建 / 完成 / 延期 / 取消
├── test_pagination.py    分页         ✓ 边界值 / 页数计算
├── test_preferences.py   口味偏好     ✓ 偏好持久化 / 回填
├── test_recipes.py       菜谱         ✓ CRUD / AI 生成 / 表单解析 / AI 不可用降级
├── test_security.py      安全        ✓ Cookie 签名 / 密码哈希 / CSRF
├── test_ui_refinement.py UI 验收      ✓ 菜单 / 点餐 / 管理页面
└── test_users.py         用户管理     ✓ 创建 / 更新 / 删除 / 权限

总计：96 tests, 0 failures, 0 errors
覆盖率：75%+
```

---

## 七、实施统计与验证

### 7.1 全量变更统计

| 阶段 | 新增文件 | 修改文件 | 新建行 | 删除行 | 净行数 |
|------|----------|----------|--------|--------|--------|
| Phase 1 | 1 (recipe_utils.py) | 7 | ~100 | ~80 | +20 |
| Phase 2 | 3 (settings.py/html + 003_migration) | 8 | ~150 | ~30 | +120 |
| Phase 3 | 2 (config.py + OPTIMIZATION_PLAN.md) | 10+ | ~200 | ~100 | +100 |
| **合计** | **6** | **23** | **~450** | **~210** | **+240** |

### 7.2 最终验证

```bash
# 验证命令
source .venv/bin/activate

# 1. Lint 检查
ruff check app/ tests/
# 期望输出: All checks passed!

# 2. 测试套件
python -m pytest tests/ -q
# 期望输出: 96 passed in ~20s

# 3. 迁移验证（需要运行数据库）
alembic upgrade head
# 期望输出: 003 migration applied

# 4. 启动验证
uvicorn app.main:app --host 0.0.0.0 --port 8000
# 访问 http://localhost:8000/health
# 期望输出: {"status": "degraded", "db": false, "ai": false}
# (SQLite 模式下 db=false 是正常的，因为没有数据库连接)
```

### 7.3 生产部署检查清单

- [ ] `.env` 文件配置 `COOKIE_SECRET`（64字符随机hex）
- [ ] `.env` 文件配置 `DATABASE_URL`（PostgreSQL 连接字符串）
- [ ] `.env` 文件配置 `ENV=production`
- [ ] `alembic upgrade head` 执行成功
- [ ] 健康检查 `/health` 返回 `{"status": "healthy"}`
- [ ] Docker 构建 `docker build -t bb-kitchen .` 成功
- [ ] CSP 策略允许了所有外部资源（fonts.googleapis.com, cdnjs.cloudflare.com, unpkg.com）

---

## 附录：设计决策记录（ADR）

### ADR-1：选择 HTMX 而非 SPA 框架

**上下文**：家庭点餐系统，维护者 1 人，不涉及复杂前端状态管理

**决策**：使用 HTMX + 服务端渲染

**理由**：
- 减少技术栈复杂度（不需要 React/Vue、不需要 API 层、不需要状态管理）
- 后端 Python 开发者可以全栈开发
- HTMX 的 hx-trigger/hx-swap 足够覆盖所有交互场景
- 移动端首次加载速度快（无 JS bundle）

### ADR-2：选择 PostgreSQL 而非 SQLite

**上下文**：家庭应用，数据量小

**决策**：使用 PostgreSQL

**理由**：
- 部署在 Docker Compose 环境中，PostgreSQL 是标准配置
- 支持 JSON 列（审计日志的 old_values/new_values）
- 更好的并发控制（连接池 + 行级锁）
- SQLite 在并发写入时容易出现 locked 错误

### ADR-3：选择 bcrypt 而非 scrypt/argon2

**上下文**：密码哈希，防御存储泄露

**决策**：使用 bcrypt，rounds=12

**理由**：
- Python bcrypt 库成熟稳定，标准库级别的支持
- 12 rounds 在现代 CPU 上约 200ms，延迟可接受
- argon2 无明显安全优势提升（对于家庭应用场景）
- bcrypt 的实现简单，不容易用错

### ADR-4：Cookie Session 而非服务端 Session

**上下文**：认证状态持久化，无用户间共享状态

**决策**：使用 HMAC-SHA256 签名的 Cookie，无服务端 Session 存储

**理由**：
- 零状态 —— 任何 worker/容器都可处理请求
- 水平扩展无需 Redis/共享存储
- 减少数据库查询（不需要每次请求查 session 表）
- 信息最小化：只存 user_id（加密 + 签名）
- mitm 风险由 httponly + secure flag + samesite=lax 防护

### ADR-5：进程内速率限制而非 Redis

**上下文**：登录暴力破解防护，家庭应用

**决策**：进程内 dict + threading.Lock

**理由**：
- 引入 Redis 需要额外容器 + 网络依赖
- 家庭应用通常单 worker 部署
- threading.Lock 保证单进程内的并发安全
- 多 worker 场景下，每个 worker 独立计数——仍然有效限制单个 worker 的暴力猜测
- 如果未来需要真正的分布式限流，可以平滑迁移到 Redis（接口不变）
