#!/usr/bin/env python3
"""Reject removal/narrowing of the frozen Java/Python internal API contract."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "contracts/internal-execution-v1.openapi.json"
BASELINE = ROOT / "contracts/baseline/internal-execution-v1.openapi.json"


def fail(message: str) -> None:
    print(f"CONTRACT INCOMPATIBLE: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    current = json.loads(CURRENT.read_text())
    baseline = json.loads(BASELINE.read_text())
    if "openapi" not in baseline:
        fail("baseline has not been frozen")
    for path, path_item in baseline["paths"].items():
        if path not in current["paths"]:
            fail(f"removed path {path}")
        for method in set(path_item) & {"get", "post", "put", "delete", "patch"}:
            if method not in current["paths"][path]:
                fail(f"removed operation {method.upper()} {path}")
    old_schemas = baseline["components"]["schemas"]
    new_schemas = current["components"]["schemas"]
    for name, old in old_schemas.items():
        if name not in new_schemas:
            fail(f"removed schema {name}")
        new = new_schemas[name]
        missing_required = set(old.get("required", [])) - set(new.get("required", []))
        if missing_required:
            fail(f"{name} no longer requires {sorted(missing_required)}")
        missing_properties = set(old.get("properties", {})) - set(new.get("properties", {}))
        if missing_properties:
            fail(f"{name} removed properties {sorted(missing_properties)}")
        if "enum" in old and not set(old["enum"]).issubset(new.get("enum", [])):
            fail(f"{name} narrowed enum")
    print(f"CONTRACT COMPATIBLE: {current['info']['version']} against frozen baseline")


if __name__ == "__main__":
    main()
