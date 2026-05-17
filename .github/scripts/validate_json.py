#!/usr/bin/env python3
"""
Validates JSON files in a Community Asset Bundle (CAB) repo.

Checks:
  1. Every .json file is syntactically valid with no duplicate keys
  2. hardpointdatadef_*.json:
       - Required fields: ID, HardpointData
       - ID matches the filename stem
       - HardpointData entries each have a 'location' string
       - No duplicate locations within one def
  3. mod.json has a Name field (when manifest keys are present)

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from pathlib import Path


def _make_dup_key_hook(dup_collector: list[str]):
    def hook(pairs: list[tuple[str, object]]) -> dict:
        seen: set[str] = set()
        result: dict = {}
        for key, value in pairs:
            if key in seen:
                dup_collector.append(key)
            seen.add(key)
            result[key] = value
        return result
    return hook


def validate_hardpoint(path: Path, data: dict, errors: list[str]) -> None:
    stem = path.stem  # e.g. hardpointdatadef_daikyu

    id_val = data.get("ID")
    if not id_val:
        errors.append(f"{path}: missing required field 'ID'")
    elif id_val != stem:
        errors.append(f"{path}: ID '{id_val}' does not match filename stem '{stem}'")

    hp_data = data.get("HardpointData")
    if hp_data is None:
        errors.append(f"{path}: missing required field 'HardpointData'")
        return
    if not isinstance(hp_data, list):
        errors.append(f"{path}: 'HardpointData' must be an array")
        return

    seen_locations: set[str] = set()
    for i, entry in enumerate(hp_data):
        if not isinstance(entry, dict):
            errors.append(f"{path}: HardpointData[{i}] is not an object")
            continue
        loc = entry.get("location")
        if not isinstance(loc, str) or not loc:
            errors.append(f"{path}: HardpointData[{i}] missing 'location' string")
            continue
        if loc in seen_locations:
            errors.append(f"{path}: duplicate location '{loc}' in HardpointData")
        seen_locations.add(loc)


def validate_file(path: Path, errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        errors.append(f"{path}: cannot read: {e}")
        return

    dup_keys: list[str] = []
    try:
        data = json.loads(text, object_pairs_hook=_make_dup_key_hook(dup_keys))
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return

    if dup_keys:
        errors.append(f"{path}: duplicate JSON keys: {sorted(set(dup_keys))}")

    if not isinstance(data, dict):
        return

    name = path.name.lower()

    if name.startswith("hardpointdatadef_"):
        validate_hardpoint(path, data, errors)
        return

    if name == "mod.json":
        manifest_keys = {"Name", "Enabled", "Active", "DLL", "Manifest", "DependsOn"}
        if data.keys() & manifest_keys and "Name" not in data:
            errors.append(f"{path}: mod.json missing required field 'Name'")


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors: list[str] = []
    total = 0

    for json_file in sorted(root.rglob("*.json")):
        if any(part.startswith(".") for part in json_file.parts):
            continue
        total += 1
        validate_file(json_file, errors)

    if errors:
        print(f"FAILED — {len(errors)} error(s) across {total} files:\n")
        for err in errors:
            print(f"  {err}")
        return 1

    print(f"OK — {total} JSON files passed validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
