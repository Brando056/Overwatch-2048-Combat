from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from typing import Optional

try:
    import pygame

    _PYGAME_AVAILABLE = True
except Exception:  # pragma: no cover - 环境缺少 pygame 时优雅降级。
    pygame = None  # type: ignore[assignment]
    _PYGAME_AVAILABLE = False


# 主菜单循环播放的三首曲目，每次结束后重新随机选择一首。
MENU_TRACKS = ("Colosseo.ogg", "kiriko_origin.ogg", "midtown.ogg")

# 战斗音乐固定顺序的循环队列。
BATTLE_SEQUENCE = (
    "select_hero.ogg",
    "round1.ogg",
    "last30.ogg",
    "overtime.ogg",
    "round1.ogg",
)

# 英雄技能触发时播放的音效文件。
SKILL_SFX = {
    "delete": "DVA_self_destruct.ogg",
    "change": "duplicate.ogg",
    "recall": "tracer.ogg",
}

# 敌方技能触发时播放的音效文件。
ENEMY_SKILL_SFX = {
    "seismic_slam": "meteor_strike.ogg",
    "shadow_consume": "reaper.ogg",
    "system_hack": "EMP.ogg",
    "gravity_field": "sigma.ogg",
    "cage_fight": "SSVGG.ogg",
}

# 惊喜盒子效果触发时播放的音效文件。
MYSTERY_BOX_SFX = {
    "full_heal": "mercy.ogg",
    "dragon_blade": "dragon_blade.ogg",
    "kitsune_rush": "kitsune_rush.ogg",
    "gravity_field": "sigma.ogg",
    "biotic_orb": "moira.ogg",
    "cage_fight": "SSVGG.ogg",
}

MUSIC_DIR = Path(__file__).resolve().parent / "music"

# 背景音乐起始播放位置（秒），按文件名配置；未配置的文件从头播放。
MUSIC_START_OFFSETS: dict[str, float] = {
    "select_hero.ogg": 5.5,
    "round1.ogg": 3,
    "last30.ogg": 2,
    "overtime.ogg": 2,
}

# 一次性音效起始播放位置（秒），按文件名配置；未配置的文件从头播放。
# Sound 对象没有内置的起始秒数参数，需要在加载时手动裁剪音频数据。
SFX_START_OFFSETS: dict[str, float] = {
    "dragon_blade.ogg": 1.8,
    "duplicate.ogg": 2.9,
    "DVA_self_destruct.ogg": 2.4,
    "EMP.ogg": 1,
    "kitsune_rush.ogg": 3,
    "mercy.ogg": 3,
    "meteor_strike.ogg": 1.9,
    "moira.ogg": 1,
    "reaper.ogg": 2.4,
    "sigma.ogg": 2,
    "SSVGG.ogg": 2,
    "tracer.ogg": 2,
}

# 默认音量，取值范围 0.0（静音）到 1.0（最大）；可通过 AudioManager 的
# set_music_volume / set_sfx_volume 在运行时调整。
DEFAULT_MUSIC_VOLUME = 1.0
DEFAULT_SFX_VOLUME = 1.0


class AudioManager:
    """管理背景音乐循环队列和一次性技能/效果音效的播放。"""

    def __init__(self, music_dir: Path = MUSIC_DIR, rng: Optional[random.Random] = None) -> None:
        # 初始化 pygame 混音器；缺少 pygame 或初始化失败时静默禁用音频。
        self.music_dir = music_dir
        self.rng = rng or random.Random()
        self.enabled = _PYGAME_AVAILABLE
        self._sfx_cache: dict[str, "pygame.mixer.Sound"] = {}
        self._mode: Optional[str] = None
        self._battle_index = 0
        self._music_volume = DEFAULT_MUSIC_VOLUME
        self._sfx_volume = DEFAULT_SFX_VOLUME
        if self.enabled:
            try:
                pygame.mixer.init()
                pygame.mixer.music.set_volume(self._music_volume)
            except Exception:
                self.enabled = False

    @property
    def mode(self) -> Optional[str]:
        # 暴露当前背景音乐模式（"menu"、"battle" 或 None），便于界面避免重复触发。
        return self._mode

    def _path(self, filename: str) -> Path:
        # 拼接音频文件在 music 目录中的完整路径。
        return self.music_dir / filename

    def _get_sound(self, filename: str) -> Optional["pygame.mixer.Sound"]:
        # 缓存已加载的音效，避免重复从磁盘读取。
        if not self.enabled:
            return None
        if filename in self._sfx_cache:
            return self._sfx_cache[filename]
        path = self._path(filename)
        if not path.exists():
            return None
        try:
            sound = pygame.mixer.Sound(str(path))
            sound = self._trim_sound(sound, SFX_START_OFFSETS.get(filename, 0.0))
        except Exception:
            return None
        self._sfx_cache[filename] = sound
        return sound

    @staticmethod
    def _trim_sound(sound: "pygame.mixer.Sound", start_seconds: float) -> "pygame.mixer.Sound":
        # Sound 对象没有内置的起始秒数参数，按字节裁剪原始采样数据实现跳过开头播放。
        if start_seconds <= 0:
            return sound
        mixer_init = pygame.mixer.get_init()
        if mixer_init is None:
            return sound
        frequency, format_bits, channels = mixer_init
        bytes_per_sample = abs(format_bits) // 8
        frame_size = bytes_per_sample * channels
        raw = sound.get_raw()
        skip_bytes = int(start_seconds * frequency) * frame_size
        if skip_bytes >= len(raw):
            return sound
        return pygame.mixer.Sound(buffer=raw[skip_bytes:])

    def play_sfx(self, filename: str, volume: Optional[float] = None) -> None:
        # 播放一次音效；与当前背景音乐同时播放，不打断背景音乐。
        # volume 为 None 时使用全局音效音量，否则覆盖为该音效单次使用的音量。
        sound = self._get_sound(filename)
        if sound is not None:
            sound.set_volume(self._sfx_volume if volume is None else max(0.0, min(1.0, volume)))
            sound.play()

    def play_skill_sfx(self, skill_id: str) -> None:
        # 根据英雄技能标识播放对应音效。
        filename = SKILL_SFX.get(skill_id)
        if filename:
            self.play_sfx(filename)

    def play_enemy_skill_sfx(self, skill_id: str) -> None:
        # 根据敌方技能标识播放对应音效。
        filename = ENEMY_SKILL_SFX.get(skill_id)
        if filename:
            self.play_sfx(filename)

    def play_mystery_box_sfx(self, effect_id: str) -> None:
        # 根据惊喜盒子效果标识播放对应音效。
        filename = MYSTERY_BOX_SFX.get(effect_id)
        if filename:
            self.play_sfx(filename)

    def set_music_volume(self, volume: float) -> None:
        # 设置背景音乐音量，取值范围会被限制在 0.0 到 1.0。
        self._music_volume = max(0.0, min(1.0, volume))
        if self.enabled:
            try:
                pygame.mixer.music.set_volume(self._music_volume)
            except Exception:
                pass

    def set_sfx_volume(self, volume: float) -> None:
        # 设置后续播放的音效的默认音量；已缓存的音效在下次播放时生效。
        self._sfx_volume = max(0.0, min(1.0, volume))

    def _play_music_file(self, filename: str) -> None:
        # 加载并播放一首背景音乐曲目；失败时保持静音而不崩溃。
        # 若 MUSIC_START_OFFSETS 中配置了该文件，则从指定秒数开始播放。
        if not self.enabled:
            return
        path = self._path(filename)
        if not path.exists():
            return
        start = MUSIC_START_OFFSETS.get(filename, 0.0)
        try:
            pygame.mixer.music.load(str(path))
            if start > 0:
                pygame.mixer.music.play(start=start)
            else:
                pygame.mixer.music.play()
        except Exception:
            pass

    def start_menu_music(self) -> None:
        # 开始主菜单音乐循环：随机选择一首并进入循环模式。
        self._mode = "menu"
        self._play_music_file(self.rng.choice(MENU_TRACKS))

    def start_battle_music(self) -> None:
        # 开始战斗音乐固定顺序循环，从队列第一首开始。
        self._mode = "battle"
        self._battle_index = 0
        self._play_music_file(BATTLE_SEQUENCE[self._battle_index])

    def stop_music(self) -> None:
        # 停止当前背景音乐并退出循环模式。
        self._mode = None
        if self.enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def poll(self) -> None:
        # 由界面定时调用；当前曲目播放结束后推进到循环中的下一首。
        if not self.enabled or self._mode is None:
            return
        try:
            busy = pygame.mixer.music.get_busy()
        except Exception:
            return
        if busy:
            return
        if self._mode == "menu":
            self._play_music_file(self.rng.choice(MENU_TRACKS))
        elif self._mode == "battle":
            self._battle_index = (self._battle_index + 1) % len(BATTLE_SEQUENCE)
            self._play_music_file(BATTLE_SEQUENCE[self._battle_index])
