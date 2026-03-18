# AGENTS.md

## Project goal
Build and maintain a private Telegram-to-local-PC Reddit TL;DR pipeline.

## Core user flow
1. The user sends a Reddit post link to a private Telegram bot.
2. The bot accepts requests only from one allowed Telegram user ID.
3. The bot normalizes the Reddit URL into a canonical valid post URL.
4. The bot stores a local job.
5. A local worker process picks the job up.
6. The worker runs the Reddit scrape + cleaning + chunking + local Ollama summary pipeline.
7. The worker extracts `tldr_comment` from the pipeline result.
8. The bot sends the TL;DR back to the same Telegram chat.

## Mandatory startup routine
Before making code changes, always:
1. Read `CHECKPOINT.md`
2. Read `README.md`
3. Read this `AGENTS.md`
4. Inspect current repository state
5. Check which files changed recently
6. If repository state differs from `CHECKPOINT.md`, refresh `CHECKPOINT.md` first
7. Then continue with implementation

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
- If changing prompts, preserve the current JSON contract used by the summarizer unless explicitly told to change it.
- Preserve Windows compatibility.
- Do not assume Linux shell behavior.
- Prefer local-first solutions over external services.

## Architecture preferences
- Telegram bot and worker must remain separate processes.
- Queue should remain simple and inspectable.
- JSON or SQLite are acceptable, but do not overcomplicate storage.
- The worker must be idempotent for the same job ID where practical.
- Result files should be stored under `data/results/<job_id>/`.
- Existing local summarizer logic should remain reusable.
- `reddit_ollama_summarizer.py` currently exists in the repository root and must be treated as part of the active pipeline integration.

## Security
- Only one Telegram user ID is allowed.
- Ignore all messages from other users.
- Accept only Reddit URLs.
- Reject unsupported links cleanly.
- Normalize Reddit URLs before enqueueing jobs.
- Never weaken sender validation unless explicitly requested.

## URL handling requirements
- Accept canonical Reddit post URLs.
- Accept Reddit share links like `/s/...` when possible.
- Accept Reddit links with tracking/query parameters.
- Normalize accepted Reddit links into a canonical post URL before storing or processing.
- Reject non-post Reddit URLs cleanly.

## Integration requirements
- The project may call the summarizer through `REDDIT_PIPELINE_COMMAND` or `REDDIT_PIPELINE_CALLABLE`.
- The current working integration uses the root-level `reddit_ollama_summarizer.py`.
- If command execution changes, preserve Windows-safe behavior.
- Avoid shell quoting bugs on Windows.
- Do not break existing `.env`-based configuration.

## Implementation priorities
1. Working private Telegram flow
2. Reliable queue and worker
3. Stable integration with local Reddit summarizer
4. Clean logs and errors
5. Good Windows compatibility
6. Optional command support like `/status` and `/last`

## Coding style
- Python 3.11+
- Type hints where practical
- Small functions
- Clear names
- Minimal hidden magic
- Keep changes focused and easy to review

## Required checkpoint discipline
After every meaningful change, update `CHECKPOINT.md`.

Each checkpoint update must include:
- Timestamp
- What changed
- Files changed
- Why the change was made
- Current known issues
- Next recommended step

## Git awareness
If repository changes were made outside Codex:
- do not assume old context is still accurate
- re-read changed files before editing
- update `CHECKPOINT.md` to reflect the new reality before proceeding

## Deliverables
- Working Telegram bot
- Working worker
- `.env.example`
- README with run steps
- Small test script for local verification
- Updated `CHECKPOINT.md` after meaningful work
