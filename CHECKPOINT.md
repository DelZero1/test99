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
- Added local English/Croatian output-language detection in `reddit_ollama_summarizer.py`
- Expanded chunk, merge, and final TL;DR prompts to produce more detailed and language-aware summaries
- Added `output_language` metadata to summarizer outputs and surfaced it in the markdown report

## Files recently changed
- `reddit_ollama_summarizer.py`
- `CHECKPOINT.md`
- `README.md`

## Important current assumptions
- `.env` is loaded through `python-dotenv`
- `REDDIT_PIPELINE_COMMAND` is the active integration path
- The worker is intended to call the local root-level `reddit_ollama_summarizer.py`
- The project is Windows-first in actual usage
- Reddit share links from the mobile app should be normalized before job creation
- Summarizer language selection is intentionally simple and local-only, returning either `en` or `hr`

## Known issues
- Need to verify result discovery remains reliable for all summarizer outputs
- README still needs polishing for Windows-specific setup and examples
- Very large Reddit threads may still yield partial scraping depending on public Reddit behavior
- Daily discussion / megathread summaries are lower quality than standard single-topic posts
- The language detector is heuristic-based and may misclassify heavily mixed-language threads or jargon-heavy posts

## Next recommended steps
1. Run live English and Croatian summarizer smoke tests against Ollama and review output quality
2. Add focused tests for language detection and prompt-building behavior
3. Improve README for Windows usage
4. Add resilience checks around pipeline output lookup
5. Review megathread handling after prompt changes

## Change log
### 2026-03-18
- Added automatic `.env` loading
- Fixed worker pipeline execution on Windows
- Integrated root-level `reddit_ollama_summarizer.py`
- Added Reddit URL normalization for share links and tracking-parameter links
- Updated Telegram bot intake to store canonical Reddit URLs
- Refreshed repository state review against current source tree and recent git history
- Added heuristic `detect_output_language()` support for English/Croatian summaries
- Updated chunk, merge, and TL;DR prompts to request more detailed, less generic output in the detected language
- Added `output_language` to final summary metadata and markdown reporting

## Latest checkpoint update
- Timestamp: 2026-03-18 16:43:18 UTC
- What changed:
  - Implemented local language detection using the post title, post body, and sampled comments
  - Reused detected language across chunk prompts, final merge prompt, and final TL;DR pass
  - Made the generated TL;DR/reader summary/final analysis prompts substantially more detailed and reader-facing
  - Added output language metadata to JSON output and markdown report context
- Files changed:
  - `reddit_ollama_summarizer.py`
  - `CHECKPOINT.md`
- Why the change was made:
  - To improve TL;DR usefulness while preserving the existing bot/worker/local summarizer architecture
  - To keep English threads summarized in English and Croatian threads summarized in Croatian
- Current known issues:
  - Live Ollama output quality still depends on the installed local model
  - Heuristic language detection may need tuning for mixed-language or very short posts
- Next recommended step:
  - Run end-to-end summaries on one English and one Croatian Reddit thread and review whether the new prompts produce the desired detail level
