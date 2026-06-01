import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

_PUBLIC_LINK = re.compile(
    r"^([A-Za-z0-9_]+)/(\d+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedLink:
    channel: str
    message_id: int


class LinkParseError(ValueError):
    pass


def _normalize_link(raw: str) -> str:
    link = (raw or "").strip()
    for _ in range(3):
        decoded = unquote(link)
        if decoded == link:
            break
        link = decoded
    return link


def parse_telegram_link(raw_link: str) -> ParsedLink:
    link = _normalize_link(raw_link)
    if not link:
        raise LinkParseError("Link is empty.")

    if link.startswith(("http://", "https://")):
        parsed = urlparse(link)
        host = parsed.netloc.lower().removeprefix("www.")
        if host != "t.me":
            raise LinkParseError("Only t.me links are supported.")
        path = parsed.path.strip("/")
    else:
        path = link.strip("/")
        lower = path.lower()
        for prefix in ("https://t.me/", "http://t.me/", "t.me/", "www.t.me/"):
            if lower.startswith(prefix):
                path = path[len(prefix) :]
                break

    if path.lower().startswith("c/"):
        raise LinkParseError(
            "Private channel links (t.me/c/...) are not supported. Use a public @channel link."
        )

    match = _PUBLIC_LINK.match(path)
    if not match:
        raise LinkParseError(
            "Invalid link format. Expected: https://t.me/channelname/123"
        )

    channel, message_id_str = match.groups()
    message_id = int(message_id_str)
    if message_id <= 0:
        raise LinkParseError("Message ID must be a positive number.")

    return ParsedLink(channel=channel, message_id=message_id)
