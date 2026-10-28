# 2048: Overwatch VS Talon Game Rules

Version: 1.2  
Effective date: October 28, 2026  
Document status: Implementation reference

## 1 Purpose of This Document

This document is the sole rules reference for the "2048: Overwatch VS Talon" project. Code, the question bank, save data, and the leaderboard must all be implemented according to this document. The values, inputs, state changes, random mechanics, and end conditions in this document are definitive rules; implementations must not add or modify behavior on their own.

This project is a battle game developed in Python, based on `5×5 board 2048`, and it runs with a graphical user interface (GUI) rather than a terminal text interface. The player moves number tiles with `W`, `A`, `S`, `D` or the arrow keys, merges tiles according to 2048 rules, and converts merge results into damage, healing, maximum health, ability uses, and score. The game includes a Battle Mode and an Endgame Challenge Mode.

The theme names are used only for in-game text and feature naming. No image assets are used; when hero abilities, enemy abilities, and Surprise Box effects trigger, the corresponding voice line/sound effect is played, and background music is played according to the rules in Section 17.

## 2 Fixed Terminology

| Term | Definition |
|---|---|
| Board | A grid of 5 rows and 5 columns, 25 positions in total. |
| Tile | A non-empty number on the board. Its initial value can only be 2 or 4, and it is always a power of 2 afterwards. |
| Empty cell | A position with no number tile and no blocker cell. |
| Blocker cell | A position where tiles cannot be placed, moved, or merged. |
| Valid move | A move after which at least one tile has changed position, or at least one merge has occurred. |
| Merge | Two tiles of the same value that meet along the movement direction combine into one tile of double the value. |
| Turn | One valid move and its complete resolution process. |
| Hero ability uses | An integer resource shared by all three hero abilities. |
| Consecutive correct answers | The number of Bug questions currently answered correctly in a row; resets to zero after a wrong answer. |
| Consecutive wrong answers | The number of Bug questions currently answered wrongly in a row; resets to zero after a correct answer; when it reaches 5, a health penalty is triggered and it resets to zero. |
| Death count | The cumulative number of times the player's current health has dropped to 0, starting from 0. |
| Surprise Box | A single coordinate state saved independently of the board values; it is neither a number tile nor a blocker cell. |

## 3 Game Data

### 3.1 Board Data

The board is stored as a two-dimensional list. Empty cells are represented by `0`, and blocker cells are represented by `-1`. Number tiles are represented by positive integers.

The Surprise Box is stored in a separate `mystery_box` coordinate. It does not block tile movement; when a tile passes through or stops at that coordinate during a valid move, the box effect triggers immediately and the box is removed, and the tile still completes the move according to normal 2048 rules. At most 1 Surprise Box can exist per game.

Board coordinates range from `A1` to `E5`:

| Column | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| Row 1 | A1 | B1 | C1 | D1 | E1 |
| Row 2 | A2 | B2 | C2 | D2 | E2 |
| Row 3 | A3 | B3 | C3 | D3 | E3 |
| Row 4 | A4 | B4 | C4 | D4 | E4 |
| Row 5 | A5 | B5 | C5 | D5 | E5 |

### 3.2 Battle Mode Initial Data

| Data item | Initial value |
|---|---:|
| Board size | 5×5 |
| Initial tile count | 3 |
| Initial tile value | Each tile has a 90% chance of being 2 and a 10% chance of being 4 |
| Player max health | 500 |
| Player current health | 500 |
| Enemy max health | 200 |
| Enemy current health | 200 |
| Initial score | 0 |
| Initial valid turn count | 0 |
| Initial hero ability uses | 3 |
| Initial consecutive correct answers | 0 |
| Initial consecutive wrong answers | 0 |
| Initial death count | 0 |
| Initial blocker cells | 0 |
| Initial hidden quest | 1 |
| Base Bug probability | 5% |

### 3.3 Endgame Challenge Mode Initial Data

| Data item | Initial value |
|---|---:|
| Board size | 5×5 |
| Initial tile count | 20 |
| Initial tile values | 2, 4, 8, 16, 32 |
| Initial score | 0 |
| Initial valid turn count | 0 |
| Initial hero ability uses | 3 |
| Initial blocker cells | 0 |
| Bug mechanic | Not enabled |
| Player health | Not used |
| Enemy health | Not used |

## 4 2048 Movement Rules

### 4.1 Movement Directions

| Input | Direction |
|---|---|
| `W` | Up |
| `A` | Left |
| `S` | Down |
| `D` | Right |

Input is case-insensitive. Spaces are removed before the input is evaluated.

### 4.2 Movement and Merge Order

Each time a direction input is received, a move is first previewed according to normal 2048 rules to determine whether the input is valid. The preview is used only for this determination and must not modify the game state. For a normal move, process in the following order:

1. Read the current board snapshot.
2. Move tiles in the input direction until they hit the board edge, a blocker cell, or another tile that cannot merge. The movement order depends on the input direction: moving left means simulating the movement starting from the leftmost column, and likewise moving up means simulating the movement starting from the topmost row.
3. Merge adjacent tiles with the same value.
4. The same original tile can take part in at most one merge per move.
5. Merged tiles continue to move in the input direction until they can no longer move.
6. Compare the board before and after the move.
7. If the board has not changed, the input is not a valid move: the turn count does not increase, no new tile is generated, no Bug is triggered, and no enemy ability is triggered.
8. If the board has changed, the input becomes a valid turn and proceeds to the turn resolution in Section 5.

Merge examples:

- `2 2 2 0 0` after moving left becomes `4 2 0 0 0`.
- `2 2 2 2 0` after moving left becomes `4 4 0 0 0`.
- `4 4 8 8 0` after moving left becomes `8 16 0 0 0`.

Blocker cells are never moved, merged, or overwritten. Tiles can move up to a blocker cell, but cannot pass through it.

### 4.3 New Tile Generation

After a valid move is completed and merges are resolved, the system generates one new tile in a random empty cell:
The initial random generation probabilities are:
- 90% chance to generate `2`;
- 10% chance to generate `4`.

Starting from step 20:
- 85% chance to generate `2`;
- 10% chance to generate `4`;
- 5% chance to generate `8`.

Starting from step 40:
- 75% chance to generate `2`;
- 15% chance to generate `4`;
- 7% chance to generate `8`;
- 3% chance to generate `16`.

It stays unchanged afterwards.
If there are no empty cells, no new tile is generated. Random selection uses the Python standard library `random`.

When a Bug question is answered wrongly, the system compresses the tiles in the input direction but does not perform merges. As long as at least one tile changes position, a new tile is still generated; if the preview shows that only a normal merge could have caused a change, the move is still a valid turn, but the board remains unchanged and no new tile is generated.

## 5 Player Turn Resolution

In Battle Mode, a valid move is resolved in the following order:

1. Preview the normal move, confirm the input is valid, and save the turn-start snapshot.
2. Determine whether a Bug is triggered according to Section 8; if it is not triggered or is answered correctly, perform the normal move; if answered wrongly, perform a move without merges.
3. Add score and execute battle rewards based on the merge results that actually occurred.
4. If the board has empty cells after the actual move, generate one new tile.
5. Increase the valid turn count.
6. Update hidden quest progress, check the consecutive-answer reward, and generate a Surprise Box when the quest is completed for the first time.
7. Check enemy actions, enemy abilities, and blocker cell durations.
8. Check player death, enemy death, board failure, and other end conditions.

If an enemy ability changes the board, the ability's effect takes place after the new tile is generated. Enemy abilities do not double-count this turn's merge score or merge rewards.

## 6 Merge Score and Battle Rewards

### 6.1 Score

The value of the new tile produced by each merge is that merge's score. For example, merging two `8`s into `16` adds 16 points.

When multiple merges occur in one move, all merge scores are added together.

### 6.2 Merge Rewards

Every merge with a given result increases the corresponding cumulative count. When the cumulative count reaches the threshold, the reward is executed immediately and the threshold is subtracted from that type's cumulative count. Counts exceeding the threshold are kept and not lost.

| Merge result | Trigger threshold | Reward |
|---:|---:|---|
| 4 | Every 2 times | Deal 10 damage to the enemy. |
| 8 | Every 5 times | Restore 10 player health, not exceeding max health. |
| 16 | Every 3 times | Increase max health by 10 and restore 10 health. |
| 32 | Every 2 times | Deal 35 damage to the enemy. |
| 64 | Every 1 time | Gain 1 hero ability use. The hero ability use cap is 5. |
| 128 and above | Every 3 times | Deal damage to the enemy equal to 1× the merge result's value. |

After damage resolution, the enemy's current health is at minimum 0. After healing resolution, the player's current health is at maximum the max health.

## 7 Hero Abilities

Hero abilities can be used in both Battle Mode and Endgame Challenge Mode. The three hero abilities share the same resource pool. Each successful use consumes 1 hero ability use.

When hero ability uses are 0, hero abilities cannot be used. Hero ability uses are at most 5; recovery effects beyond 5 are counted as 5.

### 7.1 Hero Ability List

| Input | Name | Effect | Target |
|---|---|---|---|
| | Self-Destruct Program | Delete one number tile, turning it into an empty cell. DVA_self_destruct.ogg | A coordinate containing a number tile must be selected. |
| | Change Number | Change one number tile to an adjacent level. Duplicate.ogg | A coordinate containing a number tile must be selected, then "Decrease" or "Increase" must be selected. |
| | Return to Previous Step | Restore to the state at the end of the previous complete turn. tracer.ogg | No coordinate needed; can be used at most 3 times per game. |

Only one ability can be used per turn.

### 7.2 Change Number

When changing a number:

- "Decrease" divides the number by 2;
- "Increase" multiplies the number by 2;
- A number cannot be decreased to `1`;
- A number cannot be increased above `512`;
- Changing a number does not directly trigger a merge;
- Changed numbers do not count toward the trigger counts of merge rewards;
- No new tile is generated after changing a number;
- Changing a number does not increase the turn count;
- Changing a number does not trigger enemy abilities;
- Any mergeable state formed by changing a number is handled in the next valid move.

### 7.3 Return to Previous Step

After each valid turn begins and the input is confirmed valid, a snapshot is saved first. The snapshot represents the state before that turn is executed, and includes:

- All game state except hero ability uses and the used count of Return to Previous Step;
- The board, blocker cells, and their remaining duration in turns;
- The current and max health of the player and the enemy;
- The score, valid turn count, and all merge cumulative counts;
- The hidden quest, Surprise Box, and question usage records;
- The enemy ability timer, the last enemy ability, and the direction-reversal state;
- The consecutive correct answers, consecutive wrong answers, and death count;
- The used state of the quiz rescue;
- The random number generator state.

After using Return to Previous Step, the most recent snapshot is restored, but the hero ability uses already consumed are not restored. Return to Previous Step itself does not generate a snapshot and does not save any new undoable state, and the same turn cannot be undone consecutively. Return to Previous Step can be successfully used at most 3 times per game.

## 8 Bug and Quiz Mechanic

### 8.1 Bug Trigger

A Bug is determined only during valid moves in Battle Mode. At the start of each valid move, a random number in the range `[0, 1)` is generated:

- If the random number is less than the current Bug probability, a Bug is triggered;
- Otherwise, no Bug is triggered.

The current Bug probability is:

```text
min(5% + floor((completed valid turns + 1) / 10) × 5%, 30%)
```

That is:

- Valid turns 1 to 9: 5%;
- Valid turns 10 to 19: 10%;
- Valid turns 20 to 29: 15%;
- Valid turns 30 to 39: 20%;
- Valid turns 40 to 49: 25%;
- From valid turn 50 onward: 30%;

### 8.2 Answering Questions

After a Bug is triggered, one question is randomly chosen from the local question bank. There are only two question types: multiple choice and fill-in-the-blank. After the question is displayed, the turn is paused and the player must submit an answer.

When answered correctly:

- The move executes normal movement and merging;
- Score is added normally;
- Merge rewards are executed normally;
- Consecutive correct answers increases by 1, and consecutive wrong answers resets to zero.

When answered wrongly:

- Tiles execute the move;
- No merges are performed in this move;
- No merge score is added;
- No merge rewards are executed;
- Consecutive correct answers resets to zero, and consecutive wrong answers increases by 1;
- This valid move still increases the turn count;
- A new tile is still generated this turn;
- Enemy abilities may still be triggered this turn.

When 5 Bug questions are answered correctly in a row, 1 hero ability use is restored immediately, and then consecutive correct answers resets to zero.

When 5 Bug questions are answered wrongly in a row, the player's current health is immediately reduced by an amount equal to 20% of the current max health (rounded down), with current health at minimum 0; the player's max health is not affected. After the deduction, consecutive wrong answers is immediately reset to zero and counting starts again. After this penalty is resolved, end conditions such as player death are still checked in the order of Section 10.

### 8.3 Question Bank Format

The question bank file is `data/questions.json`, in the following format:

```json
[
  {
    "id": "q001",
    "type": "choice",
    "question": "Which keyword is used to define a function in Python?",
    "options": ["A. func", "B. def", "C. function", "D. make"],
    "answer": "B",
    "explanation": "Python uses def to define functions."
  },
  {
    "id": "q002",
    "type": "fill",
    "question": "The first index of a Python list is ____.",
    "answer": "0",
    "explanation": "Python uses zero-based indexing."
  }
]
```

Answers to multiple-choice questions must be stored as uppercase letters. When comparing fill-in-the-blank answers, leading and trailing spaces are removed and case is ignored.

Within the same game, questions must not repeat until all questions have been used. If the question bank is empty or the file fails to load, the program must display an error and safely exit the current game, and must not fabricate questions or automatically judge answers as correct.

## 9 Battle Mode

### 9.1 Enemy Actions

Battle Mode has only one difficulty, and no difficulty selection is provided. Each valid turn triggers at most one enemy ability. Ability triggers use a fixed turn interval:

| First ability | Subsequent ability interval |
|---:|---:|
| Turn 8 | Every 8 turns |

When an ability triggers, one is randomly chosen from the currently available abilities. The same ability cannot trigger twice in a row. After an ability triggers, the timer is reset.

### 9.2 Enemy Abilities

| Ability | Effect |
|---|---|
| Ground-Splitting Punch | Randomly shuffles the positions of all number tiles; tile values are unchanged; blocker cell positions are unchanged. meteor_strike.ogg |
| Shadow Devour | Randomly deletes one number tile; if there are no number tiles, it has no effect. reaper.ogg |
| System Hack | The direction of the next valid move is reversed; hero abilities can still be used. EMP.ogg |
| Gravity Field | Lowers all numbers on the board greater than 16 by one level; for example, 32 becomes 16. sigma.ogg |
| Cage Match | Generates a blocker cell in one random empty cell, lasting 3 valid turns. If there are no empty cells, it has no effect. SSVGG.ogg |

Every two turns, the enemy launches an attack at a fixed interval, deducting 15 health from the player.
The direction reversal from System Hack takes effect at the very start of the next direction input, earlier than the valid-move preview and Bug determination. When a blocker cell is generated, its expiry turn is recorded as "current valid turn count plus 3". At the end of each valid turn, blocker cells whose expiry turn is less than or equal to the current valid turn count are removed; a newly generated blocker cell does not have its duration reduced in the turn it is generated.

### 9.3 Hidden Quest

At the start of each game, 1 quest is randomly selected from the quest pool. Once selected, the quest content is shown in the status bar for the rest of the game.

| Quest ID | Quest | Completion condition |
|---|---|---|
| T01 | Reach 512 | A tile with a value of at least 512 has ever appeared on the board. |
| T02 | Quick Merge | Complete at least 5 merges within 7 valid turns. |
| T03 | High-Score Action | Earn at least 500 points in a single valid turn. |

After the quest is completed, 1 Surprise Box is generated in a random empty cell. The generation position cannot be a number tile, a blocker cell, or the position of an existing Surprise Box; if there are no available empty cells, no box is generated and none is issued later. At most 1 hidden quest can be completed and 1 Surprise Box generated per game.

### 9.4 Surprise Box

A Surprise Box occupies one empty cell. When a tile moves onto the position of a Surprise Box, the effect triggers immediately, and then that position becomes an empty cell. Each generated box randomly chooses one type from the table below:

| Type | Effect |
|---|---|
| Heroes Never Die | Restores the player's current health to max health. mercy.ogg |
| Dragon Blade Unsheathed | Deals 100 damage to the enemy. dragon_blade.ogg |
| Spirit Fox, Guide Me | Increases hero ability uses by 3, up to a maximum of 5. kitsune_rush.ogg |
| Gravity Field | Lowers the largest number on the board by one level. sigma.ogg |
| Biotic Orb | Deducts 10 of the player's current health; current health is at minimum 0. moira.ogg |
| Cage Match | Generates a blocker cell in a random empty cell after the current move ends, lasting 3 valid turns; if there are no available empty cells, it has no effect. SSVGG.ogg |

## 10 Battle Mode Win/Loss Conditions

End conditions are checked in the following priority order:

1. Enemy current health is less than or equal to 0: the player wins.
2. Player current health is less than or equal to 0: death count increases by 1, and the quiz rescue begins.
3. The board has no valid move: the quiz rescue begins.
4. The quiz rescue fails: the player loses.

### 10.1 Quiz Rescue

Rescues triggered by death and by a stuck board share the same rescue resource; at most 1 quiz rescue is allowed per game, regardless of the trigger reason. When the player dies, the death count always increases by 1 and is recorded, but only the 1st death can enter the rescue; the 2nd and later deaths directly result in the player losing, with no further rescue.

During the rescue phase, 3 new questions are answered in a row:

- All 3 answered correctly: the rescue succeeds and the game continues;
- Any one answered wrongly: the rescue fails and the game ends;
- When the rescue is triggered by player death: the player's health is restored to 50% of max health, rounded down;
- When the rescue is triggered by the board having no valid move: 3 number tiles are randomly deleted, then the game continues;
- After a successful rescue, both consecutive correct answers and consecutive wrong answers reset to zero;
- At most 1 quiz rescue is allowed per game (whether triggered by death or by a stuck board).


## 11 Endgame Challenge Mode

### 11.1 Initial Board Generation

Generate 20 random tiles, with value probabilities as follows:

| Tile value | Probability |
|---:|---:|
| 2 | 45% |
| 4 | 30% |
| 8 | 15% |
| 16 | 7% |
| 32 | 3% |

After the initial board is generated, it must satisfy the following conditions:

- At least 1 empty cell;
- At least 1 valid move exists;
- No blocker cells may be generated;
- No tiles with a value greater than 32 may be generated.

If the conditions are not met, regenerate, with at most 100 attempts. If all 100 attempts fail, use the fixed board:

```text
  2   4   8  16   2
  4   8  16  32   4
  8  16  32   2   0
 16  32   2   4   8
  0   2  16   0   0
```

### 11.2 Objectives

At the start of each game, 1 objective is randomly selected from the objective pool:

| Objective ID | Objective | Success condition |
|---|---|---|
| C01 | Merge 256 | A tile with a value of at least 256 appears on the board. |
| C02 | Achieve a High Score | Total score reaches 5000. |
| C03 | Complete Merges | Complete at least 8 merges cumulatively. |
| C04 | Keep Space | When 128 is reached, the board has at least 3 empty cells. |
| C05 | Triple 128 | Have at least 3 tiles of 128 at the same time. |

### 11.3 End Conditions

- Objective achieved: the challenge succeeds;
- The board has no valid move and Return to Previous Step cannot restore a valid move: the challenge fails;
- The player quits voluntarily: not recorded as a successful result.

Endgame mode does not trigger Bugs, hidden quests, Surprise Boxes, or quiz rescue. Enemy abilities are triggered.

## 12 Graphical Interface Input

The game runs with a desktop GUI and does not read terminal text input. The player operates through keyboard shortcuts, mouse clicks on board tiles, and clicks on interface buttons; coordinate selection is done by clicking tiles on the board, and no letter-plus-number coordinate text input is needed.

### 12.1 Main Game Input

| Input method | Function |
|---|---|
| Keyboard `W`/`A`/`S`/`D` or arrow keys | Attempt one move in the corresponding direction. |
| Direction buttons (UP / DOWN / LEFT / RIGHT) | Same function as the corresponding arrow keys. |
| Keyboard `H` or HELP button | Show the current status, objective, hero ability uses, and rule hints. |
| Keyboard `L` or LEADERBOARD button | Show the leaderboard. |
| Keyboard `Q` or RETURN TO MENU button | Quit the current game and return to the main menu. |
| Keyboard `P` | Prompt the player to select an ability button; does not directly open a menu (ability buttons are always shown in the sidebar). |

### 12.2 Hero Ability Operation

The three ability buttons (DELETE, CHANGE VALUE, RECALL) are always shown in the sidebar, and clicking the corresponding button selects that ability; there is no numeric or letter shortcut menu.

- Before using DELETE or CHANGE VALUE, first click a number tile on the board to complete the coordinate selection; clicking an empty cell, a blocker cell, or an area outside the board is not a valid selection.
- After CHANGE VALUE selects a tile, a popup window provides two buttons, "INCREASE" and "DECREASE", corresponding to "Increase" and "Decrease" respectively.
- RECALL does not require selecting a coordinate; clicking the button attempts to execute it immediately.
- The CANCEL SELECTION button is used to cancel the ability selection currently in progress.

### 12.3 Illegal Operations

Illegal operations must not change any game state. The interface displays an error message (a popup or status bar text) and then continues to wait for the next input. All of the following are illegal operations:

- Attempting to move or use an ability while the game is over or while a rescue/penalty process is in progress;
- Attempting to use a hero ability when hero ability uses are 0;
- Selecting an empty cell, a blocker cell, or a position with no tile when deleting or changing a number;
- Return to Previous Step has no restorable snapshot, or has reached the limit of 3 uses per game;
- When changing a number, there are no options other than clicking "INCREASE" or "DECREASE", so there is no malformed input;
- The multiple-choice answer window only provides the option buttons given by the question, and the fill-in-the-blank answer window requires submitting non-empty text.

## 13 Leaderboard and Local Files

### 13.1 File Structure

```text
data/
  questions.json
  leaderboard.json
```

If the `data` directory does not exist, the program creates it at startup.

### 13.2 Leaderboard Records

Each record uses the following fields:

```json
{
  "name": "Player",
  "mode": "battle",
  "difficulty": "easy",
  "score": 1234,
  "turns": 42,
  "result": "win",
  "date": "2026-09-07"
}
```

Field rules:

- `name`: the player name with leading and trailing spaces removed, 1 to 20 characters long;
- `mode`: can only be `battle` or `challenge`;
- `difficulty`: fixed to `easy` (the only difficulty) in Battle Mode, and fixed to `none` in Challenge Mode;
- `score`: a non-negative integer;
- `turns`: a non-negative integer;
- `result`: can only be `win`, `loss`, or `quit`;
- `date`: uses the `YYYY-MM-DD` format.

### 13.3 Sorting and Error Handling

The leaderboard only records battle wins and endgame challenge successes; it does not record voluntary quits or failures. The leaderboard keeps at most 5 records, sorted in the following order:

1. Score from high to low;
2. When scores are equal, valid turn count from low to high;
3. When still equal, the record with the earlier date comes first.

If the JSON file does not exist, it is treated as an empty leaderboard. If the JSON format is invalid, fields are missing, or writing fails, the program displays an error and keeps running; it must not overwrite the original file, and a leaderboard error must not crash the game.

## 14 Program Module Boundaries

The implementation must contain at least the following responsibility boundaries. Module names may differ, but responsibilities must not be mixed into the main loop:

| Module | Responsibility |
|---|---|
| `GameBoard` | Stores the board, movement, merging, tile generation, coordinate checking, and valid-move checking. |
| `BattleManager` | Stores health, and handles damage, healing, rewards, and battle win/loss. |
| `AbilityManager` | Manages hero ability uses, hero ability usage, and turn snapshots. |
| `QuizManager` | Loads the question bank, draws questions, checks answers, and manages answer streaks. |
| `EventManager` | Manages Bugs, enemy abilities, hidden quests, and Surprise Boxes. |
| `Leaderboard` | Loads, validates, sorts, and saves the leaderboard. |
| `AudioManager` | Manages the background music loop queue and the playing, stopping, and layering rules of ability/effect sound effects (see Section 17). |
| `main.py` | Builds the GUI window, binds buttons and keyboard events, calls modules, and controls the game flow. |

Core logic must be testable independently of the GUI display. Random mechanics should allow a random number generator or random seed to be passed in, so that tests can be reproduced.

## 15 Required Tests

After implementation is complete, at least the following cases must be tested:

1. Moving an empty board in any direction does not increase the turn count.
2. `2 2 2 2 0` moved left results in `4 4 0 0 0`.
3. The same tile does not merge twice in one move.
4. Blocker cells are not overwritten, and tiles cannot pass through blocker cells.
5. An invalid move does not generate a new tile.
6. A valid move generates exactly one new tile.
7. When a Bug is answered correctly, merges happen normally; when answered wrongly, tiles only move without merging.
8. The Bug probability changes according to the rules at valid turns 10, 20, and 30.
9. Merge rewards trigger correctly after reaching the threshold, and counts exceeding the threshold are kept.
10. Hero ability uses cannot exceed 5.
11. Return to Previous Step does not restore hero ability uses that have already been consumed.
12. Enemy abilities do not trigger twice in the same turn.
13. When the enemy dies, the player's victory is determined first.
14. The quiz rescue triggers at most once, and death and a stuck board share the same rescue resource.
15. The 2nd death directly results in failure, with no further rescue.
16. When 5 Bug questions are answered wrongly in a row, 20% of the current max health (rounded down) is deducted, and consecutive wrong answers resets to zero.
17. Illegal input or illegal operations do not change the game state.
18. Missing or corrupted JSON files do not crash the program.
19. The leaderboard keeps only the top 5 and is sorted in the specified order.

## 16 Implementation Priority

Implement in the following order:

1. Board representation, directional movement, merging, and new tile generation.
2. Valid-move determination, turn counting, and score.
3. Battle health, merge rewards, and battle win/loss.
4. The three hero abilities and snapshot restoration.
5. Bugs, the question bank, and quiz rescue.
6. Enemy abilities, hidden quests, and Surprise Boxes.
7. Endgame Challenge Mode.
8. Leaderboard, error handling, and tests.

## 17 Music and Voice

The game does not use image assets, but uses background music and voice lines/sound effects. Audio files are stored in the `music/` directory, all in `.ogg` format.

### 17.1 Main Menu Music

When the main menu is displayed, one of the following three tracks is played at random:

- `Colosseo.ogg`
- `kiriko_origin.ogg`
- `midtown.ogg`

After each track finishes, one of the three is randomly chosen again (including possibly choosing the track that just finished), looping repeatedly until the player leaves the main menu (entering Battle Mode or Endgame Challenge Mode). When Battle Mode or Endgame Challenge Mode is entered, the main menu music stops.

### 17.2 Battle Music

After entering Battle Mode, a fixed-order battle music queue is played, looping the whole group in the following order:

1. `select_hero.ogg`
2. `round1.ogg`
3. `last30.ogg`
4. `overtime.ogg`
5. `round1.ogg`

When one track finishes, the next track in the queue plays immediately; after the 5th track (`round1.ogg`) finishes, it returns to the 1st track (`select_hero.ogg`) and restarts, looping continuously until the battle ends or the player returns to the main menu. Endgame Challenge Mode does not play battle music and does not play main menu music; in this mode background music runs muted (ability sound effects still play normally).

### 17.3 Ability and Effect Sound Effects

When the following actions trigger, the corresponding sound effect file is played once:

| Source | Name | Sound effect file |
|---|---|---|
| Hero ability | Self-Destruct Program | `DVA_self_destruct.ogg` |
| Hero ability | Change Number | `duplicate.ogg` |
| Hero ability | Return to Previous Step | `tracer.ogg` |
| Enemy ability | Ground-Splitting Punch | `meteor_strike.ogg` |
| Enemy ability | Shadow Devour | `reaper.ogg` |
| Enemy ability | System Hack | `EMP.ogg` |
| Enemy ability | Gravity Field | `sigma.ogg` |
| Enemy ability | Cage Match | `SSVGG.ogg` |
| Surprise Box | Heroes Never Die | `mercy.ogg` |
| Surprise Box | Dragon Blade Unsheathed | `dragon_blade.ogg` |
| Surprise Box | Spirit Fox, Guide Me | `kitsune_rush.ogg` |
| Surprise Box | Gravity Field | `sigma.ogg` |
| Surprise Box | Biotic Orb | `moira.ogg` |
| Surprise Box | Cage Match | `SSVGG.ogg` |

Sound effect playback rules:

- Each time the corresponding effect triggers, the sound effect plays once, without looping.
- While a sound effect plays, the current background music (main menu music or battle music) continues to play at the same time.
- If the implementation environment does not support playing sound effects and background music simultaneously, instead: pause the background music, play the sound effect in full, then resume the background music from where it was paused.
- When multiple effects trigger one after another in the same turn, the sound effects play in the order the effects occur and must not cut each other off.

## 18 Default Behavior

Any behavior not defined in this document is handled by the following default rule: do not change the game state, display a clear prompt, and wait for the player to input again.
