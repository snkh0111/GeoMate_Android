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
| 7 | 打包 APK（Android Studio Gradle + Chaquopy 集成） | 完成 |
| 8 | 登录 + 空白初始状态 + 上传 PDF 一键自动生成（路线/计划/知识库） | 完成 |
| 9 | 前端重设计 + 静态演示页接入后端真实数据 + LLM 失败自动降级 | 完成 |
| 10 | 前端编辑功能完善：学习计划行内编辑 + 野外记录编辑浮层（产状/天气）+ 知识库文档管理 | 完成 |
| 11 | 前后端全量 E2E 回归（含新功能）全部通过 + CDN 引用回归修复，重新打包 APK | 完成 |
| 12 | 删除知识库文档时级联删除其生成的路线/学习计划（兼容旧数据）+ 同步最新前后端与 APK 到 GitHub | 完成 |

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

- 纯 HTML/CSS 静态设计稿：Tailwind + Lucide 图标（本地 vendor，无 CDN），苹果风格设计令牌。
- 页面：登录 / 首页 / 路线 / 路线详情 / 学习计划 / 知识库 / 野外记录 / AI 助手 / 我的。
- assets/js/：api.js（API 客户端）、app.js（启动引导）、nav.js（导航 + 登录守卫）、route-detail.js、routes.js、plans.js、knowledge.js、notes.js、login.js、chat.js（SSE 对话）。

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

- Android Studio 解压版 D:\as（JDK 21 + SDK 35 + Gradle 8.9 + AGP 8.7.3 + Chaquopy 15.0.1）+ WebView。
- 构建命令（android/ 下）：

  ```powershell
  $env:JAVA_HOME="D:\as\jbr"; $env:ANDROID_HOME="D:\as\sdk"
  $env:HTTPS_PROXY="http://127.0.0.1:7892"; $env:HTTP_PROXY="http://127.0.0.1:7892"
  .\gradlew.bat assembleDebug --no-daemon
  ```

- 产出 app-debug.apk（36MB，arm64-v8a + armeabi-v7a），位于 android/app/build/outputs/apk/debug/。

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

### 10. 前端编辑功能完善（2026-08-13）

- **学习计划行内编辑**：plans.js 每个任务行新增「编辑任务」按钮 → 行内输入框改任务名/分类 → `PUT /plans/{id}`（仅传修改字段，后端 exclude_unset 部分更新），保存后自动刷新。
- **野外记录编辑浮层补产状/天气**：notes.js + notes.html 的编辑浮层新增「产状（∠）」与「天气」输入框；产状以 `300°∠35°` 格式输入，前端正则解析为 dip_direction/dip_angle 后 `PUT /notes/{id}`，后端自动计算 attitude 并展示在卡片。
- **知识库文档删除**：knowledge.js 文档卡片新增「删除文档」按钮 → `DELETE /knowledge/documents/{id}`（连向量块一并删除）。
- 后端能力本就完整（PUT /plans、PUT /notes、DELETE 系列），前端仅补齐交互调用，api.js 无需改动。

### 11. 全量 E2E 回归 + CDN 回归修复 + 重新打包（2026-08-13）

以学生身份（注册→登录）走通全部功能：

- 健康检查 / 注册 / 登录 / 登出 / 登录守卫 ✅
- 空白初始状态（新用户计划 0、记录为空）✅
- 上传 PDF → 一键自动生成（规则引擎离线，路线跳过重复 + 7 学习计划 + 知识库 4 片段）✅
- 路线列表 / 详情 / 加入学习计划 ✅
- 学习计划勾选完成（进度实时更新）+ **行内编辑（改任务名/分类）** ✅
- 知识库语义检索（意图自动识别，相关度命中）+ **文档删除** ✅
- 野外记录新增 + **编辑浮层（产状 310°∠62°、天气 晴）** ✅
- AI 对话离线知识库降级回答 ✅
- 个人统计与全链路数据一致 ✅
- 浏览器控制台 / 后端日志无错误 ✅

**API 级端到端测试（本次新增，26/26 通过）**：健康检查、注册、重复注册 409、登录、错误密码 401、上传 PDF、一键自动生成（mode=rule）、文档列表/详情/内容、路线列表/详情、计划列表/每日/统计/勾选、野外记录增查改 + GeoJSON、知识库统计/文档/语义检索（命中 3 条）、AI 助教 SSE 降级流式回答。

- **CDN 引用回归修复（重要）**：阶段 10 编辑功能迭代时页面被还原为外网 CDN 引用（cdn.jsdelivr.net / unpkg.com），Android 断网场景会白屏/无样式。本次回归发现后，9 个页面全部改回本地 `assets/vendor/`（tailwind.global.js + lucide.min.js），并同步修复 frontend/ 与 android/app/src/main/assets/www/ 两处副本；浏览器实测 Tailwind 样式（--tw- 变量）与 Lucide 图标正常加载、零资源错误。
- 已重新打包 APK（含以上全部功能与修复）。

### 12. 知识库删除级联删除 + 同步最新产物（2026-08-13）

- **删除知识库文档时级联删除其生成的路线/学习计划**：`KnowledgeService.delete_document` 补齐完整级联兜底，依次按三种来源收集 route/plan ID 再删除：
  1. `parsed_content["generated"]` 里 auto-generate 写入的 ID；
  2. `source_document_id` 反查（新增字段，新数据）；
  3. 按路线名 / 任务名反查（更早的旧数据，`source_document_id` 为 NULL）。
- 同时删除来源分析文档（AnalysisDocument）、向量 chunks、共享 PDF 文件，并 commit。
- **数据模型与迁移**：`KnowledgeDocument / FieldRoute / StudyPlan` 新增 `source_document_id`（来源分析文档 ID），`database.py` 的 `_run_dev_migrations` 用 `ALTER TABLE ... ADD COLUMN` 为老设备轻量补列，避免丢数据。
- **验证**：桌面临时脚本覆盖「旧数据 NULL + generated 兜底」与「新数据 source_document_id」两场景均通过；真机 `adb install -r` 后后端正常启动、`/health 200`。用户确认「非常完美」。
- 本次已把最新 frontend / backend / android 源码与 APK（release/GeoMate-debug.apk）同步并提交到 GitHub。

## 踩坑记录

- **chaquo.com 国内访问不稳**：构建须走 http://127.0.0.1:7892 代理（Clash 混合端口；socks 需 PySocks，勿用）+ pip 超时重试（build.gradle 已配 --timeout 120 --retries 10）。
- **pydantic-core 无 Android wheel**：必须用 pydantic 1.10.17 + fastapi 0.99.1；全库适配 v1 API（model_validate → from_orm/parse_obj），**新增代码禁止再写 model_validate/model_dump**。
- **requirements 相对路径**：Android 依赖清单必须用相对路径形式。
- **清华镜像覆盖 Chaquopy 索引**：会拉不到 Android wheel，需移除镜像配置。
- **CDN 引用易在迭代中回归**：页面改版/新增功能时若从旧模板复制，可能把 `<script src="../assets/vendor/...">` 还原成外网 CDN 链接。每次改动后应全局搜索 `cdn.jsdelivr.net|unpkg.com` 确认零残留（本次已补到 9 个页面并三处同步）。
- **桌面嵌入后端 HF 下载卡死（2026-08-13）**：桌面 EMBEDDING_BACKEND=auto 会走 sentence-transformers 加载 BAAI/bge-small-zh-v1.5，模型未缓存时从 HuggingFace 下载，国内直连超时 → /knowledge/search 卡死数十秒。解决：backend_Android/.env 设 `EMBEDDING_BACKEND=light`（与 Android 完全一致，纯 numpy 离线可用，零模型下载）。
- **greenlet / aiosqlite 无 Android wheel（2026-08-13）**：SQLAlchemy async 依赖 greenlet C 扩展，Chaquopy 只能装 wheel → 全后端 async→sync 改造（create_engine + Session + 同步端点）。任何依赖 C 扩展且无 Android wheel 的库（greenlet、pydantic-core、PyMuPDF、chromadb）都不能用。
- **级联删除必须兼容旧数据（2026-08-13）**：仅按新增的 `source_document_id` 匹配会漏掉早期生成的 NULL 行，必须用 `generated` ID + 名称反查兜底。

## 已知问题

- Anthropic API 国内直连超时：LLM 模式需代理；无 key 或调用失败时自动走离线规则引擎/知识库 RAG，不影响使用。
- HuggingFace 模型下载国内不可用：桌面若用 sentence-transformers 后端需代理或预缓存模型；默认 .env 建议 EMBEDDING_BACKEND=light。
- 规则引擎生成的路线名/任务名带章节序号前缀（前端已清洗展示）。
- 知识库初始为空，由用户上传 PDF 后自动填充。
- **从 PDF 中搜索/语义检索能力仍有欠缺**：当前 LightEmbeddings（字符 bigram 特征哈希 512 维）+ LightVectorStore（SQLite + numpy 余弦相似度）为离线零依赖方案，检索相关性/召回不如真正的语义嵌入模型，遇到同义表述、跨句检索时命中质量有限（见下一步）。

## 下一步

1. **优化 PDF 语义搜索/检索能力**（当前欠缺点）：改进 LightEmbeddings 的分词与特征（如中文分词、n-gram 权重、关键词提取、BM25 混合检索、重排等），在不引入 torch/sentence-transformers 的前提下提升知识库语义检索的召回与相关度排序。
2. 真机联调最新 APK（含登录/空白状态/上传自动生成/编辑功能 + 级联删除修复 + CDN 本地化修复）。
3. 应用图标、release 签名、构建机 Python 对齐 3.11（消除 .pyc 编译警告）。
