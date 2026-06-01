import logging

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from link_parser import LinkParseError, parse_telegram_link
from rate_limit import RateLimitMiddleware
from telegram_service import (
    TelegramFetchError,
    fetch_post_comments,
    init_client,
    shutdown_client,
)

FRONTEND_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "frontend"

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
    await init_client()


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


@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
