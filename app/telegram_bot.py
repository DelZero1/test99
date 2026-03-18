from __future__ import annotations

import html
from typing import cast

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import Settings
from app.logging_utils import configure_logging
from app.queue_store import QueueStore
from app.security import SenderValidationError, validate_sender
from app.url_utils import InvalidRedditUrl, normalize_reddit_url


class TelegramRedditBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = configure_logging(settings.logs_dir, "telegram_bot")
        self.queue_store = QueueStore(settings.jobs_dir, settings.results_dir)
        self.application = Application.builder().token(settings.telegram_bot_token).build()
        self.application.add_handler(CommandHandler("status", self.handle_status))
        self.application.add_handler(CommandHandler("last", self.handle_last))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )

    def run(self) -> None:
        self.logger.info("Starting Telegram bot polling loop")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            user_id = validate_sender(update, self.settings.allowed_telegram_user_id)
        except SenderValidationError:
            self.logger.warning("Ignoring message from unauthorized user")
            return

        message = cast(Message | None, update.effective_message)
        if message is None or not message.text:
            return

        raw_text = message.text.strip()

        try:
            normalized_url = normalize_reddit_url(raw_text)
        except InvalidRedditUrl:
            await message.reply_text("Pošalji isključivo valjani Reddit post URL.")
            return
        except Exception as exc:
            self.logger.exception("Unexpected URL normalization error: %s", exc)
            await message.reply_text("Nisam uspio obraditi link. Pokušaj poslati puni Reddit post URL.")
            return

        job = self.queue_store.enqueue_job(
            reddit_url=normalized_url,
            chat_id=message.chat_id,
            user_id=user_id,
        )

        self.logger.info(
            "Enqueued job %s for chat %s | raw_url=%s | normalized_url=%s",
            job.job_id,
            message.chat_id,
            raw_text,
            normalized_url,
        )

        if raw_text != normalized_url:
            await message.reply_text(
                "Zaprimio sam link i normalizirao ga u valjani Reddit post URL.\n"
                "Krećem s obradom."
            )
        else:
            await message.reply_text("Zaprimio sam link. Krećem s obradom.")

    async def handle_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            validate_sender(update, self.settings.allowed_telegram_user_id)
        except SenderValidationError:
            self.logger.warning("Ignoring /status from unauthorized user")
            return

        message = cast(Message | None, update.effective_message)
        if message is None:
            return

        jobs = self.queue_store.list_jobs(limit=5)
        if not jobs:
            await message.reply_text("Nema poslova u lokalnom redu.")
            return

        lines = ["Zadnji poslovi:"]
        for job in jobs:
            lines.append(f"- {job.job_id[:8]} | {job.status} | {html.escape(job.reddit_url)}")
        await message.reply_text("\n".join(lines))

    async def handle_last(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            validate_sender(update, self.settings.allowed_telegram_user_id)
        except SenderValidationError:
            self.logger.warning("Ignoring /last from unauthorized user")
            return

        message = cast(Message | None, update.effective_message)
        if message is None:
            return

        jobs = self.queue_store.list_jobs(limit=1)
        if not jobs:
            await message.reply_text("Još nema nijednog obrađenog linka.")
            return

        job = jobs[0]
        lines = [f"Zadnji posao: {job.job_id}", f"Status: {job.status}", f"URL: {job.reddit_url}"]
        if job.title:
            lines.append(f"Naslov: {job.title}")
        if job.tldr_text:
            lines.append(f"TL;DR: {job.tldr_text}")
        if job.error_message:
            lines.append(f"Greška: {job.error_message}")
        await message.reply_text("\n".join(lines))