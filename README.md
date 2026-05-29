# 宝宝的私房菜馆

为家庭设计的轻量级移动端优先点餐系统，支持 AI 智能菜谱生成。

## 功能特性

### 菜品管理
- 菜品库的增删改查，支持图片上传（JPG/PNG/GIF/WebP，最大 5MB）
- 软删除机制，有未完成订单时保护菜品不被删除
- 10 秒内防重复提交（幂等创建）

### 点菜系统
- 同一时间仅有一个进行中的订单，加菜时自动创建
- 每个点菜项记录口味、就餐时间、地点、食材、备注
- 状态流转：待处理 → 已完成/已延期
- 「同上次一样」一键填入该用户当前菜品的上一次偏好
- 所有人可查看和编辑同一张订单

### AI 菜谱生成
- 接入 AGY CLI (Antigravity CLI)，基于菜品名称和描述自动生成结构化菜谱
- 输出包含：食材清单、烹饪步骤、烹饪时长、难度评估、小贴士
- 支持 Docker 和本地双模式（Docker 通过 HTTP 代理桥接宿主机 AGY CLI）
- AI 不可用时回退为手动录入，不影响核心流程

### 用户与权限
- bcrypt 密码哈希 + HMAC-SHA256 签名 Cookie 会话
- 角色系统：管理员 / 普通用户
- CSRF 双重提交 Cookie 防护
- 登录频率限制（每 IP 每分钟最多 5 次）
- 用户自定义主题色，全局生效

### 管理后台
- 成员管理：新增、编辑、删除用户，分配角色和主题色
- 订单历史：分页查看所有历史订单（每页 20 条）
- 审计日志：记录所有操作的执行人、动作、新旧值对比（敏感字段自动脱敏）

### 统计看板
- 点菜总次数、订单总场次
- 最受欢迎菜品 TOP 5
- 最活跃用户 TOP 5

### UI/UX
- 移动端优先，适配 iPhone 安全区域
- 毛玻璃粘性顶栏 + 固定底部标签导航
- 搜索过滤、Toast 通知、表单提交加载态
- CSS 动画（渐入、滑入、缩放），尊重 `prefers-reduced-motion`

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.12+) |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 |
| 前端 | HTMX + Jinja2 模板引擎 |
| CSS | Tailwind CSS（本地构建） |
| 容器化 | Docker & Docker Compose |
| 依赖管理 | uv |
| AI | AGY CLI (Antigravity CLI) |

## 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL（Docker 方式无需单独安装）
- [AGY CLI](https://antigravity.google/cli)（AI 功能可选）

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/sunxmoon/bb-private-kitchen.git
cd bb-private-kitchen

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 修改数据库密码等配置

# 3. 在宿主机启动 AGY 代理（AI 功能可选）
cd host && bash setup.sh && cd ..
python3 host/agy_proxy.py &

# 4. 创建外部 Docker 网络（PostgreSQL 数据库网络）
docker network create postgresql_default

# 5. 启动应用
docker-compose up --build -d
```

应用运行在 `http://localhost:8002`。

### 方式二：本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt
# 或使用 uv：
uv pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 DATABASE_URL 指向你的 PostgreSQL

# 3. 初始化数据库并启动
bash run.sh
# 或分步执行：
python3 seed_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 默认用户

数据库初始化后自动创建三个种子用户：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| 哥哥 | 666 | 管理员 |
| 姐姐 | 666 | 普通用户 |
| 宝宝 | 666 | 普通用户 |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://user:password@localhost/ordering_db` |
| `COOKIE_SECRET` | Cookie 签名密钥 | 自动生成（`.cookie_secret` 文件） |
| `AGY_HOST_URL` | AGY 代理地址（Docker 模式） | `http://host.docker.internal:8765` |
| `ENV` | 运行环境，设为 `production` 启用 Secure Cookie | — |

## 项目结构

```
.
├── app/                        # FastAPI 后端
│   ├── main.py                 # 应用入口、中间件、生命周期、内嵌迁移
│   ├── models.py               # SQLAlchemy 数据模型（6张表）
│   ├── schemas.py              # Pydantic 验证模型
│   ├── crud.py                 # 数据库操作 + 审计日志
│   ├── security.py             # 密码哈希、Cookie 签名
│   ├── csrf.py                 # CSRF 防护
│   ├── rate_limit.py           # 登录频率限制
│   ├── ai_client.py            # AGY AI 客户端
│   ├── dependencies.py         # 共享依赖（认证、模板、文件上传）
│   ├── database.py             # 数据库连接配置
│   └── routers/                # 路由模块
│       ├── auth.py             # 登录/注销
│       ├── dishes.py           # 菜品管理
│       ├── orders.py           # 订单管理
│       ├── recipes.py          # 菜谱 + AI 生成
│       ├── admin.py            # 管理后台
│       └── history.py          # 统计看板
├── templates/                  # Jinja2 模板
├── static/                     # 静态资源（CSS、上传文件）
├── tests/                      # pytest 测试用例
├── host/                       # AGY CLI 代理
│   └── agy_proxy.py            # HTTP 代理服务
├── docs/                       # 设计文档
├── Dockerfile                  # 容器构建（multi-stage）
├── docker-compose.yml          # Docker Compose 编排
├── pyproject.toml              # 项目与依赖配置
├── seed_db.py                  # 数据库初始化与种子数据
├── run.sh                      # 本地一键启动脚本
└── cleanup_images.py           # 孤立图片清理工具
```

## 数据模型

```
User ──┬── Dish ──── Recipe       （菜品 + 菜谱，一对一）
       ├── Order ──── OrderItem   （订单 + 点餐项，一对多）
       └── AuditLog              （审计日志）
```

| 模型 | 说明 |
|------|------|
| User | 家庭成员，含 name / password / theme_color / role |
| Dish | 菜品，含 name / description / image_url / is_active |
| Recipe | 菜谱，与 Dish 一对一，content 存 JSON |
| Order | 订单，status: open / completed |
| OrderItem | 点餐明细，含偏好字段 + 状态 |
| AuditLog | 操作审计，记录 old/new values |

## 测试

```bash
# 运行全部测试
pytest

# 运行并生成覆盖率报告
pytest --cov=app --cov-report=html

# 运行特定测试模块
pytest tests/test_auth.py
```

## 运维工具

```bash
# 清理孤立图片（dry-run）
python3 cleanup_images.py

# 实际删除孤立图片
python3 cleanup_images.py --force
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
