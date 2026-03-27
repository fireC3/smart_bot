from pathlib import Path
import json
from typing import Any


class JsonStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load_sync(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        text = self._path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)

    async def save(self, data: dict[str, Any]) -> None:
        import aiofiles
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
