# 宝宝的私房菜馆 (Private Kitchen)

一个为家庭设计的简易点菜系统。

## 技术栈
- **后端**: FastAPI (Python 3.10+)
- **数据库**: PostgreSQL
- **前端**: HTMX + Tailwind CSS + Jinja2 模板引擎
- **容器化**: Docker & Docker Compose

## 快速开始

### 1. 克隆并进入目录
```bash
git clone https://github.com/sunxmoon/bb-private-kitchen.git
cd bb-private-kitchen
```

### 2. 环境配置
复制示例环境变量文件并根据需要修改：
```bash
cp .env.example .env
```

### 3. 使用 Docker 运行 (推荐)
```bash
docker-compose up --build
```
应用将在 `http://localhost:8000` 运行。

### 4. 本地手动运行
确保已安装 Python 3.10+ 和 PostgreSQL。

1. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

2. **初始化数据库**:
   ```bash
   python3 seed_db.py
   ```

3. **启动应用**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## 项目结构
- `app/`: FastAPI 后端逻辑
- `static/`: 静态资源（图片、上传文件等）
- `templates/`: Jinja2 HTML 模板
- `tests/`: 测试脚本
- `.loki/`: 项目规范与设计文档
