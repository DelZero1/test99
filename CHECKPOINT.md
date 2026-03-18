# CHECKPOINT.md

## Current project state
- Project: private Telegram Reddit TL;DR bot
- Platform: Windows / PowerShell
- Python env: `.venv`
- Telegram bot and worker run as separate local processes
- Local summarizer pipeline is active and integrated through `REDDIT_PIPELINE_COMMAND`
- The file `reddit_ollama_summarizer.py` now exists in the repository root and is part of the current working setup

## Current flow
1. User sends a Reddit link to the private Telegram bot
2. Bot validates sender against one allowed Telegram user ID
3. Bot normalizes the Reddit URL into a canonical post URL
4. Bot enqueues a local job
5. Worker processes the job
6. Worker runs `reddit_ollama_summarizer.py`
7. Worker reads summary output and sends TL;DR back to Telegram

## Last completed work
- Fixed `.env` loading in `app/config.py`
- Fixed Windows command execution path handling in `app/reddit_pipeline.py`
- Removed Windows-breaking quoting issue from pipeline execution
- Added Reddit URL normalization to support share links and links with tracking parameters
- Updated Telegram bot to normalize URLs before enqueueing jobs
- Moved `reddit_ollama_summarizer.py` into the repository root for direct local integration
- Confirmed bot and worker now run and process jobs locally

## Files recently changed
- `app/config.py`
- `app/reddit_pipeline.py`
- `app/url_utils.py`
- `app/telegram_bot.py`
- `reddit_ollama_summarizer.py`
- `.env`
- `README.md`

## Important current assumptions
- `.env` is loaded through `python-dotenv`
- `REDDIT_PIPELINE_COMMAND` is the active integration path
- The worker is intended to call the local root-level `reddit_ollama_summarizer.py`
- The project is Windows-first in actual usage
- Reddit share links from the mobile app should be normalized before job creation

## Known issues
- Need to verify result discovery remains reliable for all summarizer outputs
- README still needs polishing for Windows-specific setup and examples
- Very large Reddit threads may still yield partial scraping depending on public Reddit behavior
- Daily discussion / megathread summaries are lower quality than standard single-topic posts

## Next recommended steps
1. Improve worker result discovery if needed
2. Add tests for URL normalization
3. Improve README for Windows usage
4. Add resilience checks around pipeline output lookup
5. Optionally add a more explicit checkpoint/update workflow for Codex

## Change log
### 2026-03-18
- Added automatic `.env` loading
- Fixed worker pipeline execution on Windows
- Integrated root-level `reddit_ollama_summarizer.py`
- Added Reddit URL normalization for share links and tracking-parameter links
- Updated Telegram bot intake to store canonical Reddit URLs
