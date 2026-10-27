from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


class Leaderboard:
    """负责读取、验证和保存排行榜数据。"""

    def __init__(self, path: Path) -> None:
        # 保存排行榜文件位置，并确保其父目录存在。
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        # 读取排行榜；文件不存在或内容损坏时返回空列表。
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
        # 验证记录后，仅将胜利记录加入排行榜并保留前五名。
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
        # 将排序后的记录写回 JSON 文件。
        try:
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(records, file, indent=2)
            return True
        except OSError:
            return False

    @staticmethod
    def _valid_record(record: Any) -> bool:
        # 检查单条排行榜记录是否包含正确的数据类型和字段。
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
