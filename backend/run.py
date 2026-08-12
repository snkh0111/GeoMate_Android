"""Development server entry point (desktop testing only).

For Android deployment, use android_bridge.py instead.

Usage:
    python run.py   # starts server at http://127.0.0.1:8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
