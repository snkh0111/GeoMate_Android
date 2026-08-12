# 产品进度（PROGRESS）

> 最后更新：2026-08-13

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
| 7 | 打包 APK（Android Studio Gradle + Chaquopy 集成） | ✅ 完成 |
| 8 | 登录 + 空白初始状态 + 上传 PDF 一键自动生成（路线/计划/知识库） | ✅ 完成 |
| 9 | 前端重设计 + 静态演示页接入后端真实数据 + LLM 失败自动降级 | ✅ 完成 |

## 阶段详情

### 1. 后端 Android 化（backend/）

- 移除 ChromaDB（含原生依赖，Android 不兼容），自研 LightVectorStore（SQLite + numpy 余弦相似度），API 签名与原实现一致。
- 新增 android_bridge.py：Chaquopy 入口，检测 Android 运行时，自动切换到应用私有目录（ANDROID_APP_DATA_DIR）。
- requirements_android.txt：Android 兼容依赖清单（fastapi 0.99.1 + pydantic 1.10.17 + numpy + pypdf）。
- 业务逻辑（35+ API 端点）完全不变。

### 2. 虚拟环境测试（D:\GeoMate_Android_venv）

- 后端在纯 Python + 有限依赖下完整运行，13/13 模块导入通过。
- 桌面 venv 已与 Android 对齐：pydantic 1.10.17 + fastapi 0.99.1（消除 pydantic 2 与 1 的 API 差异）。

### 3. 前端设计（frontend/）

- 纯 HTML/CSS 静态设计稿：Tailwind + Lucide 图标（本地 vendor，无 CDN），苹果风格设计令牌 v4。
- 页面：登录 / 首页 / 路线 / 路线详情 / 学习计划 / 知识库 / 野外记录 / AI 助手 / 我的。
- assets/js/：api.js（API 客户端）、app.js（启动引导）、nav.js（导航）、route-detail.js、routes.js、plans.js、knowledge.js、notes.js、login.js、chat.js（SSE 对话）。

### 4. 前后端联动与修复

- 修复 ShowStatus 大小写错误；修复 querySelector 非法选择器。
- chat.js 修正接口路径（/intelligence/chat）与 SSE 事件类型（llm + text）。
- 详情页 key_points 对象数组渲染、枚举中文映射。

### 5. 端到端自测（2026-08-11）

- 后端 API：health / register / routes / plans / knowledge / chat 全部通过。
- 前端页面：页面跳转正常，路线详情动态数据填充正确，计划页统计正常。
- AI 对话：fallback（无 key）模式知识库教学式回答完整链路可用。

### 6. 嵌入模型与 CDN 依赖优化（2026-08-12）

- 嵌入模型（关键阻塞）：原实现依赖 sentence-transformers + torch，Chaquopy 无法安装。现新增 light_embeddings.py（纯 Python + numpy，字符 bigram 特征哈希，512 维），EMBEDDING_BACKEND=auto|light|sentence-transformers 三态切换，Android 自动使用 light（零 torch）。实测 RAG 全链路命中正确。
- CDN 依赖（关键阻塞）：8+ 页面引用外网 CDN，已下载 tailwind.global.js + lucide.min.js 到 assets/vendor/，全部页面本地引用，控制台零错误。

### 7. APK 打包（2026-08-12）

- Android Studio 解压版 D:\as（JDK21 + SDK 35 + Gradle 8.9）+ Chaquopy 15.0.1 + WebView。
- 构建链路关键修复：pydantic-core 无 Android wheel → 降级 pydantic 1.x + fastapi 0.99（全库适配 v1 API：model_validate→from_orm/parse_obj）；chaquo.com 超时 → 走 http://127.0.0.1:7892 代理 + pip 超时重试。
- 产出 app-debug.apk（36MB，arm64-v8a + armeabi-v7a）。

### 8. 登录 + 空白初始状态 + 上传自动生成（2026-08-12）

- 新增登录/注册页（login.html + login.js），后端 POST /users/login（SHA-256 校验），会话存 localStorage，nav.js 全局登录守卫。
- 移除 app.js 自动注册与 seed；home 首页真实统计（0 初始）+ 空状态引导。
- 上传 PDF → POST /documents/{id}/auto-generate 一键管线：解析→分析→生成路线→生成计划→知识库入库。
- 离线规则分析器 rule_analyzer.py：无 Anthropic Key 时从章节标题/地质词库提取路线、知识点、学习任务（与 LLM 输出同构）。
- 后端"未启动"三根因修复：config.py 目录解析时序（Android 直接取应用私有目录）、android_bridge.py 环境初始化提前 + 移除模块级自动启动、CORS 白名单加 null。

### 9. 前端重设计 + 静态页接后端 + LLM 降级（2026-08-13）

- 用户重新设计前端后，修复回归：login.js 开发模式登录 → 真实账号密码；autoGenerate 分步漏知识库 → 一键接口；首页统计 total→total_tasks；CDN 引用回归 → 全部改回本地 vendor。
- **四个静态演示页全部接入后端真实数据**（UI 设计不变，仅替换数据源）：
  - routes.html → routes.js：真实路线列表（清洗规则引擎序号前缀）+ 类型筛选 + 空状态。
  - plans.html → plans.js：/plans/daily 每日分组 + /plans/stats 进度 + 点击任务行 PATCH toggle 勾选完成。
  - knowledge.html → knowledge.js：真实统计/文档列表 + /knowledge/search 语义检索 + 分类筛选 + 上传 PDF 入库。
  - notes.html → notes.js：/notes 真实记录 + 路线筛选 + 「新增记录」真实创建。
- 路线详情联动：nav.js 卡片改传 route id，route-detail.js 用 GET /routes/{id} 拉取真实数据，「加入学习计划」按钮真实调用 POST /plans/ 创建。
- profile.html 统计字段修正（completed → completed_tasks）。
- intelligence_service.py：LLM 调用失败自动降级规则引擎（rule_fallback），管线永不因网络失败中断。
- 端到端回归全部通过：注册登录 → 空白首页 → 上传自动生成 → 路线列表/详情/加入计划 → 计划勾选 → 知识库搜索 → 野外记录新增 → 个人统计。

## 已知问题

- Anthropic API 国内直连超时：LLM 模式需代理；无 key 或调用失败时自动走离线规则引擎/知识库 RAG，不影响使用。
- 规则引擎生成的路线名/任务名带章节序号前缀（前端已清洗展示）。
- 知识库初始为空，由用户上传 PDF 后自动填充。

## 下一步

1. 重新构建 APK（含登录/空白/自动生成 + 静态页接后端全部修复）后真机联调。
2. 应用图标、release 签名、构建机 Python 对齐 3.11。
