"""Run the Ask API: python -m app"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # Railway injects PORT; bind all interfaces. Local stays on localhost.
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    uvicorn.run("app.api:app", host=host, port=port, reload=False)
