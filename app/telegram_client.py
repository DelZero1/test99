from __future__ import annotations

from telegram import Bot


async def send_message(bot_token: str, chat_id: int, text: str) -> None:
    bot = Bot(token=bot_token)
    async with bot:
        await bot.send_message(chat_id=chat_id, text=text)
