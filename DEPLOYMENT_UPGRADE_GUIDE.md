# 宝宝的私房菜馆 — Docker Compose 生产环境升级部署指南

本文档详细说明如何在生产服务器上通过 Docker Compose 平滑升级「宝宝的私房菜馆」应用至最新版本。

---

## 升级概览

本次升级包含如下变更：
1. **前端交互重构**：引入点餐篮（购物车）多选与批量点餐功能（`static/js/cart.js`）、客户端图片压缩（`static/js/compress.js`）、响应式居中卡片布局、操作防抖与防重提交。
2. **后端能力增强**：新增批量下单接口 `/api/orders/batch`、单用户多端登录状态控制（`token_version`）、SSE 订单事件精准推送。
3. **数据库结构迁移**：
   - `005_add_pg_trgm_index`：启用 PostgreSQL `pg_trgm` 扩展并建立菜品名称三元组 GIN 索引，优化模糊搜索。
   - `006_add_user_token_version`：向 `users` 表添加 `token_version` 字段（默认值 1），支持单点/全端登出安全机制。
4. **自动化执行**：应用容器启动时（FastAPI Lifespan）会自动触发 Alembic 执行增量数据库迁移，无需手工登入容器跑迁移命令。

---

## 前置准备与环境确认

### 1. 确认服务器运行环境
登录生产服务器，进入项目部署根目录：
```bash
cd /path/to/bb-private-kitchen   # 替换为实际部署目录
```

### 2. 检查当前容器运行状态
```bash
docker compose ps
```
确保 `web` 容器正在运行，且绑定的外部 PostgreSQL 网络正常存在：
```bash
docker network inspect postgresql_default >/dev/null && echo "✅ 数据库网络正常" || echo "❌ 数据库网络不存在"
```

---

## 升级步骤

### 第一步：备份数据库（强烈建议）
在执行任何代码与数据库迁移前，先执行一次数据库全量逻辑备份：

```bash
# 1. 创建备份目录
mkdir -p ./backups

# 2. 从运行中的 PostgreSQL 容器导出数据库备份（假设容器名为 postgresql 或查 docker ps 确定）
# 如果你的 PostgreSQL 容器名称不同，请将下方的 postgres 替换为实际容器名
docker exec -t $(docker ps -q -f name=postgres) pg_dump -U postgres bb_kitchen > ./backups/bb_kitchen_pre_upgrade_$(date +%Y%m%d_%H%M%S).sql

# 3. 检查备份文件大小与内容
ls -lh ./backups/
```

> **提示**：如果数据库账号或数据库名有自定义，请使用 `.env` 中配置的 `DATABASE_URL` 参数对应的账号和数据库名称。

---

### 第二步：同步最新代码
拉取 Git 仓库的最新代码：

```bash
# 检查本地工作区是否有未提交修改
git status

# 拉取最新主分支代码
git fetch origin
git pull origin main
```

检查本次更新的代码文件：
```bash
git log -n 3 --oneline
```

---

### 第三步：重新构建镜像
本次更新包含前端 Tailwind CSS 编译和静态资源更新，推荐使用 `--no-cache` 参数重新构建 `web` 镜像，确保所有新资源和编译产物 100% 打包：

```bash
docker compose build --no-cache web
```

构建过程中注意观察：
- Tailwind CSS 自动化下载与编译是否输出：`Done in ...ms`。
- Python 依赖安装与两阶段构建无报错。

---

### 第四步：平滑重启容器
重新创建并后台启动 `web` 服务容器：

```bash
docker compose up -d web
```

> **注意**：
> - `docker compose up -d` 会停止旧容器并使用新镜像创建新容器。
> - 本项目的菜品图片保存在 Docker 命名卷 `uploads`（挂载在 `/app/static/uploads`），数据卷会被自动挂载保留，**已上传的图片不会丢失**。

---

### 第五步：验证升级与日志检查

#### 1. 查看容器启动日志
重点检查 Alembic 自动迁移记录与 Uvicorn 启动信息：
```bash
docker compose logs -f web --tail=50
```

**预期正常日志包含**：
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 004 -> 005, add pg_trgm_index
INFO  [alembic.runtime.migration] Running upgrade 005 -> 006, add_user_token_version
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

按 `Ctrl + C` 退出日志跟踪。

#### 2. 检查健康检查状态
```bash
# 状态应为 Up ... (healthy)
docker compose ps web
```

#### 3. 验证 HTTP 接口响应
```bash
# 本地测试健康检查端点（映射端口为 8002）
curl -I http://127.0.0.1:8002/health
```
**预期输出**：
```http
HTTP/1.1 200 OK
content-type: application/json
```

---

### 第六步：页面与功能验证清单

通过浏览器访问 `http://<服务器IP或域名>:8002`：

| 模块 | 检查项目 | 预期效果 |
| :--- | :--- | :--- |
| **登录状态** | 登录已有账号（如 哥哥 / 666） | 成功进入，Token 校验正常（`token_version` 生效） |
| **菜品广场** | 列表与分类展示 | 菜品卡片比例协调，分类切换流畅 |
| **点餐交互** | 点击菜品底部的 `+` 按钮 | 底部浮动点餐篮弹出，徽标数量准确自增 |
| **点餐篮抽屉** | 点击底部浮动点餐栏 | 弹出侧边/底部购物车抽屉，可增减份数、选择偏好口味与时间 |
| **批量点餐提交** | 点击「确认下单」 | 成功提交并提示「点餐成功！」，跳转到我的订单页面 |
| **我的订单** | 查看订单列表与状态 | 订单信息完整显示，SSE 实时通信正常 |
| **图片上传** | 添加新菜品上传图片 | 客户端控制台可看到压缩提示，上传快速且清晰 |

---

## 应急回滚预案（Rollback Plan）

如果在升级后发现严重异常，请按以下步骤快速回滚到升级前的状态：

### 1. 切换回滚代码版本
```bash
# 切换至上一个稳定 commit 或 tag
git checkout HEAD~1   # 或指定 Commit ID: git checkout <previous_commit_hash>
```

### 2. 重新编译并拉起旧版本镜像
```bash
docker compose build --no-cache web
docker compose up -d web
```

### 3. （如必要）回滚数据库迁移
如果需要将数据库结构回滚到 004 版本：
```bash
# 进入运行中的容器执行 alembic downgrade
docker compose exec web alembic downgrade 004
```

### 4. （极端情况）恢复数据库快照
如果在迁移中发生数据损坏，可使用第一步备份的 SQL 还原：
```bash
cat ./backups/bb_kitchen_pre_upgrade_*.sql | docker exec -i $(docker ps -q -f name=postgres) psql -U postgres -d bb_kitchen
```

---

## 常见问题排查（FAQ）

### Q1: 提示 `network postgresql_default not found`
- **原因**：外部 PostgreSQL 容器所属的网络名称与 `docker-compose.yml` 中的配置不匹配。
- **解决**：运行 `docker network ls` 查看当前运行的数据库容器实际使用的网络名称，并检查 `docker-compose.yml` 中的 `networks.database_postgres.name`。

### Q2: 浏览器界面样式好像还是旧的？
- **原因**：浏览器 HTTP 强缓存或 CDN 缓存。
- **解决**：按 `Ctrl + F5`（Mac 为 `Cmd + Shift + R`）强制刷新浏览器；模板中的静态文件链接已升级带有版本号 `?v=2.2`。

### Q3: 提示 `permission denied` 上传图片失败？
- **原因**：宿主机 Docker 卷权限变动。
- **解决**：容器内是以 `appuser` (uid 1000) 运行的，运行以下命令修正卷权限：
  ```bash
  docker compose exec -u 0 web chown -R appuser:appgroup /app/static/uploads
  ```
