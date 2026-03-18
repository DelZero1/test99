# telegram-reddit-tldr

## Purpose
Implement and maintain a private Telegram bot that forwards Reddit links to a local processing pipeline and sends back a TL;DR summary.

## When to use
Use this skill when working on:
- Telegram message intake
- local queue handling
- worker orchestration
- Reddit pipeline integration
- TL;DR delivery

## Constraints
- Single private user only
- Local PC execution only
- No cloud database unless explicitly requested
- Prefer readability and reliability over complexity

## Expected inputs
- Telegram text message containing a Reddit URL

## Expected outputs
- Telegram message containing the final TL;DR
- Optional status message while processing

## Required behavior
- Validate sender by Telegram user ID
- Validate URL as Reddit post URL
- Create local job record
- Process job asynchronously through local worker
- Return `tldr_comment` if available
- Return fallback summary if `tldr_comment` missing
- Return clear error message if processing fails

## File ownership
- app/telegram_bot.py
- app/worker.py
- app/queue_store.py
- app/reddit_pipeline.py
- app/tldr_service.py
