# AGENTS.md

## Project goal
Build a private Telegram-to-local-PC Reddit TL;DR pipeline.

## User flow
1. User sends a Reddit post link to a private Telegram bot.
2. Bot accepts requests only from one allowed Telegram user ID.
3. Bot stores a job locally.
4. Local worker picks the job up.
5. Worker runs the Reddit scrape + cleaning + chunking + local Ollama summary pipeline.
6. Worker extracts `tldr_comment` from the result.
7. Bot sends the TL;DR back to the same Telegram chat.

## Rules
- Keep the system private and single-user.
- Do not add multi-user logic unless explicitly requested.
- Prefer simple, inspectable local storage first.
- Prefer small modules over one large file.
- Keep all secrets in environment variables.
- Never hardcode the bot token or allowed user ID.
- Log all failures to `data/logs/`.
- Fail gracefully and return human-readable Telegram error messages.
- Reuse the existing Reddit pipeline instead of rewriting it from scratch unless necessary.
- If changing prompts, preserve the current JSON contract used by the summarizer.

## Architecture preferences
- Telegram bot and worker should be separate processes.
- Queue should be simple: JSON or SQLite is acceptable.
- The worker must be idempotent for the same job ID.
- Result files should be stored under `data/results/<job_id>/`.

## Security
- Only one Telegram user ID is allowed.
- Ignore all messages from other users.
- Accept only Reddit URLs.
- Reject unsupported links cleanly.

## Implementation priorities
1. Working private Telegram flow
2. Reliable queue and worker
3. Stable integration with local Reddit summarizer
4. Clean logs and errors
5. Optional command support like /status and /last

## Coding style
- Python 3.11+
- Type hints where practical
- Small functions
- Clear names
- Minimal hidden magic

## Deliverables
- Working Telegram bot
- Working worker
- `.env.example`
- README with run steps
- Small test script for local verification
