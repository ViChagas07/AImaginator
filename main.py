"""Entry point para o Render.

O Render usa por padrão `uvicorn main:app`, então re-exportamos o app
da API (apps/api/main.py) a partir da raiz do repositório.
"""

from apps.api.main import app

__all__ = ["app"]
