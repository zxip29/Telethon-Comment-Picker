"""
One-time (or repeat) Telegram login to create a session file.

IMPORTANT: Use your personal account (phone number). Do NOT use a bot token.

Run from the backend directory: python scripts/login.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient

from config import API_HASH, API_ID, SESSION_NAME

SESSION_PATH = str(Path(__file__).resolve().parent.parent / SESSION_NAME)


async def main() -> None:
    print("Sign in with your PHONE NUMBER (user account).")
    print("When prompted for bot token, press Ctrl+C and start again — do not use @BotFather tokens.\n")

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()

    if me.bot:
        print("\nERROR: You signed in as a BOT. This app requires a user account.")
        print("Delete these files and run this script again:")
        print(f"  {SESSION_PATH}.session")
        print(f"  {SESSION_PATH}.session-journal (if it exists)")
        await client.log_out()
        await client.disconnect()
        sys.exit(1)

    print(f"Logged in as {me.first_name} (id={me.id}) — user account OK")
    print(f"Session saved to {SESSION_PATH}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
