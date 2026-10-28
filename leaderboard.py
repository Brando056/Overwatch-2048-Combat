from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


class Leaderboard:
    """Responsible for reading, validating, and saving leaderboard data."""

    def __init__(self, path: Path) -> None:
        # Store the leaderboard file location and make sure its parent directory exists.
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        # Read the leaderboard; return an empty list if the file is missing or corrupted.
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                return []
            return [record for record in data if self._valid_record(record)]
        except (OSError, json.JSONDecodeError):
            return []

    def add(
        self,
        name: str,
        mode: str,
        score: int,
        turns: int,
        result: str = "win",
    ) -> bool:
        # After validating the record, add only winning records to the leaderboard and keep the top five.
        cleaned_name = name.strip()
        if not 1 <= len(cleaned_name) <= 20:
            return False
        if mode not in {"battle", "challenge"}:
            return False
        if result not in {"win", "loss", "quit"}:
            return False
        record = {
            "name": cleaned_name,
            "mode": mode,
            "difficulty": "none" if mode == "challenge" else "easy",
            "score": max(0, int(score)),
            "turns": max(0, int(turns)),
            "result": result,
            "date": date.today().isoformat(),
        }
        records = self.load()
        if result == "win":
            records.append(record)
        records.sort(key=lambda item: (-item["score"], item["turns"], item["date"]))
        records = records[:5]
        return self._save(records)

    def _save(self, records: list[dict[str, Any]]) -> bool:
        # Write the sorted records back to the JSON file.
        try:
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(records, file, indent=2)
            return True
        except OSError:
            return False

    @staticmethod
    def _valid_record(record: Any) -> bool:
        # Check whether a single leaderboard record has the correct data types and fields.
        if not isinstance(record, dict):
            return False
        required = {"name", "mode", "difficulty", "score", "turns", "result", "date"}
        if not required.issubset(record):
            return False
        return (
            isinstance(record["name"], str)
            and record["mode"] in {"battle", "challenge"}
            and isinstance(record["score"], int)
            and isinstance(record["turns"], int)
            and record["result"] in {"win", "loss", "quit"}
            and isinstance(record["date"], str)
        )