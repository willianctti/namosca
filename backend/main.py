"""Ponto de entrada compatível: ``python main.py``.

A aplicação está no pacote modular ``app``. Este iniciador pequeno mantém
funcionando o comando usado pelos exemplos antigos do FlyBrainWeb.
"""

from __future__ import annotations

import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
