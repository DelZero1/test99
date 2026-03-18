from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.config import Settings
from app.logging_utils import configure_logging
from app.queue_store import Job, QueueStore
from app.reddit_pipeline import PipelineExecutionError, RedditPipeline
from app.telegram_client import send_message
from app.tldr_service import SummaryExtractionError, TldrService


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = configure_logging(settings.logs_dir, "worker")
        self.queue_store = QueueStore(settings.jobs_dir, settings.results_dir)
        self.pipeline = RedditPipeline(settings)
        self.tldr_service = TldrService(settings.pipeline_output_filename)

    def run_forever(self) -> None:
        self.logger.info("Starting worker loop")
        while True:
            job = self.queue_store.claim_next_job(scan_limit=self.settings.queue_scan_limit)
            if job is None:
                time.sleep(self.settings.poll_interval_seconds)
                continue
            self.process_job(job)

    def process_job(self, job: Job) -> None:
        self.logger.info("Processing job %s", job.job_id)
        result_dir = Path(job.result_dir)
        try:
            self.pipeline.run(job.reddit_url, job.job_id, result_dir)
            title, tldr_text = self.tldr_service.extract(result_dir)
            completed_job = self.queue_store.complete_job(job.job_id, title=title, tldr_text=tldr_text)
            asyncio.run(
                send_message(
                    bot_token=self.settings.telegram_bot_token,
                    chat_id=completed_job.chat_id,
                    text=self._success_message(completed_job.title, completed_job.tldr_text or ""),
                )
            )
            self.logger.info("Completed job %s", job.job_id)
        except (PipelineExecutionError, SummaryExtractionError, FileNotFoundError) as exc:
            self._handle_failure(job, str(exc))
        except Exception as exc:  # pragma: no cover - defensive guardrail
            self._handle_failure(job, f"Neočekivana greška: {exc}")

    def _handle_failure(self, job: Job, error_message: str) -> None:
        safe_error = error_message.strip() or "Obrada nije uspjela."
        self.queue_store.fail_job(job.job_id, safe_error)
        self.logger.exception("Job %s failed: %s", job.job_id, safe_error)
        asyncio.run(
            send_message(
                bot_token=self.settings.telegram_bot_token,
                chat_id=job.chat_id,
                text=f"Obrada nije uspjela: {safe_error}",
            )
        )

    def _success_message(self, title: str | None, tldr_text: str) -> str:
        lines = []
        if title:
            lines.append(f"Naslov: {title}")
        lines.append(f"TL;DR: {tldr_text}")
        return "\n\n".join(lines)
