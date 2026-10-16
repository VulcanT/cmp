from __future__ import annotations

from fastapi import FastAPI

from cmp import __version__
from cmp.approvals.web import router as approvals_router
from cmp.config import get_settings

app = FastAPI(title="CMP", version=__version__)
app.include_router(approvals_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": str(get_settings().mode)}
