from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    allowed_telegram_user_id: int
    base_data_dir: Path
    jobs_dir: Path
    results_dir: Path
    logs_dir: Path
    poll_interval_seconds: float
    queue_scan_limit: int
    pipeline_command: str | None
    pipeline_callable: str | None
    pipeline_output_filename: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = require_env("TELEGRAM_BOT_TOKEN")
        allowed_user_id = int(require_env("ALLOWED_TELEGRAM_USER_ID"))
        base_data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
        jobs_dir = base_data_dir / "jobs"
        results_dir = base_data_dir / "results"
        logs_dir = base_data_dir / "logs"
        ensure_directories(jobs_dir, results_dir, logs_dir)
        return cls(
            telegram_bot_token=token,
            allowed_telegram_user_id=allowed_user_id,
            base_data_dir=base_data_dir,
            jobs_dir=jobs_dir,
            results_dir=results_dir,
            logs_dir=logs_dir,
            poll_interval_seconds=float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "3")),
            queue_scan_limit=int(os.getenv("QUEUE_SCAN_LIMIT", "100")),
            pipeline_command=os.getenv("REDDIT_PIPELINE_COMMAND"),
            pipeline_callable=os.getenv("REDDIT_PIPELINE_CALLABLE"),
            pipeline_output_filename=os.getenv("PIPELINE_OUTPUT_FILENAME", "final_summary.json"),
        )


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
