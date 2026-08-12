# GeoMate — 威海地质野外实习助手（Android 版）

> 面向地理科学专业的移动端地质野外实习助手。本仓库为 **Android 版**：
> 将原 Web 版（FastAPI 后端 + H5 前端）改造为可在 Android 上运行的应用，最终目标为打包 APK。

## 项目简介

GeoMate 为地质野外实习提供一体化支持：

- 🔐 **账号登录**：首次进入需注册/登录（SHA-256 密码校验），数据按用户隔离，所有页面初始为空白状态。
- 📄 **上传自动生成**：上传实习 PDF，一键自动生成实习路线、学习计划与知识库（离线规则引擎，无需 API Key）。
- 📋 **实习路线**：威海经典实习路线，含教学目标、关键观察点、注意事项、所需工具，可一键加入学习计划。
- 📖 **学习计划**：按天分组的任务清单，支持完成度跟踪、勾选完成与进度统计。
- 🧠 **知识库**：上传实习 PDF（路线指导书、岩石手册、评分标准等），自动解析、切片、嵌入，语义检索 + 分类筛选。
- 🤖 **AI 地质助教**：基于知识库的问答（RAG）+ Anthropic Claude 大模型流式回答（无 Key 或调用失败自动走离线规则引擎/知识库回答）。
- 📝 **野外记录**：数字野簿，记录点位、岩性描述、产状、标本编号。

## 技术架构

```
┌───────────────────────────────┐
│  前端 frontend/（H5 静态应用）  │
│  HTML + Tailwind + Lucide     │
│  （资源本地化，无外网 CDN）     │
│  通过 fetch 调用本地后端 API   │
└──────────────┬────────────────┘
               │ http://127.0.0.1:8000
┌──────────────▼────────────────┐
│  后端 backend/（FastAPI）      │
│  SQLite + SQLAlchemy          │
│  LightVectorStore（SQLite+    │
│   numpy 余弦相似度，替代       │
│   ChromaDB 以便 Android 兼容） │
│  LightEmbeddings（字符 bigram │
│   特征哈希 512 维，零 torch）  │
│  离线规则分析器 + Claude(可选) │
└──────────────┬────────────────┘
               │ Chaquopy
┌──────────────▼────────────────┐
│        Android APK 壳         │
│  WebView + Chaquopy 内嵌服务  │
└───────────────────────────────┘
```

### 关键设计

- **Android 兼容**：移除 ChromaDB / torch / sentence-transformers 等含原生依赖的包；向量存储为 SQLite + numpy（LightVectorStore），嵌入为纯 numpy 字符 bigram 特征哈希（light_embeddings，EMBEDDING_BACKEND=auto|light|sentence-transformers 三态切换），pydantic 降级 1.x（Android 无 pydantic-core wheel），PDF 解析优先 PyMuPDF、失败回退 pypdf。
- **离线可用**：无 API Key 时走内置规则分析器（从章节标题/地质词库提取路线、知识点、学习任务），LLM 调用失败自动降级，上传→自动生成管线离线可跑通。
- **内嵌服务**：`android_bridge.py` 作为 Chaquopy 入口，在 Android 上于 `127.0.0.1:8000` 启动 FastAPI，WebView 前端直接访问，数据存于应用私有目录。

## 目录结构

```
GeoMate_Android/
├── android/        # Android 壳工程（WebView + Chaquopy 内嵌后端）
│   └── app/src/main/
│       ├── assets/www/   # 前端 H5（与 frontend/ 同步）
│       ├── python/       # 后端 Python（与 backend/ 同步）+ android_bridge.py + requirements.txt
│       └── java/…        # MainActivity（WebView + 后端启动）
├── backend/        # 后端程序（FastAPI + SQLite + LightVectorStore）
│   ├── app/ai/rule_analyzer.py      # 离线规则分析器（无 key 兜底）
│   ├── app/ai/rag/light_embeddings.py  # 轻量嵌入（零 torch）
│   ├── app/ai/rag/light_store.py       # 轻量向量库（替代 ChromaDB）
│   ├── android_bridge.py          # Chaquopy 安卓入口
│   ├── run.py                     # 桌面端开发启动入口
│   └── requirements_android.txt
├── frontend/       # 前端程序（H5 静态应用）
│   ├── pages/      #   页面（登录/首页/路线/计划/知识库/野外记录/AI 助手/我的）
│   ├── assets/js/  #   交互脚本（api/app/nav/login/chat/routes/plans/knowledge/notes/route-detail）
│   ├── assets/vendor/  # 本地化 Tailwind + Lucide（无 CDN）
│   └── colors_and_type.css
└── PROGRESS.md     # 产品进度（最新）
```

## Android 打包

`android/` 为 Android 工程（WebView + Chaquopy 内嵌后端）。构建需 JDK 21 + Android SDK + Gradle 8.9（AGP 8.7.3 + Chaquopy 15.0.1）：

```powershell
$env:JAVA_HOME="D:\as\jbr"; $env:ANDROID_HOME="D:\as\sdk"
$env:HTTPS_PROXY="http://127.0.0.1:7892"; $env:HTTP_PROXY="http://127.0.0.1:7892"
cd android
.\gradlew.bat assembleDebug --no-daemon
```

> 注：
> - 构建前需将 `frontend/` 同步到 `android/app/src/main/assets/www/`、`backend/`（app 包）同步到 `android/app/src/main/python/`。
> - Chaquopy 需从 chaquo.com 拉取 Python 依赖，国内网络不稳定必须走代理（或自行配置镜像），build.gradle 已内置 `--timeout 120 --retries 10`。
> - 产物：`android/app/build/outputs/apk/debug/app-debug.apk`（约 36MB，arm64-v8a + armeabi-v7a）。

## 快速开始（桌面端开发测试）

### 后端

```bash
cd backend
pip install -r requirements_android.txt
cp .env.example .env   # ANTHROPIC_API_KEY 留空即可用离线规则引擎
python run.py          # http://127.0.0.1:8000
```

### 前端

```bash
cd frontend
python -m http.server 5173 --bind 127.0.0.1
# 浏览器访问 http://127.0.0.1:5173/pages/login.html
```

## 产品进度

最新进度详见 [PROGRESS.md](PROGRESS.md)。

## License

本项目仅供学习交流使用。
