"""htmx approval pages. Phase 1: single user, no auth (run behind a VPN / Tailscale)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from cmp.approvals.service import AlreadyDecided, decide, list_batch
from cmp.db.session import session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[3] / "templates"))


@router.get("/batches/{batch_date}", response_class=HTMLResponse)
def batch_page(request: Request, batch_date: date) -> HTMLResponse:
    with session() as s:
        rows = list_batch(s, batch_date)
    return templates.TemplateResponse(
        request, "batch.html", {"rows": rows, "batch_date": batch_date}
    )


@router.post("/proposals/{proposal_id}/decide", response_class=HTMLResponse)
def decide_proposal(
    request: Request, proposal_id: int, decision: str = Form(...), note: str | None = Form(None)
) -> HTMLResponse:
    try:
        with session() as s:
            row = decide(s, proposal_id, decision, by="hoang", note=note)
            s.refresh(row)
    except AlreadyDecided as e:
        raise HTTPException(409, "already decided") from e
    except KeyError as e:
        raise HTTPException(404) from e
    return templates.TemplateResponse(request, "_row.html", {"p": row})
