"""Android bridge — Chaquopy entry point for embedded FastAPI server.

Called from Android Java/Kotlin via:
    Python.getInstance().getModule("android_bridge").callAttr("start_server")

Starts the FastAPI server on localhost so the WebView frontend can connect.
"""

import asyncio
import logging
import os
import sys
import threading

import uvicorn

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Detect if running on Android (via Chaquopy)
IS_ANDROID = hasattr(sys, "getandroidapilevel") or "chaquopy" in sys.modules

# 最近一次启动错误（供 UI 通过 get_last_error() 展示定位）
LAST_ERROR = ""


def _setup_android_env():
    """Set environment variables for Android runtime."""
    if not IS_ANDROID:
        return

    from java import jclass  # type: ignore

    try:
        context = jclass("com.chaquo.python.Python").getApplicationContext()
        app_data = context.getFilesDir().getAbsolutePath()
        os.environ["ANDROID_APP_DATA_DIR"] = app_data
        logger.info("Android app data dir: %s", app_data)
    except Exception as e:
        logger.warning("Could not get Android context: %s", e)


# Must run BEFORE importing app.config: config.py resolves BASE_DIR from
# ANDROID_APP_DATA_DIR on Android. (config.py also falls back to resolving the
# app-private dir itself, so this is a belt-and-braces approach.)
if IS_ANDROID:
    _setup_android_env()

from app.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


def get_last_error() -> str:
    """返回最近一次后端启动错误（供 Android UI 展示定位）。"""
    return LAST_ERROR


def _set_error(tag: str, exc: Exception) -> None:
    """记录启动异常：写入内存变量 + 应用目录日志文件。"""
    global LAST_ERROR
    import traceback

    tb = traceback.format_exc()
    LAST_ERROR = f"[{tag}] {exc}\n{tb[-1500:]}"
    logger.error("GeoMate backend error: %s", LAST_ERROR)
    try:
        base = os.environ.get("ANDROID_APP_DATA_DIR", ".")
        with open(os.path.join(base, "geomate_backend.log"), "a", encoding="utf-8") as f:
            f.write(f"\n===== {tag} =====\n{LAST_ERROR}\n")
    except Exception:
        pass


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the FastAPI server. Blocks until the server is running.

    Called from Android main thread or a background thread.
    On Android, the server runs on 127.0.0.1 (localhost) so
    the WebView can reach it via http://127.0.0.1:8000.

    Args:
        host: Bind address (default 127.0.0.1 for local-only access).
        port: Port number (default 8000).
    """
    try:
        _start_server_impl(host, port)
    except Exception as e:
        _set_error("server_start", e)
        raise


def _start_server_impl(host: str, port: int):
    _setup_android_env()

    # Proxy fix: clear env vars that may interfere
    for var in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(var, None)

    logger.info("Starting GeoMate server on %s:%d (Android=%s)", host, port, IS_ANDROID)

    # Override settings for runtime
    settings.SERVER_HOST = host
    settings.SERVER_PORT = port

    # Run uvicorn (no reload on Android)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


def start_server_async(host: str = "127.0.0.1", port: int = 8000):
    """Start the server in a background thread (non-blocking).

    Returns immediately; the server runs in a daemon thread.
    Use this to start the server without blocking the Android UI thread.
    """
    thread = threading.Thread(
        target=start_server,
        args=(host, port),
        daemon=True,
        name="GeoMate-Server",
    )
    thread.start()
    logger.info("Server thread started")
    return thread
