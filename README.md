# 2048: Overwatch VS Talon

2048: Overwatch VS Talon is a 5×5 board 2048 combat game built with Python + Tkinter. The game combines classic 2048 gameplay with a combat system, hero skills, a quiz mechanic, enemy skills, hidden quests, surprise boxes, and an endgame challenge mode.

## System Requirements

- **Python 3.8+** (Tkinter must be included)
- **pygame 2.0.0+** (used for audio playback)

### Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: Tkinter usually comes bundled with Python distributions. If it is missing:
- **macOS**: Install the official Python from [python.org](https://www.python.org)

## Running the Game

Run the following in the project directory:

```bash
python3 main.py
```

## Game Features

### Core Gameplay
- **5×5 board**: Number-merging mechanics based on 2048 rules
- **Combat mode**: Fight the enemy by merging tiles to gain damage / healing / skill charges
- **Endgame challenge mode**: Complete specific objectives on preset boards

### Combat System
- **Merge rewards**: Merging different values triggers different effects
  - Merge 4 → damage the enemy
  - Merge 8 → heal yourself
  - Merge 16 → increase max HP
  - Merge 32/64/128+ → stronger effects
- **Enemy skills** (triggered every 8 turns):
  - Earth-Splitting Punch: shuffles the board
  - Shadow Devour: deletes tiles
  - System Hack: reverses the direction of your next move
  - Gravity Field: reduces high-value tiles
  - Cage Match: generates blocked cells
- **Hidden quests**: Complete them to receive a surprise box reward
- **Quiz revival**: When HP reaches zero or the board is stuck, answer 3 questions correctly to revive (once per game)

### Hero Skills
- **Self-Destruct Program**: Delete any tile
- **Change Number**: Multiply a tile's value by 2 or divide it by 2
- **Undo**: Revert the previous turn (limited to 3 times per game)

### Bug Quiz Mechanic
- Each turn has a chance to trigger a programming question (the probability increases with turns, up to 30%)
- Correct answer: normal merge + 5 consecutive correct answers award 1 skill charge
- Wrong answer: tiles move but do not merge + 5 consecutive wrong answers deduct 20% of max HP

### Audio System
- **Main menu music**: 3 Overwatch theme songs play in random loop
- **Battle music**: 5 tracks play in a fixed-order loop
- **Sound effects**: Skills, enemy skills, and box effects all have corresponding voice lines

## Controls

### Keyboard Controls
- **W/A/S/D** or **Arrow keys**: Move tiles
- **P**: Open the skill menu
- **H**: Show the help panel
- **L**: View the leaderboard
- **Q**: Return to the main menu

### Mouse Controls
- Click the on-screen arrow buttons to move tiles
- Click the menu buttons to access skills / help / leaderboard

## Project Structure

```
Final_Project/
├── main.py                 # Main GUI program and interface logic
├── game_engine.py          # Game rules engine (board / combat / skills / events)
├── music_ogg.py           # Audio manager
├── leaderboard.py         # Leaderboard system
├── data/
│   ├── questions.json     # Question bank (20 programming questions)
│   └── leaderboard.json   # Leaderboard records
├── music/                 # Audio assets (19 .ogg files)
├── fonts/
│   └── Times New Roman.ttf
├── tests/
│   └── test_game_engine.py
├── GAME_RULES.md          # Complete game rules document (implementation basis)
└── requirements.txt       # Python dependencies
```


## Rules Document

For detailed game rules, values, mechanics, and implementation requirements, see [GAME_RULES.md](GAME_RULES.md). This document is the sole source of truth for the project and includes:
- Complete game data and initial values
- 2048 move/merge algorithm
- Combat system value tables
- Detailed rules for hero skills and enemy skills
- Bug quiz mechanic
- Music and sound effect mapping tables
- Required test checklist

## Acknowledgements

Audio assets are from *Overwatch*, copyright Blizzard Entertainment. This project is for learning and educational exchange only.
