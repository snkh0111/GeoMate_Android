# 产品进度（PROGRESS）

> 最后更新：2026-08-12

## 目标

将 GeoMate（威海地质野外实习助手）由 Web 应用改造为 **Android APK**：后端可在 Android 上运行，前端为 H5 应用，最终通过 WebView + Chaquopy 打包。

## 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 创建 backend_Android，后端代码 Android 化（不改变业务逻辑） | 完成 |
| 2 | D 盘虚拟环境安装依赖，验证后端在安卓兼容环境下可运行 | 完成 |
| 3 | 前端 frontend_Android 设计（H5 静态应用） | 完成 |
| 4 | 前后端联动测试 + 交互 bug 修复 | 完成 |
| 5 | 端到端自测（后端 API / 前端页面 / AI 对话全链路） | 完成 |
| 6 | 解决 Android 兼容两大阻塞：嵌入模型（torch）与前端 CDN 依赖 | 完成 |
| 7 | 打包 APK（Android Studio Gradle + Chaquopy 集成） | 未开始 |

## 阶段详情

### 1. 后端 Android 化（backend/）

- 移除 ChromaDB（含原生依赖，Android 不兼容），自研 LightVectorStore（SQLite + numpy 余弦相似度），API 签名与原实现一致。
- 新增 android_bridge.py：Chaquopy 入口，检测 Android 运行时，自动切换到应用私有目录（ANDROID_APP_DATA_DIR）。
- requirements_android.txt：Android 兼容依赖清单。
- 业务逻辑（35+ API 端点）完全不变。

### 2. 虚拟环境测试（D:\GeoMate_Android_venv，Python 3.12）

- 后端在纯 Python + 有限依赖下完整运行，13/13 模块导入通过。
- 依赖使用清华镜像安装。

### 3. 前端设计（frontend/）

- 纯 HTML/CSS 静态设计稿：Tailwind + Lucide 图标，苹果风格配色（colors_and_type.css）。
- 页面：首页 / 路线 / 路线详情 / 学习计划 / 知识库 / 野外记录 / AI 助手 / 我的。
- assets/js/：api.js（API 客户端）、app.js（启动引导）、nav.js（导航）、route-detail.js（详情动态加载）、chat.js（SSE 对话）。

### 4. 前后端联动与修复

- 修复 ShowStatus 大小写错误；修复 querySelector 非法选择器。
- chat.js 修正接口路径（/intelligence/chat）与 SSE 事件类型（llm + text）。
- 详情页 key_points 对象数组渲染、枚举中文映射。

### 5. 端到端自测（2026-08-11）

- 后端 API：health / register / routes（7 条）/ plans（28 项）/ knowledge / chat 全部通过。
- 前端页面：8 个页面跳转正常，路线详情动态数据填充正确，计划页统计正常。
- AI 对话：fallback（无 key）模式知识库教学式回答完整链路可用。

### 6. 嵌入模型与 CDN 依赖优化（2026-08-12）

- 嵌入模型（关键阻塞）：原实现依赖 sentence-transformers + torch，Chaquopy 无法安装。
  现新增 light_embeddings.py（纯 Python + numpy，字符 bigram 特征哈希，512 维），
  embeddings.py 支持 EMBEDDING_BACKEND=auto|light|sentence-transformers 三态切换：
  Android 环境自动使用 light 后端（零 torch / 零模型下载），桌面端保持高质量语义模型。
  实测 RAG 检索链路（切片→嵌入→余弦检索→命中）全部正确。
- CDN 依赖（关键阻塞）：原 8 个页面引用 jsdelivr Tailwind 与 unpkg Lucide 外网 CDN，
  离线/Android 下样式与图标会失效。已下载 tailwind.global.js（275KB）与
  lucide.min.js（397KB）到 frontend/assets/vendor/，全部页面改为本地引用。
  浏览器实测：本地资源加载、主题色/图标渲染正常，控制台零错误。
- requirements_android.txt 移除 sentence-transformers（Android 仅需 numpy）。

## 已知问题

- Anthropic API 国内直连超时：api.anthropic.com 国内网络不稳定，LLM 模式需要代理或依赖 fallback 模式（知识库教学式回答）。
- frontend/assets/js/api.js 中 getTutorStream 指向旧路径 /intelligence/tutor/stream（未被调用，chat.js 已独立修正）。
- 知识库（向量库）初始为空，需上传实习 PDF 后才有检索内容。

## 下一步

1. Android Studio 工程搭建（Gradle + Chaquopy 插件）。
2. 前端 H5 打包进 WebView，android_bridge.py 启动内嵌 FastAPI 服务。
3. 真机联调（本地服务访问、权限、light 嵌入后端验证）。
4. 签名打包 APK。
