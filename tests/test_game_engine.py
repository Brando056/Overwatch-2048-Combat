from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path


# 将项目根目录加入导入路径，方便直接运行测试文件。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from game_engine import GameEngine, QuestionManager  # noqa: E402  # 测试文件需要先调整导入路径。
from leaderboard import Leaderboard  # noqa: E402  # 测试文件需要先调整导入路径。


class GameEngineTests(unittest.TestCase):
    """覆盖棋盘移动、任务和题库的核心规则。"""

    def test_standard_merge_chain(self) -> None:
        # 验证四个相同方块向左移动时会正确分成两次合并。
        engine = GameEngine("battle", random.Random(1))
        engine.board = [[0, 0, 0, 0, 0] for _ in range(5)]
        engine.board[0] = [2, 2, 2, 2, 0]

        board, merges = engine._simulate_board("left", allow_merge=True)

        self.assertEqual(board[0], [4, 4, 0, 0, 0])
        self.assertEqual(merges, [4, 4])

    def test_blocked_cell_stops_movement(self) -> None:
        # 验证阻挡格会把移动区域分隔开，阻止两侧方块跨越合并。
        engine = GameEngine("battle", random.Random(2))
        engine.board = [[0, 0, 0, 0, 0] for _ in range(5)]
        engine.board[0] = [2, -1, 2, 0, 0]

        board, merges = engine._simulate_board("left", allow_merge=True)

        self.assertEqual(board[0], [2, -1, 2, 0, 0])
        self.assertEqual(merges, [])

    def test_successful_move_updates_turn_and_score(self) -> None:
        # 验证一次有效合并会增加回合数和分数。
        engine = GameEngine("battle", random.Random(4))
        engine.board = [[0, 0, 0, 0, 0] for _ in range(5)]
        engine.board[0] = [2, 2, 0, 0, 0]

        preview = engine.start_move("left")
        self.assertIsNotNone(preview)
        result = engine.resolve_move(preview, bug_correct=True)

        self.assertTrue(result.success)
        self.assertEqual(engine.turn, 1)
        self.assertEqual(engine.score, 4)

    def test_bug_probability_boundaries(self) -> None:
        # 验证错误事件概率会按回合增加并保持在最高值。
        engine = GameEngine("battle", random.Random(5))
        for turn, expected in (
            (0, 0.05),
            (9, 0.10),
            (19, 0.15),
            (29, 0.20),
            (49, 0.30),
            (59, 0.30),
        ):
            engine.turn = turn
            self.assertAlmostEqual(engine.current_bug_probability(), expected)

    def test_challenge_has_no_bug_and_has_objective(self) -> None:
        # 验证挑战模式关闭错误事件并拥有任务目标。
        engine = GameEngine("challenge", random.Random(6))

        self.assertTrue(engine.is_challenge)
        self.assertEqual(engine.current_bug_probability(), 0.0)
        self.assertIsNotNone(engine.challenge_mission)

    def test_question_answers(self) -> None:
        # 验证题库答案检查能够识别正确和错误答案。
        questions = QuestionManager(PROJECT_ROOT / "data" / "questions.json", random.Random(7))
        question = questions.next_question()

        self.assertTrue(QuestionManager.check_answer(question, question["answer"]))
        self.assertFalse(QuestionManager.check_answer(question, "incorrect"))

    def test_wrong_streak_penalty_deducts_max_hp(self) -> None:
        # 验证连续答错 5 道 Bug 题会扣除 20% 最大生命值并重置连错计数。
        # 单个方块在棋盘中左右移动，不会发生合并，确保每次移动都有效。
        engine = GameEngine("battle", random.Random(8))
        engine.board = [[0, 0, 0, 0, 0] for _ in range(5)]
        engine.board[0][0] = 2

        hp_before_fifth_wrong = engine.player_hp
        for step in range(1, 6):
            direction = "right" if step % 2 else "left"
            preview = engine.start_move(direction)
            self.assertIsNotNone(preview)
            preview.bug_triggered = True
            if step == 5:
                hp_before_fifth_wrong = engine.player_hp
            result = engine.resolve_move(preview, bug_correct=False)

        self.assertTrue(result.wrong_streak_penalty)
        self.assertEqual(engine.bug_wrong_streak, 0)
        self.assertEqual(engine.player_hp, hp_before_fifth_wrong - int(engine.player_max_hp * 0.2))

    def test_second_death_ends_game_without_rescue(self) -> None:
        # 验证第一次死亡仍可救援，但第二次死亡会直接结束游戏。
        engine = GameEngine("battle", random.Random(9))
        engine.board = [[0, 0, 0, 0, 0] for _ in range(5)]
        engine.board[0][4] = 2

        engine.turn = 1
        engine.player_hp = 1
        preview = engine.start_move("left")
        self.assertIsNotNone(preview)
        preview.bug_triggered = False
        first_result = engine.resolve_move(preview, bug_correct=True)
        self.assertEqual(first_result.rescue_type, "death")
        self.assertFalse(first_result.game_over)
        self.assertEqual(engine.death_count, 1)

        rescue_result = engine.resolve_rescue(success=True)
        self.assertTrue(rescue_result.success)
        self.assertFalse(engine.game_over)

        engine.turn = 3
        engine.player_hp = 1
        preview = engine.start_move("right")
        self.assertIsNotNone(preview)
        preview.bug_triggered = False
        second_result = engine.resolve_move(preview, bug_correct=True)

        self.assertIsNone(second_result.rescue_type)
        self.assertTrue(second_result.game_over)
        self.assertEqual(second_result.result, "loss")
        self.assertEqual(engine.death_count, 2)


class LeaderboardTests(unittest.TestCase):
    """覆盖排行榜保存和前五名筛选规则。"""

    def test_leaderboard_keeps_top_five(self) -> None:
        # 验证排行榜只保留分数最高的五条胜利记录。
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "leaderboard.json"
            leaderboard = Leaderboard(path)
            for score in range(6):
                self.assertTrue(
                    leaderboard.add(
                        name=f"Player{score}",
                        mode="battle",
                        score=score,
                        turns=score + 1,
                    )
                )

            records = leaderboard.load()
            self.assertEqual(len(records), 5)
            self.assertEqual(records[0]["score"], 5)


if __name__ == "__main__":
    # 直接运行测试文件时启动 unittest 测试发现器。
    unittest.main()
