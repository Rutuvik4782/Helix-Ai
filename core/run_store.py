import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class RunStore:
    def __init__(self, file_path: str):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8"):
                pass

    def save_run(self, payload: Dict) -> Dict:
        record = {
            "run_id": payload.get("run_id") or uuid4().hex,
            "created_at": payload.get("created_at") or datetime.utcnow().isoformat() + "Z",
            **payload,
        }
        with open(self.file_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        return record

    def list_runs(self, limit: int = 20) -> List[Dict]:
        runs = self._read_all()
        runs.reverse()
        return [self._summarize(run) for run in runs[:limit]]

    def get_run(self, run_id: str) -> Optional[Dict]:
        for run in reversed(self._read_all()):
            if run.get("run_id") == run_id:
                return run
        return None

    def _read_all(self) -> List[Dict]:
        runs = []
        with open(self.file_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    runs.append(json.loads(line))
        return runs

    def _summarize(self, run: Dict) -> Dict:
        return {
            "run_id": run.get("run_id"),
            "created_at": run.get("created_at"),
            "probable_source_version": run.get("probable_source_version"),
            "risk_score": run.get("risk_score"),
            "validation_success": run.get("validation_success"),
            "applied_transformations": run.get("applied_transformations", []),
            "legacy_issue_count": run.get("legacy_issue_count", 0),
        }
