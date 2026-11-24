"""Read a snapshot folder: snapshots/<alias>/<timestamp>/<area>/<name>.json (+ _manifest.json)."""
import json
from pathlib import Path


class SnapshotError(Exception):
    """A file the check needs is missing or was not collected successfully."""


class Snapshot:
    def __init__(self, folder):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise SnapshotError(f"snapshot folder not found: {self.folder}")
        self._cache = {}

    def manifest(self, area):
        path = self.folder / area / "_manifest.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _file_status(self, area, name):
        """Status recorded by the collector for <name>.json, or None if the manifest does not say."""
        manifest = self.manifest(area)
        if not manifest:
            return None
        for entry in manifest.get("files", []):
            if entry.get("file") == f"{name}.json":
                return entry.get("status")
        return None

    def ref(self, area, name):
        """Relative path used as evidence in results: '<area>/<name>.json'."""
        return f"{area}/{name}.json"

    def load(self, area, name):
        key = (area, name)
        if key in self._cache:
            return self._cache[key]
        path = self.folder / area / f"{name}.json"
        if not path.exists():
            raise SnapshotError(f"{self.ref(area, name)} is not in the snapshot")
        status = self._file_status(area, name)
        if status in ("failed", "skipped"):
            raise SnapshotError(f"{self.ref(area, name)} was recorded as {status} by the collector")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            raise SnapshotError(f"{self.ref(area, name)} is not valid JSON")
        if data.get("status") != 0:
            raise SnapshotError(f"{self.ref(area, name)} holds an sf error, not data")
        self._cache[key] = data["result"]
        return data["result"]

    def records(self, area, name):
        """Records of a `sf data query` result."""
        result = self.load(area, name)
        if not isinstance(result, dict) or "records" not in result:
            raise SnapshotError(f"{self.ref(area, name)} is not a query result")
        if result.get("done") is False:
            raise SnapshotError(f"{self.ref(area, name)} is incomplete (done: false)")
        return result["records"]
