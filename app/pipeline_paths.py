import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


def _load_dotenv(path: Path) -> None:
    """Minimalny loader .env (KEY=VALUE); nie nadpisuje zmiennych już ustawionych w środowisku."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


_load_dotenv(ROOT / ".env")
