"""Mist City random run events — one per run, announced with a banner.

Owner: Chat 7 (Mist City).

  outage   POWER OUTAGE  — the street goes dark; only the duo's flashlight cones
                           (and zombie eye-glints) cut through for a while.
  acid     ACID RAIN     — green rain; every few seconds anyone NOT under an
                           awning / roof / catwalk takes a small sting.
  siren    SIREN HORDE   — an air-raid siren wails, then a big wave shambles in
                           from both edges of the screen.
  supply   SUPPLY DROP   — a parachute crate floats down ahead of the duo with
                           good salvage and a spare first-aid kit.

Each event is a tiny object with ``start/update/draw_world/draw_overlay`` that
MistRun drives. All full-screen surfaces are cached (no per-frame allocation).
"""
import math
import pygame
from ..settings import SCREEN_W, SCREEN_H
from .world2d import Crate, GROUND_Y, NEON_MINT, NEON_PINK, NEON_AMBER

KINDS = ("outage", "acid", "siren", "supply")
TITLES = {"outage": "POWER OUTAGE!", "acid": "ACID RAIN!", "siren": "SIREN - A HORDE IS COMING!",
          "supply": "SUPPLY DROP INBOUND!"}
HINTS = {"outage": "Stick together - your flashlights are all you have",
         "acid": "Shelter under awnings, roofs and catwalks",
         "siren": "Get to high ground or fight back to back",
         "supply": "Break the crate for premium salvage"}
LABELS = {"outage": "Power Outage", "acid": "Acid Rain", "siren": "Siren Horde",
          "supply": "Supply Drop"}

SUPPLY_DROPS = [
    ("old_battery", 0.85, (1, 2)),
    ("gear_scrap", 0.80, (1, 3)),
    ("mutant_herb", 0.60, (1, 2)),
    ("wire", 0.60, (2, 3)),
    ("tainted_crystal", 0.30, (1, 1)),
]

_CACHE = {}


def _cone(facing):
    """Flashlight mask: white RGB, alpha = how much darkness is KEPT (BLEND_RGBA_MIN)."""
    key = ("cone", facing)
    if key in _CACHE:
        return _CACHE[key]
    w, h = 460, 300
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((255, 255, 255, 255))
    ox, oy = (70 if facing > 0 else w - 70), h // 2
    for k, a in ((1.00, 205), (0.86, 160), (0.72, 110), (0.58, 70), (0.44, 40)):
        L = int((w - 90) * k)
        hw = int(h * 0.46 * k)
        tip = ox + facing * L
        pygame.draw.polygon(s, (255, 255, 255, a), [(ox, oy - 10), (tip, oy - hw), (tip, oy + hw), (ox, oy + 10)])
        pygame.draw.circle(s, (255, 255, 255, a), (ox, oy), int(66 * k))
    _CACHE[key] = s
    return s


def _halo():
    if "halo" not in _CACHE:
        s = pygame.Surface((140, 140), pygame.SRCALPHA)
        s.fill((255, 255, 255, 255))
        for r, a in ((70, 190), (52, 140), (34, 90)):
            pygame.draw.circle(s, (255, 255, 255, a), (70, 70), r)
        _CACHE["halo"] = s
    return _CACHE["halo"]


def _vignette():
    if "vig" not in _CACHE:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for i in range(12):
            a = int(150 * (1 - i / 12.0) ** 2)
            pygame.draw.rect(s, (230, 60, 80, a), (i * 6, i * 6, SCREEN_W - i * 12, SCREEN_H - i * 12), 6)
        _CACHE["vig"] = s
    return _CACHE["vig"]


def _full(key, rgba):
    if key not in _CACHE:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill(rgba)
        _CACHE[key] = s
    return _CACHE[key]


class RunEvent:
    kind = "?"
    duration = 40.0

    def __init__(self, run):
        self.run = run
        self.t = 0.0
        self.done = False

    @property
    def title(self):
        return TITLES[self.kind]

    @property
    def label(self):
        return LABELS[self.kind]

    def remaining(self):
        return max(0.0, self.duration - self.t)

    def start(self):
        r = self.run
        r.banner = [self.title, 3.0]
        r.hint(HINTS[self.kind], 4.0)
        r._snd("thunder" if self.kind in ("outage", "acid") else "bell")
        if self.kind == "siren":
            r._snd("siren")            # plays if Core ever adds it (unknown names are no-ops)

    def update(self, dt):
        self.t += dt
        if self.t >= self.duration:
            self.done = True

    def stop(self):
        self.done = True

    def draw_world(self, surf, camx, t):
        pass

    def draw_overlay(self, surf, camx, t):
        pass


class Outage(RunEvent):
    kind = "outage"
    duration = 40.0

    def __init__(self, run):
        super().__init__(run)
        self.dark = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.flick = 0.0

    def update(self, dt):
        super().update(dt)
        self.flick = max(0.0, self.flick - dt)
        if self.run.rng.random() < dt * 0.25:        # the odd flicker of power
            self.flick = 0.12

    def draw_overlay(self, surf, camx, t):
        # fade in over 1 s and out over the last 1.5 s
        k = min(1.0, self.t / 1.0, max(0.0, self.remaining()) / 1.5)
        if self.flick > 0:
            k *= 0.35
        a = int(226 * k)
        if a <= 4:
            return
        d = self.dark
        d.fill((8, 10, 18, a))
        for q in self.run.p2:
            sx, sy = int(q.x - camx), int(q.y - 28)
            if q.ghost:
                h = _halo()
                d.blit(h, (sx - 70, sy - 70), special_flags=pygame.BLEND_RGBA_MIN)
                continue
            c = _cone(q.facing)
            ox = 70 if q.facing > 0 else c.get_width() - 70
            d.blit(c, (sx - ox, sy - c.get_height() // 2), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(d, (0, 0))
        # zombie eyes glint through the dark
        for z in self.run.zombies:
            if z.hp <= 0:
                continue
            for ex, ey in z.eye_points():
                x = int(ex - camx)
                if -10 < x < SCREEN_W + 10:
                    pygame.draw.circle(surf, (120, 250, 180), (x, int(ey)), 2)
        # flashlight lenses
        for q in self.run.p2:
            if not q.ghost:
                pygame.draw.circle(surf, (255, 250, 220), (int(q.x - camx + q.facing * 10), int(q.y - 28)), 3)


class AcidRain(RunEvent):
    kind = "acid"
    duration = 42.0
    TICK = 2.2
    DMG = 5

    def __init__(self, run):
        super().__init__(run)
        rng = run.rng
        self.drops = [[rng.uniform(0, SCREEN_W), rng.uniform(0, SCREEN_H), rng.uniform(520, 760),
                       rng.randint(10, 18)] for _ in range(110)]
        self.tick = self.TICK

    def update(self, dt):
        super().update(dt)
        r = self.run
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] -= d[2] * 0.18 * dt
            if d[1] > GROUND_Y + 30:
                d[1] -= GROUND_Y + 60
                d[0] = r.rng.uniform(0, SCREEN_W + 80)
        self.tick -= dt
        if self.tick <= 0:
            self.tick = self.TICK
            for q in r.p2:
                if q.ghost or r.world.is_covered(q.x, q.y):
                    continue
                if r._hurt_player(q, self.DMG, "acid rain", knock=False):
                    r._pop(q.x, q.y - 58, "sizzle!", (170, 240, 120))
                    r._burst(q.x, q.y - 40, (170, 240, 120), n=5)

    def draw_overlay(self, surf, camx, t):
        k = min(1.0, self.t / 1.5, self.remaining() / 1.5)
        if k <= 0:
            return
        tint = _full("acid_tint", (120, 220, 90, 34))
        tint.set_alpha(int(255 * k))
        surf.blit(tint, (0, 0))
        col = (178, 246, 130)
        for x, y, v, ln in self.drops:
            if k < 1 and (int(x) % 10) / 10.0 > k:
                continue
            pygame.draw.line(surf, col, (int(x), int(y)), (int(x - ln * 0.18), int(y + ln)), 1)
        # umbrella hint above sheltered players
        for q in self.run.p2:
            if not q.ghost and self.run.world.is_covered(q.x, q.y):
                pygame.draw.arc(surf, NEON_MINT, (int(q.x - camx) - 12, int(q.y) - 62, 24, 16), 0, math.pi, 2)


class SirenHorde(RunEvent):
    kind = "siren"
    duration = 14.0
    WAVE_AT = 2.5
    COUNT = 8

    def __init__(self, run):
        super().__init__(run)
        self.spawned = False

    def update(self, dt):
        super().update(dt)
        if not self.spawned and self.t >= self.WAVE_AT:
            self.spawned = True
            self.run._horde(self.COUNT)

    def draw_overlay(self, surf, camx, t):
        if self.t > 9.0:
            return
        v = _vignette()
        v.set_alpha(int(255 * (0.45 + 0.55 * abs(math.sin(t * 5.0)))))
        surf.blit(v, (0, 0))


class SupplyDrop(RunEvent):
    kind = "supply"
    duration = 30.0

    def __init__(self, run):
        super().__init__(run)
        self.crate = None
        self.fall_y = -80.0
        self.landed = False

    def start(self):
        super().start()
        r = self.run
        lw = r.world.level_w
        lead = max(q.x for q in r.p2)
        x = lead + r.rng.uniform(170, 330)
        x = max(r.camx + 140, min(r.camx + SCREEN_W - 140, x))     # lands on-screen
        if getattr(r.world, "exit_x", None) and abs(x - r.world.exit_x) < 120:
            x = r.world.exit_x - 170
        x = max(200.0, min(lw - 200.0, x))
        self.crate = Crate(x, -80, rare=True)
        self.crate.supply = True
        self.crate.max_hp = self.crate.hp = 3
        self.crate.drops = SUPPLY_DROPS
        r.world.crates.append(self.crate)

    def update(self, dt):
        super().update(dt)
        c = self.crate
        if c is None or self.landed:
            return
        c.y = min(float(GROUND_Y), c.y + 150 * dt)
        c.x += math.sin(self.t * 1.7) * 14 * dt
        if c.y >= GROUND_Y:
            self.landed = True
            r = self.run
            r.shake = max(r.shake, 4.0)
            r._burst(c.x, GROUND_Y - 6, (220, 210, 190), n=16)
            r._snd("hit")
            r.medkits.append([c.x + 44, float(GROUND_Y), True])
            r._pop(c.x, GROUND_Y - 70, "SUPPLIES!", NEON_AMBER)

    def draw_world(self, surf, camx, t):
        c = self.crate
        if c is None or c.hp <= 0:
            return
        sx = int(c.x - camx)
        if not self.landed:
            top = int(c.y) - 120
            pygame.draw.ellipse(surf, NEON_PINK, (sx - 46, top, 92, 44))
            pygame.draw.ellipse(surf, (250, 214, 232), (sx - 46, top, 92, 44), 2)
            for k in (-40, -14, 14, 40):
                pygame.draw.line(surf, (230, 230, 236), (sx + k, top + 30), (sx, int(c.y) - 34), 1)
        # pink smoke flare marks the spot
        for k in range(4):
            a = ((t * 0.8 + k * 0.25) % 1.0)
            pygame.draw.circle(surf, (236, 170, 206), (sx + 26 + int(a * 12), int(c.y) - 20 - int(a * 70)),
                               4 + int(a * 8), 2)


EVENT_CLASSES = {"outage": Outage, "acid": AcidRain, "siren": SirenHorde, "supply": SupplyDrop}


def make(kind, run):
    return EVENT_CLASSES[kind](run)
