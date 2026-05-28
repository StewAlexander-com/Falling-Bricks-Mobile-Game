# Falling Bricks — Enhanced Edition

### Click the image below to watch the intro video
[![YouTube Short Thumbnail](https://img.youtube.com/vi/LvjWiNNIV68/maxresdefault.jpg)](https://youtube.com/shorts/LvjWiNNIV68)

---

_**Falling Bricks**_ is a dynamic arcade-style dodge game for iOS built with [Pythonista 3](https://omz-software.com/pythonista/). Control a ball and survive increasingly chaotic waves of falling bricks as long as you can.

---

## What's New — Enhanced Edition

The codebase was fully audited and rewritten with a focus on architecture hardening, visual polish, and a genuine difficulty curve. Key changes from the original:

### Bug Fixes
| Bug | Fix |
|-----|-----|
| Duplicate level-up: `update()` and `check_milestone()` both incremented level | Unified into a single `_check_milestone()` path |
| Entry timer not reset on restart | `_init_state()` owns all mutable state, called on setup and reset |
| High-score file corruption on crash | Atomic write via `.tmp` + `os.replace()` |
| Scene-graph mutation from background thread | UI queue (`_ui_queue`) drained on main `update()` tick |
| `SpriteNode(color=Color(...))` TypeError | All colour args are plain `(r, g, b, a)` tuples throughout |
| Two different `SAFE_GAP` constants in use | Single constant used everywhere |
| Background removed on reset | Only nodes tagged `is_game_over_elem` are cleaned up |

### Architecture
- All game state lives in `_init_state()` — one source of truth for both `setup()` and `reset_game()`
- `threading.Lock`-guarded UI queue for safe cross-thread scene mutations
- All tuneable values are named module-level constants (speeds, counts, timing, gaps)
- Every `try/except` logs to `print()` — failures are visible without crashing

### Graphics
- **Bevelled bricks**: each brick is three layered `SpriteNode`s (base + highlight strip + shadow strip)
- **Speed-encoded visuals**: faster bricks are physically taller and shift toward orange-red; slower bricks cool toward blue — the player can read danger at a glance
- **Player trail**: 4 fading translucent circles follow the ball
- **Specular highlight**: white dot on the ball gives it depth
- **Particle burst**: 8 debris dots explode from the collision point on death
- **Level-up flash**: full-screen colour wash that fades out (replaced a scene-scale action that moved the background)
- **HUD**: semi-transparent bar with Score (left), Level (centre), Pause button (right of centre)

### Pause Button
Replaced the invisible top-right tap zone with a rendered **❚❚** icon (two white `SpriteNode` bars on a dark pill). Swaps to a **◆** (diamond) when paused with "Tap ▶ to resume" on screen. Positioned at 75% of screen width to stay clear of Pythonista's system close button.

---

## Difficulty Curve

### Per-level progression
- Base speed: `2.2 + level × 0.20` px/frame, capped at `9.5`
- A time-pressure bonus adds up to +35% on top of level speed over ~600 s — marathon runs keep accelerating without level-ups
- Entry delay between random bricks decays at `0.87^level` with an additional time-based compression, floor `0.15 s`

### Erratic-speed tiers (every 3 levels)
From Level 3 onward, each brick rolls its own independent speed jitter. The window grows with every tier:

| Levels | Tier | Per-brick jitter |
|--------|------|-----------------|
| 1–2    | 0    | None — uniform wall |
| 3–5    | 1    | ±12% |
| 6–8    | 2    | ±20% |
| 9–11   | 3    | ±28% |
| 12–14  | 4    | ±36% |
| 15+    | 5+   | up to ±55% cap |

Jitter is biased slightly upward so erratic tiers are harder on average, not neutral.

### Visual speed encoding
- **Taller brick** = faster (up to +10 px at speed cap)
- **Hotter colour** (orange → red) = faster individual brick
- **Cooler colour** (blue shift) = slower outlier
- Ambient tier heat affects all bricks; per-brick heat is additive on top

### Solvability guarantee
Before every random brick spawn, `_placement_is_solvable()` simulates placing the new brick into the live threat band and checks that at least **2 passable corridors** would remain. If no valid position exists, the spawn is deferred — the player is never legitimately doomed by the generator.

---

## Installation

**Requirements:** iOS device with [Pythonista 3](https://omz-software.com/pythonista/) installed.

1. Clone or download this repository
2. Transfer the following files to Pythonista's documents folder  
   *(Files → iCloud Drive → Pythonista 3)*:
   - `Falling-bricks.py`
   - `ode_to_joy.m4a`
   - `background.jpg`
3. Open Pythonista 3, navigate to `Falling-bricks.py`, tap **▶**

---

## How to Play

| Action | Control |
|--------|---------|
| Move ball | Touch and drag horizontally |
| Pause / Resume | Tap the **❚❚** button in the top bar |
| Skip to scores after death | Tap anywhere on the game-over screen |
| Restart | Tap anywhere on the high-score screen |

- Survive as long as possible — score is time-based
- Every 20 points advances one level (faster bricks, more bricks, tighter gaps)
- Enter your name if you crack the top-5

---

## Game Mechanics

### Scoring
- Score accumulates continuously based on survival time
- Level advances every 20 points
- A `milestone_boost` multiplier (×1.12 per level) compounds with level speed

### Brick count per wave
- Levels 1–3: 3–5 bricks
- Level 4+: `level + tier` to `level + tier + 2`, capped at 12
- Max 14 live bricks on screen simultaneously

### Safe passage
- Wave generation guarantees ≥ 2 corridors ≥ `(ball_diameter + 32)` px wide
- Runtime solvability check on every additional random spawn

---

## File Structure

```
Falling-Bricks-Mobile-Game/
├── Falling-bricks.py     # Main game (Enhanced Edition)
├── ode_to_joy.m4a        # Background music
├── background.jpg        # Background image
├── high_scores.json      # Auto-generated — top 5 scores
└── README.md
```

---

## Roadmap

- 🎚️ Selectable difficulty setting
- 📳 Haptic feedback on collision
- 🎨 Ball skin customisation
- ☁️ iCloud high-score sync
- 🎵 Additional music tracks
- ✨ Power-up items

---

## Credits

- Game engine: Pythonista `scene` framework by Ole Zorn
- Background music: public domain arrangement of Beethoven's *Ode to Joy*
- Sound effects: Pythonista built-in sound library

---

*Report bugs or suggest features via [Issues](https://github.com/StewAlexander-com/Falling-Bricks-Mobile-Game/issues).*
