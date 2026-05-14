# 宝宝的私房菜馆 (BB's Private Kitchen)

为家庭设计的轻量级移动端优先点菜系统，支持 AI 智能菜谱生成。

## 功能特性

### 菜品管理
- 菜品库的增删改查，支持图片上传（JPG/PNG/GIF/WebP）
- 软删除机制，有未完成订单时保护菜品不被删除
- 10 秒内防重复提交

### 点菜系统
- 同一时间仅有一个进行中的订单，加菜时自动创建
- 每个点菜项记录口味、就餐时间、地点、食材、备注
- 状态流转：待处理 → 已完成/已延期，已完成可撤销
- 「同上次一样」一键填入该用户当前菜品的上一次偏好
- 随机翻牌器：不知道吃什么时的趣味选择
- 所有人可查看和编辑同一张订单

### AI 菜谱生成
- 接入 Google Gemini CLI，基于菜品名称和描述自动生成结构化菜谱
- 包含食材清单、烹饪步骤、烹饪时长、难度、小贴士
- 支持 Docker 和本地双模式，Docker 通过 HTTP 代理桥接宿主机 Gemini CLI
- AI 不可用时回退为手动录入

### 用户与权限
- bcrypt 密码哈希 + HMAC-SHA256 签名 Cookie 会话
- 角色系统：管理员 / 普通用户
- CSRF 双重提交 Cookie 防护
- 登录频率限制（每 IP 每分钟最多 5 次）
- 用户自定义主题色，全局生效

### 管理后台
- 成员管理：新增、编辑、删除用户，分配角色和主题色
- 订单历史：分页查看所有历史订单（每页 20 条）
- 审计日志：记录所有操作的执行人、动作、新旧值对比

### 统计看板
- 点菜总次数、订单总数
- 最受欢迎菜品 TOP 5
- 最活跃用户 TOP 5

### 审计日志
- 所有增删改操作自动记录到审计日志
- 敏感字段（密码、Token）自动脱敏

### UI/UX
- 移动端优先，适配 iPhone 安全区域
- 毛玻璃粘性顶栏 + 固定底部标签导航
- 搜索过滤、Toast 通知、表单提交加载态
- CSS 动画（渐入、滑入、缩放），尊重 `prefers-reduced-motion`

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.12+) |
| 数据库 | PostgreSQL + SQLAlchemy ORM |
| 前端 | HTMX + Jinja2 模板引擎 |
| CSS | Tailwind CSS（本地构建） |
| 容器化 | Docker & Docker Compose |
| 依赖管理 | uv |
| AI | Google Gemini CLI |

## 搭建步骤

### 环境要求

- Python 3.12+
- PostgreSQL（Docker 方式无需单独安装）
- [Google Gemini CLI](https://github.com/google-gemini/gemini-cli)（AI 功能可选）
- 宿主机需安装 Docker 和 Docker Compose（Docker 方式）

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/sunxmoon/bb-private-kitchen.git
cd bb-private-kitchen

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 修改数据库密码等配置

# 3. 在宿主机启动 Gemini 代理（AI 功能可选）
cd host && bash setup.sh && cd ..
# 启动代理服务：
python3 host/gemini_proxy.py &
# 或设为 systemd 服务：参考 setup.sh 输出的服务配置

# 4. 创建外部 Docker 网络（PostgreSQL 数据库网络）
docker network create postgresql_default

# 5. 启动应用
docker-compose up --build -d
```

应用运行在 `http://localhost:8002`，默认种子用户：
- 哥哥（管理员）/ 密码：666
- 姐姐 / 密码：666
- 宝宝 / 密码：666

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

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://...` |
| `COOKIE_SECRET` | Cookie 签名密钥 | 可选，自动生成 |
| `CSRF_SECRET` | CSRF 令牌密钥 | 可选，自动生成 |
| `GEMINI_HOST_URL` | Gemini 代理地址（Docker 模式） | `http://host.docker.internal:8765` |
| `ENV` | 运行环境，`production` 时启用 Secure Cookie | — |

## 项目结构

```
.
├── app/                    # FastAPI 后端
│   ├── main.py             # 应用入口、中间件、生命周期
│   ├── models.py           # SQLAlchemy 数据模型
│   ├── schemas.py          # Pydantic 验证模型
│   ├── crud.py             # 数据库操作
│   ├── security.py         # 密码哈希、Cookie 签名
│   ├── csrf.py             # CSRF 防护
│   ├── rate_limit.py       # 登录频率限制
│   ├── gemini_client.py    # Gemini AI 客户端
│   ├── dependencies.py     # 共享依赖（认证、模板等）
│   ├── database.py         # 数据库连接
│   └── routers/            # 路由模块
│       ├── auth.py         # 登录/注销
│       ├── dishes.py       # 菜品管理
│       ├── orders.py       # 订单管理
│       ├── recipes.py      # 菜谱 + AI 生成
│       ├── admin.py        # 管理后台
│       └── history.py      # 统计看板
├── templates/              # Jinja2 模板
├── static/                 # 静态资源（CSS、上传文件）
├── tests/                  # 测试用例（91% 覆盖率）
├── host/                   # Gemini CLI 代理
│   ├── gemini_proxy.py     # HTTP 代理服务
│   └── setup.sh            # 宿主机部署脚本
├── docs/                   # 设计文档
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml          # 项目与依赖配置
├── seed_db.py              # 数据库初始化与种子数据
├── run.sh                  # 本地一键启动脚本
├── cleanup_images.py       # 孤立图片清理工具
└── requirements.txt        # pip 依赖清单
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
