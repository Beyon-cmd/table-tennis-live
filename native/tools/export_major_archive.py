"""Mechanical export of the verified Python archive for the native app."""
from __future__ import annotations

import json
import ast
from pathlib import Path


def source_constant(path: Path, name: str):
    """Read archive literals without importing the legacy app or its dependencies."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{name} not found in {path}")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    events = source_constant(root / "data_sources" / "majors.py", "MAJOR_EVENTS")
    team_results = source_constant(root / "data_sources" / "major_team_results.py", "TEAM_RESULTS")
    destination = Path(__file__).resolve().parents[1] / "TableTennisLive.Core" / "Data" / "historical-majors.json"
    payload = {
        "events": events,
        "teams": {f"{event_id}|{discipline}": result
                  for (event_id, discipline), result in team_results.items()},
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(events)} events and {len(team_results)} team records")


if __name__ == "__main__":
    main()
