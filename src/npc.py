"""Town NPCs with dialogue, gifting and friendship hearts.

Villager personalities, gift tastes, birthdays, schedules and heart events live
in ``story_data.py`` (pure data); the Story mixin (systems/story_system.py)
spawns scheduled villagers, runs heart events and attaches ``npc.game`` so
dialogue / gifts can read the clock, weather and birthdays.
"""
import math
import random
import pygame
from .settings import TILE
from . import assets
from . import story_data as SD

_DIR = {(0, 1): "down", (0, -1): "up", (-1, 0): "left", (1, 0): "right"}

MAX_FRIEND = 500            # 10 hearts x 50 points (was 250 / 5 hearts)
HEART_PTS = 50

NPC_DATA = {
    "Mira":  {"color": (220, 120, 150), "loves": "blueberry",
              "lines": SD.LINES["Mira"]["any"]},
    "Tomas": {"color": (110, 150, 220), "loves": "potato",
              "lines": SD.LINES["Tomas"]["any"]},
    "Elya":  {"color": (150, 200, 130), "loves": "cauliflower",
              "lines": SD.LINES["Elya"]["any"]},
    "Luang Por": {"color": (228, 150, 60), "loves": "lotus",
                  "lines": SD.LINES["Luang Por"]["any"]},
    # ---- 2026-09 villagers (Story domain) ----
    "Fah":     {"color": SD.VILLAGERS["Fah"]["color"], "loves": "melon",
                "lines": SD.LINES["Fah"]["any"]},
    "Somchai": {"color": SD.VILLAGERS["Somchai"]["color"], "loves": "tuna",
                "lines": SD.LINES["Somchai"]["any"]},
    "Kai":     {"color": SD.VILLAGERS["Kai"]["color"], "loves": "gold_ore",
                "lines": SD.LINES["Kai"]["any"]},
    "Luna":    {"color": SD.VILLAGERS["Luna"]["color"], "loves": "crocus",
                "lines": SD.LINES["Luna"]["any"]},
}

LOOKS = {"Mira": ("ponytail", 7, 1), "Tomas": ("short", 0, 3), "Elya": ("bun", 2, 2),
         "Luang Por": ("bald", 0, 3)}    # shaved head, as a monk should be
for _n in SD.NEW_VILLAGERS:
    LOOKS[_n] = SD.VILLAGERS[_n]["looks"]

GIFT_POINTS = {"love": 60, "like": 35, "neutral": 15, "dislike": -20}


def npc_skin(name):
    return assets.SKIN_TONES[LOOKS.get(name, ("short", 0, 2))[2] % len(assets.SKIN_TONES)]


def npc_frames(name, arms=True):
    """Walk frames; arms="umbrella" = one hand up, gripping an umbrella."""
    style, hair_i, skin_i = LOOKS.get(name, ("short", 0, 2))
    return assets.player_frames(npc_skin(name), style,
                                assets.HAIR_COLORS[hair_i % len(assets.HAIR_COLORS)],
                                NPC_DATA.get(name, {}).get("color", (160, 160, 170)),
                                arms)


class NPC:
    def __init__(self, name, gx, gy, friend=None):
        self.name = name
        self.data = NPC_DATA[name]
        self.x = gx * TILE + TILE / 2
        self.y = gy * TILE + TILE / 2
        self.home = (self.x, self.y)
        self._friend = friend if friend is not None else {}
        self._friend.setdefault(name, 0)
        self.frames = npc_frames(name)
        self.dirname = "down"
        self.anim_t = 0.0
        self.idle_t = 0.0
        self.moving = False
        self._t = random.random() * 3
        self.vx, self.vy = 0, 0
        self.game = None          # attached by StoryMixin (clock / weather / birthdays)
        self.target = None        # (wx, wy) schedule walk target
        self.leaving = False      # walking off to another area -> removed on arrival
        self.gone = False
        self._stuck = 0.0
        self._last_line = None
        self.event_ready = False  # a heart event is waiting (drawn as a bubble)
        self.react = None         # [taste, seconds] gift-reaction emote bubble

    @property
    def hearts(self):
        return self._friend.get(self.name, 0)

    @hearts.setter
    def hearts(self, v):
        self._friend[self.name] = max(0, min(MAX_FRIEND, int(v)))

    def rect(self):
        return pygame.Rect(self.x - 14, self.y - 10, 28, 22)

    # ---------------- movement ----------------
    def walk_to(self, wx, wy, leaving=False):
        self.target = (wx, wy)
        self.leaving = leaving
        self._stuck = 0.0

    def _walk_target(self, dt, area):
        tx, ty = self.target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 4:
            self.x, self.y = tx, ty
            self.target = None
            self.home = (tx, ty)
            self.moving = False
            if self.leaving:
                self.gone = True
            return
        sp = 72.0
        ux, uy = dx / dist, dy / dist
        moved = False
        nx = self.x + ux * sp * dt
        if not area.is_solid(int(nx // TILE), int(self.y // TILE)):
            self.x = nx
            moved = moved or abs(ux) > 0.1
        ny = self.y + uy * sp * dt
        if not area.is_solid(int(self.x // TILE), int(ny // TILE)):
            self.y = ny
            moved = moved or abs(uy) > 0.1
        if not moved:
            self._stuck += dt
            if self._stuck > 1.6:             # blocked by a building: just arrive
                self.x, self.y = tx, ty
        self.moving = True
        if abs(dx) > abs(dy):
            self.dirname = "right" if dx > 0 else "left"
        else:
            self.dirname = "down" if dy > 0 else "up"
        self.anim_t += dt * 7

    def face(self, x, y):
        """Turn toward a point and hold still for a moment (being talked to)."""
        dx, dy = x - self.x, y - self.y
        if abs(dx) > abs(dy):
            self.dirname = "right" if dx > 0 else "left"
        else:
            self.dirname = "down" if dy > 0 else "up"
        if self.target is None:
            self.vx = self.vy = 0
            self.moving = False
            self._t = 3.0

    def update(self, dt, area):
        self.idle_t += dt
        if self.react is not None:
            self.react[1] -= dt
            if self.react[1] <= 0:
                self.react = None
        if self.target is not None:
            self._walk_target(dt, area)
            return
        # gentle idle wander around home
        self._t -= dt
        if self._t <= 0:
            self._t = random.uniform(1.5, 4)
            if random.random() < 0.4:
                self.vx, self.vy = 0, 0           # pause
            else:
                ang = random.uniform(0, 6.28)
                self.vx, self.vy = pygame.math.Vector2(1, 0).rotate_rad(ang) * 24
        self.moving = bool(self.vx or self.vy)
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        if abs(nx - self.home[0]) < 90 and abs(ny - self.home[1]) < 90 \
                and not area.is_solid(int(nx // TILE), int(ny // TILE)):
            self.x, self.y = nx, ny
        else:
            self.vx, self.vy = -self.vx, -self.vy
        if self.moving:
            if abs(self.vx) > abs(self.vy):
                self.dirname = "right" if self.vx > 0 else "left"
            else:
                self.dirname = "down" if self.vy > 0 else "up"
            self.anim_t += dt * 6

    # ---------------- talk / gifts ----------------
    def _ctx(self):
        g = self.game
        if g is None:
            return None
        try:
            return (g.time.season, str(getattr(g, "weather", "sunny")), g.time.minutes,
                    g.world.current)
        except Exception:
            return None

    def _fmt(self, line):
        g = self.game
        p = q = "friend"
        if g is not None and getattr(g, "players", None):
            i = getattr(g, "_story_talker", 0) or 0
            try:
                p = g.players[i].name
                q = g.players[1 - i].name
            except Exception:
                pass
        return line.replace("{p}", p).replace("{q}", q)

    def pick_line(self):
        """A line that fits the season / weather / hour / friendship / place."""
        L = SD.LINES.get(self.name, {})
        ctx = self._ctx()
        g = self.game
        if getattr(self, "couple_line", False):
            self.couple_line = False
            cl = SD.COUPLE_LINES.get(self.name)
            if cl:
                return random.choice(cl)
        if g is not None and hasattr(g, "_story_is_birthday") and g._story_is_birthday(self.name):
            bl = L.get("birthday")
            if bl:
                return random.choice(bl)
        if ctx:
            done = sorted(getattr(g, "story_bundles_done", ()) or ())
            cands, general = SD.context_lines(self.name, ctx[0], ctx[1], ctx[2],
                                              self.heart_count, ctx[3], done=done,
                                              restored=bool(getattr(g, "story_restored", False)))
        else:
            cands, general = [], list(self.data.get("lines", []))
        general = general or list(self.data.get("lines", [])) or ["Hello!"]
        pool = cands if (cands and random.random() < 0.6) else general
        opts = [ln for ln in pool if ln != self._last_line] or pool
        line = random.choice(opts)
        self._last_line = line
        return line

    def talk(self, first_today=None):
        """+5 friendship for the first chat of the day (per villager), so
        mashing the action key can't farm hearts."""
        g = self.game
        if first_today is None:
            seen = getattr(g, "story_talked_today", None) if g is not None else None
            if isinstance(seen, set):
                first_today = self.name not in seen
                seen.add(self.name)
            else:
                first_today = True
        if first_today:
            self.hearts = self.hearts + 5
        return f"{SD.display(self.name)}: " + self._fmt(self.pick_line())

    def gift_taste(self, item_id):
        return SD.taste(self.name, item_id)

    def give_gift(self, item_id):
        taste = self.gift_taste(item_id)
        g = self.game
        bday = bool(g is not None and hasattr(g, "_story_is_birthday")
                    and g._story_is_birthday(self.name))
        pts = GIFT_POINTS[taste]
        if bday:
            pts = pts * 4 if pts > 0 else pts      # birthday gifts count x4
        self.hearts = self.hearts + pts
        lines = SD.LINES.get(self.name, {}).get(taste) or ["Thanks for the gift!"]
        msg = f"{SD.display(self.name)}: " + self._fmt(random.choice(lines))
        tag = {"love": " (loves it! +heart)", "like": " (likes it)",
               "neutral": "", "dislike": " (dislikes it...)"}[taste]
        if g is not None and hasattr(g, "_story_after_gift"):
            try:
                extra = g._story_after_gift(self, item_id, taste, bday)
                if extra:
                    tag += extra
            except Exception:
                pass
        return msg + tag

    @property
    def heart_count(self):
        return self.hearts // HEART_PTS

    # set each frame by the Story system on rainy days (canopy colour or None)
    umbrella = None

    def draw(self, surf, cam):
        surf.blit(assets.shadow(), (self.x - cam.x - 13, self.y - cam.y + 4))
        frame_i = int(self.anim_t) % 4 if self.moving else 0
        bob = 0 if self.moving else int(math.sin(self.idle_t * 3) * 1.5)
        pos = (self.x - TILE / 2 - cam.x, self.y - TILE / 2 - 12 - cam.y + bob)
        if self.umbrella is None:
            surf.blit(self.frames[self.dirname][frame_i], pos)
        else:
            self._draw_with_umbrella(surf, pos, frame_i)
        hx = int(self.x - cam.x)
        hy = int(self.y - cam.y - 30 + math.sin(self.idle_t * 2) * 2)
        if self.react is not None:
            self._draw_react(surf, hx, hy - 10)
        elif self.event_ready:
            # a pulsing heart speech bubble: something special wants to happen
            pr = 1.0 + 0.12 * math.sin(self.idle_t * 5)
            r = int(9 * pr)
            by = hy - 8
            pygame.draw.circle(surf, (255, 250, 252), (hx, by), r + 2)
            pygame.draw.polygon(surf, (255, 250, 252), [(hx - 3, by + r), (hx + 3, by + r),
                                                        (hx, by + r + 5)])
            pygame.draw.circle(surf, (236, 96, 128), (hx - 3, by - 1), 3)
            pygame.draw.circle(surf, (236, 96, 128), (hx + 3, by - 1), 3)
            pygame.draw.polygon(surf, (236, 96, 128), [(hx - 6, by), (hx + 6, by), (hx, by + 6)])
        elif self.heart_count > 0:
            # floating heart indicator above NPC
            pygame.draw.circle(surf, (230, 90, 110), (hx - 3, hy), 3)
            pygame.draw.circle(surf, (230, 90, 110), (hx + 3, hy), 3)
            pygame.draw.polygon(surf, (230, 90, 110), [(hx - 6, hy + 1), (hx + 6, hy + 1), (hx, hy + 8)])

    def _draw_with_umbrella(self, surf, pos, frame_i):
        """Walk frame with one hand up on the shaft; the canopy rides over the
        head, leaning a touch toward the gripping hand. Seen from behind the
        shaft is in FRONT of the villager, so it all goes under the body."""
        from . import story_art
        from .assets import chars
        d = self.dirname
        fr = npc_frames(self.name, "umbrella")[d][frame_i]
        step = -1 if frame_i in (1, 3) else 0
        hx, hy = chars.UMBRELLA_HAND[d]
        hand = (int(pos[0] + hx), int(pos[1] + hy + step))
        lean = {"down": 8, "up": 4, "left": -11, "right": 11}[d]
        sway = int(round(math.sin(self.idle_t * 2.2 + self.x * 0.01)))
        can = story_art.umbrella_canopy(self.umbrella)
        top = (int(pos[0] + TILE / 2 + lean + sway), int(pos[1] + 1 + step))

        def umbrella():
            pygame.draw.line(surf, (96, 74, 62), (top[0], top[1] - 12), hand, 2)
            surf.blit(can, (top[0] - can.get_width() // 2, top[1] - 20))
        if d == "up":
            umbrella()
            surf.blit(fr, pos)
            return
        surf.blit(fr, pos)
        umbrella()
        pygame.draw.circle(surf, npc_skin(self.name), hand, 3)     # fingers over the shaft

    def _draw_react(self, surf, hx, hy):
        """Gift reaction emote: love = big heart, like = music note,
        neutral = '...', dislike = grumpy scribble cloud."""
        kind, t = self.react
        pop = min(1.0, (2.2 - t) * 6) if t > 2.0 else 1.0
        r = int(11 * pop)
        if r <= 1:
            return
        by = hy - 4 - int((1.0 - min(1.0, t)) * 6)
        pygame.draw.circle(surf, (255, 252, 250), (hx, by), r + 2)
        pygame.draw.polygon(surf, (255, 252, 250), [(hx - 4, by + r), (hx + 4, by + r),
                                                    (hx, by + r + 6)])
        pygame.draw.circle(surf, (120, 100, 130), (hx, by), r + 2, 1)
        if kind == "love":
            c = (236, 84, 120)
            pygame.draw.circle(surf, c, (hx - 4, by - 2), 4)
            pygame.draw.circle(surf, c, (hx + 4, by - 2), 4)
            pygame.draw.polygon(surf, c, [(hx - 8, by - 1), (hx + 8, by - 1), (hx, by + 8)])
            pygame.draw.circle(surf, (255, 200, 214), (hx - 5, by - 3), 1)
        elif kind == "like":
            c = (90, 150, 220)
            pygame.draw.circle(surf, c, (hx - 3, by + 4), 3)
            pygame.draw.line(surf, c, (hx - 1, by + 4), (hx - 1, by - 6), 2)
            pygame.draw.line(surf, c, (hx - 1, by - 6), (hx + 5, by - 3), 2)
        elif kind == "dislike":
            c = (120, 110, 130)
            for i in range(3):
                pygame.draw.arc(surf, c, (hx - 8 + i * 3, by - 6 + i * 2, 12, 9), 0, 5.5, 1)
        else:
            for i in (-5, 0, 5):
                pygame.draw.circle(surf, (120, 110, 130), (hx + i, by + 1), 2)
