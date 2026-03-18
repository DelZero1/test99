# Private Telegram Reddit TL;DR Bot

This project runs a **single-user**, **local-first** Telegram bot that accepts a Reddit post link, stores a local job, lets a separate worker process run your existing Reddit summarizer pipeline, and sends the resulting TL;DR back to Telegram.

## What it does

1. Telegram bot accepts text messages from **one allowed Telegram user ID only**.
2. The bot accepts **only Reddit post URLs**.
3. Valid links are written as JSON job files under `data/jobs/`.
4. A separate worker process polls the queue and executes your **existing** Reddit summarizer pipeline.
5. The worker reads `final_summary.json`, extracts `tldr_comment` with fallback to `reader_summary` or `final_summary`, and sends the result back to the same Telegram chat.
6. Logs are written under `data/logs/`.
7. Per-job output is stored under `data/results/<job_id>/`.

## Project layout

```text
app/
  config.py
  logging_utils.py
  queue_store.py
  reddit_pipeline.py
  security.py
  telegram_bot.py
  telegram_client.py
  tldr_service.py
  url_utils.py
  worker.py
scripts/
  run_bot.py
  run_worker.py
  test_queue.py
.env.example
requirements.txt
README.md
```

## Requirements

- Python 3.11+
- A Telegram bot token
- Your Telegram numeric user ID
- An existing local Reddit summarizer pipeline that can be called either:
  - as a shell command, or
  - as a Python importable callable

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Fill in:

   - `TELEGRAM_BOT_TOKEN`
   - `ALLOWED_TELEGRAM_USER_ID`

4. Configure **one** integration method for your existing Reddit pipeline.

## Pipeline integration

The worker intentionally uses a **thin wrapper** so you can reuse your existing scraper/cleaner/chunking/Ollama summarizer instead of replacing it.

### Option A: shell command wrapper

Set `REDDIT_PIPELINE_COMMAND` in `.env`.

Example:

```env
REDDIT_PIPELINE_COMMAND=python /absolute/path/to/your_pipeline.py --url "{reddit_url}" --output-dir {output_dir}
```

Available placeholders:

- `{reddit_url}` or `{url}`: incoming Reddit post URL
- `{job_id}`: generated local job ID
- `{output_dir}` / `{result_dir}`: the job output directory under `data/results/<job_id>/`

**Assumption:** your existing script can be told where to place `final_summary.json`. If it cannot, add a very small wrapper script that forwards arguments into your current pipeline and writes the final JSON into the provided output directory.

### Option B: importable Python callable

Set `REDDIT_PIPELINE_CALLABLE` in `.env`.

Example:

```env
REDDIT_PIPELINE_CALLABLE=my_pipeline.runner:run_pipeline
```

The callable should accept either:

- keyword args: `reddit_url=...`, `job_id=...`, `output_dir=...`, or
- positional args: `(reddit_url, job_id, output_dir)`

## Expected pipeline output

Inside each job result directory, the worker looks for `final_summary.json` by default.

Expected fields:

- preferred: `tldr_comment`
- fallback 1: `reader_summary`
- fallback 2: `final_summary`
- optional title: `post_title` or `title`

Example:

```json
{
  "title": "Some Reddit Post",
  "tldr_comment": "Short summary here"
}
```

If your pipeline writes a different filename, set `PIPELINE_OUTPUT_FILENAME`.

## Run the bot and worker

In one terminal:

```bash
set -a
source .env
set +a
python scripts/run_bot.py
```

In another terminal:

```bash
set -a
source .env
set +a
python scripts/run_worker.py
```

## Telegram behavior

### On valid Reddit link

The bot immediately replies:

```text
Zaprimio sam link. Krećem s obradom.
```

### On success

The worker sends back:

- post title, if present
- extracted TL;DR

### On failure

The worker sends a short human-readable error message.

## Optional commands

- `/status` shows the latest local jobs
- `/last` shows the most recent job summary or failure

## Local verification

Run the included smoke test:

```bash
python scripts/test_queue.py
```

This verifies:

- job enqueue
- job claiming
- local result writing
- TL;DR extraction fallback flow

## Notes

- Unauthorized Telegram users are ignored.
- Non-Reddit links are rejected with a clear message.
- The worker is designed to be idempotent for a given completed job because results remain on disk and queue state is stored in JSON.
- If a worker crashes mid-job, the `.claim` file for that job may remain. Delete `data/jobs/<job_id>.claim` manually to requeue it, or change the queue logic later if you want automatic stale-claim recovery.
- This implementation keeps the system intentionally simple and local-first, per your requirements.
