import logging

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from link_parser import LinkParseError, parse_telegram_link
from rate_limit import RateLimitMiddleware
from telegram_service import (
    TelegramFetchError,
    auth_send_code,
    auth_status,
    auth_verify,
    fetch_post_comments,
    init_client,
    shutdown_client,
)

from pathlib import Path as _P
FRONTEND_DIR = _P(__file__).resolve().parent / "frontend"
if not FRONTEND_DIR.is_dir():
    FRONTEND_DIR = _P(__file__).resolve().parent.parent / "frontend"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Giveaway Comment Viewer",
    description="Fetch and format Telegram post comments for giveaways",
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    try:
        await init_client()
    except Exception as exc:
        logger.warning("Telegram not ready yet: %s", exc)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await shutdown_client()


def _error_response(
    message: str, status_code: int, detail: str | None = None
) -> JSONResponse:
    body: dict = {"error": message, "total_fetched": 0, "comments": []}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


@app.get("/comments")
async def get_comments(link: str = Query(..., description="Telegram post URL")):
    try:
        parsed = parse_telegram_link(link)
    except LinkParseError as exc:
        return _error_response(str(exc), 400)

    try:
        comments = await fetch_post_comments(parsed.channel, parsed.message_id)
    except TelegramFetchError as exc:
        return _error_response(exc.message, exc.status_code)
    except RuntimeError as exc:
        return _error_response(str(exc), 503)
    except Exception as exc:
        logger.exception("Unhandled error for link=%s", link)
        return _error_response(
            "Failed to fetch comments from Telegram.",
            500,
            detail=str(exc),
        )

    total = len(comments)
    if total == 0:
        return {
            "total_fetched": 0,
            "comments": [],
            "message": "No comments found for this post.",
        }

    return {
        "total_fetched": total,
        "comments": comments,
    }


@app.get("/auth/status")
async def auth_status_route():
    try:
        return await auth_status()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/auth/send_code")
async def auth_send_code_route(body: dict = Body(...)):
    phone = str(body.get("phone", "")).strip()
    if not phone:
        return JSONResponse(status_code=400, content={"error": "Phone required"})
    try:
        await auth_send_code(phone)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return {"ok": True}


@app.post("/auth/verify")
async def auth_verify_route(body: dict = Body(...)):
    try:
        return await auth_verify(
            str(body.get("code", "")).strip(), body.get("password") or None
        )
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

