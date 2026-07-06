from typing import Dict, List, Optional
from core.database import save_run, list_runs, get_run

class RunStore:
    def __init__(self, file_path: str):
        # We ignore file_path since we now use SQLite DATABASE_PATH configured in settings,
        # but we keep the parameter in the constructor to avoid breaking main.py initialization.
        self.file_path = file_path

    def save_run(self, payload: Dict) -> Dict:
        return save_run(payload)

    def list_runs(self, limit: int = 20) -> List[Dict]:
        return list_runs(limit)

    def get_run(self, run_id: str) -> Optional[Dict]:
        return get_run(run_id)
