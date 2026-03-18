from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.telegram_bot import TelegramRedditBot


def main() -> None:
    settings = Settings.from_env()
    TelegramRedditBot(settings).run()


if __name__ == "__main__":
    main()
