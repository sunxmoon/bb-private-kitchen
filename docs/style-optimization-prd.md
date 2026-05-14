# PRD：首屏样式加载优化 — 消除 FOUC

## 1. Executive Summary

**Problem**：当前使用 Tailwind Play CDN（`cdn.tailwindcss.com`）在客户端运行时动态生成样式。移动端网络环境下，HTML 先渲染完毕，CDN 样式数秒后才加载完成，导致页面出现无样式闪烁（FOUC），视觉割裂严重。

**Solution**：将 Tailwind CSS 从 CDN 运行时模式改为**构建时静态生成**，在 Docker build 阶段扫描模板提取用到的 class，输出优化后的 CSS 文件，与应用静态资源一同部署。

**Success Criteria**：
- 首次加载页面时，样式与 HTML 同时呈现，无 FOUC
- 静态 CSS 文件体积 ≤ 150KB（gzip 后 ≤ 30KB）
- Lighthouse Performance 评分 ≥ 85（当前基线待测）
- 首屏可交互时间（TTI）降低 ≥ 40%

---

## 2. User Experience & Functionality

### User Personas

| 角色 | 设备 | 当前问题 |
|------|------|---------|
| 家庭成员（手机端） | iPhone/Android · 4G/WiFi | 每次打开页面先看到白底黑字，0.5~3秒后样式才生效 |
| 管理员（家庭主厨） | 手机为主，偶尔桌面 | 滑动浏览菜品时感到卡顿和闪烁 |

### User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-01 | 作为手机用户，我打开页面时应该直接看到完整的样式，而不是先看到原始 HTML 再等待样式加载 | • 页面首次 paint 时字体、颜色、布局均已正确<br>• `<body>` 默认不可见直到 CSS 加载完成 |
| US-02 | 作为家庭成员，我希望页面在任何网络条件下都能快速展示完整 UI | • 弱网环境（Slow 3G 模拟）下首屏样式在 1.5s 内呈现<br>• CSS 文件与应用同源，无 DNS/SSL 额外开销 |

### Non-Goals
- 不重构 Tailwind 的使用方式（保留现有 class 用法）
- 不替换 Font Awesome / HTMX CDN（仅优化加载策略）
- 不引入前端构建工具链（Webpack / Vite）
- 不修改现有模板结构

---

## 3. Technical Specifications

### 现状分析

```
当前加载顺序：
  HTML 解析 → <script src="cdn.tailwindcss.com"> 发起请求
           → HTML 继续渲染（无样式）
           → CDN 响应 → Tailwind JS 解析 DOM → 注入 <style> → 样式生效
```

三个 CDN 资源：
| 资源 | 大小 | 影响 |
|------|------|------|
| `cdn.tailwindcss.com` | ~300KB JS | ✗ FOUC 主因 |
| `cdnjs.cloudflare.com/.../font-awesome` | ~60KB CSS | ✗ 图标延迟 |
| `unpkg.com/htmx.org` | ~14KB JS | ✓ 无视觉影响 |

### 方案 A（推荐）：Tailwind CLI 静态生成

```
构建步骤：
  tailwind.config.js (扫描模板路径)
       ↓
  static/css/input.css (@tailwind directives)
       ↓
  tailwindcss -i input.css -o static/css/output.css --minify
       ↓
  static/css/tailwind.min.css (~30KB gzipped)

加载顺序：
  HTML 解析 → <link href="tailwind.min.css">（已缓存）
           → HTML 继续渲染（样式立即可用）
```

**所需依赖**：
- `tailwindcss` v3 可执行文件（通过 Standalone CLI 二进制下载，约 40MB，仅构建阶段需要）

**Standalone CLI 方式**（无需 Node.js）：
```dockerfile
ADD https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
RUN chmod +x /usr/local/bin/tailwindcss
RUN tailwindcss -i static/css/input.css -o static/css/output.css --minify
```

### 配置文件

**`tailwind.config.js`**：
```js
module.exports = {
  content: ["./templates/**/*.html"],
  theme: { extend: {} },
  plugins: [],
}
```

**`static/css/input.css`**：
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 方案 B（兜底）：CDN + 预加载优化

如果构建阶段增加 tailwindcss 二进制不可接受，可采用以下方案缓解 FOUC：

```html
<!-- head 中增加 preconnect + preload -->
<link rel="preconnect" href="https://cdn.tailwindcss.com">
<link rel="preconnect" href="https://cdnjs.cloudflare.com">
<style>
  /* 关键 CSS 内联：隐藏 body 直到 Tailwind 就绪 */
  body { opacity: 0; }
  body.tailwind-ready { opacity: 1; transition: opacity 0.1s; }
</style>
<script>
  // Tailwind 加载完成后显示页面
  window.addEventListener('load', () => {
    document.body.classList.add('tailwind-ready');
  });
</script>
```

### 推荐实施路径

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1 | 创建 `tailwind.config.js`，配置 content 路径 | 基础配置 |
| 2 | 创建 `static/css/input.css`，添加 `@tailwind` 指令 | 入口文件 |
| 3 | 在 Dockerfile 增加构建步骤（下载 Standalone CLI + 编译） | 生成 CSS |
| 4 | 修改 `base.html`，移除 CDN script，引入本地 CSS | 无 FOUC |
| 5 | Font Awesome 增加 preconnect + 本地 fallback | 图标提速 |
| 6 | 测试验证（慢网速模拟 + Lighthouse） | 数据 |

---

## 4. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `tailwind.config.js` | 新增 | Tailwind CLI 配置 |
| `static/css/input.css` | 新增 | Tailwind 源文件 |
| `static/css/tailwind.min.css` | 生成产物 | 编译后的 CSS（加入 .gitignore） |
| `templates/base.html` | 修改 | 移除 CDN script，引入本地 CSS，增加 preconnect |
| `Dockerfile` | 修改 | 增加 tailwind Standalone CLI 下载 + 编译步骤 |
| `.dockerignore` | 修改 | 保留 `node_modules` 相关规则 |
| `.gitignore` | 修改 | 忽略生成的 `tailwind.min.css` |

---

## 5. Risks & Roadmap

### Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tailwind Standalone CLI 下载失败（GitHub releases 不可达） | Low | 方案 B 兜底，或改用 npm 安装 |
| 生成的 CSS 遗漏某些动态 class（如拼接的 class 名） | Medium | Tailwind CLI 支持 `safelist` 配置；所有动态 class 显式列出 |
| CSS 文件未及时更新导致样式缺失 | Low | Docker build 阶段总是重新生成 |
| Standalone CLI 版本与 Tailwind 特性不兼容 | Low | 锁定版本号 v3.4.17 |

### Roadmap

| Phase | Scope | Time |
|-------|-------|------|
| **Phase 1** | tailwind.config.js + input.css + base.html 修改 + .gitignore | 30min |
| **Phase 2** | Dockerfile 构建步骤 + Docker 测试 build | 30min |
| **Phase 3** | 慢网速模拟验证 + 调整 fonts/icons 加载策略 | 30min |
| **Phase 4** | 部署到服务器验证 | 15min |

---

## 6. A/B 验证

| 指标 | 优化前（CDN） | 优化后（本地） | 工具 |
|------|-------------|-------------|------|
| 首次内容渲染（FCP） | 基线 | 降低 ≥40% | Chrome DevTools / Lighthouse |
| 样式可见时间 | 0.5~3s 延迟 | 与 HTML 同步 | 手机 Slow 3G 模拟 |
| CSS 请求数 | 2（Tailwind + FA） | 1（本地 tailwind.min.css） | Network panel |
| 传输大小 | ~360KB | ≤ 150KB | Network panel |
