"""The TV: switch it on and actually watch something.

Interact with a placed TV (or press Action while lounging on a seat when a TV
in the room is on). A retro set fills the screen with four channels:

  CH 3  Valley Weather   today + tomorrow's forecast, temperatures, a farm tip
  CH 5  Farm Almanac     the date, what to plant this season, festival & birthdays
  CH 7  Kitchen Corner   the recipe of the day and whether you can cook it now
  CH 9  Our Farm Life    the two of you: days together, love boosts, harvests...

  Left/Right  change channel      1-4  jump to a channel
  Action      switch the TV off   Esc / B  walk away (it keeps playing)

Pure UI that only READS game state, so it also runs locally on a LAN client.
The world TV picks up the channel too (``HomeMixin`` feeds ``isofurn.TV_ART``).
"""
import math
import random
import pygame

from .settings import SCREEN_W, P1_KEYS, P2_KEYS, SEASONS, DAYS_PER_SEASON
from . import ui_kit as K

CHANNELS = [("weather", 3, "Valley Weather"), ("almanac", 5, "Farm Almanac"),
            ("cooking", 7, "Kitchen Corner"), ("us", 9, "Our Farm Life")]
ON_T = 0.42
OFF_T = 0.34
STATIC_T = 0.30
SCR_W, SCR_H = 800, 430

# per-channel palette (backdrop top, bottom, accent)
_PAL = {
    "almanac": ((80, 132, 84), (46, 86, 60), (250, 226, 140)),
    "cooking": ((226, 138, 98), (170, 84, 70), (255, 238, 196)),
    "us":      ((214, 120, 156), (126, 70, 120), (255, 222, 234)),
}
_SKY = {   # weather -> (top, bottom)
    "sunny": ((110, 178, 236), (190, 226, 250)),
    "rain":  ((96, 112, 140), (150, 164, 188)),
    "storm": ((52, 58, 84), (98, 104, 132)),
    "fog":   ((160, 170, 180), (206, 212, 216)),
    "windy": ((120, 184, 220), (206, 232, 238)),
    "snow":  ((150, 170, 204), (226, 234, 246)),
}
_BASE_TEMP = {"Spring": 19, "Summer": 31, "Fall": 16, "Winter": -1}
_TEMP_ADJ = {"sunny": 3, "rain": -3, "storm": -4, "fog": -2, "windy": -2, "snow": -3}
_TIP = {
    "sunny": "Clear skies tomorrow - remember to water your crops!",
    "rain": "Rain tomorrow: the crops water themselves. Sleep in a little!",
    "storm": "Storm warning! Crops get watered, but stay close to home.",
    "fog": "Morning fog rolls in - it lifts by noon. Great fishing weather.",
    "windy": "A breezy day: petals and leaves on the wind. Hang on to your hat!",
    "snow": "Snow tomorrow. Bundle up and keep the fireplace going.",
}


def _grad(w, h, top, bot):
    s = pygame.Surface((w, h))
    for y in range(h):
        k = y / max(1, h - 1)
        s.fill(tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)), (0, y, w, 1))
    return s


_GRADS = {}


def _cached_grad(key, w, h, top, bot):
    s = _GRADS.get(key)
    if s is None:
        s = _GRADS[key] = _grad(w, h, top, bot)
    return s


_SCAN = None


def _scanlines():
    """CRT scanlines + a soft corner vignette (built once)."""
    global _SCAN
    if _SCAN is None:
        _SCAN = pygame.Surface((SCR_W, SCR_H), pygame.SRCALPHA)
        for y in range(0, SCR_H, 3):
            _SCAN.fill((0, 0, 0, 30), (0, y, SCR_W, 1))
        for i in range(12):                                  # darkest at the very edge
            pygame.draw.rect(_SCAN, (0, 0, 0, 40 - i * 3), (i * 2, i * 2, SCR_W - i * 4,
                                                           SCR_H - i * 4), 2, border_radius=28)
    return _SCAN


def temperature(season, kind, day):
    """A friendly made-up forecast temperature (deg C), stable per day."""
    j = ((day * 37) % 5) - 2
    return _BASE_TEMP.get(season, 18) + _TEMP_ADJ.get(kind, 0) + j


def recipe_of_day(time):
    from . import cooking
    keys = list(cooking.RECIPES)
    n = time.year * 1000 + time.season_idx * 100 + time.day
    return keys[(n * 7919) % len(keys)]


class TVScreen:
    def __init__(self, game, pidx, tv, channel=0, client=False, from_seat=False):
        self.g = game
        self.pidx = pidx
        self.tv = tv
        self.client = client
        self.from_seat = from_seat
        self.ch = channel % len(CHANNELS)
        self.phase = "on"
        self.t = 0.0
        self.clock = 0.0
        self.static = 0.0
        rng = random.Random(7)
        self._drops = [[rng.random(), rng.random()] for _ in range(70)]
        self._noise = None

    @property
    def name(self):
        return CHANNELS[self.ch][0]

    # ---- input ----
    def handle_key(self, key):
        if self.phase == "off":
            return
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self._leave(power_off=False)
            return
        if key in (P1_KEYS["action"], P2_KEYS["action"]):
            self._leave(power_off=True)
            return
        d = 0
        if key in (P1_KEYS["left"], P2_KEYS["left"], P1_KEYS["up"], P2_KEYS["up"]):
            d = -1
        elif key in (P1_KEYS["right"], P2_KEYS["right"], P1_KEYS["down"], P2_KEYS["down"]):
            d = 1
        elif pygame.K_1 <= key < pygame.K_1 + len(CHANNELS):
            tgt = key - pygame.K_1
            if tgt != self.ch:
                self.ch = tgt
                self._zap()
            return
        if d:
            self.ch = (self.ch + d) % len(CHANNELS)
            self._zap()

    def _zap(self):
        self.static = STATIC_T
        a = self.g.audio
        a.play("tv_zap" if "tv_zap" in getattr(a, "sfx", {}) else "ui_move")
        self.g._tv_channel_changed(self)

    def _leave(self, power_off):
        if power_off:
            self.phase, self.t = "off", 0.0
            a = self.g.audio
            a.play("tv_off" if "tv_off" in getattr(a, "sfx", {}) else "ui_toggle")
        else:
            self.g._tv_closed(self, power_off=False)

    def update(self, dt):
        self.clock += dt
        self.t += dt
        self.static = max(0.0, self.static - dt)
        if self.phase == "on" and self.t >= ON_T:
            self.phase, self.t = "live", 0.0
        elif self.phase == "off" and self.t >= OFF_T:
            self.g._tv_closed(self, power_off=True)

    # ---- draw ----
    def draw(self, surf):
        K.dim(surf, 170, (14, 10, 20))
        color = self._piece_color()
        # cabinet
        cab = pygame.Rect(0, 0, SCR_W + 64, SCR_H + 110)
        cab.midtop = (SCREEN_W // 2, 112)
        pygame.draw.rect(surf, (20, 16, 22), cab.move(0, 6), border_radius=26)
        pygame.draw.rect(surf, (40, 40, 48), cab, border_radius=24)
        pygame.draw.rect(surf, (64, 64, 76), cab, 3, border_radius=24)
        trim = pygame.Rect(cab.x + 10, cab.bottom - 58, cab.w - 20, 46)
        pygame.draw.rect(surf, color, trim, border_radius=14)
        pygame.draw.rect(surf, tuple(int(v * 0.6) for v in color), trim, 2, border_radius=14)
        dark_trim = sum(color) < 380
        K.blit_text(surf, K.font(15, True), "HarvestVision",
                    (250, 246, 236) if dark_trim else (60, 50, 60),
                    (trim.x + 22, trim.centery), align="left")
        on = self.phase != "off"
        led = (110, 230, 130) if on else (200, 70, 70)
        pygame.draw.circle(surf, (30, 26, 34), (trim.right - 26, trim.centery), 8)
        pygame.draw.circle(surf, led, (trim.right - 26, trim.centery), 6)
        pygame.draw.circle(surf, (255, 255, 255), (trim.right - 28, trim.centery - 2), 2)
        for i in range(len(CHANNELS)):                       # channel buttons 1..4
            cx = trim.centerx - 54 + i * 36
            hot = i == self.ch
            pygame.draw.circle(surf, (250, 240, 214) if hot else (70, 66, 78), (cx, trim.centery), 11)
            pygame.draw.circle(surf, (30, 26, 34), (cx, trim.centery), 11, 2)
            K.blit_text(surf, K.font(12, True), str(i + 1),
                        (60, 40, 30) if hot else (200, 196, 210), (cx, trim.centery))
        # screen
        scr = pygame.Rect(0, 0, SCR_W, SCR_H)
        scr.midtop = (cab.centerx, cab.y + 26)
        pygame.draw.rect(surf, (8, 8, 12), scr.inflate(14, 14), border_radius=18)
        vis = self._crt_rect(scr)
        if vis is not None:
            pic = pygame.Surface((SCR_W, SCR_H))
            self._draw_channel(pic)
            if self.static > 0:
                self._draw_static(pic, min(1.0, self.static / STATIC_T))
            pic.blit(_scanlines(), (0, 0))
            if vis.size == scr.size:
                surf.blit(pic, scr)
            elif vis.w > 0 and vis.h > 0:
                surf.blit(pygame.transform.smoothscale(pic, vis.size), vis)
                if vis.h < 16:                                  # bright scan line
                    pygame.draw.rect(surf, (230, 240, 255), vis)
        # glass sheen
        sheen = pygame.Surface(scr.size, pygame.SRCALPHA)
        pygame.draw.polygon(sheen, (255, 255, 255, 14),
                            [(0, 0), (SCR_W * 0.45, 0), (SCR_W * 0.25, SCR_H), (0, SCR_H)])
        surf.blit(sheen, scr)
        pygame.draw.rect(surf, (90, 90, 104), scr.inflate(14, 14), 3, border_radius=18)
        hint = ("Left/Right channel  -  Action switch off  -  Esc back to your seat"
                if self.from_seat else
                "Left/Right channel  -  Action switch off  -  Esc walk away (TV stays on)")
        hf = K.fit_font(hint, 700, (14, 13, 12), bold=True)
        pill = pygame.Rect(0, 0, hf.size(hint)[0] + 36, 28)
        pill.center = (SCREEN_W // 2, cab.bottom + 24)
        K.pill(surf, pill, (28, 22, 34), outline=(90, 90, 104), alpha=240)
        K.blit_text(surf, hf, hint, (236, 226, 214), pill.center)

    def _crt_rect(self, scr):
        if self.phase == "on":
            k = min(1.0, self.t / ON_T)
            if k < 0.35:
                w, h = int(scr.w * (k / 0.35)), 4
            else:
                w, h = scr.w, int(4 + (scr.h - 4) * ((k - 0.35) / 0.65) ** 0.7)
            r = pygame.Rect(0, 0, max(1, w), max(1, h))
            r.center = scr.center
            return r
        if self.phase == "off":
            k = min(1.0, self.t / OFF_T)
            if k < 0.5:
                w, h = scr.w, int(scr.h * (1 - k / 0.5)) + 3
            else:
                w, h = int(scr.w * (1 - (k - 0.5) / 0.5)), 3
            if w <= 2:
                return None
            r = pygame.Rect(0, 0, w, h)
            r.center = scr.center
            return r
        return scr

    def _draw_static(self, pic, k):
        # a few pre-rolled noise frames, cycled (cheap "snow" between channels)
        if self._noise is None:
            self._noise = []
            rnd = random.Random(3)
            for _ in range(4):
                n = pygame.Surface((SCR_W // 4, SCR_H // 4))
                for x in range(n.get_width()):
                    for y in range(n.get_height()):
                        v = rnd.randint(0, 255)
                        n.set_at((x, y), (v, v, v))
                self._noise.append(pygame.transform.scale(n, (SCR_W, SCR_H)))
        big = self._noise[int(self.clock * 30) % len(self._noise)]
        big.set_alpha(int(255 * k))
        pic.blit(big, (0, 0))

    def _piece_color(self):
        from . import furniture as F
        try:
            return F.PALETTE[self.tv.ci % len(F.PALETTE)][1]
        except Exception:
            return (138, 140, 150)

    # ---- channels ----
    def _osd(self, pic):
        _n, num, title = CHANNELS[self.ch]
        t = K.outlined(K.font(22, True), f"CH {num}", (140, 255, 150), (10, 30, 14), 2)
        pic.blit(t, (SCR_W - t.get_width() - 18, 12))
        tt = K.outlined(K.font(24, True), title.upper(), (255, 255, 255), (30, 24, 40), 2)
        pic.blit(tt, (22, 12))
        g = self.g
        clock = f"{g.time.season} {g.time.day}  -  {g.time.clock_str()}"
        ct = K.outlined(K.font(14, True), clock, (240, 240, 250), (30, 24, 40), 1)
        pic.blit(ct, (24, 44))

    def _draw_channel(self, pic):
        getattr(self, "_ch_" + self.name)(pic)
        self._osd(pic)

    def _panel(self, pic, rect, alpha=150, col=(255, 255, 255)):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*col, alpha), s.get_rect(), border_radius=16)
        pic.blit(s, rect.topleft)

    # CH 3 -- weather
    def _ch_weather(self, pic):
        from . import weather as W
        g = self.g
        today = getattr(g, "weather", W.SUNNY)
        tom = getattr(g, "weather_tomorrow", W.SUNNY)
        top, bot = _SKY.get(tom, _SKY["sunny"])
        pic.blit(_cached_grad(("sky", tom), SCR_W, SCR_H, top, bot), (0, 0))
        self._weather_fx(pic, tom)
        snow = tom == W.SNOW
        pygame.draw.ellipse(pic, (236, 242, 250) if snow else (104, 160, 96),
                            (-120, SCR_H - 90, 560, 220))
        pygame.draw.ellipse(pic, (214, 226, 240) if snow else (86, 142, 84),
                            (300, SCR_H - 70, 640, 220))
        try:
            from .systems.weather_system import weather_icon
        except Exception:
            weather_icon = None
        last = g.time.day >= DAYS_PER_SEASON
        tom_season = SEASONS[(g.time.season_idx + (1 if last else 0)) % len(SEASONS)]
        cards = [("TODAY", today, g.time.season, g.time.day),
                 ("TOMORROW", tom, tom_season, g.time.day % DAYS_PER_SEASON + 1)]
        for i, (head, kind, season, day) in enumerate(cards):
            r = pygame.Rect(70 + i * 350, 98, 310, 212)
            self._panel(pic, r, 180)
            pygame.draw.rect(pic, (255, 255, 255), r, 2, border_radius=16)
            K.blit_text(pic, K.font(18, True), head, (60, 70, 100), (r.centerx, r.y + 22))
            if weather_icon:
                ic = weather_icon(kind, 96)
                bob = math.sin(self.clock * 2.2 + i) * 4
                pic.blit(ic, ic.get_rect(center=(r.centerx - 70, r.y + 112 + bob)))
            lab = W.LABEL.get(kind, str(kind).title())
            K.blit_text(pic, K.font(24, True), lab, (40, 50, 80), (r.centerx + 56, r.y + 86))
            temp = temperature(season, kind, day)
            tcol = ((230, 110, 70) if temp >= 25 else (70, 120, 200) if temp <= 5
                    else (60, 70, 100))
            K.blit_text(pic, K.font(40, True), f"{temp}°C", tcol, (r.centerx + 56, r.y + 132))
            K.blit_text(pic, K.font(13, True), f"{season} {day}", (90, 100, 130),
                        (r.centerx, r.bottom - 18))
        tip = _TIP.get(tom, "")
        box = pygame.Rect(40, SCR_H - 100, SCR_W - 80, 56)
        self._panel(pic, box, 200, (30, 34, 60))
        f = K.fit_font(tip, box.w - 30, (18, 17, 16, 15, 14), bold=True)
        K.blit_text(pic, f, tip, (255, 246, 214), box.center)

    def _weather_fx(self, pic, kind):
        t = self.clock
        if kind in ("sunny", "windy"):                       # sun peeking between the cards
            cx, cy = SCR_W // 2, 50
            for i in range(10):
                a = t * 0.4 + i * math.pi / 5
                pygame.draw.line(pic, (255, 236, 150), (cx + math.cos(a) * 28, cy + math.sin(a) * 28),
                                 (cx + math.cos(a) * 40, cy + math.sin(a) * 40), 4)
            pygame.draw.circle(pic, (255, 214, 92), (cx, cy), 22)
            pygame.draw.circle(pic, (255, 238, 170), (cx - 6, cy - 6), 8)
        if kind in ("rain", "storm"):
            for d in self._drops:
                x = (d[0] * SCR_W + t * 90) % SCR_W
                y = (d[1] * SCR_H + t * 520) % SCR_H
                pygame.draw.line(pic, (190, 210, 240), (x, y), (x - 5, y + 16), 2)
            if kind == "storm" and (t % 3.1) < 0.12:
                pic.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_ADD)
        if kind == "snow":
            for d in self._drops:
                x = (d[0] * SCR_W + math.sin(t + d[1] * 9) * 20) % SCR_W
                y = (d[1] * SCR_H + t * 50) % SCR_H
                pygame.draw.circle(pic, (255, 255, 255), (int(x), int(y)), 3)
        if kind == "fog":
            s = pygame.Surface((420, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 255, 255, 60), s.get_rect())
            for i in range(4):
                x = (t * (18 + i * 6) + i * 260) % (SCR_W + 400) - 300
                pic.blit(s, (x, 120 + i * 60))
        if kind == "windy":
            for i, d in enumerate(self._drops[:24]):
                x = (d[0] * SCR_W + t * 260) % (SCR_W + 40) - 20
                y = d[1] * SCR_H * 0.8 + math.sin(t * 3 + i) * 12
                pygame.draw.ellipse(pic, (255, 196, 214) if i % 2 else (180, 220, 140),
                                    (x, y, 10, 6))

    # CH 5 -- almanac
    def _ch_almanac(self, pic):
        from .crops import CROPS
        from . import assets, festival
        g = self.g
        top, bot, acc = _PAL["almanac"]
        pic.blit(_cached_grad("almanac", SCR_W, SCR_H, top, bot), (0, 0))
        for i in range(12):                                  # drifting leaves
            x = (i * 97 + int(self.clock * 12)) % (SCR_W + 60) - 30
            y = 70 + (i * 53) % (SCR_H - 90)
            pygame.draw.ellipse(pic, (96, 150, 96), (x, y, 26, 12))
        season = g.time.season
        left = DAYS_PER_SEASON - g.time.day
        head = pygame.Rect(30, 72, SCR_W - 60, 60)
        self._panel(pic, head, 70, (0, 0, 0))
        K.blit_text(pic, K.font(22, True), f"{season}, day {g.time.day}  (year {g.time.year})",
                    acc, (head.x + 20, head.y + 20), align="left")
        K.blit_text(pic, K.font(15, True),
                    (f"{left} day{'s' if left != 1 else ''} left this season" if left else
                     "Last day of the season - tomorrow the seasons turn!"),
                    (230, 240, 220), (head.x + 20, head.y + 43), align="left")
        # what to plant (greyed out when it can't ripen before the season ends)
        crops = [(k, v) for k, v in CROPS.items() if v["season"] == season]
        box = pygame.Rect(30, 144, 470, SCR_H - 160)
        self._panel(pic, box, 190)
        K.blit_text(pic, K.font(17, True), f"Plant this {season}", (50, 90, 50),
                    (box.x + 16, box.y + 18), align="left")
        y = box.y + 38
        f = K.font(14, True)
        for k, v in crops[:6]:
            ok = v["grow"] <= left
            try:
                pic.blit(assets.item_icon(k), (box.x + 14, y))
            except Exception:
                pass
            col = (50, 60, 50) if ok else (150, 150, 140)
            K.blit_text(pic, f, k.replace("_", " ").title(), col, (box.x + 52, y + 14), align="left")
            info = f"{v['grow']}d" + (f", regrows {v['regrow']}d" if v.get("regrow") else "")
            K.blit_text(pic, f, info, col, (box.x + 210, y + 14), align="left")
            K.blit_text(pic, f, f"{v['sell']}g" if ok else "too late",
                        (170, 116, 30) if ok else (170, 90, 80), (box.right - 16, y + 14),
                        align="right")
            y += 36
        # festival + birthdays
        side = pygame.Rect(514, 144, SCR_W - 544, SCR_H - 160)
        self._panel(pic, side, 190)
        K.blit_text(pic, K.font(17, True), "Coming up", (50, 90, 50),
                    (side.x + 16, side.y + 18), align="left")
        lines = []
        fd = festival.FEST_DAY - g.time.day
        fname = festival.name(season)
        if fd == 0:
            lines.append(("TODAY:", f"{fname}!"))
        elif fd > 0:
            lines.append((f"In {fd} day{'s' if fd != 1 else ''}:", fname))
        try:
            from .story_data import VILLAGERS, DISPLAY
            for nm, d in VILLAGERS.items():
                bs, bd = d.get("birthday", (-1, -1))
                if bs == g.time.season_idx and 0 <= bd - g.time.day <= 7:
                    dd = bd - g.time.day
                    when = "TODAY:" if dd == 0 else f"In {dd} day{'s' if dd != 1 else ''}:"
                    lines.append((when, f"{DISPLAY.get(nm, nm)}'s birthday"))
        except Exception:
            pass
        if not lines:
            lines.append(("", "A quiet week on the farm."))
        y = side.y + 44
        fb = K.font(15, True)
        for a, b in lines[:4]:
            if a:
                K.blit_text(pic, K.font(13, True), a, (120, 100, 60), (side.x + 16, y), align="left")
                y += 18
            for ln in K.wrap(fb, b, side.w - 30)[:2]:
                K.blit_text(pic, fb, ln, (50, 60, 50), (side.x + 16, y), align="left")
                y += 20
            y += 8

    # CH 7 -- cooking show
    def _ch_cooking(self, pic):
        from . import cooking, assets
        g = self.g
        top, bot, acc = _PAL["cooking"]
        pic.blit(_cached_grad("cooking", SCR_W, SCR_H, top, bot), (0, 0))
        for x in range(0, SCR_W, 40):                        # checkered tablecloth
            for y in range(SCR_H - 110, SCR_H, 40):
                c = (250, 236, 226) if (x // 40 + y // 40) % 2 == 0 else (214, 86, 80)
                pic.fill(c, (x, y, 40, 40))
        fid = recipe_of_day(g.time)
        f = cooking.FOODS[fid]
        K.blit_text(pic, K.font(16, True), "Today's recipe", acc, (SCR_W // 2, 84))
        K.blit_text(pic, K.font(32, True), f["label"], (255, 255, 255), (SCR_W // 2, 116))
        # the dish on a plate, with rising steam
        px, py = 220, 236
        pygame.draw.ellipse(pic, (120, 70, 60), (px - 118, py + 44, 236, 40))
        pygame.draw.ellipse(pic, (250, 250, 246), (px - 110, py + 20, 220, 70))
        pygame.draw.ellipse(pic, (226, 226, 220), (px - 80, py + 32, 160, 46), 3)
        try:
            ic = assets.item_icon(fid)
            big = pygame.transform.scale(ic, (ic.get_width() * 4, ic.get_height() * 4))
            bob = math.sin(self.clock * 2) * 3
            pic.blit(big, big.get_rect(midbottom=(px, py + 66 + bob)))
        except Exception:
            pass
        st = pygame.Surface((24, 24), pygame.SRCALPHA)
        for i in range(3):
            ph = (self.clock * 0.8 + i / 3) % 1
            sx = px - 30 + i * 30 + math.sin(ph * 6) * 6
            sy = py - 30 - ph * 50
            st.fill((0, 0, 0, 0))
            pygame.draw.circle(st, (255, 255, 255, int(150 * (1 - ph))), (12, 12), 10)
            pic.blit(st, (sx - 12, sy - 12))
        # ingredients card
        card = pygame.Rect(420, 150, 350, 226)
        self._panel(pic, card, 215)
        K.blit_text(pic, K.font(16, True), "You'll need", (150, 70, 50),
                    (card.x + 18, card.y + 20), align="left")
        need = cooking.RECIPES[fid]
        have_fn = getattr(g, "_kitchen_count", None) or g._count_all
        ok_all = True
        y = card.y + 40
        for it, q in need.items():
            have = have_fn(it)
            ok = have >= q
            ok_all = ok_all and ok
            try:
                pic.blit(assets.item_icon(it), (card.x + 16, y))
            except Exception:
                pass
            K.blit_text(pic, K.font(15, True), f"{q} x {cooking.label(it)}", (60, 40, 30),
                        (card.x + 54, y + 14), align="left")
            K.blit_text(pic, K.font(14, True), f"have {have}",
                        (70, 140, 60) if ok else (200, 70, 60), (card.right - 16, y + 14),
                        align="right")
            y += 34
        stats = f"+{f['energy']} energy   +{f['health']} HP"
        bt = cooking.buff_text(fid)
        if bt:
            stats += f"   {bt}"
        K.blit_text(pic, K.font(14, True), stats, (90, 110, 60), (card.centerx, card.bottom - 48))
        msg = ("You have everything - head to the Stove!" if ok_all
               else "Stock the fridge and give it a try!")
        K.blit_text(pic, K.font(15, True), msg, (70, 140, 60) if ok_all else (150, 90, 60),
                    (card.centerx, card.bottom - 22))

    # CH 9 -- the two of you
    def _ch_us(self, pic):
        g = self.g
        top, bot, acc = _PAL["us"]
        pic.blit(_cached_grad("us", SCR_W, SCR_H, top, bot), (0, 0))
        for i in range(16):                                 # floating hearts
            ph = (self.clock * 0.12 + i / 16) % 1
            x = (i * 151) % SCR_W + math.sin(self.clock + i) * 10
            y = SCR_H + 20 - ph * (SCR_H + 60)
            r = 5 + (i % 3) * 2
            col = (240, 170, 200)
            pygame.draw.circle(pic, col, (int(x - r * 0.5), int(y)), r // 2 + 2)
            pygame.draw.circle(pic, col, (int(x + r * 0.5), int(y)), r // 2 + 2)
            pygame.draw.polygon(pic, col, [(x - r - 1, y + 1), (x + r + 1, y + 1), (x, y + r + 4)])
        names = [p.name for p in g.players]
        K.blit_text(pic, K.font(28, True), f"{names[0]}  &  {names[1]}", (255, 255, 255),
                    (SCR_W // 2, 92))
        try:                                                # the two farmers, hopping
            from . import assets
            for i, p in enumerate(g.players):
                spr = assets.player_sprite(p.appearance)
                big = pygame.transform.scale(spr, (spr.get_width() * 2, spr.get_height() * 2))
                hop = abs(math.sin(self.clock * 2.4 + i * 1.3)) * 6
                pic.blit(big, big.get_rect(midbottom=(SCR_W // 2 - 70 + i * 140, 222 - hop)))
            hx, hy = SCR_W // 2, 168 + math.sin(self.clock * 3) * 3
            for dx in (-7, 7):
                pygame.draw.circle(pic, (236, 80, 120), (int(hx + dx), int(hy)), 9)
            pygame.draw.polygon(pic, (236, 80, 120),
                                [(hx - 16, hy + 3), (hx + 16, hy + 3), (hx, hy + 20)])
        except Exception:
            pass
        life = getattr(g, "stats_life", {}) or {}
        rows = [("Days together", int(life.get("days", 0)) + 1),
                ("Love boosts", life.get("love", 0)),
                ("Gifts to each other", life.get("partner_gifts", 0)),
                ("Crops harvested", life.get("crops", 0)),
                ("Fish caught", life.get("fish", 0)),
                ("Meals cooked", life.get("cooked", 0))]
        box = pygame.Rect(60, 238, SCR_W - 120, 150)
        self._panel(pic, box, 210)
        f, fb = K.font(15, True), K.font(22, True)
        for i, (lab, v) in enumerate(rows):
            cx = box.x + 24 + (i % 3) * (box.w - 40) // 3
            cy = box.y + 18 + (i // 3) * 66
            K.blit_text(pic, f, lab, (130, 70, 100), (cx, cy + 6), align="left")
            K.blit_text(pic, fb, f"{int(v):,}", (200, 70, 110), (cx, cy + 34), align="left")
