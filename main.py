from __future__ import annotations

import os
import random
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter import font as tkfont
from typing import Optional

# 禁用 macOS 旧版 Tk 警告
os.environ['TK_SILENCE_DEPRECATION'] = '1'

from game_engine import (
    BLOCKED,
    BOARD_SIZE,
    GameEngine,
    MovePreview,
    QuestionManager,
    TurnResult,
)
from leaderboard import Leaderboard
from music_ogg import AudioManager


# 定位项目资源文件，界面通过这些路径读取题库、排行榜和字体。
ROOT_DIR = Path(__file__).resolve().parent
QUESTION_PATH = ROOT_DIR / "data" / "questions.json"
LEADERBOARD_PATH = ROOT_DIR / "data" / "leaderboard.json"
FONT_PATH = ROOT_DIR / "fonts" / "Times New Roman.ttf"

# 统一管理界面使用的颜色，避免在各个控件中重复写颜色值。
COLORS = {
    "background": "#0c141d",
    "panel": "#152332",
    "panel_light": "#203246",
    "line": "#315064",
    "text": "#e8f1f5",
    "muted": "#8da5b5",
    "accent": "#63d5e8",
    "accent_dark": "#256d7b",
    "orange": "#f0a35b",
    "danger": "#e87171",
    "success": "#75d38b",
    "tile_empty": "#1b2a38",
    "tile_blocked": "#3d4750",
}

# 为不同数字方块提供不同颜色，帮助玩家快速区分数值。
TILE_COLORS = {
    2: "#314b5f",
    4: "#3c6373",
    8: "#267a86",
    16: "#3f9a83",
    32: "#91a64e",
    64: "#d19b45",
    128: "#d16f49",
    256: "#b9525e",
    512: "#884d88",
}


class FlatButton(tk.Label):
    """使用 Label 模拟按钮，确保 macOS 主题下文字和颜色稳定显示。"""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        width: int,
        height: int,
        normal_bg: str,
        normal_fg: str,
        hover_bg: str,
        hover_fg: str,
        disabled_bg: str,
        disabled_fg: str,
        **kwargs,
    ) -> None:
        # Label 在不同 Tk 主题下比原生 Button 更容易保持指定的前景色和背景色。
        super().__init__(
            parent,
            text=text,
            width=width,
            height=height,
            bg=normal_bg,
            fg=normal_fg,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self._command = command
        self._enabled = True
        self._normal_bg = normal_bg
        self._normal_fg = normal_fg
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, _event: tk.Event) -> None:
        # 鼠标进入时显示悬停颜色。
        if self._enabled:
            self.configure(bg=self._hover_bg, fg=self._hover_fg)

    def _on_leave(self, _event: tk.Event) -> None:
        # 鼠标离开时恢复常态颜色。
        if self._enabled:
            self.configure(bg=self._normal_bg, fg=self._normal_fg)

    def _on_press(self, _event: tk.Event) -> str:
        # 按下按钮时立即显示反馈，并阻止 Label 的默认事件继续传播。
        if self._enabled:
            self.configure(bg=self._hover_bg, fg=self._hover_fg)
        return "break"

    def _on_release(self, event: tk.Event) -> str:
        # 只有在鼠标仍位于按钮内部时才执行对应命令。
        if not self._enabled:
            return "break"
        inside = self.winfo_containing(event.x_root, event.y_root) is self
        if inside:
            self.configure(bg=self._hover_bg, fg=self._hover_fg)
            self._command()
        else:
            self.configure(bg=self._normal_bg, fg=self._normal_fg)
        return "break"

    def set_enabled(self, enabled: bool) -> None:
        # 更新按钮的可用状态、颜色和鼠标指针样式。
        self._enabled = enabled
        self.configure(
            bg=self._normal_bg if enabled else self._disabled_bg,
            fg=self._normal_fg if enabled else self._disabled_fg,
            cursor="hand2" if enabled else "arrow",
        )

    def set_colors(self, background: str, foreground: str) -> None:
        # 动态更新按钮当前状态的背景色和文字颜色。
        self._normal_bg = background
        self._normal_fg = foreground
        self._hover_bg = background
        self._hover_fg = foreground
        if self._enabled:
            self.configure(bg=background, fg=foreground)


class GameApp:
    """构建并驱动游戏的 Tkinter 桌面界面。"""

    def __init__(self) -> None:
        # 初始化窗口、游戏对象、界面变量以及键盘快捷键。
        self.root = tk.Tk()
        self.root.title("2048: Overwatch VS Talon")
        self.root.geometry("1180x780")
        self.root.minsize(1000, 700)
        self.root.configure(bg=COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        # 使用更兼容的字体检测
        try:
            test_font = tkfont.Font(family="Times New Roman", size=12)
            actual = test_font.actual()["family"]
            if "Times" in actual or FONT_PATH.exists():
                self.font_family = "Times New Roman"
            else:
                self.font_family = "Helvetica"
        except Exception:
            self.font_family = "Helvetica"
        self.engine: Optional[GameEngine] = None
        self.questions: Optional[QuestionManager] = None
        self.leaderboard = Leaderboard(LEADERBOARD_PATH)
        self.audio = AudioManager()
        self.tile_buttons: dict[tuple[int, int], FlatButton] = {}
        self.selected_coordinate: Optional[tuple[int, int]] = None
        self.active_skill: Optional[str] = None
        self.skill_status = ""
        self.status_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.score_var = tk.StringVar()
        self.turn_var = tk.StringVar()
        self.player_hp_var = tk.StringVar()
        self.enemy_hp_var = tk.StringVar()
        self.charge_var = tk.StringVar()
        self.enemy_skill_timer_var = tk.StringVar()
        self.mission_var = tk.StringVar()
        self.mode_var = tk.StringVar()
        self.selected_var = tk.StringVar()
        self.skill_button_refs: dict[str, FlatButton] = {}

        self.root.bind("<KeyPress>", self.on_key)
        self.show_menu()
        self._poll_audio()

    def run(self) -> None:
        # 启动 Tkinter 事件循环。
        self.root.mainloop()

    def _poll_audio(self) -> None:
        # 定期检查背景音乐是否播放完毕，并切换到循环队列的下一首。
        self.audio.poll()
        self.root.after(500, self._poll_audio)

    def make_font(self, size: int, bold: bool = False) -> tkfont.Font:
        # 创建统一字体，优先使用项目中提供的字体文件对应的字体名称。
        return tkfont.Font(
            family=self.font_family,
            size=size,
            weight="bold" if bold else "normal",
        )

    def clear_root(self) -> None:
        # 切换页面前清理窗口中的旧控件和临时选择状态。
        for child in self.root.winfo_children():
            child.destroy()
        self.tile_buttons.clear()
        self.skill_button_refs.clear()
        self.selected_coordinate = None
        self.active_skill = None
        self.skill_status = ""

    def make_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        width: int = 16,
        accent: bool = False,
        compact: bool = False,
    ) -> FlatButton:
        # 按照项目配色创建统一风格的可点击控件。
        button = FlatButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=1,
            normal_bg=COLORS["accent_dark"] if accent else COLORS["panel_light"],
            normal_fg=COLORS["text"],
            hover_bg=COLORS["accent"] if accent else COLORS["line"],
            hover_fg=COLORS["background"] if accent else COLORS["text"],
            disabled_bg=COLORS["panel"],
            disabled_fg=COLORS["muted"],
            font=self.make_font(10 if compact else 12, bold=accent),
            padx=8,
            pady=6 if compact else 9,
        )
        return button

    def show_menu(self) -> None:
        # 显示主菜单，并提供模式选择、排行榜和退出入口。
        if self.audio.mode != "menu":
            self.audio.start_menu_music()
        self.clear_root()
        frame = tk.Frame(self.root, bg=COLORS["background"])
        frame.pack(fill=tk.BOTH, expand=True)

        top_line = tk.Frame(frame, bg=COLORS["accent"], height=4)
        top_line.pack(fill=tk.X)

        content = tk.Frame(frame, bg=COLORS["background"])
        content.pack(expand=True)

        tk.Label(
            content,
            text="Overwatch VS Talon",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=self.make_font(38, bold=True),
        ).pack(pady=(70, 4))
        tk.Label(
            content,
            text="2048 COMBAT GAME",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=self.make_font(15, bold=True),
        ).pack(pady=(0, 48))

        # 强制刷新以确保在旧版 Tk 上正确渲染
        self.root.update_idletasks()

        self.make_button(
            content,
            "BATTLE MODE",
            lambda: self.start_game("battle"),
            width=24,
            accent=True,
        ).pack(pady=8)
        self.make_button(
            content,
            "CHALLENGE MODE",
            lambda: self.start_game("challenge"),
            width=24,
        ).pack(pady=8)
        self.make_button(
            content,
            "LEADERBOARD",
            self.show_leaderboard,
            width=24,
        ).pack(pady=8)
        self.make_button(
            content,
            "QUIT",
            self.root.destroy,
            width=24,
        ).pack(pady=(8, 28))

        tk.Label(
            content,
            text="Keyboard: WASD / Arrow Keys    P: Skills    H: Help    L: Leaderboard    Q: Menu",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=self.make_font(10),
        ).pack()

        tk.Label(
            content,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=self.make_font(9),
        ).pack(pady=(14, 0))

    def start_game(self, mode: str) -> None:
        # 创建新的规则引擎和题目管理器，然后进入游戏页面。
        try:
            questions = QuestionManager(QUESTION_PATH, rng=random.Random())
        except (OSError, ValueError) as error:
            messagebox.showerror("Question Error", str(error), parent=self.root)
            self.show_menu()
            return
        self.engine = GameEngine(mode=mode, rng=random.Random())
        self.questions = questions
        if mode == "battle":
            self.audio.start_battle_music()
        else:
            self.audio.stop_music()
        self.show_game()

    def show_game(self) -> None:
        # 构建游戏主界面，包括棋盘、方向控制和右侧信息面板。
        if self.engine is None:
            return
        self.clear_root()

        root_frame = tk.Frame(self.root, bg=COLORS["background"])
        root_frame.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        header = tk.Frame(root_frame, bg=COLORS["background"])
        header.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            header,
            textvariable=self.title_var,
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=self.make_font(24, bold=True),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            textvariable=self.mode_var,
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=self.make_font(12, bold=True),
        ).pack(side=tk.RIGHT, pady=8)

        main_area = tk.Frame(root_frame, bg=COLORS["background"])
        main_area.pack(fill=tk.BOTH, expand=True)

        board_panel = tk.Frame(
            main_area,
            bg=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        board_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 14))

        board_title = tk.Frame(board_panel, bg=COLORS["panel"])
        board_title.pack(fill=tk.X, padx=18, pady=(16, 8))
        tk.Label(
            board_title,
            text="MATRIX BOARD",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=self.make_font(10, bold=True),
        ).pack(side=tk.LEFT)
        tk.Label(
            board_title,
            textvariable=self.selected_var,
            bg=COLORS["panel"],
            fg=COLORS["orange"],
            font=self.make_font(10),
        ).pack(side=tk.RIGHT)

        self.build_board(board_panel)
        self.build_direction_controls(board_panel)

        side_panel = tk.Frame(
            main_area,
            bg=COLORS["panel"],
            width=350,
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        side_panel.pack(side=tk.RIGHT, fill=tk.Y)
        side_panel.pack_propagate(False)
        self.build_side_panel(side_panel)

        footer = tk.Frame(root_frame, bg=COLORS["background"])
        footer.pack(fill=tk.X, pady=(14, 0))
        self.make_button(footer, "HELP", self.show_help, width=10, compact=True).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.make_button(
            footer,
            "LEADERBOARD",
            self.show_leaderboard,
            width=14,
            compact=True,
        ).pack(side=tk.LEFT, padx=8)
        self.make_button(
            footer,
            "RETURN TO MENU",
            self.show_menu,
            width=16,
            compact=True,
        ).pack(side=tk.RIGHT)

        self.refresh_game()

    def build_board(self, parent: tk.Misc) -> None:
        # 创建固定大小的棋盘按钮，并将每个按钮绑定到对应坐标。
        board = tk.Frame(parent, bg=COLORS["panel"], padx=22, pady=12)
        board.pack(expand=True)
        for row in range(BOARD_SIZE):
            for column in range(BOARD_SIZE):
                button = FlatButton(
                    board,
                    text="",
                    command=lambda r=row, c=column: self.select_tile((r, c)),
                    width=7,
                    height=3,
                    normal_bg=COLORS["tile_empty"],
                    normal_fg=COLORS["text"],
                    hover_bg=COLORS["tile_empty"],
                    hover_fg=COLORS["text"],
                    disabled_bg=COLORS["tile_empty"],
                    disabled_fg=COLORS["muted"],
                    font=self.make_font(21, bold=True),
                )
                button.grid(row=row, column=column, padx=4, pady=4, sticky="nsew")
                self.tile_buttons[(row, column)] = button

    def build_direction_controls(self, parent: tk.Misc) -> None:
        # 创建四个方向按钮，供不使用键盘时操作棋盘。
        controls = tk.Frame(parent, bg=COLORS["panel"])
        controls.pack(pady=(0, 18))
        self.make_button(
            controls, "UP", lambda: self.try_move("up"), width=8, compact=True
        ).grid(row=0, column=1, padx=4, pady=3)
        self.make_button(
            controls, "LEFT", lambda: self.try_move("left"), width=8, compact=True
        ).grid(row=1, column=0, padx=4, pady=3)
        self.make_button(
            controls, "DOWN", lambda: self.try_move("down"), width=8, compact=True
        ).grid(row=1, column=1, padx=4, pady=3)
        self.make_button(
            controls, "RIGHT", lambda: self.try_move("right"), width=8, compact=True
        ).grid(row=1, column=2, padx=4, pady=3)

    def build_side_panel(self, parent: tk.Misc) -> None:
        # 创建分数、生命值、任务、技能和状态信息区域。
        stats = tk.Frame(parent, bg=COLORS["panel"])
        stats.pack(fill=tk.X, padx=18, pady=(18, 0))
        self.add_stat(stats, "SCORE", self.score_var)
        self.add_stat(stats, "TURN", self.turn_var)
        self.add_stat(stats, "PLAYER HP", self.player_hp_var)
        self.add_stat(stats, "ENEMY HP", self.enemy_hp_var)
        self.add_stat(stats, "SKILL CHARGES", self.charge_var)
        self.add_stat(stats, "NEXT ENEMY SKILL", self.enemy_skill_timer_var)

        separator = tk.Frame(parent, bg=COLORS["line"], height=1)
        separator.pack(fill=tk.X, padx=18, pady=15)

        tk.Label(
            parent,
            text="MISSION",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=self.make_font(10, bold=True),
        ).pack(anchor="w", padx=18)
        tk.Label(
            parent,
            textvariable=self.mission_var,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            justify=tk.LEFT,
            anchor="w",
            wraplength=300,
            font=self.make_font(11),
        ).pack(fill=tk.X, padx=18, pady=(6, 0))

        separator = tk.Frame(parent, bg=COLORS["line"], height=1)
        separator.pack(fill=tk.X, padx=18, pady=15)

        tk.Label(
            parent,
            text="SKILLS",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=self.make_font(10, bold=True),
        ).pack(anchor="w", padx=18)
        skills = tk.Frame(parent, bg=COLORS["panel"])
        skills.pack(fill=tk.X, padx=18, pady=(7, 0))

        for skill_id, label in (
            ("delete", "DELETE"),
            ("change", "CHANGE VALUE"),
            ("recall", "RECALL"),
        ):
            button = self.make_button(
                skills,
                label,
                lambda skill=skill_id: self.begin_skill(skill),
                width=24,
                compact=True,
            )
            button.pack(fill=tk.X, pady=3)
            self.skill_button_refs[skill_id] = button

        self.make_button(
            skills,
            "CANCEL SELECTION",
            self.cancel_skill,
            width=24,
            compact=True,
        ).pack(fill=tk.X, pady=(8, 3))

        self.status_label = tk.Label(
            parent,
            textvariable=self.status_var,
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            justify=tk.LEFT,
            anchor="w",
            wraplength=310,
            font=self.make_font(10),
        )
        self.status_label.pack(fill=tk.X, padx=18, pady=(16, 0))

    def add_stat(self, parent: tk.Misc, label: str, variable: tk.StringVar) -> None:
        # 在信息面板中添加一行左侧标题和右侧动态数值。
        row = tk.Frame(parent, bg=COLORS["panel"])
        row.pack(fill=tk.X, pady=2)
        tk.Label(
            row,
            text=label,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=self.make_font(9, bold=True),
        ).pack(side=tk.LEFT)
        tk.Label(
            row,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=self.make_font(11, bold=True),
        ).pack(side=tk.RIGHT)

    def refresh_game(self) -> None:
        # 将规则引擎的最新状态同步到所有界面控件。
        if self.engine is None:
            return
        engine = self.engine
        self.title_var.set("Overwatch VS Talon")
        self.mode_var.set("BATTLE MODE" if engine.is_battle else "CHALLENGE MODE")
        self.score_var.set(str(engine.score))
        self.turn_var.set(str(engine.turn))
        if engine.player_hp is None:
            self.player_hp_var.set("N/A")
        else:
            self.player_hp_var.set(f"{engine.player_hp} / {engine.player_max_hp}")
        if engine.enemy_hp is None:
            self.enemy_hp_var.set("N/A")
        else:
            self.enemy_hp_var.set(f"{engine.enemy_hp} / {engine.enemy_max_hp}")
        self.charge_var.set(f"{engine.skill_charges} / 5")
        # 敌方技能在战斗模式和残局挑战模式下都会触发，倒计时在两种模式下都显示。
        self.enemy_skill_timer_var.set(f"{engine.turns_until_enemy_skill} turns")

        if engine.is_battle and engine.mission:
            mission = engine.mission
        else:
            mission = engine.challenge_mission
        if mission is None:
            self.mission_var.set("No active mission.")
        else:
            progress = "COMPLETE" if engine.mission_complete else "ACTIVE"
            self.mission_var.set(
                f"[{progress}] {mission['title']}\n{mission['description']}"
            )

        self.status_var.set(self.skill_status or engine.status_message)
        self.selected_var.set(
            f"Selected: {engine.coordinate_label(self.selected_coordinate)}"
            if self.selected_coordinate is not None
            else "No tile selected"
        )

        for coordinate, button in self.tile_buttons.items():
            row, column = coordinate
            value = engine.board[row][column]
            selected = coordinate == self.selected_coordinate
            if value == BLOCKED:
                text = "BLOCK"
                background = COLORS["tile_blocked"]
                foreground = COLORS["muted"]
            elif value == 0:
                text = "·"
                background = COLORS["tile_empty"]
                foreground = COLORS["muted"]
            else:
                text = str(value)
                background = TILE_COLORS.get(value, "#5f4b85")
                foreground = COLORS["text"]
            if engine.mystery_box == coordinate:
                text = "?"
                background = COLORS["orange"]
                foreground = COLORS["background"]
            if selected:
                background = COLORS["accent"]
                foreground = COLORS["background"]
            button.configure(text=text)
            button.set_colors(background, foreground)

        active = not engine.game_over and not engine.pending_rescue_type
        for button in self.skill_button_refs.values():
            button.set_enabled(active and engine.skill_charges > 0)

    def select_tile(self, coordinate: tuple[int, int]) -> None:
        # 处理棋盘格点击，并根据当前技能状态执行相应操作。
        if self.engine is None or self.engine.game_over:
            return
        self.selected_coordinate = coordinate
        if self.active_skill == "change":
            self.open_change_dialog(coordinate)
        elif self.active_skill == "delete":
            # 音效已在按下 DELETE 技能按钮时播放，这里只结算效果。
            result = self.engine.use_skill("delete", coordinate=coordinate)
            self.finish_skill_action(result)
        else:
            self.skill_status = (
                f"Selected {self.engine.coordinate_label(coordinate)}. "
                "Choose a skill or continue moving."
            )
            self.refresh_game()

    def begin_skill(self, skill_id: str) -> None:
        # 开始技能操作；音效在按下技能按钮的瞬间播放，而不是效果结算时。
        if self.engine is None:
            return
        self.audio.play_skill_sfx(skill_id)
        if skill_id == "recall":
            result = self.engine.use_skill("recall")
            self.finish_skill_action(result)
            return
        self.active_skill = skill_id
        self.selected_coordinate = None
        self.skill_status = (
            "Select a numbered tile on the board."
            if skill_id == "delete"
            else "Select a numbered tile to change."
        )
        self.refresh_game()

    def open_change_dialog(self, coordinate: tuple[int, int]) -> None:
        # 为 Change Value 技能打开增加或减少数值的选择窗口。
        if self.engine is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Value")
        dialog.configure(bg=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(
            dialog,
            text=f"Tile {self.engine.coordinate_label(coordinate)}",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=self.make_font(14, bold=True),
        ).pack(padx=24, pady=(22, 14))
        controls = tk.Frame(dialog, bg=COLORS["background"])
        controls.pack(padx=20, pady=(0, 22))

        def choose(increase: bool) -> None:
            # 音效已在按下 CHANGE VALUE 技能按钮时播放，这里只结算效果。
            result = self.engine.use_skill(
                "change",
                coordinate=coordinate,
                increase=increase,
            )
            dialog.destroy()
            self.finish_skill_action(result)

        self.make_button(
            controls, "INCREASE", lambda: choose(True), width=13, compact=True
        ).pack(side=tk.LEFT, padx=4)
        self.make_button(
            controls, "DECREASE", lambda: choose(False), width=13, compact=True
        ).pack(side=tk.LEFT, padx=4)

    def cancel_skill(self) -> None:
        # 取消当前技能选择并清除棋盘上的选择状态。
        self.active_skill = None
        self.selected_coordinate = None
        self.skill_status = "Skill selection cancelled."
        self.refresh_game()

    def finish_skill_action(self, result: TurnResult) -> None:
        # 清理技能操作状态，并在技能不可用时显示警告。
        self.active_skill = None
        self.selected_coordinate = None
        self.skill_status = result.message
        self.refresh_game()
        if not result.success:
            messagebox.showwarning("Skill Unavailable", result.message, parent=self.root)

    def try_move(self, direction: str) -> None:
        # 请求规则引擎创建移动预览，并根据结果进入答题或直接结算。
        if self.engine is None or self.engine.game_over:
            return
        preview = self.engine.start_move(direction)
        if preview is None:
            self.skill_status = "That direction does not create a valid move."
            self.refresh_game()
            return
        self.active_skill = None
        self.selected_coordinate = None
        if preview.bug_triggered:
            self.open_quiz_dialog(preview, rescue=False)
        else:
            result = self.engine.resolve_move(preview, bug_correct=True)
            self.handle_turn_result(result)

    def open_quiz_dialog(self, preview: MovePreview, rescue: bool) -> None:
        # 显示错误事件或救援流程所需的题目窗口。
        if self.questions is None:
            return
        try:
            question = self.questions.next_question()
        except (OSError, ValueError) as error:
            messagebox.showerror("Question Error", str(error), parent=self.root)
            self.show_menu()
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("System Quiz" if not rescue else "Rescue Quiz")
        dialog.configure(bg=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        # 答题窗口必须提交答案才能继续，禁止通过关闭按钮跳过，避免卡死。
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            dialog,
            text="BUG DETECTED" if not rescue else "RESCUE PROTOCOL",
            bg=COLORS["background"],
            fg=COLORS["orange"],
            font=self.make_font(16, bold=True),
        ).pack(padx=30, pady=(24, 8))
        tk.Label(
            dialog,
            text=question["question"],
            bg=COLORS["background"],
            fg=COLORS["text"],
            justify=tk.LEFT,
            wraplength=500,
            font=self.make_font(13),
        ).pack(padx=30, pady=(0, 18))

        answer_var = tk.StringVar()
        controls = tk.Frame(dialog, bg=COLORS["background"])
        controls.pack(fill=tk.X, padx=30, pady=(0, 24))

        def submit(answer: str) -> None:
            # 检查答案后关闭题目窗口，并继续对应的结算流程。
            correct = self.questions.check_answer(question, answer)
            dialog.destroy()
            if rescue:
                self.handle_rescue_answer(correct)
            else:
                result = self.engine.resolve_move(preview, bug_correct=correct)
                self.handle_turn_result(result)

        if question.get("type") == "choice":
            for option in question.get("options", []):
                self.make_button(
                    controls,
                    option,
                    lambda value=option[0]: submit(value),
                    width=42,
                    compact=True,
                ).pack(fill=tk.X, pady=3)
        else:
            entry = tk.Entry(
                controls,
                textvariable=answer_var,
                bg=COLORS["panel_light"],
                fg=COLORS["text"],
                insertbackground=COLORS["text"],
                relief=tk.FLAT,
                font=self.make_font(13),
            )
            entry.pack(fill=tk.X, pady=(0, 10), ipady=7)
            entry.focus_set()
            self.make_button(
                controls,
                "SUBMIT",
                lambda: submit(answer_var.get()),
                width=16,
                accent=True,
                compact=True,
            ).pack()
            entry.bind("<Return>", lambda _event: submit(answer_var.get()))

    def handle_turn_result(self, result: TurnResult) -> None:
        # 将回合结果显示在界面上，并打开救援或结束窗口。
        if self.engine is None:
            return
        # 惊喜盒子效果在结算顺序上先于敌方技能发生，音效按发生顺序播放。
        if result.mystery_effect:
            self.audio.play_mystery_box_sfx(result.mystery_effect)
        if result.enemy_skill:
            self.audio.play_enemy_skill_sfx(result.enemy_skill)
        self.skill_status = result.message
        self.refresh_game()
        if result.rescue_type:
            self.open_rescue_dialog()
            return
        if result.game_over:
            self.show_game_over(result)

    def open_rescue_dialog(self) -> None:
        # 从第一道题开始执行三题连续答对的救援流程。
        if self.engine is None or self.questions is None:
            return
        self.run_rescue_question(remaining=3, correct_count=0)

    def run_rescue_question(self, remaining: int, correct_count: int) -> None:
        # 递归推进救援答题；题目全部答对后恢复游戏。
        if remaining <= 0:
            result = self.engine.resolve_rescue(success=True)
            self.handle_turn_result(result)
            return
        self.open_quiz_dialog_for_rescue(remaining, correct_count)

    def open_quiz_dialog_for_rescue(self, remaining: int, correct_count: int) -> None:
        # 显示救援流程中的单道题目，并根据答案决定继续或失败。
        if self.questions is None:
            return
        question = self.questions.next_question()
        dialog = tk.Toplevel(self.root)
        dialog.title("Rescue Quiz")
        dialog.configure(bg=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        # 救援答题窗口必须提交答案才能继续，禁止通过关闭按钮跳过，避免卡死。
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            dialog,
            text=f"RESCUE PROTOCOL  {4 - remaining}/3",
            bg=COLORS["background"],
            fg=COLORS["orange"],
            font=self.make_font(16, bold=True),
        ).pack(padx=30, pady=(24, 8))
        tk.Label(
            dialog,
            text=question["question"],
            bg=COLORS["background"],
            fg=COLORS["text"],
            justify=tk.LEFT,
            wraplength=500,
            font=self.make_font(13),
        ).pack(padx=30, pady=(0, 18))
        controls = tk.Frame(dialog, bg=COLORS["background"])
        controls.pack(fill=tk.X, padx=30, pady=(0, 24))

        def submit(answer: str) -> None:
            # 救援流程中只要有一道题答错，就会立即结束救援。
            correct = self.questions.check_answer(question, answer)
            dialog.destroy()
            if not correct:
                result = self.engine.resolve_rescue(success=False)
                self.handle_turn_result(result)
                return
            self.run_rescue_question(remaining - 1, correct_count + 1)

        if question.get("type") == "choice":
            for option in question.get("options", []):
                self.make_button(
                    controls,
                    option,
                    lambda value=option[0]: submit(value),
                    width=42,
                    compact=True,
                ).pack(fill=tk.X, pady=3)
        else:
            answer_var = tk.StringVar()
            entry = tk.Entry(
                controls,
                textvariable=answer_var,
                bg=COLORS["panel_light"],
                fg=COLORS["text"],
                insertbackground=COLORS["text"],
                relief=tk.FLAT,
                font=self.make_font(13),
            )
            entry.pack(fill=tk.X, pady=(0, 10), ipady=7)
            entry.focus_set()
            self.make_button(
                controls,
                "SUBMIT",
                lambda: submit(answer_var.get()),
                width=16,
                accent=True,
                compact=True,
            ).pack()
            entry.bind("<Return>", lambda _event: submit(answer_var.get()))

    def handle_rescue_answer(self, correct: bool) -> None:
        # 处理救援题答案，并把结果交回规则引擎。
        if self.engine is None:
            return
        if correct:
            self.skill_status = "Correct answer."
            self.refresh_game()
            self.run_rescue_question(remaining=0, correct_count=3)
        else:
            result = self.engine.resolve_rescue(success=False)
            self.handle_turn_result(result)

    def show_game_over(self, result: TurnResult) -> None:
        # 显示最终成绩，胜利时允许玩家将姓名写入排行榜。
        # 使用自定义 Toplevel 代替 simpledialog/messagebox 原生对话框，
        # 避免旧版 Tk（8.5）在 macOS 上原生对话框不可见但仍模态阻塞导致卡死。
        if self.engine is None:
            return
        if result.result == "win":
            self.prompt_leaderboard_name(result)
        else:
            self.finish_game_over(result)

    def prompt_leaderboard_name(self, result: TurnResult) -> None:
        # 打开自定义输入框，让胜利的玩家将姓名写入排行榜。
        if self.engine is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Mission Complete")
        dialog.configure(bg=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            dialog,
            text="MISSION COMPLETE",
            bg=COLORS["background"],
            fg=COLORS["success"],
            font=self.make_font(16, bold=True),
        ).pack(padx=30, pady=(24, 8))
        tk.Label(
            dialog,
            text="Enter your name for the leaderboard:",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=self.make_font(12),
        ).pack(padx=30, pady=(0, 10))

        name_var = tk.StringVar()
        entry = tk.Entry(
            dialog,
            textvariable=name_var,
            bg=COLORS["panel_light"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief=tk.FLAT,
            font=self.make_font(13),
        )
        entry.pack(padx=30, pady=(0, 14), ipady=7, fill=tk.X)
        entry.focus_set()

        def submit() -> None:
            name = name_var.get().strip()
            dialog.destroy()
            if name and self.engine is not None:
                self.leaderboard.add(
                    name=name,
                    mode=self.engine.mode,
                    score=self.engine.score,
                    turns=self.engine.turn,
                )
            self.finish_game_over(result)

        self.make_button(
            dialog, "SUBMIT", submit, width=16, accent=True, compact=True
        ).pack(padx=30, pady=(0, 20))
        entry.bind("<Return>", lambda _event: submit())
        dialog.lift()
        dialog.focus_force()

    def finish_game_over(self, result: TurnResult) -> None:
        # 显示最终战况摘要，关闭窗口后返回主菜单。
        if self.engine is None:
            self.show_menu()
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Game Over")
        dialog.configure(bg=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            dialog,
            text=result.message,
            bg=COLORS["background"],
            fg=COLORS["text"],
            wraplength=360,
            justify=tk.LEFT,
            font=self.make_font(13, bold=True),
        ).pack(padx=30, pady=(24, 8))
        tk.Label(
            dialog,
            text=f"Final score: {self.engine.score}",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=self.make_font(12),
        ).pack(padx=30, pady=(0, 18))

        def close() -> None:
            dialog.destroy()
            self.show_menu()

        self.make_button(
            dialog, "RETURN TO MENU", close, width=18, accent=True, compact=True
        ).pack(padx=30, pady=(0, 20))
        dialog.lift()
        dialog.focus_force()

    def show_leaderboard(self) -> None:
        # 打开排行榜窗口并展示当前保存的前五名记录。
        records = self.leaderboard.load()
        dialog = tk.Toplevel(self.root)
        dialog.title("Leaderboard")
        dialog.geometry("620x380")
        dialog.configure(bg=COLORS["background"])
        dialog.transient(self.root)

        tk.Label(
            dialog,
            text="LEADERBOARD",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=self.make_font(20, bold=True),
        ).pack(pady=(22, 14))

        tree = ttk.Treeview(
            dialog,
            columns=("rank", "name", "mode", "score", "turns", "date"),
            show="headings",
            height=10,
        )
        headings = {
            "rank": "#",
            "name": "Name",
            "mode": "Mode",
            "score": "Score",
            "turns": "Turns",
            "date": "Date",
        }
        widths = {"rank": 45, "name": 170, "mode": 100, "score": 90, "turns": 80, "date": 110}
        for column, heading in headings.items():
            tree.heading(column, text=heading)
            tree.column(column, width=widths[column], anchor=tk.CENTER)
        for index, record in enumerate(records, start=1):
            tree.insert(
                "",
                tk.END,
                values=(
                    index,
                    record["name"],
                    record["mode"].title(),
                    record["score"],
                    record["turns"],
                    record["date"],
                ),
            )
        tree.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 18))
        self.make_button(
            dialog,
            "CLOSE",
            dialog.destroy,
            width=12,
            compact=True,
        ).pack(pady=(0, 20))

    def show_help(self) -> None:
        # 显示键盘和技能操作说明。
        messagebox.showinfo(
            "Controls",
            "Move: WASD or Arrow Keys\n"
            "Skills: use the skill buttons or press P\n"
            "Select a board tile before using Delete or Change Value\n"
            "Help: H\n"
            "Leaderboard: L\n"
            "Return to menu: Q",
            parent=self.root,
        )

    def on_key(self, event: tk.Event) -> None:
        # 将键盘输入转换为移动、技能、帮助、排行榜或菜单操作。
        if self.engine is None:
            if event.keysym.lower() == "l":
                self.show_leaderboard()
            return
        key = event.keysym.lower()
        direction_map = {
            "w": "up",
            "up": "up",
            "s": "down",
            "down": "down",
            "a": "left",
            "left": "left",
            "d": "right",
            "right": "right",
        }
        if key in direction_map:
            self.try_move(direction_map[key])
        elif key == "p":
            self.skill_status = "Select a skill button."
            self.refresh_game()
        elif key == "h":
            self.show_help()
        elif key == "l":
            self.show_leaderboard()
        elif key == "q":
            self.show_menu()


if __name__ == "__main__":
    # 直接运行本文件时启动桌面游戏。
    GameApp().run()
