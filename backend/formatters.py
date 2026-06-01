"""Giveaway-style comment formatting."""


def _escape_quotes(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def format_comment_line(index: int, display: str, text: str) -> str:
    """
    Examples:
      no.1 @username - "comment text"
      no.2 Full Name - "comment text"
      no.3 User12345 - "comment text"
    """
    user = display or "User0"
    body = _escape_quotes(text or "")
    return f'no.{index} {user} - "{body}"'


def format_all_comments(comments: list[dict[str, str]]) -> list[str]:
    lines = []
    for i, item in enumerate(comments, start=1):
        lines.append(
            format_comment_line(
                i,
                item.get("display", "User0"),
                item.get("text", ""),
            )
        )
    return lines


def join_formatted(lines: list[str]) -> str:
    return "\n".join(lines)
