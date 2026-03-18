from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.worker import Worker


def main() -> None:
    settings = Settings.from_env()
    Worker(settings).run_forever()


if __name__ == "__main__":
    main()
