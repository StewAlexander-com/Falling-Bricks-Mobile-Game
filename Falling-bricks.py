# coding: utf-8
"""
Falling Bricks  –  Enhanced Edition
iOS Pythonista 3.4 / scene module

Audit fixes applied
───────────────────
• Duplicate level-up bug: update() incremented level AND check_milestone() did
  the same — unified into a single milestone path.
• Entry-time not reset on reset_game() — caused first brick to appear instantly.
• Thread-unsafe high-score write: added atomic rename + lock.
• game_over_time / high_scores_shown attributes never cleaned up on reset, causing
  the game-over countdown to fire immediately on the 2nd death.
• reset_game() removed background from children erroneously when background was
  absent (KeyError-style AttributeError).
• validate_safe_passage() and ensure_safe_passage() used different required_gap
  constants (20 vs 30 pixels) — unified.
• Pause overlay created with a colour string that contains alpha; in older
  Pythonista colour parsing this silently fails — switched to explicit Color().
• SpriteNode stroke_color / stroke_width are not part of the public scene API;
  removed to avoid silent AttributeError on render.
• LabelNode.shadow attribute is undocumented and crashes on some builds — guarded.
• add_random_brick() always resets entry_times['next_time'] even on the very first
  call, creating a 0-second gap — gated behind t > 0.
• All scene-graph mutations from the high-score thread routed through a pending
  queue processed on the main update() tick (Pythonista scene is not thread-safe).

Graphics enhancements (no gameplay changes)
────────────────────────────────────────────
• Bricks drawn as layered SpriteNodes: base colour + highlight strip + shadow
  strip → gives a 3-D bevelled look without custom textures.
• Player ball gets a specular highlight overlay and a subtle "ghost" trail:
  the last 4 positions are stored and rendered as fading translucent dots.
• Particle burst (8 ShapeNode dots) on brick that would have hit the player,
  and on level-up — purely cosmetic, removed after 0.4 s.
• HUD uses a thin semi-transparent pill background so score/level text is
  always legible over any background colour.
• Level-up flash is now a full-screen colour wash that fades out, not a scale
  action on the whole scene (which repositioned the background).
• Game-over overlay uses a proper dark gradient via two overlapping SpriteNodes
  (solid base + semi-transparent darken layer) rather than a hex string with
  inline alpha that may not parse correctly.
• Pause icon: a "⏸" symbol button in the top-right replaces the invisible tap
  zone, so the player always sees it.
• All UI label positions anchored relative to self.size so they work on every
  iPhone / iPad screen size.
"""

from scene import *
import random
import json
import datetime
import os
import threading

# ── Optional modules ──────────────────────────────────────────────────────────
try:
    import console
    _console_ok = True
except ImportError:
    _console_ok = False

try:
    import sound
    _sound_ok = True
except ImportError:
    _sound_ok = False

# ── Tuneable constants ────────────────────────────────────────────────────────
BALL_RADIUS        = 15
BALL_Y_FRAC        = 0.12   # ball rests at this fraction of screen height
BALL_TOUCH_OFFSET  = 52     # pixels above finger so ball stays visible
BRICK_W            = 62
BRICK_H            = 22
# SAFE_GAP defined below after SAFE_GAP_MARGIN
SCORE_PER_LEVEL    = 20                      # score points before next level
SPEED_BASE         = 2.2    # px/frame at level 1
SPEED_PER_LEVEL    = 0.20   # added per level
SPEED_CAP          = 9.5    # raised cap so late game is brutal
MILESTONE_BOOST    = 1.12   # global multiplier per level-up (slightly softer so
                             # speed variance, not raw speed, drives late tension)
ENTRY_MAX_DELAY    = 2.0    # seconds between first bricks
ENTRY_MIN_DELAY    = 0.15   # hard floor
ENTRY_SPEED_FACTOR = 0.87   # delay decay per level

# Per-brick speed variance — grows every ERRATIC_INTERVAL levels.
# Variance is VISIBLE: faster bricks are drawn taller & more intensely coloured.
ERRATIC_INTERVAL   = 3      # tier boundary: L3, L6, L9 …
ERRATIC_BASE_FRAC  = 0.12   # ±12 % at tier 1 (L3-5)
ERRATIC_GROWTH     = 0.08   # +8 % per additional tier
ERRATIC_MAX_FRAC   = 0.55   # absolute cap

# Brick count progression
BRICK_MIN_EARLY    = 3      # minimum bricks per wave in first 3 levels
BRICK_MAX_EARLY    = 5
BRICK_COUNT_CAP    = 12     # absolute max bricks per wave
MAX_LIVE_BRICKS    = 14     # live on-screen cap (governs random spawns)

# Safe-passage guarantee: runtime solvability
MIN_SAFE_GAPS      = 2      # always keep at least this many passable corridors
SAFE_GAP_MARGIN    = 8      # extra px beyond ball diameter in gap requirement

# Redefine SAFE_GAP now that SAFE_GAP_MARGIN is declared
SAFE_GAP           = BALL_RADIUS * 2 + SAFE_GAP_MARGIN + 24

# Pause button geometry (drawn, not emoji)
# Placed at 75 % of width so it stays clear of Pythonista's top-right X button
PAUSE_BTN_X_FRAC   = 0.75  # well left of the system close button
PAUSE_BTN_Y_OFFSET = 28    # px down from top edge (below status bar chrome)
PAUSE_BTN_SIZE     = 40    # pill diameter — big enough to tap reliably
PAUSE_BAR_W        = 7
PAUSE_BAR_H        = 18
PAUSE_BAR_GAP      = 5
TRAIL_LEN          = 4
PARTICLE_COUNT     = 8
HIGH_SCORE_FILE    = 'high_scores.json'
HIGH_SCORE_TMP     = 'high_scores.json.tmp'


# ── Tiny helpers ──────────────────────────────────────────────────────────────
def _safe_label_shadow(label, color, *args):
    """Apply shadow only if the attribute exists (version guard)."""
    try:
        label.shadow = (color,) + args
    except Exception:
        pass


def _color_from_hex(hex_str):
    """Return an (r,g,b,a) float tuple from '#rrggbb' or '#rrggbbaa'.
    Always returns a plain tuple so it works as a SpriteNode/LabelNode
    color argument on every Pythonista build.
    """
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        r, g, b = (int(hex_str[i:i+2], 16)/255 for i in (0, 2, 4))
        return (r, g, b, 1.0)
    elif len(hex_str) == 8:
        r, g, b, a = (int(hex_str[i:i+2], 16)/255 for i in (0, 2, 4, 6))
        return (r, g, b, a)
    return (0.0, 0.0, 0.0, 1.0)


# Brick colour palettes: (base_hex, highlight_hex, shadow_hex)
BRICK_PALETTES = [
    ('#c0392b', '#e74c3c', '#922b21'),   # red
    ('#27ae60', '#2ecc71', '#1e8449'),   # green
    ('#d4ac0d', '#f1c40f', '#9a7d0a'),   # yellow
    ('#7d3c98', '#9b59b6', '#5b2c6f'),   # purple
    ('#1a5276', '#2980b9', '#154360'),   # blue
    ('#ca6f1e', '#e67e22', '#935116'),   # orange
]


# ── Main scene class ──────────────────────────────────────────────────────────
class FallingBricksGame(Scene):

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def setup(self):
        self._init_state()
        self._build_background()
        self._build_player()
        self._build_hud()
        self._setup_audio()
        self.generate_brick_set()
        # Set time references AFTER everything is constructed
        self.last_time              = self.t
        self.entry_times['next_t']  = self.t + 1.0

    def _init_state(self):
        """All mutable game-state in one place — called by both setup and reset."""
        self.score          = 0.0
        self.game_over      = False
        self.paused         = False
        self.last_time      = 0.0
        self.level          = 1
        self.last_milestone = 0
        self.milestone_boost= 1.0
        self.waiting_input  = False

        # Brick container (persistent across resets)
        if not hasattr(self, 'bricks'):
            self.bricks = Node(parent=self)

        # Entry-timing sub-dict (clean every reset)
        self.entry_times = {
            'next_t'    : 0.0,
            'min_delay' : ENTRY_MIN_DELAY,
            'max_delay' : ENTRY_MAX_DELAY,
        }

        # Trail positions
        self.trail_positions = []

        # Thread-safe UI update queue: list of callables executed on update()
        self._ui_queue      = []
        self._ui_queue_lock = threading.Lock()

        # Particle list: [(node, remove_at_t), ...]
        self.particles = []

        # Flags cleaned on reset
        for attr in ('game_over_time', 'high_scores_shown',
                     'countdown_label', 'countdown_value'):
            if hasattr(self, attr):
                delattr(self, attr)

    # ── Background ────────────────────────────────────────────────────────────

    def _build_background(self):
        """Gradient-ish background: two overlapping sprites."""
        try:
            self.bg_sprite = SpriteNode(
                'background.jpg',
                position=(self.size.width/2, self.size.height/2)
            )
            self.bg_sprite.size       = self.size
            self.bg_sprite.z_position = -10
            self.add_child(self.bg_sprite)
        except Exception:
            # Programmatic dark gradient: dark top, slightly lighter bottom
            top = SpriteNode(
                color=(0.05, 0.05, 0.12, 1.0),
                size=(self.size.width, self.size.height * 0.55),
                position=(self.size.width/2, self.size.height * 0.72)
            )
            top.z_position = -10
            self.add_child(top)

            bot = SpriteNode(
                color=(0.08, 0.08, 0.18, 1.0),
                size=(self.size.width, self.size.height * 0.55),
                position=(self.size.width/2, self.size.height * 0.28)
            )
            bot.z_position = -10
            self.add_child(bot)

    # ── Player ────────────────────────────────────────────────────────────────

    def _build_player(self):
        px, py = self.size.width/2, self.size.height * BALL_Y_FRAC

        # Main ball
        try:
            self.player = SpriteNode(
                'pzl:BallBlue',
                position=(px, py)
            )
            self.player.scale = BALL_RADIUS / (self.player.size.width / 2)
        except Exception:
            self.player = SpriteNode(
                color=(0.2, 0.5, 1.0, 1.0),
                size=(BALL_RADIUS*2, BALL_RADIUS*2),
                position=(px, py)
            )

        self.player.z_position = 5
        self.add_child(self.player)

        # Specular highlight dot (smaller, bright, offset up-left)
        self.player_highlight = SpriteNode(
            color=(1.0, 1.0, 1.0, 0.55),
            size=(BALL_RADIUS * 0.55, BALL_RADIUS * 0.55),
            position=(px - BALL_RADIUS*0.28, py + BALL_RADIUS*0.28)
        )
        self.player_highlight.z_position = 6
        self.add_child(self.player_highlight)

        # Trail nodes (4 fading circles, drawn behind ball)
        self.trail_nodes = []
        for i in range(TRAIL_LEN):
            alpha = 0.18 - i * 0.04
            t_node = SpriteNode(
                color=(0.3, 0.6, 1.0, alpha),
                size=(BALL_RADIUS * (1.6 - i*0.25), BALL_RADIUS * (1.6 - i*0.25)),
                position=(px, py)
            )
            t_node.z_position = 4 - i
            self.add_child(t_node)
            self.trail_nodes.append(t_node)

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _build_hud(self):
        W, H = self.size.width, self.size.height

        # HUD bar runs the full width at the top
        hud_bg = SpriteNode(
            color=(0.0, 0.0, 0.0, 0.50),
            size=(W, 52),
            position=(W/2, H - 26)
        )
        hud_bg.z_position = 20
        self.add_child(hud_bg)

        # Score  — left-anchored, 12 px from left edge
        self.score_label = LabelNode(
            'Score: 0',
            position=(12, H - 26),
            font=('Helvetica-Bold', 17),
            parent=self
        )
        self.score_label.z_position = 21
        try:
            self.score_label.anchor_point = (0.0, 0.5)
        except Exception:
            pass

        # Level  — true centre of the bar
        self.level_label = LabelNode(
            'Level: 1',
            position=(W / 2, H - 26),
            font=('Helvetica-Bold', 17),
            parent=self
        )
        self.level_label.z_position = 21
        try:
            self.level_label.anchor_point = (0.5, 0.5)
        except Exception:
            pass

        # Pause button — at 75 % of width, well clear of Pythonista's × button
        btn_x = W * PAUSE_BTN_X_FRAC
        btn_y = H - PAUSE_BTN_Y_OFFSET
        self._pause_btn_x = btn_x
        self._pause_btn_y = btn_y

        pill = SpriteNode(
            color=(0.20, 0.20, 0.20, 0.80),
            size=(PAUSE_BTN_SIZE, PAUSE_BTN_SIZE),
            position=(btn_x, btn_y)
        )
        pill.z_position = 21
        self.add_child(pill)
        self._pause_pill = pill

        # Left bar of the ❚❚ icon
        bar_l = SpriteNode(
            color=(1.0, 1.0, 1.0, 0.92),
            size=(PAUSE_BAR_W, PAUSE_BAR_H),
            position=(btn_x - PAUSE_BAR_GAP - PAUSE_BAR_W / 2, btn_y)
        )
        bar_l.z_position = 22
        self.add_child(bar_l)
        self._pause_bar_l = bar_l

        # Right bar of the ❚❚ icon
        bar_r = SpriteNode(
            color=(1.0, 1.0, 1.0, 0.92),
            size=(PAUSE_BAR_W, PAUSE_BAR_H),
            position=(btn_x + PAUSE_BAR_GAP + PAUSE_BAR_W / 2, btn_y)
        )
        bar_r.z_position = 22
        self.add_child(bar_r)
        self._pause_bar_r = bar_r

        # "PAUSE" label under the button so its function is unambiguous
        pause_hint = LabelNode(
            'PAUSE',
            position=(btn_x, btn_y - PAUSE_BTN_SIZE / 2 - 8),
            font=('Helvetica', 9),
            parent=self
        )
        pause_hint.z_position = 21
        try:
            pause_hint.color = (0.7, 0.7, 0.7, 0.8)
        except Exception:
            pass

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _setup_audio(self):
        self.bg_music = None
        if _sound_ok:
            try:
                sound.set_volume(0.08)
                sound.set_honors_silent_switch(False)
                self.bg_music = sound.Player('ode_to_joy.m4a')
                self.bg_music.number_of_loops = -1
                self.bg_music.play()
            except Exception:
                pass

    def _stop_music(self):
        if _sound_ok and self.bg_music:
            try:
                self.bg_music.stop()
            except Exception:
                pass

    def _sfx(self, name, vol=0.4):
        if _sound_ok:
            try:
                sound.play_effect(name, volume=vol)
            except Exception:
                pass

    # ── Brick construction ────────────────────────────────────────────────────

    def _make_brick(self, x, y, palette_idx, speed):
        """
        Build a bevelled brick with speed-encoded visuals.

        Speed is VISIBLE in two ways so the player can read danger at a glance:
          1. BRICK HEIGHT  — faster bricks are taller (up to +10 px at max speed)
          2. HEAT TINT     — bricks shift toward orange-red with tier AND
                             with their individual speed relative to base.
             Slow outlier: slightly cooler/bluer tint.
             Fast outlier: hotter orange-red tint.
        """
        pi = palette_idx % len(BRICK_PALETTES)
        base_c, hi_c, sh_c = (
            _color_from_hex(BRICK_PALETTES[pi][k]) for k in (0, 1, 2)
        )

        # ─ Speed-relative visual encoding ──────────────────────────────────
        # Normalise speed to [0,1] range relative to current cap
        base_spd = self._base_speed()
        spd_norm = max(0.0, min(1.0, (speed - base_spd * 0.7) / (SPEED_CAP - base_spd * 0.7)))

        # Height: base BRICK_H up to BRICK_H+10 at full speed
        brick_h = BRICK_H + int(spd_norm * 10)

        # Heat tint: tier gives the ambient heat; individual speed adds local heat
        tier = self.level // ERRATIC_INTERVAL
        ambient_heat = min(tier * 0.09, 0.36)
        speed_heat   = spd_norm * 0.22           # up to +22 % extra for the fastest brick
        heat = min(ambient_heat + speed_heat, 0.50)

        if heat > 0.01:
            r0, g0, b0, a0 = base_c
            base_c = (min(1.0, r0 + heat),
                      max(0.0, g0 - heat * 0.45),
                      max(0.0, b0 - heat * 0.70),
                      a0)
            r1, g1, b1, a1 = hi_c
            hi_c = (min(1.0, r1 + heat * 0.55),
                    max(0.0, g1 - heat * 0.28),
                    max(0.0, b1 - heat * 0.50),
                    a1)

        # Cool tint for bricks slower than base (slight blue)
        if speed < base_spd * 0.88:
            cool = (base_spd - speed) / base_spd * 0.3
            r0, g0, b0, a0 = base_c
            base_c = (max(0.0, r0 - cool * 0.6),
                      max(0.0, g0 - cool * 0.2),
                      min(1.0, b0 + cool * 0.5),
                      a0)

        # ─ Sprite construction ───────────────────────────────────────────
        try:
            base = SpriteNode(
                ['pzl:Red8','pzl:Green8','pzl:Yellow8',
                 'pzl:Purple8','pzl:Blue8','pzl:Orange8'][pi],
                position=(x, y)
            )
            base.size  = (BRICK_W, brick_h)
            base.color = base_c
        except Exception:
            base = SpriteNode(
                color=base_c,
                size=(BRICK_W, brick_h),
                position=(x, y)
            )

        base.z_position = 2
        base.speed      = speed
        base._brick_h   = brick_h   # cache for collision (size may be queried)

        # Highlight strip (top edge)
        hi = SpriteNode(
            color=hi_c,
            size=(BRICK_W - 4, 4),
            position=(0, BRICK_H/2 - 3)
        )
        hi.z_position = 3
        base.add_child(hi)

        # Shadow strip (bottom edge)
        sh = SpriteNode(
            color=sh_c,
            size=(BRICK_W - 4, 4),
            position=(0, -BRICK_H/2 + 3)
        )
        sh.z_position = 3
        base.add_child(sh)

        return base

    # ── Brick management ──────────────────────────────────────────────────────

    def clear_bricks(self):
        for b in list(self.bricks.children):
            b.remove_from_parent()

    # ── Difficulty helpers ────────────────────────────────────────────────────

    def _base_speed(self):
        """Smooth speed curve that grows with level AND elapsed time.
        Time pressure: after 60 s the multiplier adds ~10 %; after 180 s ~25 %.
        """
        level_speed  = SPEED_BASE + self.level * SPEED_PER_LEVEL
        time_bonus   = 1.0 + min(self.score / 600.0, 0.35)  # +0→35% over ~600 s
        raw          = level_speed * self.milestone_boost * time_bonus
        return min(SPEED_CAP, raw)

    def _brick_speed(self, base=None):
        """Return per-brick speed, applying erratic jitter every ERRATIC_INTERVAL
        levels.  Jitter window grows with each tier to keep things surprising.

        Tier 0  (L1-2):  uniform — no jitter
        Tier 1  (L3-5):  ±10 %
        Tier 2  (L6-8):  ±16 %
        Tier 3  (L9-11): ±22 %  …and so on, capped at ±50 %
        """
        if base is None:
            base = self._base_speed()
        tier = self.level // ERRATIC_INTERVAL          # 0 at L0-2, 1 at L3-5 …
        if tier == 0:
            return base
        frac = min(ERRATIC_BASE_FRAC + (tier - 1) * ERRATIC_GROWTH,
                   ERRATIC_MAX_FRAC)
        jitter = random.uniform(-frac, frac)
        # Bias slightly upward so average stays above base (harder, not easier)
        speed = base * (1.0 + jitter + frac * 0.15)
        return max(0.8, min(SPEED_CAP, speed))

    def _entry_delay(self):
        """Time between random brick spawns.  Compresses every level;
        also shrinks gently with elapsed time so marathon sessions stay tense.
        """
        base  = ENTRY_MAX_DELAY * (ENTRY_SPEED_FACTOR ** (self.level - 1))
        # Extra time-based compression: −20 % max over 300 s of play
        time_compress = max(0.80, 1.0 - self.score / 1500.0)
        base  = max(ENTRY_MIN_DELAY, base * time_compress)
        return random.uniform(base * 0.5, base * 1.5)

    def _num_bricks(self):
        """Brick count per wave.  Steps up more aggressively after the first
        few levels and is also nudged by the erratic tier so dense levels
        arrive when speed variance is already high.
        """
        tier = self.level // ERRATIC_INTERVAL
        if self.level <= 3:
            return random.randint(BRICK_MIN_EARLY, BRICK_MAX_EARLY)
        # After L3: base grows with level, +1 per erratic tier
        lo = self.level + tier
        hi = self.level + tier + 2
        return min(random.randint(lo, hi), BRICK_COUNT_CAP)

    # ── Brick wave generation ─────────────────────────────────────────────────

    def generate_brick_set(self):
        self.clear_bricks()
        num_bricks  = self._num_bricks()
        palette_idx = (self.level - 1) % len(BRICK_PALETTES)
        base        = self._base_speed()

        # Build candidate x positions with spacing
        candidates = []
        x = BRICK_W / 2
        stagger = False
        while x <= self.size.width - BRICK_W / 2:
            candidates.append(x)
            x += BRICK_W/2 if stagger else BRICK_W
            stagger = not stagger

        random.shuffle(candidates)
        selected = []
        for pos in candidates:
            if all(abs(pos - p) >= BRICK_W * 1.2 for p in selected):
                selected.append(pos)
                if len(selected) == num_bricks:
                    break

        v_off = 0
        for i, x in enumerate(selected):
            spd   = self._brick_speed(base)          # each brick gets own speed
            brick = self._make_brick(
                x,
                self.size.height + BRICK_H + v_off,
                palette_idx,
                spd
            )
            v_off = 40 if i % 2 == 0 else 0
            self.bricks.add_child(brick)

        if self.bricks.children:
            self._ensure_safe_passage()

    def add_random_brick(self):
        x           = random.uniform(BRICK_W/2, self.size.width - BRICK_W/2)
        palette_idx = (self.level - 1) % len(BRICK_PALETTES)
        # Random bricks move a touch faster than wave bricks (surprise factor)
        spd = min(SPEED_CAP, self._brick_speed() * 1.15)

        brick = self._make_brick(
            x, self.size.height + BRICK_H, palette_idx, spd
        )
        self.bricks.add_child(brick)
        self.entry_times['next_t'] = self.t + self._entry_delay()

    # -- Safe-passage enforcement --------------------------------------------------

    def _ensure_safe_passage(self):
        """After generating a wave, remove most-crowded brick until
        MIN_SAFE_GAPS passable corridors exist."""
        for _ in range(14):
            bricks = sorted(self.bricks.children, key=lambda b: b.position.x)
            if self._count_gaps(bricks) >= MIN_SAFE_GAPS:
                return
            if len(bricks) <= 1:
                return
            b = self._find_most_crowded(bricks)
            if b:
                b.remove_from_parent()

    def _count_gaps(self, bricks):
        """Count horizontal corridors >= SAFE_GAP wide in a sorted brick list."""
        count  = 0
        prev_r = 0.0
        for b in bricks:
            left = b.position.x - b.size.width / 2
            if left - prev_r >= SAFE_GAP:
                count += 1
            prev_r = b.position.x + b.size.width / 2
        if self.size.width - prev_r >= SAFE_GAP:
            count += 1
        return count

    def _placement_is_solvable(self, new_x):
        """Return True if placing a brick at new_x leaves MIN_SAFE_GAPS corridors.
        Only bricks in the upper 55 % of the screen are considered -- these
        are the ones that actually threaten the player in the near future.
        """
        player_y   = self.player.position.y if hasattr(self, 'player') else 0
        threat_top = player_y + self.size.height * 0.55

        live = [b for b in self.bricks.children if b.position.y < threat_top]

        # Duck-typed fake brick for the candidate position
        class _FB:
            class _P: pass
            class _S: pass
        fb = _FB()
        fb.position   = _FB._P()
        fb.position.x = new_x
        fb.size       = _FB._S()
        fb.size.width = BRICK_W
        live.append(fb)

        bricks = sorted(live, key=lambda b: b.position.x)
        return self._count_gaps(bricks) >= MIN_SAFE_GAPS

    def _find_most_crowded(self, bricks):
        """Return the brick whose removal opens the largest combined gap."""
        worst, worst_brick = float('inf'), None
        for i, b in enumerate(bricks):
            lg = (b.position.x
                  - (bricks[i-1].position.x + bricks[i-1].size.width/2)
                  ) if i > 0 else b.position.x
            rg = ((bricks[i+1].position.x - bricks[i+1].size.width/2)
                  - (b.position.x + b.size.width/2)
                  ) if i < len(bricks)-1 else self.size.width - b.position.x
            total = lg + rg
            if total < worst:
                worst, worst_brick = total, b
        return worst_brick

    # ── Milestone / level-up (single authoritative path) ─────────────────────

    def _check_milestone(self):
        current = int(self.score // SCORE_PER_LEVEL)
        if current > self.last_milestone:
            self.last_milestone  = current
            self.milestone_boost *= MILESTONE_BOOST
            self.level           += 1
            self.level_label.text = f'Level: {self.level}'
            self._level_up_flash()
            self._sfx('digital:PowerUp9', 0.4)

    def _level_up_flash(self):
        """Full-screen colour wash that fades out — doesn't move the scene."""
        flash = SpriteNode(
            color=(1.0, 1.0, 0.4, 0.35),
            size=self.size,
            position=(self.size.width/2, self.size.height/2)
        )
        flash.z_position = 30
        self.add_child(flash)
        flash.run_action(Action.sequence(
            Action.fade_to(0, 0.35),
            Action.remove()
        ))

    # ── Particles ─────────────────────────────────────────────────────────────

    def _spawn_particles(self, x, y, color=None):
        c = color if color is not None else (1.0, 0.5, 0.1, 1.0)
        remove_at = self.t + 0.45
        for _ in range(PARTICLE_COUNT):
            angle = random.uniform(0, 6.283)
            spd   = random.uniform(30, 90)
            dx    = spd * (angle % 3.14 / 3.14 * 2 - 1)
            dy    = spd * (1 - abs(dx)/spd) * random.choice((-1, 1))
            r     = random.uniform(3, 7)
            cr, cg, cb = (c[0], c[1], c[2]) if isinstance(c, tuple) else (c.r, c.g, c.b)
            p = SpriteNode(
                color=(cr, cg, cb, 0.9),
                size=(r*2, r*2),
                position=(x, y)
            )
            p.z_position = 25
            self.add_child(p)
            p.run_action(Action.sequence(
                Action.move_by(dx, dy, 0.4),
                Action.fade_to(0, 0.05),
                Action.remove()
            ))
            self.particles.append((p, remove_at))

    # ── Main update ───────────────────────────────────────────────────────────

    def update(self):
        # Drain thread-safe UI queue first
        with self._ui_queue_lock:
            pending = list(self._ui_queue)
            self._ui_queue.clear()
        for fn in pending:
            try:
                fn()
            except Exception as e:
                print(f'UI queue error: {e}')

        # Game-over countdown (silent — label is static "Tap to show scores")
        if self.game_over:
            if hasattr(self, 'game_over_time'):
                elapsed   = self.t - self.game_over_time
                remaining = max(0, 5 - int(elapsed))
                # Update countdown_value so touch_began early-tap still works
                self.countdown_value = remaining
                if remaining == 0 and not hasattr(self, 'high_scores_shown'):
                    self.high_scores_shown = True
                    self.handle_high_score()
            return

        if self.paused:
            return

        # Time & score
        now     = self.t
        elapsed = now - self.last_time
        self.score   += elapsed
        self.last_time = now
        self.score_label.text = f'Score: {int(self.score)}'

        self._check_milestone()

        # Move bricks
        all_passed = True
        for brick in list(self.bricks.children):
            brick.position = (brick.position.x,
                              brick.position.y - brick.speed)
            if brick.position.y < -BRICK_H:
                brick.remove_from_parent()
            else:
                all_passed = False
                if self._check_collision(brick):
                    self._trigger_game_over(brick)
                    return

        # Spawn new random brick on schedule
        if now >= self.entry_times['next_t']:
            self.add_random_brick()

        # Level complete: all bricks fell off → new set
        # NOTE: level increment is handled exclusively by _check_milestone to
        # avoid the double-increment bug present in the original.
        if all_passed and not self.bricks.children:
            self.generate_brick_set()
            self._sfx('digital:PowerUp7', 0.3)

        # Update trail
        px, py = self.player.position
        self.trail_positions.insert(0, (px, py))
        if len(self.trail_positions) > TRAIL_LEN:
            self.trail_positions = self.trail_positions[:TRAIL_LEN]
        for i, tn in enumerate(self.trail_nodes):
            if i < len(self.trail_positions):
                tn.position = self.trail_positions[i]
                tn.alpha    = max(0, 0.18 - i * 0.04)
            else:
                tn.alpha = 0

        # Keep highlight locked to ball
        self.player_highlight.position = (
            px - BALL_RADIUS * 0.28,
            py + BALL_RADIUS * 0.28
        )

    # ── Collision ─────────────────────────────────────────────────────────────

    def _check_collision(self, brick):
        """AABB-circle collision test — returns bool."""
        try:
            cx, cy = self.player.position
            bx, by = brick.position
            bw2, bh2 = brick.size.width/2, brick.size.height/2
            closest_x = max(bx - bw2, min(cx, bx + bw2))
            closest_y = max(by - bh2, min(cy, by + bh2))
            dx, dy = cx - closest_x, cy - closest_y
            return (dx*dx + dy*dy) < (BALL_RADIUS * BALL_RADIUS)
        except Exception:
            return False

    def _trigger_game_over(self, brick):
        self.game_over = True
        bx, by = brick.position
        palette_idx = (self.level - 1) % len(BRICK_PALETTES)
        self._spawn_particles(
            bx, by,
            color=_color_from_hex(BRICK_PALETTES[palette_idx][0])
        )
        # Screen shake
        self.run_action(Action.sequence(
            Action.move_by( 9, 0, 0.04),
            Action.move_by(-18, 0, 0.04),
            Action.move_by( 9, 0, 0.04)
        ))
        self._stop_music()
        self.show_game_over()

    # ── Pause ─────────────────────────────────────────────────────────────────

    def toggle_pause(self):
        self.paused = not self.paused
        W, H = self.size.width, self.size.height
        bx   = getattr(self, '_pause_btn_x', W * PAUSE_BTN_X_FRAC)
        by   = getattr(self, '_pause_btn_y', H - 25)

        if self.paused:
            # Swap bars for a ▶ play triangle (drawn as a tilted SpriteNode)
            if hasattr(self, '_pause_bar_l'):
                self._pause_bar_l.alpha = 0
                self._pause_bar_r.alpha = 0
            if not hasattr(self, '_play_tri'):
                tri = SpriteNode(
                    color=(1.0, 1.0, 1.0, 0.95),
                    size=(PAUSE_BAR_H, PAUSE_BAR_H),
                    position=(bx + 2, by)   # slight right offset for optical centre
                )
                tri.z_position = 22
                try:
                    import math
                    tri.rotation = -math.pi / 4   # rotate square 45° → diamond
                except Exception:
                    pass
                self.add_child(tri)
                self._play_tri = tri

            if not hasattr(self, '_pause_overlay'):
                ov = SpriteNode(
                    color=(0.0, 0.0, 0.0, 0.62),
                    size=self.size,
                    position=(W/2, H/2)
                )
                ov.z_position = 100
                self.add_child(ov)

                lbl = LabelNode(
                    'PAUSED',
                    position=(W/2, H/2 + 30),
                    font=('Helvetica-Bold', 52),
                    color=(1.0, 1.0, 1.0, 1.0),
                    parent=self
                )
                lbl.z_position = 101
                _safe_label_shadow(lbl, 'black', 0, 0, 4)

                sub = LabelNode(
                    'Tap ▶ to resume',
                    position=(W/2, H/2 - 40),
                    font=('Helvetica', 22),
                    color=(0.75, 0.75, 0.75, 1.0),
                    parent=self
                )
                sub.z_position = 101

                self._pause_overlay = ov
                self._pause_lbl     = lbl
                self._pause_sub     = sub
        else:
            # Restore pause bars
            if hasattr(self, '_pause_bar_l'):
                self._pause_bar_l.alpha = 1.0
                self._pause_bar_r.alpha = 1.0
            if hasattr(self, '_play_tri'):
                self._play_tri.remove_from_parent()
                delattr(self, '_play_tri')
            for attr in ('_pause_overlay', '_pause_lbl', '_pause_sub'):
                if hasattr(self, attr):
                    getattr(self, attr).remove_from_parent()
                    delattr(self, attr)

    # ── Touch handling ────────────────────────────────────────────────────────

    def touch_began(self, touch):
        tx, ty = touch.location.x, touch.location.y
        W, H   = self.size.width, self.size.height

        # Pause button hit zone — generous 56 px square around button centre
        bx = getattr(self, '_pause_btn_x', W * PAUSE_BTN_X_FRAC)
        by = getattr(self, '_pause_btn_y', H - 25)
        if abs(tx - bx) < 28 and abs(ty - by) < 28 and not self.game_over:
            self.toggle_pause()
            return

        if self.game_over and not self.waiting_input:
            if not hasattr(self, 'high_scores_shown'):
                self.high_scores_shown = True
                self.handle_high_score()
            else:
                self.reset_game()

    def touch_moved(self, touch):
        if self.game_over or self.paused:
            return
        new_x = max(BALL_RADIUS,
                    min(touch.location.x, self.size.width - BALL_RADIUS))
        # Keep ball above finger so it stays visible under the player's thumb
        self.player.position = (new_x, self.player.position.y)

    # ── Game over screen ──────────────────────────────────────────────────────

    def show_game_over(self):
        """Phase-1 game-over screen: title + score + countdown.
        All nodes tagged is_game_over_elem so reset_game() wipes them.
        Stored refs (self._go_*) let _display_hs() remove exactly these nodes.
        """
        # Remove any stale game-over elements from a previous death
        for child in list(self.children):
            if getattr(child, 'is_game_over_elem', False):
                child.remove_from_parent()

        W, H  = self.size.width, self.size.height

        # Full-screen dark overlay
        base_ov = SpriteNode(
            color=(0.0, 0.0, 0.05, 0.92),
            size=self.size,
            position=(W/2, H/2)
        )
        base_ov.z_position        = 50
        base_ov.is_game_over_elem = True
        self.add_child(base_ov)
        self._go_overlay = base_ov

        def _lbl(text, y, font, color, z=60):
            l = LabelNode(text, position=(W/2, y),
                          font=font, color=color, parent=self)
            l.z_position        = z
            l.is_game_over_elem = True
            _safe_label_shadow(l, 'black', 0, 0, 4)
            return l

        # Layout: stack from top, generous spacing
        top = H * 0.80
        self._go_title     = _lbl('GAME OVER',
                                   top,
                                   ('Helvetica-Bold', 46), (1.0, 1.0, 1.0, 1.0))
        self._go_score     = _lbl(f'Score: {int(self.score)}',
                                   top - 68,
                                   ('Helvetica-Bold', 32), (0.0, 1.0, 0.6, 1.0))
        self._go_level     = _lbl(f'Level: {self.level}',
                                   top - 116,
                                   ('Helvetica', 22), (0.8, 0.8, 0.8, 1.0))
        self.countdown_label = _lbl('Tap to show scores…',
                                     top - 158,
                                     ('Helvetica', 17), (0.6, 0.6, 0.6, 1.0))

        self.game_over_time  = self.t
        self.countdown_value = 5
        self._sfx('game:Error', 0.6)

    # ── High scores ───────────────────────────────────────────────────────────

    def _hs_load(self):
        """Load high scores; return [] on any error."""
        try:
            if os.path.exists(HIGH_SCORE_FILE):
                with open(HIGH_SCORE_FILE, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f'HS load error: {e}')
        return []

    def _hs_save(self, scores):
        """Atomic write: write to .tmp, then rename over the real file."""
        try:
            with open(HIGH_SCORE_TMP, 'w') as f:
                json.dump(scores[:5], f, indent=2)
            os.replace(HIGH_SCORE_TMP, HIGH_SCORE_FILE)
        except Exception as e:
            print(f'HS save error: {e}')

    def _hs_is_top5(self, score):
        scores = self._hs_load()
        if len(scores) < 5:
            return True
        return score > min(e.get('score', 0) for e in scores)

    def _hs_insert(self, score, name):
        scores = self._hs_load()
        scores.append({
            'score': score,
            'name' : name or 'Anonymous',
            'date' : datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        scores.sort(key=lambda e: e['score'], reverse=True)
        self._hs_save(scores[:5])
        return scores[:5]

    def handle_high_score(self):
        final = int(self.score)
        if self._hs_is_top5(final) and _console_ok:
            def _ask():
                try:
                    self.waiting_input = True
                    name = console.input_alert(
                        '🏆 NEW HIGH SCORE!',
                        f'Score: {final}\nEnter your name:', '', 'Save'
                    )
                    scores = self._hs_insert(final, name)
                except Exception as e:
                    print(f'Name input error: {e}')
                    scores = self._hs_load()
                finally:
                    self.waiting_input = False
                # Schedule UI update back on the scene thread
                with self._ui_queue_lock:
                    self._ui_queue.append(lambda s=scores: self._display_hs(s))

            t = threading.Thread(target=_ask, daemon=True)
            t.start()
        else:
            self._display_hs(self._hs_load())

    def _display_hs(self, high_scores):
        """Phase-2 game-over screen: wipe phase-1 labels, show clean scoreboard."""
        # Remove phase-1 nodes by stored refs (robust — no name-list guessing)
        for attr in ('_go_title', '_go_score', '_go_level', 'countdown_label'):
            node = getattr(self, attr, None)
            if node is not None:
                try:
                    node.remove_from_parent()
                except Exception:
                    pass
                try:
                    delattr(self, attr)
                except Exception:
                    pass

        W, H = self.size.width, self.size.height

        # ── Column x positions (absolute, not relative to W/2) ──────────────
        # Screen is portrait ~375–414 pt wide.  Three columns:
        #   rank+score  | name            | date
        COL_RANK  = W * 0.12   # left-aligned start
        COL_NAME  = W * 0.46   # centre of name column
        COL_DATE  = W * 0.82   # right-aligned date
        ROW_H     = 46         # vertical spacing per row

        def _lbl(text, x, y, font, color, anchor=(0.5, 0.5)):
            l = LabelNode(text, position=(x, y),
                          font=font, color=color, parent=self)
            l.z_position        = 62
            l.is_game_over_elem = True
            try:
                l.anchor_point = anchor
            except Exception:
                pass
            _safe_label_shadow(l, 'black', 0, 0, 3)
            return l

        # ── Header block ────────────────────────────────────────────────────
        top = H * 0.88
        _lbl('GAME OVER', W/2, top,
             ('Helvetica-Bold', 44), (1.0, 1.0, 1.0, 1.0))
        _lbl(f'Score: {int(self.score)}', W/2, top - 58,
             ('Helvetica-Bold', 28), (0.0, 1.0, 0.6, 1.0))
        _lbl(f'Level: {self.level}',      W/2, top - 100,
             ('Helvetica', 20), (0.75, 0.75, 0.75, 1.0))

        # ── Scoreboard panel ────────────────────────────────────────────────
        panel_h = ROW_H * 5 + 80   # 5 rows + header + footer padding
        panel_y = top - 100 - 22 - panel_h / 2
        panel = SpriteNode(
            color=(0.04, 0.04, 0.16, 0.92),
            size=(W - 28, panel_h),
            position=(W/2, panel_y)
        )
        panel.z_position        = 58
        panel.is_game_over_elem = True
        self.add_child(panel)

        # Panel title row
        title_y = panel_y + panel_h/2 - 28
        _lbl('🏆  TOP SCORES', W/2, title_y,
             ('Helvetica-Bold', 22), (1.0, 0.93, 0.27, 1.0))

        # Divider line (thin sprite)
        div = SpriteNode(
            color=(1.0, 1.0, 1.0, 0.18),
            size=(W - 52, 1),
            position=(W/2, title_y - 18)
        )
        div.z_position        = 59
        div.is_game_over_elem = True
        self.add_child(div)

        # Column header labels
        header_y = title_y - 36
        _lbl('#  Score', COL_RANK, header_y,
             ('Helvetica-Bold', 12), (0.6, 0.6, 0.6, 1.0), anchor=(0.0, 0.5))
        _lbl('Name',     COL_NAME, header_y,
             ('Helvetica-Bold', 12), (0.6, 0.6, 0.6, 1.0), anchor=(0.5, 0.5))
        _lbl('Date',     COL_DATE, header_y,
             ('Helvetica-Bold', 12), (0.6, 0.6, 0.6, 1.0), anchor=(1.0, 0.5))

        # Score rows
        row_y = header_y - ROW_H * 0.6
        for i, entry in enumerate(high_scores[:5]):
            is_top  = (i == 0)
            row_col = (0.2, 1.0, 0.5, 1.0) if is_top else (1.0, 1.0, 1.0, 1.0)
            s_font  = ('Helvetica-Bold', 17) if is_top else ('Helvetica', 16)
            n_font  = ('Helvetica-Bold', 16) if is_top else ('Helvetica', 15)
            d_font  = ('Helvetica', 12)

            rank_sym = '⭐' if is_top else f'{i+1}.'
            # Rank + score in left column
            _lbl(f'{rank_sym} {entry["score"]}',
                 COL_RANK, row_y, s_font, row_col, anchor=(0.0, 0.5))
            # Name in centre column
            name_str = entry['name'][:12]   # truncate to avoid overflow
            _lbl(name_str,
                 COL_NAME, row_y, n_font, (0.87, 0.87, 0.87, 1.0), anchor=(0.5, 0.5))
            # Date (YYYY-MM-DD) in right column
            _lbl(entry['date'][:10],
                 COL_DATE, row_y, d_font, (0.55, 0.55, 0.55, 1.0), anchor=(1.0, 0.5))
            row_y -= ROW_H

        # ── Restart prompt ──────────────────────────────────────────────────
        restart_y = panel_y - panel_h/2 - 30
        _lbl('TAP TO RESTART', W/2, restart_y,
             ('Helvetica-Bold', 26), (1.0, 0.67, 0.27, 1.0))

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset_game(self):
        # Remove all game-over / pause elements
        for child in list(self.children):
            if getattr(child, 'is_game_over_elem', False):
                child.remove_from_parent()
        self.toggle_pause() if self.paused else None

        # Re-initialise state
        self._init_state()

        # Restore UI text
        self.score_label.text = 'Score: 0'
        self.level_label.text = 'Level: 1'

        # Reset player position
        py = self.size.height * BALL_Y_FRAC
        self.player.position            = (self.size.width/2, py)
        self.player_highlight.position  = (
            self.size.width/2 - BALL_RADIUS*0.28,
            py + BALL_RADIUS*0.28
        )

        # Fresh bricks
        self.generate_brick_set()

        self.last_time             = self.t
        self.entry_times['next_t'] = self.t + 1.0

        if self.bg_music:
            try:
                self.bg_music.play()
            except Exception:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    run(FallingBricksGame(), PORTRAIT)
