from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Job:
    job_id: str
    reddit_url: str
    chat_id: int
    requested_by_user_id: int
    status: str
    created_at: str
    updated_at: str
    result_dir: str
    error_message: str | None = None
    title: str | None = None
    tldr_text: str | None = None
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class QueueStore:
    def __init__(self, jobs_dir: Path, results_dir: Path) -> None:
        self.jobs_dir = jobs_dir
        self.results_dir = results_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def enqueue_job(self, reddit_url: str, chat_id: int, user_id: int) -> Job:
        timestamp = now_utc()
        job_id = uuid.uuid4().hex
        result_dir = self.results_dir / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        job = Job(
            job_id=job_id,
            reddit_url=reddit_url,
            chat_id=chat_id,
            requested_by_user_id=user_id,
            status="pending",
            created_at=timestamp,
            updated_at=timestamp,
            result_dir=str(result_dir),
        )
        self._write_job(job)
        return job

    def get_job(self, job_id: str) -> Job | None:
        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        return Job(**json.loads(path.read_text(encoding="utf-8")))

    def list_jobs(self, limit: int = 100) -> list[Job]:
        jobs: list[Job] = []
        for path in sorted(self.jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            jobs.append(Job(**json.loads(path.read_text(encoding="utf-8"))))
        return jobs

    def claim_next_job(self, scan_limit: int = 100) -> Job | None:
        for path in sorted(self.jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)[:scan_limit]:
            job = Job(**json.loads(path.read_text(encoding="utf-8")))
            if job.status != "pending":
                continue
            claim_path = self.jobs_dir / f"{job.job_id}.claim"
            try:
                fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            except FileExistsError:
                continue
            try:
                job.status = "processing"
                job.attempts += 1
                job.updated_at = now_utc()
                self._write_job(job)
                return job
            except Exception:
                claim_path.unlink(missing_ok=True)
                raise
        return None

    def complete_job(self, job_id: str, title: str | None, tldr_text: str | None) -> Job:
        job = self._require_job(job_id)
        job.status = "completed"
        job.title = title
        job.tldr_text = tldr_text
        job.error_message = None
        job.updated_at = now_utc()
        self._write_job(job)
        self._release_claim(job_id)
        return job

    def fail_job(self, job_id: str, error_message: str) -> Job:
        job = self._require_job(job_id)
        job.status = "failed"
        job.error_message = error_message
        job.updated_at = now_utc()
        self._write_job(job)
        self._release_claim(job_id)
        return job

    def _require_job(self, job_id: str) -> Job:
        job = self.get_job(job_id)
        if job is None:
            raise FileNotFoundError(f"Job not found: {job_id}")
        return job

    def _write_job(self, job: Job) -> None:
        payload = json.dumps(asdict(job), ensure_ascii=False, indent=2)
        path = self.jobs_dir / f"{job.job_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(path)

    def _release_claim(self, job_id: str) -> None:
        (self.jobs_dir / f"{job_id}.claim").unlink(missing_ok=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
