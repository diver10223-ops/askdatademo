"""Run the complete POC role/scenario/required-turn acceptance matrix."""
import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path

os.environ["ASKDATA_DATA_DIR"] = tempfile.mkdtemp(prefix="askdata-matrix-")

from app.config import PLATFORM_DB  # noqa: E402
from app.db import connect, restore_baseline  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.models import PipelineContext  # noqa: E402


def main() -> None:
    restore_baseline()
    baseline = json.loads(
        (Path(__file__).parents[1] / "fixtures/official_baseline_v1.json").read_text()
    )
    engine, checked = Engine(), 0
    for scenario in baseline["scenarios"]:
        for case in scenario["cases"]:
            session_id, role = str(uuid.uuid4()), case["role_id"]
            permission_data = next(item for item in baseline["roles"] if item["id"] == role)
            with connect(PLATFORM_DB) as db:
                permission = db.execute(
                    "SELECT permissions FROM roles WHERE id=?", (role,)
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,"
                    "config_version_id,created_at) VALUES(?,?,?,?,?,?)",
                    (session_id, role, str(uuid.uuid4()), permission, "official-v1", "now"),
                )
            parent = None
            for turn in case["turns"]:
                request_id = str(uuid.uuid4())
                with connect(PLATFORM_DB) as db:
                    context = json.loads(
                        db.execute("SELECT context FROM sessions WHERE id=?", (session_id,)).fetchone()[0]
                    )
                    db.execute(
                        "INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,"
                        "case_id,question,mode,status,config_version_id,created_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (request_id, session_id, parent, str(uuid.uuid4()), scenario["id"],
                         case["id"], turn["question"], "POC", "PENDING", "official-v1", "now"),
                    )
                asyncio.run(engine.run(PipelineContext(
                    session_id, request_id, role, "official-v1", turn["question"], parent,
                    scenario["id"], case["id"], parameters=context,
                    permissions=permission_data, config=baseline,
                )))
                with connect(PLATFORM_DB) as db:
                    request = db.execute(
                        "SELECT status,last_layer FROM requests WHERE id=?", (request_id,)
                    ).fetchone()
                    layer_count = db.execute(
                        "SELECT COUNT(*) FROM layer_executions WHERE request_id=?", (request_id,)
                    ).fetchone()[0]
                last = turn["expected_last_layer"]
                assert (request["status"], request["last_layer"]) == (
                    turn["expected_status"], last
                ), (case["id"], turn["turn"], dict(request))
                assert layer_count == int(last[1:]), (case["id"], turn["turn"], layer_count)
                parent, checked = request_id, checked + 1
    print(f"OK: POC matrix 3 roles x 8 scenarios, {checked} required turns")


if __name__ == "__main__":
    main()
