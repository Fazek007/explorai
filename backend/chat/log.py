import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings


def write_turn(record: dict) -> None:
    directory = Path(settings.LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    while (directory / f"{stamp}.json").exists():
        stamp += "x"
    path = directory / f"{stamp}.json"
    path.write_text(json.dumps(record, indent=2))
    files = sorted(item for item in directory.glob("*.json") if item.is_file())
    overflow = len(files) - 10
    if overflow > 0:
        for old in files[:overflow]:
            old.unlink()
