"""Weather logic extras + storm/fog/wind visuals.

Owner: Core (Chat 0). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

* Tomorrow's weather is PRE-ROLLED (``self.weather_tomorrow``, saved) so the TV
  and the day report can forecast it; ``Game.on_new_day`` calls
  ``_roll_weather()`` which promotes it to today and rolls the next one.
* Visuals (outdoor areas only): storm = heavy slanted rain + lightning flashes +
  thunder; fog = soft drifting bands that clear by noon; windy = petals/leaves
  blowing across the screen; rain/storm also get little ground splashes.
  Plain rain/snow streaks stay in render_system._draw_weather (UI domain).
* ``weather_icon(kind, size)`` -- cached forecast icon, shared with the day report.
"""
import math
import random

import pygame

from ..settings import SCREEN_W, SCREEN_H, SEASONS, DAYS_PER_SEASON
from .. import weather, lighting

OUTDOOR = ("farm", "town", "forest", "beach", "meadow")
_SOFT_AREAS = ("farm", "home", "coop")      # share the farm theme (audio.tracks)
_MORNING_LINE = {
    "rain": "Rainy day - the crops are watered for you.",
    "storm": "A storm rolls in! Crops are watered - stay cosy out there.",
    "fog": "A foggy morning... it should lift by noon.",
    "windy": "Windy day - petals and leaves ride the breeze.",
}

_CACHE = {}

_WIND_COLS = {
    "Spring": [(255, 196, 214), (255, 226, 236), (250, 170, 196), (255, 250, 250)],
    "Summer": [(150, 206, 120), (178, 222, 140), (120, 186, 110)],
    "Fall": [(236, 146, 76), (220, 110, 70), (246, 196, 96), (186, 120, 80)],
    "Winter": [(236, 242, 250), (255, 255, 255)],
}


# ------------------------------------------------------------------ icons
def weather_icon(kind, size=48):
    """A cute forecast icon for ``kind`` (cached per size)."""
    key = ("icon", kind, size)
    s = _CACHE.get(key)
    if s is not None:
        return s
    b = pygame.Surface((48, 48), pygame.SRCALPHA)

    def cloud(col, y=18, dark=None):
        edge = dark or tuple(max(0, c - 50) for c in col)
        for (cx, cy, r) in ((16, y + 6, 9), (26, y + 1, 11), (35, y + 7, 8)):
            pygame.draw.circle(b, edge, (cx, cy), r + 1)
        pygame.draw.rect(b, edge, (8, y + 5, 34, 11), border_radius=5)
        for (cx, cy, r) in ((16, y + 6, 9), (26, y + 1, 11), (35, y + 7, 8)):
            pygame.draw.circle(b, col, (cx, cy), r)
        pygame.draw.rect(b, col, (9, y + 6, 32, 9), border_radius=5)
        pygame.draw.circle(b, tuple(min(255, c + 25) for c in col), (23, y - 3), 4)

    if kind == weather.SUNNY:
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(b, (250, 190, 70), (24 + math.cos(a) * 13, 24 + math.sin(a) * 13),
                             (24 + math.cos(a) * 20, 24 + math.sin(a) * 20), 3)
        pygame.draw.circle(b, (236, 170, 60), (24, 24), 11)
        pygame.draw.circle(b, (255, 214, 92), (24, 24), 10)
        pygame.draw.circle(b, (255, 238, 170), (21, 21), 4)
    elif kind in (weather.RAIN, weather.STORM):
        dark = kind == weather.STORM
        cloud((150, 158, 186) if dark else (226, 232, 244), 12)
        for i, x in enumerate((14, 23, 32)):
            pygame.draw.line(b, (110, 160, 230), (x, 32 + (i % 2) * 3), (x - 3, 40 + (i % 2) * 3), 3)
        if dark:
            pygame.draw.polygon(b, (255, 214, 80), [(27, 26), (20, 37), (25, 37), (21, 46),
                                                    (32, 33), (26, 33), (30, 26)])
            pygame.draw.polygon(b, (200, 140, 30), [(27, 26), (20, 37), (25, 37), (21, 46),
                                                    (32, 33), (26, 33), (30, 26)], 1)
    elif kind == weather.SNOW:
        cloud((236, 240, 250), 12)
        for x, y in ((14, 36), (24, 40), (34, 35)):
            for a in range(3):
                ang = a * math.pi / 3
                pygame.draw.line(b, (150, 190, 236), (x - math.cos(ang) * 4, y - math.sin(ang) * 4),
                                 (x + math.cos(ang) * 4, y + math.sin(ang) * 4), 2)
    elif kind == weather.FOG:
        pygame.draw.circle(b, (250, 210, 110), (30, 16), 9)
        for i, (x0, x1) in enumerate(((6, 40), (10, 44), (4, 36), (12, 42))):
            y = 20 + i * 7
            pygame.draw.line(b, (176, 186, 204), (x0, y), (x1, y), 4)
            pygame.draw.line(b, (226, 232, 242), (x0 + 2, y - 1), (x1 - 2, y - 1), 2)
    elif kind == weather.WINDY:
        for i, (y, w) in enumerate(((16, 30), (25, 36), (34, 24))):
            pygame.draw.line(b, (150, 186, 220), (6, y), (6 + w, y), 3)
            pygame.draw.arc(b, (150, 186, 220), (w - 2, y - 8, 12, 10), -math.pi / 2,
                            math.pi / 2 + 0.6, 3)
        pygame.draw.ellipse(b, (250, 170, 196), (30, 34, 12, 7))
        pygame.draw.ellipse(b, (140, 200, 120), (10, 38, 10, 6))
    else:
        pygame.draw.circle(b, (220, 220, 230), (24, 24), 12)
    s = b if size == 48 else pygame.transform.smoothscale(b, (size, size))
    _CACHE[key] = s
    return s


def _fog_band(i):
    """Soft horizontal fog band: tiny noise strip smooth-scaled up (cached)."""
    key = ("fog", i)
    s = _CACHE.get(key)
    if s is None:
        rnd = random.Random(7 + i)
        small = pygame.Surface((48, 10), pygame.SRCALPHA)
        for x in range(48):
            puff = 0.55 + 0.45 * math.sin(x * 0.45 + i) * math.sin(x * 0.17 + 2 * i)
            for y in range(10):
                v = math.sin(math.pi * (y + 0.5) / 10)            # soft top/bottom
                a = int(max(0.0, min(1.0, v * (0.55 + 0.45 * puff) * rnd.uniform(0.85, 1.0))) * 200)
                small.set_at((x, y), (236, 240, 246, a))
        s = pygame.transform.smoothscale(small, (SCREEN_W + 480, 190))
        _CACHE[key] = s
    return s


def _make_bolt():
    """Screen-space lightning: a main jagged stroke from the sky + 1-2 forks."""
    x = random.uniform(SCREEN_W * 0.1, SCREEN_W * 0.9)
    y = -10.0
    main = [(x, y)]
    end_y = random.uniform(SCREEN_H * 0.35, SCREEN_H * 0.6)
    while y < end_y:
        y += random.uniform(22, 44)
        x += random.uniform(-26, 26)
        main.append((x, y))
    out = [(main, 3)]
    for _ in range(random.randint(1, 2)):
        i = random.randint(1, max(1, len(main) - 2))
        bx, by = main[i]
        fork = [(bx, by)]
        d = random.choice((-1, 1))
        for _ in range(random.randint(2, 4)):
            bx += d * random.uniform(10, 28)
            by += random.uniform(16, 30)
            fork.append((bx, by))
        out.append((fork, 1))
    return out


def _rainbow():
    """Soft pastel rainbow arc (cached): concentric translucent bands, top only."""
    s = _CACHE.get("rainbow")
    if s is None:
        W, H = 980, 300
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cols = [(255, 150, 160), (255, 196, 140), (255, 236, 150), (170, 226, 160),
                (150, 200, 240), (176, 160, 232), (214, 160, 226)]
        cx, cy = W // 2, H + 180
        r0 = 470
        for i, c in enumerate(cols):
            pygame.draw.circle(s, c + (70,), (cx, cy), r0 - i * 11, 11)
        # feather the ends into the sky
        fade = pygame.Surface((W, H), pygame.SRCALPHA)
        for x in range(0, W, 4):
            edge = min(x, W - x) / (W * 0.22)
            a = int(255 * max(0.0, min(1.0, edge)))
            pygame.draw.rect(fade, (255, 255, 255, a), (x, 0, 4, H))
        s.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        _CACHE["rainbow"] = s
    return s


def _fill(key, rgba):
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill(rgba)
        _CACHE[key] = s
    return s


def _gust():
    s = _CACHE.get("gust")
    if s is None:
        s = pygame.Surface((180, 8), pygame.SRCALPHA)
        for x in range(0, 180, 2):
            a = int(90 * math.sin(math.pi * x / 180))
            pygame.draw.line(s, (255, 255, 255, a), (x, 3), (x + 2, 3), 2)
        _CACHE["gust"] = s
    return s


class WeatherMixin:
    """Weather logic extras + storm/fog/wind visuals."""

    # ---------------------------------------------------------------- state
    def _on_reset_weather(self):
        self.weather_tomorrow = weather.pick(self._season_after(1))
        self._wx = {"flash": 0.0, "next_flash": random.uniform(4.0, 9.0),
                    "thunder": -1.0, "splash": 0.0, "wind": 0.0, "gust": [],
                    "double": False}

    def _season_after(self, days=1):
        t = self.time
        d = t.day + days
        sidx = t.season_idx + (d - 1) // DAYS_PER_SEASON
        return SEASONS[sidx % len(SEASONS)]

    def _roll_weather(self):
        """Promote the pre-rolled forecast to today's weather (re-rolled if it
        doesn't fit the new season) and pre-roll tomorrow's. Returns today's."""
        season = self.time.season
        w = getattr(self, "weather_tomorrow", None)
        if w not in weather.ALL or not weather.valid(w, season):
            w = weather.pick(season)
        self.weather_tomorrow = weather.pick(self._season_after(1))
        prev = getattr(self, "weather", None)
        wx = getattr(self, "_wx", None)
        if wx is not None:                          # a rainbow the morning after rain
            wx["rainbow"] = prev in (weather.RAIN, weather.STORM) and w in (weather.SUNNY,
                                                                            weather.WINDY)
            if wx["rainbow"] and getattr(self, "ui", None):
                self.ui.log("A rainbow after the rain - make a wish together!")
        line = _MORNING_LINE.get(w)
        if line and getattr(self, "ui", None):
            self.ui.log(line)
        self.emit("weather_changed", weather=w, tomorrow=self.weather_tomorrow)
        return w

    def forecast_text(self):
        w = getattr(self, "weather_tomorrow", weather.SUNNY)
        return weather.LABEL.get(w, str(w).title())

    def _on_save_weather(self):
        return {"weather_tomorrow": getattr(self, "weather_tomorrow", weather.SUNNY)}

    def _on_load_weather(self, d):
        w = d.get("weather_tomorrow")
        if w not in weather.ALL:
            w = weather.pick(self._season_after(1))
        self.weather_tomorrow = w
        if getattr(self, "weather", None) not in weather.ALL:
            self.weather = weather.pick(self.time.season)

    # ---------------------------------------------------------------- update
    def _outdoors(self):
        return self.world.current in OUTDOOR

    def _fog_strength(self):
        m = self.time.minutes
        if m <= 9 * 60:
            return 1.0
        if m >= 12 * 60:
            return 0.0
        return 1.0 - (m - 9 * 60) / 180.0

    def _on_update_weather(self, dt):
        wx = self._wx
        w = self.weather
        out = self._outdoors()
        # sky grading for lighting.apply (outdoors only; lighting checks area too)
        if not out:
            tint = None
        elif w == weather.STORM:
            tint = ((56, 64, 104), 84)
        elif w == weather.RAIN:
            tint = ((120, 130, 152), 26)
        elif w == weather.FOG:
            k = self._fog_strength()
            tint = ((226, 230, 238), int(34 * k)) if k > 0 else None
        else:
            tint = None
        lighting.set_weather_tint(tint)
        # ambience bed: rain / storm / wind outdoors, rain muffled indoors
        amb = getattr(self.audio, "set_ambience", None)
        if amb:
            kind = {weather.RAIN: "rain", weather.STORM: "storm",
                    weather.WINDY: "wind"}.get(w)
            if out or kind is None:
                amb(kind, 1.0)
            elif kind in ("rain", "storm") and self.world.current in ("home", "coop"):
                amb(kind, 0.35)
            else:
                amb(None)
        # music mood: the farm/home/barn loop turns soft on rainy days + evenings
        cur = self.world.current
        if cur in _SOFT_AREAS:
            soft = (self.time.minutes >= 20 * 60
                    or (w in (weather.RAIN, weather.STORM) and cur == "farm"))
            f = getattr(self.audio, "play_mood", None)
            if f:
                f(cur, soft)                 # cheap no-op while already on that loop
        if wx["flash"] > 0:
            wx["flash"] = max(0.0, wx["flash"] - dt * 2.6)
        if w != weather.WINDY or not out:
            wx["warm"] = None
        if not out:
            wx["thunder"] = -1.0
            return
        cam = self.cam
        if w == weather.STORM:
            wx["next_flash"] -= dt
            if wx["next_flash"] <= 0:
                wx["flash"] = 1.0
                if not wx["double"]:
                    wx["bolt"] = _make_bolt()           # one visible bolt per strike
                if wx["double"] or random.random() < 0.6:
                    wx["double"] = False
                    wx["next_flash"] = random.uniform(7.0, 15.0)
                    wx["thunder"] = random.uniform(0.25, 0.9)
                else:
                    wx["double"] = True             # quick second flicker
                    wx["next_flash"] = random.uniform(0.12, 0.22)
            if wx["thunder"] > 0:
                wx["thunder"] -= dt
                if wx["thunder"] <= 0:
                    wx["thunder"] = -1.0
                    self.audio.play("thunder")
                    self.add_shake(2.5)
        if w in (weather.RAIN, weather.STORM):
            f = getattr(self.parts, "rain_splash", None)
            if f:
                wx["splash"] -= dt
                rate = 0.03 if w == weather.STORM else 0.07
                while wx["splash"] <= 0:
                    wx["splash"] += rate
                    f(cam.x + random.uniform(0, SCREEN_W), cam.y + random.uniform(40, SCREEN_H))
        elif w == weather.WINDY:
            f = getattr(self.parts, "petal", None)
            cols = _WIND_COLS.get(self.time.season, _WIND_COLS["Spring"])
            here = (self.world.current, w)
            if f and wx.get("warm") != here:        # just arrived / wind picked up:
                wx["warm"] = here                   # fill the screen at once
                for _ in range(34):
                    f(cam.x + random.uniform(-40, SCREEN_W), cam.y + random.uniform(0, SCREEN_H),
                      random.choice(cols), vx=random.uniform(120, 220), vy=random.uniform(10, 45))
            wx["wind"] -= dt
            while f and wx["wind"] <= 0:
                wx["wind"] += 0.06
                if random.random() < 0.5:           # enter from the left edge
                    x = cam.x - 20
                    y = cam.y + random.uniform(-20, SCREEN_H * 0.85)
                else:                               # or drift down from the top
                    x = cam.x + random.uniform(-100, SCREEN_W * 0.8)
                    y = cam.y - 16
                f(x, y, random.choice(cols), vx=random.uniform(120, 220),
                  vy=random.uniform(10, 45))
            # a few white gust streaks sliding across (screen space)
            g = wx["gust"]
            for s in g:
                s[0] += s[2] * dt
            wx["gust"] = [s for s in g if s[0] < SCREEN_W + 200]
            if len(wx["gust"]) < 4 and random.random() < dt * 1.5:
                wx["gust"].append([-200.0, random.uniform(40, SCREEN_H - 60),
                                   random.uniform(520, 820)])

    # ---------------------------------------------------------------- draw
    def _rainbow_alpha(self):
        if not self._wx.get("rainbow"):
            return 0.0
        m = self.time.minutes
        if m <= 9 * 60:
            return 1.0
        return max(0.0, 1.0 - (m - 9 * 60) / 120.0)     # gone by 11:00

    def _draw_world_weather(self):
        if not self._outdoors():
            return
        w = self.weather
        scr = self.screen
        at = self.anim_t
        ra = self._rainbow_alpha()
        if ra > 0:
            rb = _rainbow()
            rb.set_alpha(int(255 * ra * (0.85 + 0.15 * math.sin(at * 0.8))))
            scr.blit(rb, (int(SCREEN_W / 2 - rb.get_width() / 2 - self.cam.x * 0.04 % 60), 70))
        if w == weather.STORM:
            # three depth layers of steep, long streaks (heavier than rain)
            for cnt, spd, length, col, wd, slant in (
                    (90, 900, 16, (120, 144, 186), 1, 7),
                    (66, 1350, 24, (160, 182, 220), 2, 10),
                    (28, 1800, 34, (206, 220, 244), 2, 13)):
                t = int(at * spd)
                for i in range(cnt):
                    x = (i * 61 + t // 3) % (SCREEN_W + 60) - 30
                    y = (i * 43 + t) % (SCREEN_H + 40) - 20
                    pygame.draw.line(scr, col, (x, y), (x - slant, y + length), wd)
            bolt = self._wx.get("bolt")
            if bolt and self._wx.get("flash", 0.0) > 0.45:
                # a jagged bolt in the sky (under the HUD): violet glow + bright core
                for pts, bw in bolt:
                    pygame.draw.lines(scr, (150, 140, 235), False, pts, bw + 4)
                for pts, bw in bolt:
                    pygame.draw.lines(scr, (255, 250, 214), False, pts, bw)
        elif w == weather.FOG:
            k = self._fog_strength()
            if k <= 0:
                return
            haze = _fill("haze", (232, 236, 244, 70))
            haze.set_alpha(int(255 * k))
            scr.blit(haze, (0, 0))
            cx = self.cam.x
            for i, (by, spd, par) in enumerate(((SCREEN_H * 0.18, 9, 0.25),
                                                (SCREEN_H * 0.52, 15, 0.4),
                                                (SCREEN_H * 0.80, 22, 0.55))):
                band = _fog_band(i % 2)
                off = -((at * spd + cx * par) % 480)
                y = by + math.sin(at * 0.25 + i * 2.1) * 18 - band.get_height() / 2
                band.set_alpha(int(210 * k))
                scr.blit(band, (int(off), int(y)))
        elif w == weather.WINDY:
            gs = _gust()
            for s in self._wx.get("gust", ()):
                scr.blit(gs, (int(s[0]), int(s[1])))

    def _draw_sky_weather(self):
        """Lightning flash: after lighting so it brightens even the night, but
        under the HUD so the cards don't wash out."""
        f = self._wx.get("flash", 0.0) if hasattr(self, "_wx") else 0.0
        if f <= 0.02 or not self._outdoors() or self.state not in ("play", "sleep"):
            return
        fl = _fill("flash", (236, 240, 255, 255))
        fl.set_alpha(int(130 * f))
        self.screen.blit(fl, (0, 0))

