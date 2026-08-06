from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("ASKDATA_DATA_DIR", ROOT / "data"))
PLATFORM_DB = DATA_DIR / "platform.db"
WAREHOUSE_DB = DATA_DIR / "mock_warehouse.db"
BASELINE = ROOT / "fixtures" / "official_baseline_v1.json"
