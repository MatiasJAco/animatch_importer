import json
import os
from pathlib import Path

class RawStore:
    """Filesystem-backed raw API store. Files are written atomically."""
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        return self.root / relative

    def exists(self, relative: str) -> bool:
        return self.path(relative).is_file()

    def read_json(self, relative: str):
        with self.path(relative).open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def write_json(self, relative: str, payload) -> Path:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        return target

    def fetch_once(self, client, relative: str, endpoint: str, params=None, refresh=False):
        if self.exists(relative) and not refresh:
            return self.read_json(relative), False
        payload = client.get(endpoint, params)
        self.write_json(relative, payload)
        return payload, True
