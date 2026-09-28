"""Stargazing through the telescope (state "stargaze").

Owner: Showpieces (2026-09-28). Glue lives in ``systems/showpiece_system.py``.

* Night (from 7 PM) on a clear or windy night: a rich starfield -- a milky
  way band, twinkling stars, the moon over the farm's silhouette. Six
  constellations hide in it: hold the telescope's reticle over one for a
  moment and it lights up, gets its name and a little caption (discoveries
  are saved for the farm).
* Now and then a shooting star streaks across: press Action (Space / Enter /
  click) while it's in the sky to make a wish -- one per night; it brings a
  lucky tomorrow (the host grants the buff when the new day starts).
* Dusk: the first stars peek out. Day: soft blue sky, drifting clouds and
  birds, with a hint to come back at night. Rain / storm / snow clouds hide
  the stars; fog blurs them too much to make out any constellation.

Keys: arrows / WASD move the reticle (the mouse too), Action wishes, Esc
leaves. Pure UI: on a LAN client it runs locally and the discoveries /
wishes are sent to the host by the mixin.
"""
import math
import random

import pygame

from .settings import SCREEN_W, SCREEN_H, P1_KEYS, P2_KEYS
from . import ui_kit as K

NIGHT_FROM = 19 * 60            # minutes: stars from 7 PM ...
DUSK_FROM = 17 * 60 + 30        # ... the first ones peek out from 5:30 PM
FOCUS_T = 1.1                   # seconds the reticle must rest on a constellation
RET_SPEED = 380.0

# id, name, caption, stars (x, y in 0..1 of the sky), lines (index pairs)
CONSTELLATIONS = [
    ("hearts", "The Twin Hearts", "Two stars that always rise together.",
     [(0.105, 0.18), (0.126, 0.135), (0.15, 0.165), (0.174, 0.135), (0.195, 0.18),
      (0.186, 0.26), (0.15, 0.34), (0.114, 0.26), (0.143, 0.22), (0.158, 0.225)],
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 0), (8, 9)]),
    ("can", "The Watering Can", "It rains starlight on every seed you planted together.",
     [(0.32, 0.36), (0.39, 0.36), (0.40, 0.48), (0.31, 0.48), (0.395, 0.43), (0.455, 0.335),
      (0.475, 0.318), (0.284, 0.405), (0.31, 0.455)],
     [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (0, 7), (7, 8)]),
    ("cat", "The Sleepy Cat", "Curled up by the moon, waiting for you to come home.",
     [(0.548, 0.105), (0.556, 0.16), (0.576, 0.2), (0.62, 0.225), (0.662, 0.2),
      (0.645, 0.145), (0.596, 0.13), (0.578, 0.108), (0.674, 0.25), (0.64, 0.272)],
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 0), (4, 8), (8, 9)]),
    ("lantern", "The Lantern", "Hung in the sky so neither of you ever gets lost.",
     [(0.82, 0.265), (0.82, 0.305), (0.797, 0.33), (0.843, 0.33), (0.85, 0.45),
      (0.79, 0.45), (0.82, 0.39)],
     [(0, 1), (1, 2), (1, 3), (2, 5), (3, 4), (4, 5)]),
    ("boat", "The Little Boat", "Room for exactly two, drifting nowhere in particular.",
     [(0.56, 0.545), (0.70, 0.545), (0.68, 0.60), (0.58, 0.60), (0.63, 0.42),
      (0.675, 0.515), (0.63, 0.545)],
     [(0, 6), (6, 1), (1, 2), (2, 3), (3, 0), (6, 4), (4, 5), (5, 6)]),
    ("sprout", "The Sprout", "Every big love starts as something small.",
     [(0.12, 0.66), (0.118, 0.57), (0.126, 0.50), (0.07, 0.52), (0.10, 0.495),
      (0.178, 0.46), (0.15, 0.44)],
     [(0, 1), (1, 2), (1, 3), (3, 4), (4, 1), (2, 5), (5, 6), (6, 2)]),
]
IDS = [c[0] for c in CONSTELLATIONS]
BY_ID = {c[0]: c for c in CONSTELLATIONS}


def sky_mode(minutes, weather):
    """('night' | 'dusk' | 'day', can_see_stars, reason) for a time + weather."""
    m = int(minutes or 12 * 60)
    tod = "night" if m >= NIGHT_FROM else "dusk" if m >= DUSK_FROM else "day"
    w = str(weather or "sunny")
    cloudy = w in ("rain", "storm", "snow")
    see = tod == "night" and not cloudy and w != "fog"
    return tod, see, w


def _grad(w, h, top, bot, mid=None):
    s = pygame.Surface((w, h))
    for y in range(h):
        k = y / max(1, h - 1)
        if mid is not None:
            if k < 0.5:
                a, b, kk = top, mid, k * 2
            else:
                a, b, kk = mid, bot, (k - 0.5) * 2
        else:
            a, b, kk = top, bot, k
        s.fill(tuple(int(a[i] + (b[i] - a[i]) * kk) for i in range(3)), (0, y, w, 1))
    return s


_BG = {}
_GLOW = {}


def glow(r, col, amax):
    """A soft radial glow (alpha falls off smoothly to 0 at radius r), cached."""
    key = (int(r), tuple(col), int(amax))
    g = _GLOW.get(key)
    if g is None:
        n = 40
        small = pygame.Surface((n, n), pygame.SRCALPHA)
        c = (n - 1) / 2.0
        for y in range(n):
            for x in range(n):
                d = math.hypot(x - c, y - c) / (n / 2.0)
                if d < 1.0:
                    small.set_at((x, y), tuple(col) + (int(amax * (1 - d) ** 2),))
        g = pygame.transform.smoothscale(small, (int(r) * 2, int(r) * 2))
        if len(_GLOW) > 40:
            _GLOW.clear()
        _GLOW[key] = g
    return g


def band(w, h, col, amax):
    """A soft horizontal haze band (fog), cached."""
    key = ("band", int(w), int(h), tuple(col), int(amax))
    g = _GLOW.get(key)
    if g is None:
        n, m = 48, 12
        small = pygame.Surface((n, m), pygame.SRCALPHA)
        for y in range(m):
            for x in range(n):
                dx = abs(x - (n - 1) / 2) / (n / 2)
                dy = abs(y - (m - 1) / 2) / (m / 2)
                d = min(1.0, math.hypot(dx * 0.8, dy))
                small.set_at((x, y), tuple(col) + (int(amax * (1 - d) ** 1.5),))
        g = pygame.transform.smoothscale(small, (int(w), int(h)))
        _GLOW[key] = g
    return g


class Stargazer:
    """Full-screen telescope view for player ``pidx`` at the Placed ``scope``."""

    def __init__(self, game, pidx, scope, client=False):
        self.g = game
        self.pidx = pidx
        self.scope = scope
        self.client = client
        self.card = pygame.Rect(46, 40, SCREEN_W - 92, SCREEN_H - 74)
        self.sky = pygame.Rect(76, 92, SCREEN_W - 152, 500)
        self.rx, self.ry = float(self.sky.centerx), float(self.sky.y + self.sky.h * 0.38)
        self.mouse = None
        self.held = set()
        self.t = 0.0
        self.focus = {}
        self.shown = None            # (cid, seconds left) -- the caption card
        self.shooting = None         # [x, y, vx, vy, life, max_life]
        self.shoot_t = random.uniform(2.5, 4.5)
        self.flash = 0.0
        self.bolt_t = random.uniform(3.0, 6.0)
        self.msg = ""
        self.msg_t = 0.0
        self.wish_fx = 0.0
        self.closed = False
        rnd = random.Random(20260928)
        W, H = self.sky.size
        self.stars = [(rnd.uniform(0, W), rnd.uniform(0, H * 0.8), rnd.choice((1, 1, 1, 2)),
                       rnd.uniform(0.35, 1.0), rnd.uniform(0, math.tau), rnd.uniform(1.2, 3.2))
                      for _ in range(260)]
        self.clouds = [[rnd.uniform(-200, W), rnd.uniform(20, H * 0.45), rnd.uniform(0.7, 1.3),
                        rnd.uniform(10, 26)] for _ in range(6)]
        self.birds = [[rnd.uniform(-300, W), rnd.uniform(60, H * 0.5), rnd.uniform(50, 80),
                       rnd.uniform(0, math.tau)] for _ in range(4)]
        self._win_pts = [(int(W * 0.72) + 19, 82), (int(W * 0.72) + 51, 82)]
        self.drops = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.7, 1.3))
                      for _ in range(120)]

    # ------------------------------------------------------------ state
    def mode(self):
        return sky_mode(getattr(self.g.time, "minutes", 12 * 60), getattr(self.g, "weather", "sunny"))

    def found(self):
        return set(getattr(self.g, "stars_found", ()) or ())

    def star_px(self, x, y):
        return (self.sky.x + x * self.sky.w, self.sky.y + y * self.sky.h)

    def centre(self, cid):
        pts = [self.star_px(*p) for p in BY_ID[cid][3]]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return cx, cy

    def aimed(self):
        """The constellation under the reticle (or None)."""
        best = None
        for cid in IDS:
            cx, cy = self.centre(cid)
            d = math.hypot(self.rx - cx, self.ry - cy)
            if d < 58 and (best is None or d < best[0]):
                best = (d, cid)
        return best[1] if best else None

    def say(self, text, secs=3.2):
        self.msg, self.msg_t = text, secs

    def spawn_shooting_star(self):
        W, H = self.sky.size
        x = random.uniform(W * 0.1, W * 0.7)
        y = random.uniform(10, H * 0.25)
        ang = random.uniform(0.35, 0.6)
        sp = random.uniform(620, 820)
        self.shooting = [self.sky.x + x, self.sky.y + y, math.cos(ang) * sp, math.sin(ang) * sp,
                         1.05, 1.05]
        a = getattr(self.g, "audio", None)
        if a:
            a.play("ui_move")

    def wishable(self):
        s = self.shooting
        return s is not None and s[4] > -0.3

    # ------------------------------------------------------------ input
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            self.handle_key(e.key)
        elif e.type == pygame.KEYUP:
            self.held.discard(e.key)
        elif e.type == pygame.MOUSEMOTION:
            if self.sky.collidepoint(e.pos):
                self.mouse = e.pos
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            if self.sky.collidepoint(e.pos):
                self.mouse = e.pos
                self.try_wish()

    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            self.close()
            return
        if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER,
                   P1_KEYS.get("action"), P2_KEYS.get("action")):
            self.try_wish()
            return
        self.held.add(key)
        self.mouse = None

    def try_wish(self):
        if not self.wishable():
            tod, see, w = self.mode()
            if tod == "night" and see:
                self.say("Wait for a shooting star to cross the sky...")
            return False
        fn = getattr(self.g, "_stars_wish", None)
        ok, msg = fn(self) if fn else (True, "You made a wish!")
        self.say(msg, 4.0)
        if ok:
            self.wish_fx = 2.2
            self.shooting[4] = min(self.shooting[4], 0.25)
        return ok

    def close(self):
        if self.closed:
            return
        self.closed = True
        fn = getattr(self.g, "_stars_closed", None)
        if fn:
            fn(self)

    # ------------------------------------------------------------ frame
    def _dir(self):
        dx = dy = 0
        for K_ in (P1_KEYS, P2_KEYS):
            if K_.get("left") in self.held:
                dx -= 1
            if K_.get("right") in self.held:
                dx += 1
            if K_.get("up") in self.held:
                dy -= 1
            if K_.get("down") in self.held:
                dy += 1
        return max(-1, min(1, dx)), max(-1, min(1, dy))

    def update(self, dt):
        self.t += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.wish_fx = max(0.0, self.wish_fx - dt)
        self.flash = max(0.0, self.flash - dt * 3)
        dx, dy = self._dir()
        if dx or dy:
            n = math.hypot(dx, dy)
            self.rx += dx / n * RET_SPEED * dt
            self.ry += dy / n * RET_SPEED * dt
        elif self.mouse is not None:
            k = min(1.0, dt * 12)
            self.rx += (self.mouse[0] - self.rx) * k
            self.ry += (self.mouse[1] - self.ry) * k
        self.rx = max(self.sky.x + 20, min(self.sky.right - 20, self.rx))
        self.ry = max(self.sky.y + 20, min(self.sky.bottom - 60, self.ry))
        W = self.sky.w
        for c in self.clouds:
            c[0] += c[3] * dt
            if c[0] > W + 120:
                c[0] = -260
        for b in self.birds:
            b[0] += b[2] * dt
            b[3] += dt * 7
            if b[0] > W + 60:
                b[0] = -80 - random.uniform(0, 200)
        tod, see, w = self.mode()
        # shooting stars (a clear night only)
        if self.shooting is not None:
            s = self.shooting
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
            if s[4] < -0.35:
                self.shooting = None
        elif see:
            self.shoot_t -= dt
            if self.shoot_t <= 0:
                self.shoot_t = random.uniform(7.0, 14.0)
                self.spawn_shooting_star()
        if w == "storm":
            self.bolt_t -= dt
            if self.bolt_t <= 0:
                self.bolt_t = random.uniform(4.0, 8.0)
                self.flash = 1.0
        # constellations: rest the reticle on one to discover it
        aim = self.aimed() if see else None
        for cid in IDS:
            f = self.focus.get(cid, 0.0)
            f = f + dt / FOCUS_T if cid == aim else max(0.0, f - dt * 1.5)
            self.focus[cid] = min(1.0, f)
        if aim is not None:
            if aim not in self.found() and self.focus[aim] >= 1.0:
                fn = getattr(self.g, "_stars_found", None)
                if fn:
                    fn(self, aim)
                self.shown = (aim, 5.0)
            elif aim in self.found():
                left = self.shown[1] if self.shown and self.shown[0] == aim else 3.0
                self.shown = (aim, max(0.6, left))
        if self.shown is not None:
            self.shown = (self.shown[0], self.shown[1] - dt)
            if self.shown[1] <= 0:
                self.shown = None
        if w == "fog" and tod == "night" and self.msg_t <= 0 and self.aimed():
            self.say("Too foggy to make out the constellations tonight")

    # ------------------------------------------------------------ draw
    def draw(self, surf):
        K.dim(surf, 170, (14, 10, 24))
        K.modal(surf, self.card, "Stargazing")
        tod, see, w = self.mode()
        clip = surf.get_clip()
        surf.set_clip(self.sky)
        surf.blit(self._backdrop(tod, w), self.sky.topleft)
        if tod == "night":
            self._draw_night(surf, see, w)
        elif tod == "dusk":
            self._draw_dusk(surf, w)
        else:
            self._draw_day(surf, w)
        self._draw_weather(surf, tod, w)
        surf.blit(self._scenery(tod, w), (self.sky.x, self.sky.bottom - 130))
        if tod != "day":                                   # the farmhouse windows glow
            for wx, wy in getattr(self, "_win_pts", ()):
                g = glow(22, (255, 196, 110), 120)
                surf.blit(g, (self.sky.x + wx - 22, self.sky.bottom - 130 + wy - 22))
        self._draw_reticle(surf, see)
        if self.flash > 0:
            lay = pygame.Surface(self.sky.size, pygame.SRCALPHA)
            lay.fill((230, 236, 255, int(150 * self.flash)))
            surf.blit(lay, self.sky.topleft)
        surf.set_clip(clip)
        # a brass rim round the view
        pygame.draw.rect(surf, (150, 112, 52), self.sky.inflate(10, 10), 5, border_radius=12)
        pygame.draw.rect(surf, (214, 172, 92), self.sky.inflate(4, 4), 2, border_radius=10)
        self._draw_caption(surf)
        self._draw_footer(surf, tod, see, w)

    def _backdrop(self, tod, w):
        key = (tod, w, self.sky.size)
        s = _BG.get(key)
        if s is not None:
            return s
        W, H = self.sky.size
        cloudy = w in ("rain", "storm", "snow")
        if tod == "night":
            if cloudy:
                s = _grad(W, H, (30, 32, 46), (58, 60, 76))
            else:
                s = _grad(W, H, (10, 12, 40), (54, 44, 96), mid=(22, 26, 70))
                # milky way: a soft diagonal band of haze + dust
                rnd = random.Random(7)
                lay = pygame.Surface((W, H), pygame.SRCALPHA)
                for _ in range(90):
                    k = rnd.random()
                    x = W * (0.22 + 0.62 * k) + rnd.gauss(0, 34)
                    y = H * (0.86 - 0.9 * k) + rnd.gauss(0, 30)
                    r = rnd.uniform(26, 60)
                    pygame.draw.ellipse(lay, (150, 140, 220, 9), (x - r, y - r * 0.6, 2 * r, 1.2 * r))
                s.blit(lay, (0, 0))
                for _ in range(520):
                    k = rnd.random()
                    x = W * (0.22 + 0.62 * k) + rnd.gauss(0, 46)
                    y = H * (0.86 - 0.9 * k) + rnd.gauss(0, 40)
                    v = rnd.randint(120, 210)
                    if 0 <= x < W and 0 <= y < H:
                        s.set_at((int(x), int(y)), (v, v, min(255, v + 30)))
                # the moon (a soft crescent with a halo)
                mx, my = int(W * 0.93), int(H * 0.13)
                s.blit(glow(86, (250, 240, 200), 70), (mx - 86, my - 86))
                pygame.draw.circle(s, (252, 246, 214), (mx, my), 20)
                pygame.draw.circle(s, (232, 224, 190), (mx - 6, my + 5), 4)
                pygame.draw.circle(s, (238, 230, 198), (mx + 7, my - 6), 3)
                pygame.draw.circle(s, (22, 26, 70), (mx + 11, my - 5), 17)
            if w == "fog":
                veil = pygame.Surface((W, H), pygame.SRCALPHA)
                veil.fill((150, 150, 170, 120))
                s.blit(veil, (0, 0))
        elif tod == "dusk":
            s = (_grad(W, H, (120, 112, 150), (200, 170, 160)) if cloudy or w == "fog"
                 else _grad(W, H, (70, 70, 150), (252, 178, 128), mid=(170, 110, 160)))
            if not cloudy:
                sx_, sy_ = int(W * 0.18), H - 100
                s.blit(glow(150, (255, 200, 130), 150), (sx_ - 150, sy_ - 150))
                pygame.draw.circle(s, (255, 222, 150), (sx_, sy_), 26)
        else:
            if cloudy:
                s = _grad(W, H, (132, 142, 160), (190, 196, 206))
            elif w == "fog":
                s = _grad(W, H, (196, 204, 214), (226, 230, 234))
            else:
                s = _grad(W, H, (110, 178, 236), (214, 236, 250))
                sx_, sy_ = int(W * 0.84), int(H * 0.2)
                s.blit(glow(130, (255, 250, 214), 150), (sx_ - 130, sy_ - 130))
                pygame.draw.circle(s, (255, 244, 186), (sx_, sy_), 30)
        if len(_BG) > 16:
            _BG.clear()
        _BG[key] = s
        return s

    def _scenery(self, tod, w):
        """The farm's horizon: hills, the farmhouse (a lit window at night), a tree."""
        key = ("scn", tod, w, self.sky.w)
        s = _BG.get(key)
        if s is not None:
            return s
        W, H = self.sky.w, 130
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        hx, hy = int(W * 0.72), 64
        self._win_pts = [(hx + 19, hy + 18), (hx + 51, hy + 18)]
        if tod == "night":
            far, near, house, roof, trunk = ((34, 36, 72), (22, 24, 46), (48, 42, 70),
                                             (66, 46, 78), (30, 26, 46))
        elif tod == "dusk":
            far, near, house, roof, trunk = ((120, 96, 140), (86, 72, 110), (104, 80, 100),
                                             (140, 80, 96), (80, 60, 70))
        else:
            far, near, house, roof, trunk = ((150, 196, 150), (112, 172, 110), (236, 222, 196),
                                             (206, 104, 96), (132, 96, 70))
        if w == "snow":
            far, near = (226, 232, 242) if tod == "day" else (150, 156, 180), \
                (240, 244, 250) if tod == "day" else (170, 176, 196)
        pts = [(0, H)] + [(x, 52 + 16 * math.sin(x / 110.0) + 8 * math.sin(x / 37.0))
                          for x in range(0, W + 20, 20)] + [(W, H)]
        pygame.draw.polygon(s, far, pts)
        pts = [(0, H)] + [(x, 84 + 12 * math.sin(x / 90.0 + 2)) for x in range(0, W + 20, 20)] + [(W, H)]
        pygame.draw.polygon(s, near, pts)
        # farmhouse
        hx, hy = int(W * 0.72), 64
        pygame.draw.rect(s, house, (hx, hy, 70, 40))
        pygame.draw.polygon(s, roof, [(hx - 8, hy + 2), (hx + 35, hy - 26), (hx + 78, hy + 2)])
        pygame.draw.rect(s, roof, (hx + 50, hy - 24, 9, 16))                     # chimney
        win = (255, 214, 130) if tod != "day" else (150, 196, 226)
        pygame.draw.rect(s, win, (hx + 12, hy + 12, 14, 12))
        pygame.draw.rect(s, win, (hx + 44, hy + 12, 14, 12))
        pygame.draw.rect(s, trunk, (hx + 30, hy + 22, 11, 18))                    # door
        # a round tree + a fence
        tx = int(W * 0.26)
        pygame.draw.rect(s, trunk, (tx - 4, 60, 9, 40))
        leaf = near if tod != "day" else (90, 156, 92)
        for dx, dy, r in ((0, 44, 24), (-16, 56, 17), (16, 54, 18)):
            pygame.draw.circle(s, leaf, (tx + dx, dy), r)
        for x in range(int(W * 0.42), int(W * 0.66), 22):
            pygame.draw.rect(s, trunk, (x, 94, 4, 16))
        pygame.draw.line(s, trunk, (int(W * 0.42), 99), (int(W * 0.66), 99), 2)
        _BG[key] = s
        return s

    def _draw_night(self, surf, see, w):
        found = self.found()
        fog = w == "fog"
        cloudy = w in ("rain", "storm", "snow")
        if cloudy:
            return
        dimk = 0.35 if fog else 1.0
        sx, sy = self.sky.topleft
        for x, y, r, b, ph, sp in self.stars:
            tw = 0.65 + 0.35 * math.sin(self.t * sp + ph)
            v = int(255 * b * tw * dimk)
            col = (v, v, min(255, v + 20))
            if r > 1:
                pygame.draw.circle(surf, col, (int(sx + x), int(sy + y)), 1)
                if b * tw > 0.8 and not fog:
                    pygame.draw.line(surf, (v // 2, v // 2, v // 2 + 20), (sx + x - 3, sy + y), (sx + x + 3, sy + y))
                    pygame.draw.line(surf, (v // 2, v // 2, v // 2 + 20), (sx + x, sy + y - 3), (sx + x, sy + y + 3))
            else:
                surf.set_at((int(sx + x), int(sy + y)), col)
        # constellations
        lay = pygame.Surface(self.sky.size, pygame.SRCALPHA)
        for cid, name, _cap, stars, lines in CONSTELLATIONS:
            pts = [(x * self.sky.w, y * self.sky.h) for x, y in stars]
            f = self.focus.get(cid, 0.0)
            done = cid in found
            if done or f > 0:
                k = 1.0 if done else f
                lit_k = 1.0 if (self.shown and self.shown[0] == cid) else 0.75
                a = int((200 if done else 150) * k * lit_k * dimk)
                col = (255, 226, 150, a) if done else (190, 210, 255, a)
                seg = len(lines) if done else int(math.ceil(len(lines) * f))
                for i, j in lines[:seg]:
                    pygame.draw.line(lay, col, pts[i], pts[j], 2)
            for i, (x, y) in enumerate(pts):
                tw = 0.8 + 0.2 * math.sin(self.t * 2.3 + i * 1.7)
                base = (255, 236, 180) if done else (236, 240, 255)
                c = tuple(int(v * tw * dimk) for v in base)
                if done:
                    pygame.draw.circle(lay, (255, 220, 140, int(60 * dimk)), (int(x), int(y)), 6)
                pygame.draw.circle(lay, c + (255,), (int(x), int(y)), 2)
                lay.set_at((int(x), int(y)), (255, 255, 255, 255))
            if done:
                cx = sum(p[0] for p in pts) / len(pts)
                top = max(p[1] for p in pts) + 16
                t = K.outlined(K.font(13, True), name, (255, 232, 170), (26, 22, 60), 2)
                lay.blit(t, (cx - t.get_width() // 2, top))
        surf.blit(lay, self.sky.topleft)
        # a shooting star + its sparkly tail
        s = self.shooting
        if s is not None and s[4] > 0:
            k = max(0.0, min(1.0, s[4] / s[5] * 1.6))
            sp = math.hypot(s[2], s[3])
            ux, uy = s[2] / sp, s[3] / sp
            L = 150
            x0_, y0_ = s[0] - ux * L, s[1] - uy * L
            bx0, by0 = int(min(x0_, s[0])) - 6, int(min(y0_, s[1])) - 6
            lay = pygame.Surface((int(abs(ux) * L) + 14, int(abs(uy) * L) + 14), pygame.SRCALPHA)
            n = 30
            for i in range(n):
                f0, f1 = i / n, (i + 1) / n
                a = int(235 * (1 - f0) ** 1.6 * k)
                wdt = 3 if f0 < 0.2 else 2 if f0 < 0.55 else 1
                p0 = (s[0] - ux * L * f0 - bx0, s[1] - uy * L * f0 - by0)
                p1 = (s[0] - ux * L * f1 - bx0, s[1] - uy * L * f1 - by0)
                pygame.draw.line(lay, (255, 246, 214, a), p0, p1, wdt)
            surf.blit(lay, (bx0, by0))
            surf.blit(glow(12, (255, 250, 230), 200), (s[0] - 12, s[1] - 12))
            pygame.draw.circle(surf, (255, 255, 240), (int(s[0]), int(s[1])), 3)
        if self.wish_fx > 0:
            k = self.wish_fx / 2.2
            for i in range(14):
                ang = i / 14 * math.tau + self.t
                d = (1 - k) * 160 + 10
                x = self.rx + math.cos(ang) * d
                y = self.ry + math.sin(ang) * d * 0.7
                c = (255, 220, 240) if i % 2 else (255, 236, 150)
                pygame.draw.circle(surf, c, (int(x), int(y)), 2 + (i % 3 == 0))

    def _draw_dusk(self, surf, w):
        if w in ("rain", "storm", "snow"):
            return
        sx, sy = self.sky.topleft
        for x, y, r, b, ph, sp in self.stars[:70]:
            if y > self.sky.h * 0.42:
                continue
            tw = 0.5 + 0.5 * math.sin(self.t * sp + ph)
            v = int(200 * b * tw)
            pygame.draw.circle(surf, (255, 240, 220), (int(sx + x), int(sy + y)), 1) if v > 120 \
                else surf.set_at((int(sx + x), int(sy + y)), (min(255, 120 + v), 110 + v // 2, 150))

    def _cloud(self, surf, x, y, scale, col, alpha):
        g = pygame.Surface((int(220 * scale), int(90 * scale)), pygame.SRCALPHA)
        for dx, dy, r in ((60, 52, 32), (100, 40, 42), (146, 54, 30), (80, 62, 28), (124, 64, 30)):
            pygame.draw.circle(g, col + (alpha,), (int(dx * scale), int(dy * scale)), int(r * scale))
        surf.blit(g, (x, y))

    def _draw_day(self, surf, w):
        sx, sy = self.sky.topleft
        cloudy = w in ("rain", "storm", "snow")
        for x, y, sc, _v in self.clouds:
            col = (150, 156, 170) if cloudy else (255, 255, 255)
            self._cloud(surf, int(sx + x), int(sy + y), sc, col, 230 if not cloudy else 250)
        if not cloudy and w != "fog":
            for x, y, _v, ph in self.birds:
                flap = math.sin(ph) * 5
                bx, by = sx + x, sy + y + math.sin(ph * 0.3) * 6
                pygame.draw.lines(surf, (70, 70, 90), False,
                                  [(bx - 9, by - flap), (bx - 3, by + 1), (bx, by - 1),
                                   (bx + 3, by + 1), (bx + 9, by - flap)], 2)

    def _draw_weather(self, surf, tod, w):
        sx, sy = self.sky.topleft
        if w in ("rain", "storm", "snow") and tod != "day":
            dark = (54, 56, 72) if tod == "night" else (130, 124, 146)
            for x, y, sc, _v in self.clouds:
                self._cloud(surf, int(sx + x), int(sy + y * 0.6), sc * 1.4, dark, 245)
            for x, y, sc, _v in self.clouds[::2]:
                self._cloud(surf, int(sx + (x + 300) % (self.sky.w + 200) - 200), int(sy + 30 + y * 0.3),
                            sc * 1.6, tuple(min(255, c + 12) for c in dark), 235)
        if w in ("rain", "storm"):
            fall = self.t * 520
            for x, y, sp in self.drops:
                yy = (y + fall * sp) % self.sky.h
                xx = (x - fall * 0.18 * sp) % self.sky.w
                pygame.draw.line(surf, (180, 196, 224), (sx + xx, sy + yy), (sx + xx - 3, sy + yy + 11), 1)
        elif w == "snow":
            fall = self.t * 50
            for x, y, sp in self.drops:
                yy = (y + fall * sp) % self.sky.h
                xx = (x + math.sin(self.t + y) * 12) % self.sky.w
                pygame.draw.circle(surf, (250, 252, 255), (int(sx + xx), int(sy + yy)), 2)
        elif w == "fog":
            for i in range(5):
                bw = self.sky.w + 500
                y = int(self.sky.h * (0.12 + i * 0.17) + math.sin(self.t * 0.4 + i) * 8)
                x = -250 + ((self.t * 10 * (i + 1) + i * 97) % 240) - 120
                surf.blit(band(bw, 150, (222, 226, 234), 110), (sx + x, sy + y - 75))
        elif w == "windy" and tod == "night":
            for x, y, sc, _v in self.clouds[:3]:
                self._cloud(surf, int(sx + (x * 2.2) % (self.sky.w + 300) - 200), int(sy + y), sc * 0.8,
                            (70, 70, 110), 90)

    def _draw_reticle(self, surf, see):
        x, y = int(self.rx), int(self.ry)
        aim = self.aimed() if see else None
        f = self.focus.get(aim, 0.0) if aim else 0.0
        found = aim in self.found() if aim else False
        ring = (240, 214, 140) if (found or f > 0) else (214, 186, 120)
        lay = pygame.Surface((140, 140), pygame.SRCALPHA)
        pygame.draw.circle(lay, ring + (40,), (70, 70), 48)
        pygame.draw.circle(lay, (255, 255, 255, 0), (70, 70), 44)
        surf.blit(lay, (x - 70, y - 70))
        pygame.draw.circle(surf, (120, 86, 40), (x, y), 47, 3)
        pygame.draw.circle(surf, ring, (x, y), 45, 2)
        for a in range(4):
            ang = a * math.pi / 2
            p0 = (x + math.cos(ang) * 30, y + math.sin(ang) * 30)
            p1 = (x + math.cos(ang) * 42, y + math.sin(ang) * 42)
            pygame.draw.line(surf, ring, p0, p1, 2)
        pygame.draw.circle(surf, ring, (x, y), 2)
        if f > 0 and not found:
            rect = pygame.Rect(x - 53, y - 53, 106, 106)
            pygame.draw.arc(surf, (255, 236, 160), rect, math.pi / 2 - f * math.tau, math.pi / 2, 4)

    def _draw_caption(self, surf):
        if self.shown is None:
            return
        cid = self.shown[0]
        _i, name, cap, _s, _l = BY_ID[cid]
        f1, f2 = K.font(20, True), K.font(14, True)
        w = max(f1.size(name)[0], f2.size(cap)[0]) + 56
        r = pygame.Rect(0, 0, w, 70)
        r.midbottom = (self.sky.centerx, self.sky.bottom - 18)
        K.draw_card(surf, r, radius=14)
        K.blit_text(surf, f1, name, K.INK, (r.centerx, r.y + 24))
        K.blit_text(surf, f2, cap, K.INK_SOFT, (r.centerx, r.y + 48))
        for dx in (-w // 2 + 22, w // 2 - 22):
            _star(surf, (r.centerx + dx, r.y + 24), 7, K.GOLD_RIM)

    def _draw_footer(self, surf, tod, see, w):
        y = self.card.bottom - 30
        found = self.found()
        # left: constellations found as little stars
        x0 = self.card.x + 40
        K.blit_text(surf, K.font(14, True), "Constellations", K.INK_SOFT, (x0, y), align="left")
        for i, cid in enumerate(IDS):
            c = (x0 + 136 + i * 22, y)
            _star(surf, c, 8, K.GOLD_RIM if cid in found else K.WELL_LINE)
        K.blit_text(surf, K.font(14, True), f"{len(found & set(IDS))}/{len(IDS)}", K.INK,
                    (x0 + 136 + len(IDS) * 22, y), align="left")
        # centre: the situation / a message
        if self.msg_t > 0:
            txt, col = self.msg, K.SPROUT
        elif tod == "day":
            txt, col = ("Grey skies today - the stars come out after 7 PM" if w in ("rain", "storm", "snow")
                        else "The stars are asleep. Come back after 7 PM!"), K.INK_SOFT
        elif tod == "dusk":
            txt, col = "The first stars are peeking out... come back after 7 PM", K.INK_SOFT
        elif w in ("rain", "storm", "snow"):
            txt, col = "Clouds hide the stars tonight. Try again on a clear night", K.INK_SOFT
        elif w == "fog":
            txt, col = "Too foggy to make out the constellations", K.INK_SOFT
        elif self.wishable():
            txt, col = "A shooting star! Press SPACE to make a wish!", K.WARN
        elif getattr(self.g, "_stars_wished_tonight", lambda: False)():
            txt, col = "You made a wish tonight. Sweet dreams!", K.SPROUT
        else:
            txt, col = "Rest the reticle on a pattern to find its name", K.INK_SOFT
        f = K.font(13, True)
        x = self.card.right - 40
        for k, lab in (("Esc", "Leave"), ("Space", "Wish"), ("Arrows", "Look")):
            w_ = f.size(k)[0] + f.size(lab)[0] + 44
            K.key_pill(surf, k, lab, (x - w_ // 2, y), fnt=f)
            x -= w_ + 8
        left = x0 + 136 + len(IDS) * 22 + 44
        gap = x - 10 - left
        ft = K.fit_font(txt, gap, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, ft, K.ellipsize(ft, txt, gap), col, (left + gap // 2, y))


def _star(surf, c, r, col):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((c[0] + math.cos(ang) * rr, c[1] + math.sin(ang) * rr))
    pygame.draw.polygon(surf, col, pts)
