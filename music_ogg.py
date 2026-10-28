from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from typing import Optional

try:
    import pygame

    _PYGAME_AVAILABLE = True
except Exception:  # pragma: no cover - degrade gracefully when pygame is missing.
    pygame = None  # type: ignore[assignment]
    _PYGAME_AVAILABLE = False


# Three tracks looped on the main menu; a new one is picked at random each time a track ends.
MENU_TRACKS = ("Colosseo.ogg", "kiriko_origin.ogg", "midtown.ogg")

# Fixed-order looping queue for battle music.
BATTLE_SEQUENCE = (
    "select_hero.ogg",
    "round1.ogg",
    "last30.ogg",
    "overtime.ogg",
    "round1.ogg",
)

# Sound effect files played when a hero skill is triggered.
SKILL_SFX = {
    "delete": "DVA_self_destruct.ogg",
    "change": "duplicate.ogg",
    "recall": "tracer.ogg",
}

# Sound effect files played when an enemy skill is triggered.
ENEMY_SKILL_SFX = {
    "seismic_slam": "meteor_strike.ogg",
    "shadow_consume": "reaper.ogg",
    "system_hack": "EMP.ogg",
    "gravity_field": "sigma.ogg",
    "cage_fight": "SSVGG.ogg",
}

# Sound effect files played when a mystery box effect is triggered.
MYSTERY_BOX_SFX = {
    "full_heal": "mercy.ogg",
    "dragon_blade": "dragon_blade.ogg",
    "kitsune_rush": "kitsune_rush.ogg",
    "gravity_field": "sigma.ogg",
    "biotic_orb": "moira.ogg",
    "cage_fight": "SSVGG.ogg",
}

MUSIC_DIR = Path(__file__).resolve().parent / "music"

# Start position (in seconds) for background music, configured per filename;
# files not listed here play from the beginning.
MUSIC_START_OFFSETS: dict[str, float] = {
    "select_hero.ogg": 5.5,
    "round1.ogg": 3,
    "last30.ogg": 2,
    "overtime.ogg": 2,
}

# Start position (in seconds) for one-shot sound effects, configured per filename;
# files not listed here play from the beginning.
# Sound objects have no built-in start-offset parameter, so the audio data
# has to be trimmed manually when loading.
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

# Default volume, ranging from 0.0 (muted) to 1.0 (maximum); can be adjusted at
# runtime via AudioManager's set_music_volume / set_sfx_volume.
DEFAULT_MUSIC_VOLUME = 1.0
DEFAULT_SFX_VOLUME = 1.0


class AudioManager:
    """Manages the looping background music queue and one-shot skill/effect sound effects."""

    def __init__(self, music_dir: Path = MUSIC_DIR, rng: Optional[random.Random] = None) -> None:
        # Initialize the pygame mixer; silently disable audio if pygame is missing or init fails.
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
        # Expose the current background music mode ("menu", "battle" or None) so the UI can avoid re-triggering.
        return self._mode

    def _path(self, filename: str) -> Path:
        # Build the full path of an audio file in the music directory.
        return self.music_dir / filename

    def _get_sound(self, filename: str) -> Optional["pygame.mixer.Sound"]:
        # Cache loaded sound effects to avoid reading from disk repeatedly.
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
        # Sound objects have no built-in start-offset parameter, so trim the raw sample data
        # by bytes to skip the beginning of the sound.
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
        # Play a sound effect once; it plays alongside the current background music without interrupting it.
        # If volume is None, the global SFX volume is used; otherwise it overrides the volume for this single play.
        sound = self._get_sound(filename)
        if sound is not None:
            sound.set_volume(self._sfx_volume if volume is None else max(0.0, min(1.0, volume)))
            sound.play()

    def play_skill_sfx(self, skill_id: str) -> None:
        # Play the sound effect matching a hero skill ID.
        filename = SKILL_SFX.get(skill_id)
        if filename:
            self.play_sfx(filename)

    def play_enemy_skill_sfx(self, skill_id: str) -> None:
        # Play the sound effect matching an enemy skill ID.
        filename = ENEMY_SKILL_SFX.get(skill_id)
        if filename:
            self.play_sfx(filename)

    def play_mystery_box_sfx(self, effect_id: str) -> None:
        # Play the sound effect matching a mystery box effect ID.
        filename = MYSTERY_BOX_SFX.get(effect_id)
        if filename:
            self.play_sfx(filename)

    def set_music_volume(self, volume: float) -> None:
        # Set the background music volume; the value is clamped to the range 0.0 to 1.0.
        self._music_volume = max(0.0, min(1.0, volume))
        if self.enabled:
            try:
                pygame.mixer.music.set_volume(self._music_volume)
            except Exception:
                pass

    def set_sfx_volume(self, volume: float) -> None:
        # Set the default volume for sound effects played from now on; already-cached effects pick it up on their next play.
        self._sfx_volume = max(0.0, min(1.0, volume))

    def _play_music_file(self, filename: str) -> None:
        # Load and play one background music track; stay silent instead of crashing on failure.
        # If the file is configured in MUSIC_START_OFFSETS, playback starts at the given second.
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
        # Start the main menu music loop: pick a random track and enter loop mode.
        self._mode = "menu"
        self._play_music_file(self.rng.choice(MENU_TRACKS))

    def start_battle_music(self) -> None:
        # Start the fixed-order battle music loop, beginning with the first track in the queue.
        self._mode = "battle"
        self._battle_index = 0
        self._play_music_file(BATTLE_SEQUENCE[self._battle_index])

    def stop_music(self) -> None:
        # Stop the current background music and leave loop mode.
        self._mode = None
        if self.enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def poll(self) -> None:
        # Called periodically by the UI; once the current track finishes, advance to the next one in the loop.
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