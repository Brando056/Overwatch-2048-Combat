from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# Define the basic limits for the board and game resources.
BOARD_SIZE = 5
EMPTY = 0
BLOCKED = -1
MAX_SKILL_CHARGES = 5
MAX_RECALL_USES = 3

# Row/column deltas for each movement direction.
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}

# Used for the reversed-movement effect caused by an enemy skill.
OPPOSITE_DIRECTION = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}

# Identifiers of skills the enemy may use.
ENEMY_SKILLS = (
    "seismic_slam",
    "shadow_consume",
    "system_hack",
    "gravity_field",
    "cage_fight",
)

# Identifiers of effects the mystery box may trigger.
MYSTERY_BOX_EFFECTS = (
    "full_heal",
    "dragon_blade",
    "kitsune_rush",
    "gravity_field",
    "biotic_orb",
    "cage_fight",
)

# Missions that can be randomly drawn in battle mode.
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

# Missions that can be randomly drawn in challenge mode.
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
    """Holds the preview result of a move before it is actually resolved."""

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
    """Holds the result after a turn or a skill action is completed."""

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
    """Core engine responsible for the board, combat, missions, and skill rules."""

    def __init__(
        self,
        mode: str = "battle",
        rng: Optional[random.Random] = None,
    ) -> None:
        # Inject the random number generator so gameplay and unit tests can use different random states.
        self.rng = rng or random.Random()
        self.reset(mode)

    def reset(self, mode: str) -> None:
        # Rebuild the complete game state according to the mode.
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

        # Battle mode starts with a few low-value tiles; challenge mode uses a pre-generated board.
        if mode == "battle":
            self._place_random_tiles(3, {2: 0.90, 4: 0.10})
        else:
            self._create_challenge_board()
        self._update_highest_tile()

    @property
    def is_battle(self) -> bool:
        # Clearer than comparing the mode string directly.
        return self.mode == "battle"

    @property
    def is_challenge(self) -> bool:
        # Convenience property for checking challenge mode.
        return self.mode == "challenge"

    @property
    def turns_until_enemy_skill(self) -> int:
        # Number of turns left until the next enemy skill triggers (skills trigger every 8 turns).
        return 8 - (self.turn % 8)

    def _create_challenge_board(self) -> None:
        # Try to generate a challenge board that has empty cells and at least one valid move.
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
        # Place the given number of new tiles in random empty cells.
        for _ in range(count):
            cells = self.empty_cells()
            if not cells:
                return
            row, column = self.rng.choice(cells)
            self.board[row][column] = self._weighted_choice(probabilities)

    def _weighted_choice(self, probabilities: dict[int, float]) -> int:
        # Pick a new tile value according to the given probability table.
        threshold = self.rng.random()
        cumulative = 0.0
        for value, probability in probabilities.items():
            cumulative += probability
            if threshold < cumulative:
                return value
        return next(reversed(probabilities))

    def empty_cells(self) -> list[tuple[int, int]]:
        # Return cells where a tile can be placed; the mystery box cell cannot be reused.
        return [
            (row, column)
            for row in range(BOARD_SIZE)
            for column in range(BOARD_SIZE)
            if self.board[row][column] == EMPTY
            and (row, column) != self.mystery_box
        ]

    def tile_cells(self) -> list[tuple[int, int]]:
        # Return the positions of all numbered tiles.
        return [
            (row, column)
            for row in range(BOARD_SIZE)
            for column in range(BOARD_SIZE)
            if self.board[row][column] > EMPTY
        ]

    def tile_values(self) -> list[int]:
        # Return the values of all numbered tiles, used for statistics and mission checks.
        return [self.board[row][column] for row, column in self.tile_cells()]

    def current_bug_probability(self) -> float:
        # In battle mode the bug probability grows with the turn count, up to a maximum.
        if not self.is_battle:
            return 0.0
        return min(0.05 + ((self.turn + 1) // 10) * 0.05, 0.30)

    def tile_probabilities(self, next_turn: Optional[int] = None) -> dict[int, float]:
        # Adjust the value distribution of newly spawned tiles based on the stage of the next turn.
        turn = self.turn + 1 if next_turn is None else next_turn
        if turn >= 40:
            return {2: 0.75, 4: 0.15, 8: 0.07, 16: 0.03}
        if turn >= 20:
            return {2: 0.85, 4: 0.10, 8: 0.05}
        return {2: 0.90, 4: 0.10}

    def _update_highest_tile(self) -> None:
        # Update the highest tile value currently on the board.
        self.highest_tile = max(self.tile_values() or [0])

    def parse_coordinate(self, text: str) -> Optional[tuple[int, int]]:
        # Convert a user coordinate such as A1 into zero-based (row, column) coordinates.
        cleaned = text.strip().upper()
        if len(cleaned) != 2 or cleaned[0] not in "ABCDE" or cleaned[1] not in "12345":
            return None
        return int(cleaned[1]) - 1, ord(cleaned[0]) - ord("A")

    def coordinate_label(self, coordinate: tuple[int, int]) -> str:
        # Convert internal (row, column) coordinates back to the letter-number label shown in the UI.
        row, column = coordinate
        return f"{chr(ord('A') + column)}{row + 1}"

    def _line_positions(self, direction: str, line_index: int) -> list[tuple[int, int]]:
        # Generate the processing order of a row or column for the given movement direction.
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
        # First compact out the empty cells, then merge adjacent equal tiles using 2048 rules.
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
        # Compute the result of a move without modifying the real board.
        result = copy.deepcopy(self.board)
        all_merges: list[int] = []

        for line_index in range(BOARD_SIZE):
            positions = self._line_positions(direction, line_index)
            segment: list[tuple[int, int]] = []

            def flush_segment() -> None:
                # Compact a contiguous movable region and write it back to the simulated board.
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
        # Compare the 2D lists to determine whether a move actually changed the board.
        return left != right

    def has_valid_move(self) -> bool:
        # The game can continue if there is an empty cell or at least one direction can move/merge.
        if self.empty_cells():
            return True
        for direction in DIRECTIONS:
            simulated, _ = self._simulate_board(direction, allow_merge=True)
            if self._board_changed(self.board, simulated):
                return True
        return False

    def start_move(self, direction: str) -> Optional[MovePreview]:
        # Create a move preview and stash the pre-move state for bug questions and the recall skill.
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
        # Resolve the move, merges, mystery box, enemy events, and game-over conditions based on the quiz result.
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
        # Save all state that affects later rules so Recall can restore it completely.
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
        # Restore the board, combat data, mission data, and random number state from a snapshot.
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
        # Count merges and grant the corresponding rewards when thresholds are reached.
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
        # Map a merged value to the number of merges needed and the reward type.
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
        # Apply the healing, damage, max HP, or skill charge produced by a merge reward.
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
        # Reduce the enemy's HP, ensuring it never drops below zero.
        if self.enemy_hp is not None:
            self.enemy_hp = max(0, self.enemy_hp - amount)

    def _heal_player(self, amount: int) -> None:
        # Restore the player's HP without exceeding the current max HP.
        if self.player_hp is not None and self.player_max_hp is not None:
            self.player_hp = min(self.player_max_hp, self.player_hp + amount)

    def _damage_player(self, amount: int) -> None:
        # Reduce the player's HP, ensuring it never drops below zero.
        if self.player_hp is not None:
            self.player_hp = max(0, self.player_hp - amount)

    def _apply_wrong_streak_penalty(self) -> None:
        # After 5 wrong bug answers in a row, deduct 20% of current max HP (rounded down).
        if self.player_max_hp is not None:
            self._damage_player(int(self.player_max_hp * 0.2))

    def _spawn_tile(self) -> None:
        # Spawn a new tile in a random empty cell after a move.
        cells = self.empty_cells()
        if not cells:
            return
        row, column = self.rng.choice(cells)
        self.board[row][column] = self._weighted_choice(self.tile_probabilities())

    def _update_mission(self) -> None:
        # Check whether the battle mode mission has been completed.
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
        # Check whether the challenge mode objective has been completed.
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
        # After a battle mission is completed, spawn a mystery box once in an empty cell.
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
        # Trigger the mystery box and apply a random effect.
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
        # Determine whether this move will cause a numbered tile to pass through the mystery box's position.
        if self.mystery_box is None:
            return False

        target = self.mystery_box
        for line_index in range(BOARD_SIZE):
            positions = self._line_positions(direction, line_index)
            segment: list[tuple[int, int]] = []

            def segment_hits_target() -> bool:
                # If a numbered tile lies behind the target position, the target is triggered by this move.
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
        # Handle the periodic enemy skill and the regular attack in battle mode.
        enemy_skill = None
        if self.turn % 8 == 0:
            enemy_skill = self._use_enemy_skill()
        if self.is_battle and self.turn % 2 == 0 and self.enemy_hp and self.enemy_hp > 0:
            self._damage_player(15)
        return enemy_skill

    def _use_enemy_skill(self) -> Optional[str]:
        # Randomly pick an enemy skill different from the last one and execute it immediately.
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
        # Clear blocked cells whose duration has run out.
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
        # Assemble the main events of this turn into the UI status bar text.
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
        # Enter the one-time rescue quiz flow when the player dies or the board has no moves left.
        if self.rescue_used:
            return self._finish("loss", "Rescue has already been used.")
        self.pending_rescue_type = rescue_type
        self.status_message = "Rescue required. Answer three questions correctly."
        return TurnResult(True, self.status_message, rescue_type=rescue_type)

    def resolve_rescue(self, success: bool) -> TurnResult:
        # Restore HP or clear board tiles depending on the rescue quiz result.
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
        # Validate and execute a player skill; at most one skill can be used per turn.
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
        # Check whether the coordinate is within the board and refers to a numbered tile.
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
        # Set the game-over state and return the final result.
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
    """Responsible for loading the question bank, drawing questions, and checking answers."""

    def __init__(self, path: Path, rng: Optional[random.Random] = None) -> None:
        # Store the question bank path and random number generator, and load the questions on initialization.
        self.path = path
        self.rng = rng or random.Random()
        self.questions = self._load_questions()
        self.used_ids: set[str] = set()

    def _load_questions(self) -> list[dict[str, Any]]:
        # Read the JSON question bank and validate its basic structure.
        with self.path.open("r", encoding="utf-8") as file:
            questions = json.load(file)
        if not isinstance(questions, list) or not questions:
            raise ValueError("Question file must contain a non-empty list.")
        for question in questions:
            if not isinstance(question, dict) or not question.get("id"):
                raise ValueError("Every question must have an id.")
        return questions

    def next_question(self) -> dict[str, Any]:
        # Prefer questions that haven't been used yet; start a new round once all have been used.
        available = [item for item in self.questions if item["id"] not in self.used_ids]
        if not available:
            self.used_ids.clear()
            available = list(self.questions)
        question = self.rng.choice(available)
        self.used_ids.add(question["id"])
        return question

    @staticmethod
    def check_answer(question: dict[str, Any], answer: str) -> bool:
        # Choice questions ignore case; text questions ignore case and leading/trailing whitespace.
        submitted = answer.strip()
        expected = str(question.get("answer", "")).strip()
        if question.get("type") == "choice":
            return submitted.upper() == expected.upper()
        return submitted.casefold() == expected.casefold()