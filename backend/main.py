"""Compatibility entrypoint: ``python main.py``.

The application itself lives in the modular ``app`` package. Keeping this tiny
launcher makes the command used by the original FlyBrainWeb examples work.
"""

from __future__ import annotations

import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
