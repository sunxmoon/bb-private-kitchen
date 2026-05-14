# 宝宝的私房菜馆 — 优化升级方案

> 基于 PRD 的详细技术实施计划
> 版本：v1.0 | 日期：2026-05-12

---

## 目录

1. [Phase 1：安全加固（High Priority）](#phase-1安全加固)
2. [Phase 2：数据完整性加固](#phase-2数据完整性加固)
3. [Phase 3：性能与可扩展性](#phase-3性能与可扩展性)
4. [Phase 4：代码质量与可维护性](#phase-4代码质量与可维护性)
5. [Phase 5：UI/UX 精细化](#phase-5uiux-精细化)
6. [Phase 6：测试与部署](#phase-6测试与部署)
7. [附录：文件变更清单](#附录文件变更清单)

---

## Phase 1：安全加固

### 1.1 审计日志密码脱敏

**问题**：`crud.py` 中 `update_user` 将完整的 `old_values` / `new_values`（包含 `password` 哈希）写入 `audit_logs` 表。

**方案**：

在 `crud.py` 的 `json_serializable` 函数中增加敏感字段过滤：

```python
SENSITIVE_FIELDS = {"password", "token", "secret"}

def json_serializable(data: dict, skip_sensitive: bool = True) -> dict:
    if not data:
        return data
    serializable = {}
    for key, value in data.items():
        if skip_sensitive and key in SENSITIVE_FIELDS:
            continue
        if isinstance(value, datetime):
            serializable[key] = value.isoformat()
        else:
            serializable[key] = value
    return serializable
```

**改动文件**：`app/crud.py`

---

### 1.2 CSRF 防护

**问题**：所有 POST 端点仅依赖 Cookie 认证，无 CSRF Token 校验，存在跨站请求伪造风险。

**方案**：使用 `itsdangerous`（Flask 签名工具，轻量级）实现 CSRF Token 机制：

1. **安装依赖**：`itsdangerous`（额外安装，或使用 `signed_cookie` 机制）

2. **中间件设计**：

```
请求流程：
GET 页面 → 服务端在响应中设置 CSRF cookie（签名后的 token）
POST 请求 → 前端从 cookie 读取 token，在表单 hidden input 中提交
           服务端校验提交的 token 与 cookie 中的签名是否匹配
```

3. **实现步骤**：

**新增文件**：`app/csrf.py`

```python
from itsdangerous import URLSafeTimedSerializer
from fastapi import Request, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

SECRET_KEY = os.getenv("CSRF_SECRET_KEY", "change-this-in-production")
CSRF_TOKEN_NAME = "csrf_token"
SALT = "csrf-salt"

serializer = URLSafeTimedSerializer(secret_key=SECRET_KEY, salt=SALT)

def generate_csrf_token() -> str:
    return serializer.dumps("csrf")

def validate_csrf_token(token: str, max_age: int = 3600) -> bool:
    try:
        serializer.loads(token, max_age=max_age)
        return True
    except Exception:
        return False

async def csrf_guard(request: Request):
    if request.method == "POST":
        token = (await request.form()).get(CSRF_TOKEN_NAME)
        cookie_token = request.cookies.get(CSRF_TOKEN_NAME)
        if not token or not cookie_token or token != cookie_token:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="CSRF validation failed")
```

4. **模板集成**：在 `base.html` 的全局表单中自动注入 CSRF 字段：

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

**注意**：家庭内部应用可暂缓此改造，但若暴露于外网则为必须。

**改动文件**：
- 新增 `app/csrf.py`
- 修改 `app/main.py`（增加 `csrf_guard` 依赖注入）
- 修改 `templates/base.html`（传递并注入 csrf_token）

---

### 1.3 登录错误提示优化

**问题**：登录失败统一返回 `/login?error=1`，无法区分"用户不存在"和"密码错误"。

**方案**：

修改 `main.py` 中登录逻辑：

```python
@app.post("/login")
async def login(name: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_name(db, name)
    if not user:
        return RedirectResponse(url="/login?error=user_not_found", status_code=303)
    if not security.verify_password(password, user.password):
        return RedirectResponse(url="/login?error=wrong_password", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, samesite="lax")
    return response
```

模板 `login.html` 中显示对应错误消息：

```html
{% if request.query_params.get('error') == 'user_not_found' %}
  <p class="text-red-500 text-sm">该用户不存在</p>
{% elif request.query_params.get('error') == 'wrong_password' %}
  <p class="text-red-500 text-sm">密码错误，请重试</p>
{% endif %}
```

**改动文件**：
- `app/main.py`
- `templates/login.html`

---

### 1.4 `.gitignore` 安全加固

**问题**：`.gitignore` 中未包含 `.env`，生产数据库密码存在泄露风险。

**方案**：补全 `.gitignore`：

```gitignore
.env
*.pyc
__pycache__/
.pytest_cache/
static/uploads/*
static/backgrounds/*
!static/uploads/.gitkeep
!static/backgrounds/.gitkeep
```

**改动文件**：`.gitignore`

---

## Phase 2：数据完整性加固

### 2.1 并发订单约束

**问题**：当前通过 `status == "open"` 查询最新订单，无 SQL 层约束，并发场景下可能创建多个 open 订单。

**方案 A（推荐）**：数据库部分唯一索引（PostgreSQL）

```
CREATE UNIQUE INDEX idx_unique_open_order ON orders (status) WHERE status = 'open';
```

方案 A 需要在数据库中手动执行或通过 Alembic 迁移。

**方案 B（应用层锁）**：

修改 `get_current_order` 和 `create_order`：

```python
from contextlib import contextmanager
from sqlalchemy import event
import threading

# 应用层写锁
_order_lock = threading.Lock()

def get_or_create_current_order(db: Session, user_id: int) -> models.Order:
    with _order_lock:
        current_order = db.query(models.Order).filter(models.Order.status == "open").order_by(models.Order.created_at.desc()).first()
        if not current_order:
            current_order = models.Order(status="open", created_by=user_id)
            db.add(current_order)
            db.flush()
        return current_order
```

**推荐先实施方案 B 后补方案 A**。

**改动文件**：
- `app/crud.py`（修改 `get_current_order` / `create_order`）

---

### 2.2 防重复提交后端加固

**问题**：现有 10 秒窗口去重依赖 `created_at` 时间戳判断，精度依赖服务器时间。

**方案**：改为基于 Redis 或内存缓存的去重标记（可选升级），当前方案维持不变但增加时区感知：

```python
def create_dish(db: Session, dish: schemas.DishCreate):
    ten_seconds_ago = datetime.utcnow() - timedelta(seconds=10)  # 使用 UTC 避免时区问题
    existing = db.query(models.Dish).filter(
        models.Dish.name == dish.name,
        models.Dish.created_by == dish.created_by,
        models.Dish.created_at >= ten_seconds_ago
    ).first()
    ...
```

**改动文件**：
- `app/crud.py`

---

### 2.3 软删除菜品引用检查

**问题**：下架菜品时未检查是否有未完成的 `order_items` 依赖该菜品。

**方案**：

```python
def delete_dish(db: Session, dish_id: int, user_id: int):
    db_dish = db.query(models.Dish).filter(models.Dish.id == dish_id).first()
    if not db_dish:
        return None
    # 检查是否有未完成的订单项引用该菜品
    pending_items = db.query(models.OrderItem).filter(
        models.OrderItem.dish_id == dish_id,
        models.OrderItem.status.in_(["pending", "delayed"])
    ).count()
    if pending_items > 0:
        raise ValueError(f"该菜品有 {pending_items} 个未完成的点单，无法下架")
    ...
```

**改动文件**：`app/crud.py` + `app/main.py`（捕获 ValueError）

---

## Phase 3：性能与可扩展性

### 3.1 历史订单分页

**问题**：`get_order_history` 一次性加载所有订单，数据量增长后页面卡顿。

**方案**：

```python
def get_order_history(db: Session, skip: int = 0, limit: int = 20):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()

def get_order_history_count(db: Session) -> int:
    return db.query(models.Order).count()
```

模板端增加分页控件：

```html
{% if orders|length >= 20 %}
<div class="flex justify-center gap-4 mt-6">
  {% if page > 1 %}
    <a href="/history?page={{ page - 1 }}" class="btn btn-secondary">上一页</a>
  {% endif %}
  <span class="self-center text-sm text-gray-500">第 {{ page }} / {{ total_pages }} 页</span>
  {% if page < total_pages %}
    <a href="/history?page={{ page + 1 }}" class="btn btn-secondary">下一页</a>
  {% endif %}
</div>
{% endif %}
```

**改动文件**：
- `app/crud.py`
- `app/main.py`
- `templates/history.html`

---

### 3.2 N+1 查询优化

**问题**：遍历订单及其 items/dish/user 时，ORM 懒加载会触发大量额外查询。

**方案**：使用 `joinedload` 或 `selectinload` 预加载关系：

```python
from sqlalchemy.orm import joinedload, selectinload

def get_orders_with_items(db: Session):
    return db.query(models.Order).options(
        selectinload(models.Order.items).selectinload(models.OrderItem.dish),
        selectinload(models.Order.items).selectinload(models.OrderItem.user)
    ).order_by(models.Order.created_at.desc()).all()
```

**改动文件**：`app/crud.py`

---

## Phase 4：代码质量与可维护性

### 4.1 路由模块拆分

**问题**：`main.py` 包含所有路由，已达 250+ 行，不利于维护。

**方案**：按业务域拆分为独立路由模块：

```
app/
├── main.py              # 应用入口 + 全局配置 + include_router
├── routers/
│   ├── __init__.py
│   ├── auth.py          # /login, /logout
│   ├── dishes.py        # /, /create-dish, /update-dish, /delete-dish, /get-preference
│   ├── orders.py        # /order, /add-item, /my-orders, /update-item, etc.
│   ├── users.py         # /users, /create-user, /update-user, /delete-user
│   └── history.py       # /history
├── dependencies.py      # get_current_user, login_required, get_db (shared)
├── models.py
├── schemas.py
├── crud.py
├── database.py
└── security.py
```

**示例** - `app/routers/auth.py`：

```python
from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud

router = APIRouter(prefix="", tags=["auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    ...

@router.post("/login")
async def login(name: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    ...

@router.get("/logout")
async def logout():
    ...
```

`app/main.py` 精简为：

```python
from fastapi import FastAPI
from .routers import auth, dishes, orders, users, history

app = FastAPI(title="宝宝的私房菜馆")
app.include_router(auth.router)
app.include_router(dishes.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(history.router)
```

**新增文件**：
- `app/routers/__init__.py`
- `app/routers/auth.py`
- `app/routers/dishes.py`
- `app/routers/orders.py`
- `app/routers/users.py`
- `app/routers/history.py`
- `app/dependencies.py`（公共依赖项提取）

**修改文件**：`app/main.py`（精简为入口文件）

---

### 4.2 清理未使用 import

**问题**：`main.py` 中存在 `shutil`、`Response`、`HTTPException` 等未使用的 import。

**方案**：在路由拆分后统一清理，使用 `ruff` 或 `autoflake` 自动化：

```bash
pip install autoflake
autoflake --in-place --remove-all-unused-imports app/*.py app/routers/*.py
```

**改动文件**：拆分后全量清理

---

### 4.3 路由层空值检查

**问题**：CRUD 函数返回 `None` 时路由层未处理，导致静默失败或 500 错误。

**方案**：统一添加 404 检查：

```python
@app.post("/update-user/{target_user_id}")
async def update_user(target_user_id: int, ..., db: Session = Depends(get_db)):
    target_user = crud.get_user(db, target_user_id)
    if not target_user:
        return RedirectResponse(url="/users?error=user_not_found", status_code=404)
    ...
```

**改动文件**：所有涉及 `get_*` 后操作的 POST 路由

---

### 4.4 初始化 Alembic 迁移

**问题**：当前使用 `create_all` 管理 schema，不适合生产环境演进。

**方案**：

```bash
pip install alembic
alembic init alembic
# 修改 alembic.ini 中 sqlalchemy.url = %DATABASE_URL%
# 修改 alembic/env.py 导入 Base.metadata
# 生成初始迁移
alembic revision --autogenerate -m "initial migration"
alembic upgrade head
```

将 `on_startup` 中的 `create_all` 替换为仅在开发环境使用：

```python
@app.on_event("startup")
def on_startup():
    if os.getenv("TESTING") == "1":
        models.Base.metadata.create_all(bind=engine)
    # 生产环境通过 alembic upgrade head 管理
```

**新增文件**：`alembic/` 目录

**修改文件**：`app/main.py`

---

## Phase 5：UI/UX 精细化

基于 UI-UX-Pro-Max 设计准则，针对当前 UI 进行以下优化：

### 5.1 触摸交互优化

**问题**：按钮在提交后无加载状态反馈，部分 touch target 尺寸偏小。

**方案**：

在 `base.html` 的全局 JS 中增强表单提交体验：

```javascript
// 增强 btn-loading 行为
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', function(e) {
    const btns = this.querySelectorAll('.btn-loading');
    btns.forEach(btn => {
      btn.disabled = true;
      btn.innerHTML = '<span class="loading loading-spinner loading-sm"></span> 处理中...';
    });
  });
});
```

所有操作按钮统一 touch target ≥ 44px（Tailwind 中通过 `min-h-[44px]` 保证）：

```html
<button class="btn btn-primary min-h-[44px] min-w-[44px]">提交</button>
```

**改动文件**：
- `templates/base.html`（JS 增强）
- `templates/*.html`（按钮尺寸统一）

---

### 5.2 表单体验提升

**问题**：表单错误反馈不足，部分表单依赖 placeholder 而非 label。

**方案**：

1. **添加可见 label**：每个输入框增加 `<label>` 标签，替代仅 placeholder 的方案
2. **内联验证**：对必填字段添加 `required` 属性和 `aria-required="true"`
3. **密码切换**：登录表单增加密码显隐切换按钮

```html
<div class="form-control">
  <label for="dish-name" class="label">
    <span class="label-text">菜品名称 <span class="text-red-500">*</span></span>
  </label>
  <input id="dish-name" name="name" type="text" required aria-required="true"
         class="input input-bordered w-full" placeholder="输入菜品名称">
</div>
```

**密码显隐**：

```javascript
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === 'password' ? 'text' : 'password';
}
```

**改动文件**：`templates/login.html`, `templates/order.html`, `templates/index.html`

---

### 5.3 空状态与反馈优化

**问题**：没有菜品/没有订单时页面空白，无引导提示。

**方案**：

```html
{% if not dishes %}
<div class="flex flex-col items-center justify-center py-16 text-gray-400">
  <svg class="w-16 h-16 mb-4" ...> <!-- 空状态图标 --> </svg>
  <p class="text-lg">还没有菜品</p>
  <p class="text-sm mt-2">点击上方"添加菜品"按钮收录第一道菜吧！</p>
</div>
{% endif %}
```

**改动文件**：
- `templates/index.html`（菜品空状态）
- `templates/my_orders.html`（订单项空状态）
- `templates/history.html`（无历史记录空状态）

---

### 5.4 Toast 通知优化

**问题**：当前 Toast 用 `alert` 样式实现，位置固定体验一般。

**方案**：优化为固定在右上角、自动消失的浮动 Toast：

```javascript
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const colors = { success: 'alert-success', error: 'alert-error', info: 'alert-info' };
  const toast = document.createElement('div');
  toast.className = `alert ${colors[type] || colors.info} shadow-lg mb-2 transition-all duration-300`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
```

```html
<!-- 在 base.html 中固定位置 -->
<div id="toast-container" class="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm"></div>
```

**改动文件**：`templates/base.html`

---

### 5.5 可访问性（Accessibility）

**问题**：缺少 aria 标签、焦点管理、键盘导航支持。

**方案**：

1. **导航栏**：增加 `aria-current="page"` 标记当前页
2. **图标按钮**：增加 `aria-label`
3. **模态框**：增加 `role="dialog"`, `aria-modal="true"`, 焦点锁定
4. **颜色对比度**：确保正文文本 ≥ 4.5:1（当前 Tailwind gray-700 在白色背景约为 4.6:1，基本达标）

```html
<nav aria-label="主导航">
  <a href="/" aria-current="{% if request.url.path == '/' %}page{% endif %}" class="...">
    ...
  </a>
</nav>
```

**改动文件**：`templates/base.html`, `templates/*.html`

---

## Phase 6：测试与部署

### 6.1 测试覆盖提升

**问题**：当前测试覆盖 CRUD + 认证，缺少订单生命周期、错误场景、CSRF、分页测试。

**新增测试用例**：

| 测试文件 | 新增用例 | 数量 |
|---------|---------|------|
| `tests/test_auth.py` | 未认证访问保护端点重定向到 `/login` | +2 |
| `tests/test_crud.py` | 更新不存在的用户返回 None | +3 |
| `tests/test_orders.py` | 创建订单 → 添加项 → 更新状态 → 删除项的完整生命周期 | +5 |
| `tests/test_pagination.py` | 分页参数测试 | +2 |
| `tests/test_idempotency.py` | 不同备注非重复、超 10s 可重复 | +2 |

**新增文件**：
- `tests/test_orders.py`
- `tests/test_pagination.py`

**安装覆盖度工具**：

```bash
pip install pytest-cov
TESTING=1 PYTHONPATH=. pytest tests/ --cov=app --cov-report=term-missing
```

---

### 6.2 Docker 部署优化

**问题**：Compose 文件中缺少数据库服务，依赖外部 PostgreSQL。

**方案**：在 `docker-compose.yml` 中增加可选的 `db` 服务（通过环境变量 `USE_EXTERNAL_DB` 切换）：

```yaml
version: '3.8'
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: moon
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ordering_db
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    profiles:
      - with-db

  web:
    build: .
    ports:
      - "8002:8000"
    env_file: .env
    depends_on:
      - db
    profiles:
      - with-db

volumes:
  pgdata:
```

**改动文件**：`docker-compose.yml`

---

### 6.3 配置管理优化

**问题**：硬编码上传路径前缀 `/`，依赖工作目录。

**方案**：在 `.env` 中增加配置变量：

```env
UPLOAD_URL_PREFIX=/static
UPLOAD_DIR=static
```

代码中读取：

```python
UPLOAD_URL_PREFIX = os.getenv("UPLOAD_URL_PREFIX", "/static")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "static")

def save_upload_file(file: UploadFile, subdir: str) -> str:
    destination_dir = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(destination_dir, exist_ok=True)
    ...
    return f"{UPLOAD_URL_PREFIX}/{subdir}/{filename}"
```

**改动文件**：
- `.env.example`
- `app/main.py`
- `app/crud.py`（如有路径相关）

---

## 实施路线图

| 阶段 | 内容 | 预估工时 | 依赖 |
|------|------|---------|------|
| **Sprint 1** | 安全加固（1.1, 1.3, 1.4 + 测试） | 1 天 | 无 |
| **Sprint 2** | 数据完整性（2.1, 2.2, 2.3 + 测试） | 1 天 | Sprint 1 |
| **Sprint 3** | 路由拆分 + 代码清理（4.1, 4.2, 4.3, 4.4） | 1.5 天 | Sprint 1 |
| **Sprint 4** | 性能优化（3.1, 3.2） | 0.5 天 | Sprint 3 |
| **Sprint 5** | UI/UX 优化（5.1 - 5.5） | 1 天 | 无 |
| **Sprint 6** | 测试覆盖 + 部署优化（6.1, 6.2, 6.3） | 1 天 | Sprint 1-4 |

**总计**：约 6 天（可按需调整优先级和范围）

---

## 附录：文件变更清单

### 新增文件（10 个）

| 文件 | 用途 |
|------|------|
| `app/csrf.py` | CSRF Token 生成与校验 |
| `app/dependencies.py` | 公共 FastAPI 依赖项 |
| `app/routers/__init__.py` | 路由包初始化 |
| `app/routers/auth.py` | 认证路由 |
| `app/routers/dishes.py` | 菜品路由 |
| `app/routers/orders.py` | 订单路由 |
| `app/routers/users.py` | 用户管理路由 |
| `app/routers/history.py` | 历史记录路由 |
| `alembic/`（目录） | 数据库迁移 |
| `tests/test_orders.py` | 订单测试 |

### 修改文件（12 个）

| 文件 | 修改内容 |
|------|---------|
| `app/main.py` | 精简为入口 + include_router |
| `app/crud.py` | 脱敏、并发锁、引用检查、分页、N+1 优化 |
| `.gitignore` | 添加 .env / 上传目录排除 |
| `templates/base.html` | Toast 容器、CSRF token、触摸反馈 JS、aria 属性 |
| `templates/login.html` | 区分错误提示、密码显隐 |
| `templates/index.html` | 空状态、表单 label |
| `templates/order.html` | 表单优化 |
| `templates/my_orders.html` | 空状态、触摸优化 |
| `templates/history.html` | 分页控件、空状态 |
| `docker-compose.yml` | 可选 db 服务 |
| `.env.example` | 新增配置项 |
| `requirements.txt` | 新增依赖（itsdangerous, pytest-cov） |
