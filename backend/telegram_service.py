import logging

from telethon import TelegramClient
from telethon.errors import (
    BotMethodInvalidError,
    ChannelInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    FloodWaitError,
    MsgIdInvalidError,
    PeerIdInvalidError,
    RPCError,
    UserNotParticipantError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.messages import GetDiscussionMessageRequest, GetRepliesRequest
from telethon.tl.types import Channel, User

from config import API_HASH, API_ID, SESSION_NAME

logger = logging.getLogger(__name__)

SESSION_PATH = str(
    __import__("pathlib").Path(__file__).resolve().parent / SESSION_NAME
)

client: TelegramClient | None = None

BOT_SESSION_MESSAGE = (
    "This Telegram session is a BOT account. Bots cannot fetch post comments. "
    "Delete backend/telegram_session.session (and .session-journal if present), "
    "then run: python scripts/login.py — sign in with your PHONE NUMBER "
    "(personal user account), not a bot token from @BotFather."
)


async def ensure_user_account(tg: TelegramClient) -> None:
    me = await tg.get_me()
    if me.bot:
        raise RuntimeError(BOT_SESSION_MESSAGE)


async def init_client() -> TelegramClient:
    global client
    if client is None:
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session is not authorized. Run: python scripts/login.py"
        )
    await ensure_user_account(client)
    return client


async def shutdown_client() -> None:
    global client
    if client is not None and client.is_connected():
        await client.disconnect()


class TelegramFetchError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _merge_users(users_map: dict[int, User], users: list | None) -> None:
    for user in users or []:
        if isinstance(user, User):
            users_map[user.id] = user


def _user_display(user: User) -> str:
    if user.username:
        return f"@{user.username.lstrip('@')}"
    parts = [p for p in (user.first_name, user.last_name) if p]
    full_name = " ".join(parts).strip()
    if full_name:
        return full_name
    return f"User{user.id}"


def _user_from_message(msg, users_map: dict[int, User]) -> User | None:
    sender = getattr(msg, "sender", None)
    if isinstance(sender, User):
        return sender

    sender_id = getattr(msg, "sender_id", None)
    if sender_id and sender_id in users_map:
        return users_map[sender_id]

    from_id = getattr(msg, "from_id", None)
    if from_id is not None:
        uid = getattr(from_id, "user_id", None)
        if uid and uid in users_map:
            return users_map[uid]

    return None


def _resolve_sender_display(msg, users_map: dict[int, User]) -> str:
    user = _user_from_message(msg, users_map)
    if user is not None:
        return _user_display(user)

    sender_id = getattr(msg, "sender_id", None)
    if sender_id is None and getattr(msg, "from_id", None) is not None:
        sender_id = getattr(msg.from_id, "user_id", None)

    if sender_id:
        return f"User{sender_id}"

    return "User0"


def _resolve_user_id(msg, users_map: dict[int, User]) -> int | None:
    user = _user_from_message(msg, users_map)
    if user is not None:
        return user.id
    sender_id = getattr(msg, "sender_id", None)
    if sender_id:
        return sender_id
    from_id = getattr(msg, "from_id", None)
    if from_id is not None:
        return getattr(from_id, "user_id", None)
    return None


def _message_to_comment(msg, users_map: dict[int, User]) -> dict:
    text = (getattr(msg, "message", None) or "").strip()
    user = _user_from_message(msg, users_map)
    username = user.username if user and user.username else None
    return {
        "user_id": _resolve_user_id(msg, users_map),
        "username": username,
        "display": _resolve_sender_display(msg, users_map),
        "text": text,
        "has_media": getattr(msg, "media", None) is not None,
        "has_text": bool(text),
    }


def _messages_to_comments(
    messages: list, users_map: dict[int, User], *, skip_id: int | None = None
) -> list[dict]:
    comments = []
    for msg in messages:
        if skip_id is not None and msg.id == skip_id:
            continue
        comments.append(_message_to_comment(msg, users_map))
    return comments


def _map_telegram_error(exc: BaseException) -> TelegramFetchError:
    if isinstance(exc, TelegramFetchError):
        return exc
    if isinstance(exc, BotMethodInvalidError):
        return TelegramFetchError(BOT_SESSION_MESSAGE, status_code=403)
    if isinstance(exc, ChannelPrivateError):
        return TelegramFetchError(
            "This channel is private or you do not have access.",
            status_code=403,
        )
    if isinstance(exc, UserNotParticipantError):
        return TelegramFetchError(
            "You are not in this channel. Open the channel in Telegram and try again.",
            status_code=403,
        )
    if isinstance(exc, (UsernameNotOccupiedError, UsernameInvalidError, ChannelInvalidError)):
        return TelegramFetchError(
            "Channel not found or invalid username.",
            status_code=404,
        )
    if isinstance(exc, MsgIdInvalidError):
        return TelegramFetchError(
            "Post not found or invalid message ID.",
            status_code=404,
        )
    if isinstance(exc, PeerIdInvalidError):
        return TelegramFetchError(
            "Comments are not available for this post (no linked discussion or not a broadcast channel).",
            status_code=400,
        )
    if isinstance(exc, ChatAdminRequiredError):
        return TelegramFetchError(
            "Cannot read comments on this channel.",
            status_code=403,
        )
    if isinstance(exc, FloodWaitError):
        return TelegramFetchError(
            f"Telegram rate limit. Wait {exc.seconds} seconds and try again.",
            status_code=429,
        )
    if isinstance(exc, ValueError):
        return TelegramFetchError(str(exc), status_code=404)
    if isinstance(exc, RPCError):
        detail = getattr(exc, "message", None) or str(exc)
        return TelegramFetchError(
            f"Telegram API error ({exc.__class__.__name__}): {detail}",
            status_code=502,
        )
    return TelegramFetchError(
        f"Unexpected error: {exc}",
        status_code=500,
    )


async def _fetch_via_get_replies(
    tg: TelegramClient,
    peer,
    reply_to_msg_id: int,
    *,
    skip_id: int | None = None,
) -> list[dict[str, str]]:
    users_map: dict[int, User] = {}
    raw_messages: list = []
    offset_id = 0
    page_size = 100

    while True:
        result = await tg(
            GetRepliesRequest(
                peer=peer,
                msg_id=reply_to_msg_id,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=page_size,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )

        _merge_users(users_map, getattr(result, "users", None))
        messages = result.messages or []
        if not messages:
            break

        raw_messages.extend(messages)

        if len(messages) < page_size:
            break
        offset_id = messages[-1].id

    raw_messages.reverse()
    return _messages_to_comments(raw_messages, users_map, skip_id=skip_id)


async def _fetch_via_discussion_group(
    tg: TelegramClient, channel_entity, message_id: int
) -> list[dict[str, str]]:
    result = await tg(
        GetDiscussionMessageRequest(peer=channel_entity, msg_id=message_id)
    )

    if not result.messages:
        return []

    discussion_msg = min(result.messages, key=lambda m: m.id)
    channel_id = discussion_msg.peer_id.channel_id
    discussion_chat = next((c for c in result.chats if c.id == channel_id), None)
    if discussion_chat is None:
        raise TelegramFetchError(
            "Could not resolve the linked discussion group for this post.",
            status_code=502,
        )

    logger.info(
        "Fetching comments from discussion group %s, reply_to=%s",
        channel_id,
        discussion_msg.id,
    )

    return await _fetch_via_get_replies(
        tg,
        discussion_chat,
        discussion_msg.id,
        skip_id=discussion_msg.id,
    )


async def fetch_post_comments(channel: str, message_id: int) -> list[dict[str, str]]:
    tg = await init_client()

    try:
        entity = await tg.get_entity(channel)
    except Exception as exc:
        logger.warning("get_entity failed for %s: %s", channel, exc)
        raise _map_telegram_error(exc) from exc

    is_broadcast = isinstance(entity, Channel) and bool(
        getattr(entity, "broadcast", False)
    )

    try:
        if is_broadcast:
            try:
                return await _fetch_via_discussion_group(tg, entity, message_id)
            except MsgIdInvalidError:
                raise
            except RPCError as exc:
                logger.warning(
                    "Discussion path failed for %s/%s: %s — trying channel GetReplies",
                    channel,
                    message_id,
                    exc,
                )

        return await _fetch_via_get_replies(
            tg, entity, message_id, skip_id=message_id
        )
    except Exception as exc:
        logger.exception("Failed to fetch comments for %s/%s", channel, message_id)
        raise _map_telegram_error(exc) from exc
