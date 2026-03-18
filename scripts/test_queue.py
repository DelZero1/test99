from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.queue_store import QueueStore
from app.tldr_service import TldrService


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        store = QueueStore(base / "jobs", base / "results")
        job = store.enqueue_job(
            reddit_url="https://www.reddit.com/r/python/comments/abc123/example_post/",
            chat_id=123,
            user_id=456,
        )
        claimed = store.claim_next_job()
        assert claimed is not None and claimed.job_id == job.job_id

        summary_dir = Path(job.result_dir)
        payload = {
            "title": "Example Reddit Post",
            "tldr_comment": "Short local summary.",
        }
        (summary_dir / "final_summary.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        title, tldr_text = TldrService().extract(summary_dir)
        completed = store.complete_job(job.job_id, title=title, tldr_text=tldr_text)
        assert completed.status == "completed"
        assert completed.tldr_text == "Short local summary."
        print("Queue and TL;DR extraction smoke test passed.")


if __name__ == "__main__":
    main()
