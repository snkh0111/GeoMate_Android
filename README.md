# GeoMate — 威海地质野外实习助手（Android 版）

> 面向地理科学专业的移动端地质野外实习助手。本仓库为 **Android 版**：
> 将原 Web 版（FastAPI 后端 + H5 前端）改造为可在 Android 上运行的应用，最终目标为打包 APK。

## 项目简介

GeoMate 为地质野外实习提供一体化支持：

- 📋 **实习路线**：威海 7 条经典实习路线（占甲埠村花岗岩、马山火山岩、棉花山沉积岩、刘公岛变质岩、鸡鸣岛海岸地貌、成山头海蚀地貌、温泉镇地热构造），含教学目标、关键观察点、注意事项、所需工具。
- 📖 **学习计划**：7 天实习任务清单，按天分组，支持完成度跟踪与统计。
- 🧠 **知识库**：上传实习 PDF（路线指导书、岩石手册、评分标准等），自动解析、切片、嵌入，语义检索。
- 🤖 **AI 地质助教**：基于知识库的问答（RAG）+ Anthropic Claude 大模型流式回答。
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
│  BAAI/bge-small-zh-v1.5 嵌入   │
│  Anthropic Claude（可选）     │
└──────────────┬────────────────┘
               │ Chaquopy
┌──────────────▼────────────────┐
│        Android APK 壳         │
│  WebView + Chaquopy 内嵌服务  │
└───────────────────────────────┘
```

### 关键设计

- **Android 兼容**：移除 ChromaDB 等含原生依赖的包，向量存储改为 SQLite + numpy 实现（`LightVectorStore`，API 与原实现一致）。
- **内嵌服务**：`android_bridge.py` 作为 Chaquopy 入口，在 Android 上于 `127.0.0.1:8000` 启动 FastAPI，WebView 前端直接访问。
- **本地优先**：数据、知识库均存于应用私有目录，离线可用。

## 目录结构

```
GeoMate_Android/
├── backend/        # 后端程序（FastAPI + SQLite + LightVectorStore）
│   ├── app/        #   应用代码（API / 服务 / 模型 / AI RAG）
│   ├── seed_data/  #   路线种子数据
│   ├── android_bridge.py      # Chaquopy 安卓入口
│   ├── run.py                 # 桌面端开发启动入口
│   └── requirements_android.txt
├── frontend/       # 前端程序（H5 静态应用）
│   ├── pages/      #   页面（首页/路线/计划/知识库/野外记录/我的/AI 助手）
│   ├── assets/js/  #   交互脚本（导航/API 客户端/路由详情/对话）
│   └── colors_and_type.css
└── PROGRESS.md     # 产品进度（最新）
```

## 快速开始（桌面端开发测试）

### 后端

```bash
cd backend
pip install -r requirements_android.txt
cp .env.example .env   # 配置 ANTHROPIC_API_KEY（可选）
python run.py          # http://127.0.0.1:8000
```

### 前端

```bash
cd frontend
python -m http.server 5173 --bind 127.0.0.1
# 浏览器访问 http://127.0.0.1:5173/pages/home.html
```

## 产品进度

最新进度详见 [PROGRESS.md](PROGRESS.md)。

## License

本项目仅供学习交流使用。
