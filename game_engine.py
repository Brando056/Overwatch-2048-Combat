from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# 定义棋盘和游戏资源的基础限制。
BOARD_SIZE = 5
EMPTY = 0
BLOCKED = -1
MAX_SKILL_CHARGES = 5
MAX_RECALL_USES = 3

# 保存移动方向对应的行列变化量。
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}

# 用于处理敌方技能造成的反向移动效果。
OPPOSITE_DIRECTION = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}

# 敌方可能使用的技能标识。
ENEMY_SKILLS = (
    "seismic_slam",
    "shadow_consume",
    "system_hack",
    "gravity_field",
    "cage_fight",
)

# 惊喜盒子可能触发的效果标识。
MYSTERY_BOX_EFFECTS = (
    "full_heal",
    "dragon_blade",
    "kitsune_rush",
    "gravity_field",
    "biotic_orb",
    "cage_fight",
)

# 战斗模式中可随机抽取的任务。
MISSIONS = (
    {
        "id": "T01",
        "title": "Reach 512",
        "description": "Have a tile valued at 512 or more.",
    },
    {
        "id": "T02",
        "title": "Rapid Merge",
        "description": "Complete 5 merges within the first 7 turns.",
    },
    {
        "id": "T03",
        "title": "High Score Action",
        "description": "Score at least 500 points in one turn.",
    },
)

# 挑战模式中可随机抽取的任务。
CHALLENGE_MISSIONS = (
    {
        "id": "C01",
        "title": "Merge 256",
        "description": "Create a tile valued at 256 or more.",
    },
    {
        "id": "C02",
        "title": "Score 5000",
        "description": "Reach a score of 5000.",
    },
    {
        "id": "C03",
        "title": "Complete Merges",
        "description": "Complete at least 8 merges.",
    },
    {
        "id": "C04",
        "title": "Keep Space",
        "description": "Reach 128 while keeping at least 3 empty cells.",
    },
    {
        "id": "C05",
        "title": "Triple 128",
        "description": "Have at least three 128 tiles at the same time.",
    },
)


@dataclass
class MovePreview:
    """保存一次移动在真正结算前的预览结果。"""

    direction: str
    effective_direction: str
    normal_board: list[list[int]]
    no_merge_board: list[list[int]]
    merges: list[int]
    normal_changed: bool
    no_merge_changed: bool
    bug_triggered: bool


@dataclass
class TurnResult:
    """保存一回合或一次技能操作完成后的结果。"""

    success: bool
    message: str = ""
    merges: Optional[list[int]] = None
    bug_triggered: bool = False
    bug_correct: Optional[bool] = None
    game_over: bool = False
    result: Optional[str] = None
    rescue_type: Optional[str] = None
    enemy_skill: Optional[str] = None
    mystery_effect: Optional[str] = None
    wrong_streak_penalty: bool = False


class GameEngine:
    """负责棋盘、战斗、任务和技能规则的核心引擎。"""

    def __init__(
        self,
        mode: str = "battle",
        rng: Optional[random.Random] = None,
    ) -> None:
        # 注入随机数生成器，便于游戏运行和单元测试使用不同的随机状态。
        self.rng = rng or random.Random()
        self.reset(mode)

    def reset(self, mode: str) -> None:
        # 根据模式重新建立完整的游戏状态。
        if mode not in {"battle", "challenge"}:
            raise ValueError("mode must be 'battle' or 'challenge'")

        self.mode = mode
        self.board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.blocked_until: dict[tuple[int, int], int] = {}
        self.mystery_box: Optional[tuple[int, int]] = None
        self.mystery_box_spawned = False
        self.score = 0
        self.turn = 0
        self.skill_charges = 3
        self.skill_used_this_turn = False
        self.recall_uses = 0
        self.reverse_next_move = False
        self.last_enemy_skill: Optional[str] = None
        self.player_max_hp = 500 if mode == "battle" else None
        self.player_hp = 500 if mode == "battle" else None
        self.enemy_max_hp = 200 if mode == "battle" else None
        self.enemy_hp = 200 if mode == "battle" else None
        self.bug_correct_streak = 0
        self.bug_wrong_streak = 0
        self.death_count = 0
        self.rescue_used = False
        self.pending_rescue_type: Optional[str] = None
        self.game_over = False
        self.game_result: Optional[str] = None
        self.status_message = "Select a direction to begin."
        self.merge_counts: dict[int, int] = {
            4: 0,
            8: 0,
            16: 0,
            32: 0,
            64: 0,
            128: 0,
        }
        self.highest_tile = 0
        self.first_seven_merge_count = 0
        self.total_merges = 0
        self.current_turn_score = 0
        self.mission = self.rng.choice(MISSIONS) if mode == "battle" else None
        self.challenge_mission = (
            self.rng.choice(CHALLENGE_MISSIONS) if mode == "challenge" else None
        )
        self.mission_complete = False
        self.snapshots: list[dict[str, Any]] = []
        self.pending_preview: Optional[MovePreview] = None

        # 战斗模式从少量低数值方块开始，挑战模式使用预先生成的棋盘。
        if mode == "battle":
            self._place_random_tiles(3, {2: 0.90, 4: 0.10})
        else:
            self._create_challenge_board()
        self._update_highest_tile()

    @property
    def is_battle(self) -> bool:
        # 提供比直接比较模式字符串更清晰的判断方式。
        return self.mode == "battle"

    @property
    def is_challenge(self) -> bool:
        # 提供挑战模式的便捷判断属性。
        return self.mode == "challenge"

    @property
    def turns_until_enemy_skill(self) -> int:
        # 距离下一次敌方技能触发还剩多少回合（技能固定每 8 回合触发一次）。
        return 8 - (self.turn % 8)

    def _create_challenge_board(self) -> None:
        # 尝试生成一个既有空位又至少存在一步有效移动的挑战棋盘。
        probabilities = {2: 0.45, 4: 0.30, 8: 0.15, 16: 0.07, 32: 0.03}
        for _ in range(100):
            self.board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
            self._place_random_tiles(20, probabilities)
            if self.empty_cells() and self.has_valid_move():
                return

        self.board = [
            [2, 4, 8, 16, 2],
            [4, 8, 16, 32, 4],
            [8, 16, 32, 2, 0],
            [16, 32, 2, 4, 8],
            [0, 2, 16, 0, 0],
        ]

    def _place_random_tiles(self, count: int, probabilities: dict[int, float]) -> None:
        # 在随机空位中放置指定数量的新方块。
        for _ in range(count):
            cells = self.empty_cells()
            if not cells:
                return
            row, column = self.rng.choice(cells)
            self.board[row][column] = self._weighted_choice(probabilities)

    def _weighted_choice(self, probabilities: dict[int, float]) -> int:
        # 按传入概率表选择一个新方块数值。
        threshold = self.rng.random()
        cumulative = 0.0
        for value, probability in probabilities.items():
            cumulative += probability
            if threshold < cumulative:
                return value
        return next(reversed(probabilities))

    def empty_cells(self) -> list[tuple[int, int]]:
        # 返回可以放置方块的空位，惊喜盒子所在位置不能重复放置。
        return [
            (row, column)
            for row in range(BOARD_SIZE)
            for column in range(BOARD_SIZE)
            if self.board[row][column] == EMPTY
            and (row, column) != self.mystery_box
        ]

    def tile_cells(self) -> list[tuple[int, int]]:
        # 返回当前所有数字方块的位置。
        return [
            (row, column)
            for row in range(BOARD_SIZE)
            for column in range(BOARD_SIZE)
            if self.board[row][column] > EMPTY
        ]

    def tile_values(self) -> list[int]:
        # 返回当前所有数字方块的数值，用于统计和任务判断。
        return [self.board[row][column] for row, column in self.tile_cells()]

    def current_bug_probability(self) -> float:
        # 战斗模式中的错误概率会随回合数增加，但有最高上限。
        if not self.is_battle:
            return 0.0
        return min(0.05 + ((self.turn + 1) // 10) * 0.05, 0.30)

    def tile_probabilities(self, next_turn: Optional[int] = None) -> dict[int, float]:
        # 根据下一回合的阶段调整新生成方块的数值分布。
        turn = self.turn + 1 if next_turn is None else next_turn
        if turn >= 40:
            return {2: 0.75, 4: 0.15, 8: 0.07, 16: 0.03}
        if turn >= 20:
            return {2: 0.85, 4: 0.10, 8: 0.05}
        return {2: 0.90, 4: 0.10}

    def _update_highest_tile(self) -> None:
        # 更新当前棋盘上的最高方块数值。
        self.highest_tile = max(self.tile_values() or [0])

    def parse_coordinate(self, text: str) -> Optional[tuple[int, int]]:
        # 将类似 A1 的用户坐标转换为从零开始的行列坐标。
        cleaned = text.strip().upper()
        if len(cleaned) != 2 or cleaned[0] not in "ABCDE" or cleaned[1] not in "12345":
            return None
        return int(cleaned[1]) - 1, ord(cleaned[0]) - ord("A")

    def coordinate_label(self, coordinate: tuple[int, int]) -> str:
        # 将内部行列坐标转换回界面显示的字母数字坐标。
        row, column = coordinate
        return f"{chr(ord('A') + column)}{row + 1}"

    def _line_positions(self, direction: str, line_index: int) -> list[tuple[int, int]]:
        # 按移动方向生成一行或一列的处理顺序。
        if direction in {"left", "right"}:
            positions = [(line_index, column) for column in range(BOARD_SIZE)]
        else:
            positions = [(row, line_index) for row in range(BOARD_SIZE)]
        if direction in {"right", "down"}:
            positions.reverse()
        return positions

    @staticmethod
    def _transform_segment(
        values: list[int],
        allow_merge: bool,
    ) -> tuple[list[int], list[int]]:
        # 先压缩空位，再按 2048 规则合并相邻且相等的方块。
        compact = [value for value in values if value > EMPTY]
        result: list[int] = []
        merges: list[int] = []
        index = 0
        while index < len(compact):
            if allow_merge and index + 1 < len(compact) and compact[index] == compact[index + 1]:
                merged_value = compact[index] * 2
                result.append(merged_value)
                merges.append(merged_value)
                index += 2
            else:
                result.append(compact[index])
                index += 1
        result.extend([EMPTY] * (len(values) - len(result)))
        return result, merges

    def _simulate_board(
        self,
        direction: str,
        allow_merge: bool,
    ) -> tuple[list[list[int]], list[int]]:
        # 在不直接修改真实棋盘的情况下，计算一次移动后的结果。
        result = copy.deepcopy(self.board)
        all_merges: list[int] = []

        for line_index in range(BOARD_SIZE):
            positions = self._line_positions(direction, line_index)
            segment: list[tuple[int, int]] = []

            def flush_segment() -> None:
                # 将连续的可移动区域压缩并写回模拟棋盘。
                nonlocal segment
                if not segment:
                    return
                values = [self.board[row][column] for row, column in segment]
                transformed, merges = self._transform_segment(values, allow_merge)
                for position, value in zip(segment, transformed):
                    result[position[0]][position[1]] = value
                all_merges.extend(merges)
                segment = []

            for position in positions:
                value = self.board[position[0]][position[1]]
                if value == BLOCKED:
                    flush_segment()
                    result[position[0]][position[1]] = BLOCKED
                else:
                    segment.append(position)
            flush_segment()

        return result, all_merges

    @staticmethod
    def _board_changed(
        left: list[list[int]],
        right: list[list[int]],
    ) -> bool:
        # 通过比较二维列表判断移动是否真正改变了棋盘。
        return left != right

    def has_valid_move(self) -> bool:
        # 有空位，或至少有一个方向可以移动/合并时，游戏仍可继续。
        if self.empty_cells():
            return True
        for direction in DIRECTIONS:
            simulated, _ = self._simulate_board(direction, allow_merge=True)
            if self._board_changed(self.board, simulated):
                return True
        return False

    def start_move(self, direction: str) -> Optional[MovePreview]:
        # 创建移动预览，并暂存移动前状态，供错误题目和回溯技能使用。
        if self.game_over or self.pending_rescue_type:
            return None
        direction = direction.strip().lower()
        if direction not in DIRECTIONS:
            return None

        effective_direction = direction
        if self.reverse_next_move:
            effective_direction = OPPOSITE_DIRECTION[direction]

        normal_board, merges = self._simulate_board(effective_direction, allow_merge=True)
        no_merge_board, _ = self._simulate_board(effective_direction, allow_merge=False)
        normal_changed = self._board_changed(self.board, normal_board)
        no_merge_changed = self._board_changed(self.board, no_merge_board)
        if not normal_changed:
            return None

        if self.reverse_next_move:
            self.reverse_next_move = False
        bug_triggered = self.is_battle and self.rng.random() < self.current_bug_probability()
        preview = MovePreview(
            direction=direction,
            effective_direction=effective_direction,
            normal_board=normal_board,
            no_merge_board=no_merge_board,
            merges=merges,
            normal_changed=normal_changed,
            no_merge_changed=no_merge_changed,
            bug_triggered=bug_triggered,
        )
        self.pending_preview = preview
        self.snapshots.append(self._snapshot())
        return preview

    def resolve_move(
        self,
        preview: MovePreview,
        bug_correct: bool = True,
    ) -> TurnResult:
        # 根据答题结果结算移动、合并、惊喜盒子、敌方事件和游戏结束条件。
        if self.pending_preview is not preview:
            return TurnResult(False, "This move is no longer available.")

        snapshot = self.snapshots[-1]
        bug_triggered = preview.bug_triggered
        mystery_box_hit = self._mystery_box_will_be_hit(preview.effective_direction)
        if bug_triggered and not bug_correct:
            self.board = copy.deepcopy(preview.no_merge_board)
            merges: list[int] = []
        else:
            self.board = copy.deepcopy(preview.normal_board)
            merges = preview.merges

        if merges:
            self._apply_merges(merges)
            self.score += sum(merges)

        mystery_effect = self.activate_mystery_box() if mystery_box_hit else None
        actual_changed = self._board_changed(self.board, snapshot["board"])
        if actual_changed and self.empty_cells():
            self._spawn_tile()

        self.turn += 1
        self.current_turn_score = sum(merges)
        wrong_streak_penalty = False
        if bug_triggered:
            if bug_correct:
                self.bug_correct_streak += 1
                self.bug_wrong_streak = 0
            else:
                self.bug_correct_streak = 0
                self.bug_wrong_streak += 1
            if self.bug_correct_streak >= 5:
                self.skill_charges = min(MAX_SKILL_CHARGES, self.skill_charges + 1)
                self.bug_correct_streak = 0
            if self.bug_wrong_streak >= 5:
                self._apply_wrong_streak_penalty()
                self.bug_wrong_streak = 0
                wrong_streak_penalty = True

        self._update_highest_tile()
        self._update_mission()
        self._update_challenge_mission()
        self._spawn_mystery_box()
        enemy_skill = self._apply_enemy_events() if self.enemy_hp is None or self.enemy_hp > 0 else None
        self._remove_expired_blocks()
        self.skill_used_this_turn = False
        self.pending_preview = None

        if self.enemy_hp is not None and self.enemy_hp <= 0:
            return self._finish("win", "Enemy defeated.", enemy_skill, mystery_effect)

        if self.is_battle:
            if self.player_hp is not None and self.player_hp <= 0:
                self.death_count += 1
                if self.death_count > 1:
                    return self._finish("loss", "Player defeated.", enemy_skill, mystery_effect)
                return self._request_rescue("death")
            if not self.has_valid_move():
                return self._request_rescue("board")
        elif self.mission_complete:
            return self._finish("win", "Challenge objective completed.", enemy_skill, mystery_effect)
        elif not self.has_valid_move():
            return self._finish("loss", "No valid moves remain.", enemy_skill, mystery_effect)

        self.status_message = self._format_turn_message(
            merges=merges,
            bug_triggered=bug_triggered,
            bug_correct=bug_correct if bug_triggered else None,
            enemy_skill=enemy_skill,
            mystery_effect=mystery_effect,
            wrong_streak_penalty=wrong_streak_penalty,
        )
        return TurnResult(
            True,
            self.status_message,
            merges=merges,
            bug_triggered=bug_triggered,
            bug_correct=bug_correct if bug_triggered else None,
            enemy_skill=enemy_skill,
            mystery_effect=mystery_effect,
            wrong_streak_penalty=wrong_streak_penalty,
        )

    def _snapshot(self) -> dict[str, Any]:
        # 保存所有会影响后续规则的状态，确保 Recall 可以完整恢复。
        return {
            "board": copy.deepcopy(self.board),
            "blocked_until": copy.deepcopy(self.blocked_until),
            "mystery_box": self.mystery_box,
            "mystery_box_spawned": self.mystery_box_spawned,
            "score": self.score,
            "turn": self.turn,
            "player_max_hp": self.player_max_hp,
            "player_hp": self.player_hp,
            "enemy_max_hp": self.enemy_max_hp,
            "enemy_hp": self.enemy_hp,
            "bug_correct_streak": self.bug_correct_streak,
            "bug_wrong_streak": self.bug_wrong_streak,
            "death_count": self.death_count,
            "rescue_used": self.rescue_used,
            "pending_rescue_type": self.pending_rescue_type,
            "last_enemy_skill": self.last_enemy_skill,
            "reverse_next_move": self.reverse_next_move,
            "merge_counts": copy.deepcopy(self.merge_counts),
            "highest_tile": self.highest_tile,
            "first_seven_merge_count": self.first_seven_merge_count,
            "total_merges": self.total_merges,
            "current_turn_score": self.current_turn_score,
            "mission_complete": self.mission_complete,
            "rng_state": self.rng.getstate(),
        }

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        # 从快照恢复棋盘、战斗数据、任务数据和随机数状态。
        self.board = copy.deepcopy(snapshot["board"])
        self.blocked_until = copy.deepcopy(snapshot["blocked_until"])
        self.mystery_box = snapshot["mystery_box"]
        self.mystery_box_spawned = snapshot["mystery_box_spawned"]
        self.score = snapshot["score"]
        self.turn = snapshot["turn"]
        self.player_max_hp = snapshot["player_max_hp"]
        self.player_hp = snapshot["player_hp"]
        self.enemy_max_hp = snapshot["enemy_max_hp"]
        self.enemy_hp = snapshot["enemy_hp"]
        self.bug_correct_streak = snapshot["bug_correct_streak"]
        self.bug_wrong_streak = snapshot["bug_wrong_streak"]
        self.death_count = snapshot["death_count"]
        self.rescue_used = snapshot["rescue_used"]
        self.pending_rescue_type = snapshot["pending_rescue_type"]
        self.last_enemy_skill = snapshot["last_enemy_skill"]
        self.reverse_next_move = snapshot["reverse_next_move"]
        self.merge_counts = copy.deepcopy(snapshot["merge_counts"])
        self.highest_tile = snapshot["highest_tile"]
        self.first_seven_merge_count = snapshot["first_seven_merge_count"]
        self.total_merges = snapshot["total_merges"]
        self.current_turn_score = snapshot["current_turn_score"]
        self.mission_complete = snapshot["mission_complete"]
        self.rng.setstate(snapshot["rng_state"])

    def _apply_merges(self, merges: list[int]) -> None:
        # 统计合并次数，并在达到阈值时发放对应奖励。
        self.total_merges += len(merges)
        for merged_value in merges:
            counter_key = merged_value if merged_value in self.merge_counts else 128
            self.merge_counts[counter_key] += 1
            threshold, reward = self._merge_reward(merged_value)
            while self.merge_counts[counter_key] >= threshold:
                self.merge_counts[counter_key] -= threshold
                self._apply_reward(reward, merged_value)

        if self.turn < 7:
            self.first_seven_merge_count += len(merges)

    @staticmethod
    def _merge_reward(merged_value: int) -> tuple[int, str]:
        # 将合并后的数值映射到奖励触发次数和奖励类型。
        if merged_value == 4:
            return 2, "damage_10"
        if merged_value == 8:
            return 5, "heal_10"
        if merged_value == 16:
            return 3, "max_hp_10"
        if merged_value == 32:
            return 2, "damage_35"
        if merged_value == 64:
            return 1, "skill_charge"
        return 3, "damage_value"

    def _apply_reward(self, reward: str, merged_value: int) -> None:
        # 执行由合并奖励产生的治疗、伤害、生命上限或技能充能。
        if reward == "damage_10":
            self._damage_enemy(10)
        elif reward == "heal_10":
            self._heal_player(10)
        elif reward == "max_hp_10":
            if self.player_max_hp is not None:
                self.player_max_hp += 10
                self._heal_player(10)
        elif reward == "damage_35":
            self._damage_enemy(35)
        elif reward == "skill_charge":
            self.skill_charges = min(MAX_SKILL_CHARGES, self.skill_charges + 1)
        elif reward == "damage_value":
            self._damage_enemy(merged_value)

    def _damage_enemy(self, amount: int) -> None:
        # 扣除敌方生命值，并确保生命值不会低于零。
        if self.enemy_hp is not None:
            self.enemy_hp = max(0, self.enemy_hp - amount)

    def _heal_player(self, amount: int) -> None:
        # 恢复玩家生命值，但不超过当前生命上限。
        if self.player_hp is not None and self.player_max_hp is not None:
            self.player_hp = min(self.player_max_hp, self.player_hp + amount)

    def _damage_player(self, amount: int) -> None:
        # 扣除玩家生命值，并确保生命值不会低于零。
        if self.player_hp is not None:
            self.player_hp = max(0, self.player_hp - amount)

    def _apply_wrong_streak_penalty(self) -> None:
        # 连续答错 5 道 Bug 题时，扣除当前最大生命值 20%（向下取整）。
        if self.player_max_hp is not None:
            self._damage_player(int(self.player_max_hp * 0.2))

    def _spawn_tile(self) -> None:
        # 在移动后随机空位生成一个新方块。
        cells = self.empty_cells()
        if not cells:
            return
        row, column = self.rng.choice(cells)
        self.board[row][column] = self._weighted_choice(self.tile_probabilities())

    def _update_mission(self) -> None:
        # 检查战斗模式任务是否已经达成。
        if not self.is_battle or self.mission is None or self.mission_complete:
            return

        mission_id = self.mission["id"]
        if mission_id == "T01":
            completed = self.highest_tile >= 512
        elif mission_id == "T02":
            completed = self.turn <= 7 and self.first_seven_merge_count >= 5
        else:
            completed = self.current_turn_score >= 500

        if completed:
            self.mission_complete = True

    def _update_challenge_mission(self) -> None:
        # 检查挑战模式目标是否已经达成。
        if not self.is_challenge or self.challenge_mission is None or self.mission_complete:
            return

        mission_id = self.challenge_mission["id"]
        if mission_id == "C01":
            completed = self.highest_tile >= 256
        elif mission_id == "C02":
            completed = self.score >= 5000
        elif mission_id == "C03":
            completed = self.total_merges >= 8
        elif mission_id == "C04":
            completed = self.highest_tile >= 128 and len(self.empty_cells()) >= 3
        else:
            completed = self.tile_values().count(128) >= 3

        if completed:
            self.mission_complete = True

    def _spawn_mystery_box(self) -> None:
        # 战斗任务完成后，在棋盘空位生成一次惊喜盒子。
        if (
            not self.is_battle
            or not self.mission_complete
            or self.mystery_box is not None
            or self.mystery_box_spawned
        ):
            return
        self.mystery_box_spawned = True
        cells = self.empty_cells()
        if cells:
            self.mystery_box = self.rng.choice(cells)

    def activate_mystery_box(self) -> Optional[str]:
        # 触发惊喜盒子并执行随机效果。
        if self.mystery_box is None:
            return None

        effect = self.rng.choice(MYSTERY_BOX_EFFECTS)
        self.mystery_box = None
        if effect == "full_heal":
            if self.player_hp is not None and self.player_max_hp is not None:
                self.player_hp = self.player_max_hp
        elif effect == "dragon_blade":
            self._damage_enemy(100)
        elif effect == "kitsune_rush":
            self.skill_charges = min(MAX_SKILL_CHARGES, self.skill_charges + 3)
        elif effect == "gravity_field":
            values = self.tile_values()
            if values:
                maximum = max(values)
                for row, column in self.tile_cells():
                    if self.board[row][column] == maximum:
                        self.board[row][column] //= 2
        elif effect == "biotic_orb":
            self._damage_player(10)
        elif effect == "cage_fight":
            cells = self.empty_cells()
            if cells:
                position = self.rng.choice(cells)
                self.board[position[0]][position[1]] = BLOCKED
                self.blocked_until[position] = self.turn + 3
        return effect

    def _mystery_box_will_be_hit(self, direction: str) -> bool:
        # 判断本次移动是否会让数字方块经过惊喜盒子所在位置。
        if self.mystery_box is None:
            return False

        target = self.mystery_box
        for line_index in range(BOARD_SIZE):
            positions = self._line_positions(direction, line_index)
            segment: list[tuple[int, int]] = []

            def segment_hits_target() -> bool:
                # 目标位置后方存在数字方块时，目标会在本次移动中被触发。
                if target not in segment:
                    return False
                target_index = segment.index(target)
                return any(
                    self.board[row][column] > EMPTY
                    for row, column in segment[target_index + 1 :]
                )

            for position in positions:
                row, column = position
                if self.board[row][column] == BLOCKED:
                    if segment_hits_target():
                        return True
                    segment = []
                else:
                    segment.append(position)
            if segment_hits_target():
                return True
        return False

    def _apply_enemy_events(self) -> Optional[str]:
        # 处理定期敌方技能以及战斗模式中的普通攻击。
        enemy_skill = None
        if self.turn % 8 == 0:
            enemy_skill = self._use_enemy_skill()
        if self.is_battle and self.turn % 2 == 0 and self.enemy_hp and self.enemy_hp > 0:
            self._damage_player(15)
        return enemy_skill

    def _use_enemy_skill(self) -> Optional[str]:
        # 随机选择一个与上次不同的敌方技能并立即执行。
        candidates = [skill for skill in ENEMY_SKILLS if skill != self.last_enemy_skill]
        skill = self.rng.choice(candidates or list(ENEMY_SKILLS))
        self.last_enemy_skill = skill

        if skill == "seismic_slam":
            positions = self.tile_cells()
            values = [self.board[row][column] for row, column in positions]
            self.rng.shuffle(values)
            for position, value in zip(positions, values):
                self.board[position[0]][position[1]] = value
        elif skill == "shadow_consume":
            positions = self.tile_cells()
            if positions:
                row, column = self.rng.choice(positions)
                self.board[row][column] = EMPTY
        elif skill == "system_hack":
            self.reverse_next_move = True
        elif skill == "gravity_field":
            for row, column in self.tile_cells():
                if self.board[row][column] > 16:
                    self.board[row][column] //= 2
        elif skill == "cage_fight":
            cells = self.empty_cells()
            if cells:
                position = self.rng.choice(cells)
                self.board[position[0]][position[1]] = BLOCKED
                self.blocked_until[position] = self.turn + 3
        return skill

    def _remove_expired_blocks(self) -> None:
        # 清除已经达到持续时间的阻挡格。
        expired = [
            position
            for position, expiry in self.blocked_until.items()
            if expiry <= self.turn
        ]
        for position in expired:
            row, column = position
            if self.board[row][column] == BLOCKED:
                self.board[row][column] = EMPTY
            self.blocked_until.pop(position, None)

    def _format_turn_message(
        self,
        merges: list[int],
        bug_triggered: bool,
        bug_correct: Optional[bool],
        enemy_skill: Optional[str],
        mystery_effect: Optional[str],
        wrong_streak_penalty: bool = False,
    ) -> str:
        # 将本回合发生的主要事件整理为界面状态栏文本。
        parts = [f"Turn {self.turn} completed."]
        if merges:
            parts.append(f"Merged {', '.join(str(value) for value in merges)}.")
        if bug_triggered and bug_correct:
            parts.append("Bug answer correct.")
        elif bug_triggered:
            parts.append("Bug answer incorrect. Merge disabled.")
        if wrong_streak_penalty:
            parts.append("5 wrong answers in a row: lost 20% of max HP.")
        if enemy_skill:
            parts.append(f"Enemy skill: {enemy_skill.replace('_', ' ').title()}.")
        if mystery_effect:
            parts.append(f"Mystery box: {mystery_effect.replace('_', ' ').title()}.")
        if self.is_battle and self.turn % 2 == 0:
            parts.append("Enemy attack dealt 15 damage.")
        return " ".join(parts)

    def _request_rescue(self, rescue_type: str) -> TurnResult:
        # 在玩家死亡或棋盘无路可走时进入一次救援答题流程。
        if self.rescue_used:
            return self._finish("loss", "Rescue has already been used.")
        self.pending_rescue_type = rescue_type
        self.status_message = "Rescue required. Answer three questions correctly."
        return TurnResult(True, self.status_message, rescue_type=rescue_type)

    def resolve_rescue(self, success: bool) -> TurnResult:
        # 根据救援答题结果恢复生命值或清理棋盘方块。
        if not self.pending_rescue_type:
            return TurnResult(False, "No rescue is pending.")
        rescue_type = self.pending_rescue_type
        self.pending_rescue_type = None
        if not success:
            return self._finish("loss", "Rescue failed.")

        self.rescue_used = True
        self.bug_correct_streak = 0
        self.bug_wrong_streak = 0
        if rescue_type == "death":
            if self.player_max_hp is not None:
                self.player_hp = self.player_max_hp // 2
        else:
            positions = self.tile_cells()
            self.rng.shuffle(positions)
            for row, column in positions[:3]:
                self.board[row][column] = EMPTY
        self.status_message = "Rescue successful. Continue the game."
        return TurnResult(True, self.status_message)

    def use_skill(
        self,
        skill_id: str,
        coordinate: Optional[tuple[int, int]] = None,
        increase: Optional[bool] = None,
    ) -> TurnResult:
        # 校验并执行玩家技能，每回合最多使用一次技能。
        if self.game_over or self.pending_rescue_type:
            return TurnResult(False, "Skills are unavailable right now.")
        if self.skill_used_this_turn:
            return TurnResult(False, "Only one skill can be used before the next turn.")
        if self.skill_charges <= 0:
            return TurnResult(False, "No skill charges available.")

        if skill_id == "delete":
            if coordinate is None or self._invalid_coordinate(coordinate):
                return TurnResult(False, "Select a numbered tile.")
            self.board[coordinate[0]][coordinate[1]] = EMPTY
        elif skill_id == "change":
            if coordinate is None or self._invalid_coordinate(coordinate):
                return TurnResult(False, "Select a numbered tile.")
            if increase is None:
                return TurnResult(False, "Choose increase or decrease.")
            value = self.board[coordinate[0]][coordinate[1]]
            next_value = value * 2 if increase else value // 2
            if next_value < 2 or next_value > 512:
                return TurnResult(False, "That value cannot be changed further.")
            self.board[coordinate[0]][coordinate[1]] = next_value
        elif skill_id == "recall":
            if self.recall_uses >= MAX_RECALL_USES or not self.snapshots:
                return TurnResult(False, "Recall is unavailable.")
            snapshot = self.snapshots.pop()
            charges_before_recall = self.skill_charges
            self._restore_snapshot(snapshot)
            self.skill_charges = max(0, charges_before_recall - 1)
            self.recall_uses += 1
            self.skill_used_this_turn = True
            self.status_message = "Previous state restored."
            return TurnResult(True, self.status_message)
        else:
            return TurnResult(False, "Unknown skill.")

        self.skill_charges -= 1
        self.skill_used_this_turn = True
        self.status_message = f"{skill_id.replace('_', ' ').title()} activated."
        return TurnResult(True, self.status_message)

    def _invalid_coordinate(self, coordinate: tuple[int, int]) -> bool:
        # 判断坐标是否在棋盘内且对应一个数字方块。
        row, column = coordinate
        return not (
            0 <= row < BOARD_SIZE
            and 0 <= column < BOARD_SIZE
            and self.board[row][column] > EMPTY
        )

    def _finish(
        self,
        result: str,
        message: str,
        enemy_skill: Optional[str] = None,
        mystery_effect: Optional[str] = None,
    ) -> TurnResult:
        # 设置游戏结束状态，并返回最终结果。
        self.game_over = True
        self.game_result = result
        self.status_message = message
        return TurnResult(
            True,
            message,
            game_over=True,
            result=result,
            enemy_skill=enemy_skill,
            mystery_effect=mystery_effect,
        )


class QuestionManager:
    """负责读取题库、抽取题目和检查答案。"""

    def __init__(self, path: Path, rng: Optional[random.Random] = None) -> None:
        # 保存题库路径和随机数生成器，并在初始化时读取题目。
        self.path = path
        self.rng = rng or random.Random()
        self.questions = self._load_questions()
        self.used_ids: set[str] = set()

    def _load_questions(self) -> list[dict[str, Any]]:
        # 读取 JSON 题库，并验证其基本结构。
        with self.path.open("r", encoding="utf-8") as file:
            questions = json.load(file)
        if not isinstance(questions, list) or not questions:
            raise ValueError("Question file must contain a non-empty list.")
        for question in questions:
            if not isinstance(question, dict) or not question.get("id"):
                raise ValueError("Every question must have an id.")
        return questions

    def next_question(self) -> dict[str, Any]:
        # 优先抽取尚未使用的题目，全部使用后再开始新一轮。
        available = [item for item in self.questions if item["id"] not in self.used_ids]
        if not available:
            self.used_ids.clear()
            available = list(self.questions)
        question = self.rng.choice(available)
        self.used_ids.add(question["id"])
        return question

    @staticmethod
    def check_answer(question: dict[str, Any], answer: str) -> bool:
        # 选择题忽略大小写，文本题同时忽略大小写和首尾空格。
        submitted = answer.strip()
        expected = str(question.get("answer", "")).strip()
        if question.get("type") == "choice":
            return submitted.upper() == expected.upper()
        return submitted.casefold() == expected.casefold()
