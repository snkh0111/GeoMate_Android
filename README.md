# GeoMate — 威海地质野外实习助手（Android 版）

> 面向地理科学专业的移动端地质野外实习助手。本仓库为 **Android 版**：
> 将原 Web 版（FastAPI 后端 + H5 前端）改造为可在 Android 上运行的应用，最终目标为打包 APK。

## 项目简介

GeoMate 为地质野外实习提供一体化支持：

- 🔐 **账号登录**：首次进入需注册/登录，数据按用户隔离，所有页面初始为空白状态。
- 📄 **上传自动生成**：上传实习 PDF，一键自动生成实习路线、学习计划与知识库（离线规则引擎，无需 API Key）。
- 📋 **实习路线**：威海经典实习路线，含教学目标、关键观察点、注意事项、所需工具，可一键加入学习计划。
- 📖 **学习计划**：按天分组的任务清单，支持完成度跟踪、勾选完成与进度统计。
- 🧠 **知识库**：上传实习 PDF（路线指导书、岩石手册、评分标准等），自动解析、切片、嵌入，语义检索 + 分类筛选。
- 🤖 **AI 地质助教**：基于知识库的问答（RAG）+ Anthropic Claude 大模型流式回答（无 Key 自动走知识库回答）。
- 📝 **野外记录**：数字野簿，记录点位、岩性描述、产状、标本编号。

## 技术架构

```
┌───────────────────────────────┐
│  前端 frontend/（H5 静态应用）  │
│  HTML + Tailwind + Lucide     │
│  通过 fetch 调用本地后端 API   │
└──────────────┬────────────────┘
               │ http://127.0.0.1:8000
┌──────────────▼────────────────┐
│  后端 backend/（FastAPI）      │
│  SQLite + SQLAlchemy 2.0 异步  │
│  LightVectorStore（SQLite+    │
│   numpy 余弦相似度，替代       │
│   ChromaDB 以便 Android 兼容） │
│  light_embeddings（纯 numpy）  │
│  规则分析器 + Anthropic(可选)  │
└──────────────┬────────────────┘
               │ Chaquopy
┌──────────────▼────────────────┐
│        Android APK 壳         │
│  WebView + Chaquopy 内嵌服务  │
└───────────────────────────────┘
```

### 关键设计

- **Android 兼容**：移除 ChromaDB / torch / sentence-transformers 等含原生依赖的包；向量存储为 SQLite + numpy（LightVectorStore），嵌入为纯 numpy 字符 bigram 特征哈希（light_embeddings），pydantic 降级 1.x（Android 无 pydantic-core wheel）。
- **离线可用**：无 API Key 时走内置规则分析器（从章节标题/地质词库提取路线、知识点、学习任务），LLM 调用失败自动降级，上传→自动生成管线离线可跑通。
- **内嵌服务**：`android_bridge.py` 作为 Chaquopy 入口，在 Android 上于 `127.0.0.1:8000` 启动 FastAPI，WebView 前端直接访问，数据存于应用私有目录。

## 目录结构

```
GeoMate_Android/
├── android/        # Android 壳工程（WebView + Chaquopy 内嵌后端）
├── backend/        # 后端程序（FastAPI + SQLite + LightVectorStore）
│   ├── app/        #   应用代码（API / 服务 / 模型 / AI RAG）
│   ├── seed_data/  #   路线种子数据
│   ├── android_bridge.py      # Chaquopy 安卓入口
│   ├── run.py                 # 桌面端开发启动入口
│   └── requirements_android.txt
├── frontend/       # 前端程序（H5 静态应用）
│   ├── pages/      #   页面（登录/首页/路线/计划/知识库/野外记录/我的/AI 助手）
│   ├── assets/js/  #   交互脚本（api/app/nav/login/chat/routes/plans/knowledge/notes/route-detail）
│   └── assets/vendor/  # 本地化 Tailwind + Lucide（无 CDN）
└── PROGRESS.md     # 产品进度（最新）
```

## Android 打包

`android/` 为 Android 工程（WebView + Chaquopy 内嵌后端）。构建需 JDK 17 + Android SDK：

- 用 Android Studio 打开 `android/` 目录，等待 Gradle 同步
- 直接 Run 到真机调试，或 Build > Generate APK 打包
- 首次同步会下载 Gradle / AGP / Chaquopy 及 Python 依赖（需联网）

> 注：构建前需将 `frontend/` 同步到 `android/app/src/main/assets/www/`、`backend/`（app 包）同步到 `android/app/src/main/python/`。

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
