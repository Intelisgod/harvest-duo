"""Animated title-screen scenery for the main menu (UI & Rendering, Chat 6).

A cosy procedural diorama drawn behind the menu: a sky that cycles
day -> golden hour -> sunset -> back, a drifting sun, puffy clouds, three
parallax hill layers, a farmhouse with chimney smoke, swaying crop rows, the
two farmers (the couple's own looks when available) idling with a little heart
floating between them, and falling petals.

Everything static is built once and cached; per frame we only do a handful of
polygons / blits (well under 2 ms).
"""
import math
import random
import pygame
from .settings import SCREEN_W, SCREEN_H
from . import assets

# sky keyframes: (top, bottom) colours; the cycle loops smoothly
_SKY = [((112, 184, 240), (212, 238, 250)),      # bright day
        ((120, 176, 236), (250, 232, 196)),      # golden hour
        ((142, 136, 204), (255, 186, 150)),      # sunset
        ((150, 150, 214), (255, 206, 170)),      # soft dusk (never dark)
        ((112, 184, 240), (212, 238, 250))]      # back to day
_CYCLE = 48.0                                    # seconds for one full loop

# hill layers: (base y, amplitude pairs, colour day, colour sunset, speed px/s)
_HILLS = [
    (430, ((34, 2, 0.4), (18, 5, 1.7)), (156, 206, 170), (190, 150, 170), 5.0),
    (482, ((26, 3, 2.1), (14, 7, 0.3)), (120, 186, 124), (170, 132, 128), 11.0),
    (548, ((20, 2, 4.0), (10, 9, 1.2)), (98, 168, 102), (140, 118, 96), 20.0),
]


def _lerp(a, b, f):
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def _sky_at(t):
    u = (t % _CYCLE) / _CYCLE * (len(_SKY) - 1)
    i = int(u)
    f = u - i
    f = f * f * (3 - 2 * f)
    top = _lerp(_SKY[i][0], _SKY[i + 1][0], f)
    bot = _lerp(_SKY[i][1], _SKY[i + 1][1], f)
    return top, bot


def _warmth(t):
    """0 at day .. 1 at sunset (for tinting hills / sun)."""
    ph = (t % _CYCLE) / _CYCLE
    return max(0.0, math.sin(ph * math.pi)) ** 1.5


class TitleScene:
    def __init__(self, game=None):
        self.g = game
        rnd = random.Random(7)
        self.clouds = [{"x": rnd.uniform(0, SCREEN_W), "y": rnd.uniform(40, 250),
                        "s": rnd.uniform(6, 16), "k": rnd.randint(0, 2)} for _ in range(7)]
        self.petals = [{"x": rnd.uniform(0, SCREEN_W), "y": rnd.uniform(-SCREEN_H, SCREEN_H),
                        "vx": rnd.uniform(10, 30), "vy": rnd.uniform(18, 40),
                        "p": rnd.uniform(0, 6.28), "c": rnd.randint(0, 2)} for _ in range(26)]
        self.smoke = []
        self._smoke_t = 0.0
        self._cloud_surfs = [self._make_cloud(i) for i in range(3)]
        self._house = None
        self._farmers = None
        self._ground = None
        self._hill_pts = [self._hill_profile(i) for i in range(len(_HILLS))]

    # ---------------------------------------------------------- builders
    @staticmethod
    def _make_cloud(k):
        w, h = (150, 60) if k == 0 else ((110, 46) if k == 1 else (190, 70))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        rnd = random.Random(k * 13 + 1)
        base = h * 0.62
        pygame.draw.ellipse(s, (226, 232, 246, 200), (6, base - 8, w - 12, 22))
        for _ in range(6):
            r = rnd.randint(int(h * 0.26), int(h * 0.42))
            cx = rnd.randint(r, w - r)
            pygame.draw.circle(s, (255, 255, 255, 235), (cx, int(base - r * 0.35)), r)
        pygame.draw.ellipse(s, (255, 255, 255, 240), (10, base - 12, w - 20, 18))
        return s

    @staticmethod
    def _hill_profile(i):
        base, amps, _, _, _ = _HILLS[i]
        pts = []
        for x in range(0, SCREEN_W + 1, 16):
            y = base
            for a, k, ph in amps:
                y -= a * math.sin(x / SCREEN_W * math.tau * k + ph)
            pts.append(y)
        return pts          # periodic over SCREEN_W (integer k)

    def _farmer_frames(self):
        if self._farmers is not None:
            return self._farmers
        looks = getattr(self.g, "look", None) or [{}, {"hair_style": 1, "shirt_color": 5,
                                                         "hair_color": 3, "skin": 1}]
        out = []
        for i in range(2):
            look = looks[i] if i < len(looks) else {}
            try:
                fr = assets.frames_for(look)
            except Exception:
                fr = assets.frames_for({})
            face = "right" if i == 0 else "left"
            fl = fr.get(face) or fr.get("down")
            out.append([pygame.transform.scale(f, (f.get_width() * 2, f.get_height() * 2))
                        for f in fl])
        self._farmers = out
        return out

    def _house_surf(self):
        if self._house is None:
            try:
                self._house = assets.building_sprite(5 * 40, 4 * 38, (238, 214, 186),
                                                     (206, 108, 104), "Home")
            except Exception:
                self._house = pygame.Surface((200, 150), pygame.SRCALPHA)
        return self._house

    def _ground_surf(self):
        """Foreground meadow with tilled crop rows + fence (static part)."""
        if self._ground is not None:
            return self._ground
        h = SCREEN_H - 560
        s = pygame.Surface((SCREEN_W, h), pygame.SRCALPHA)
        s.fill((124, 190, 112))
        rnd = random.Random(3)
        for _ in range(260):                               # grass tufts
            x, y = rnd.randint(0, SCREEN_W), rnd.randint(4, h)
            pygame.draw.line(s, (100, 166, 96), (x, y), (x + 1, y - 5), 2)
        # tilled crop rows (perspective-ish strips)
        for r in range(3):
            y = 40 + r * 34
            pygame.draw.rect(s, (150, 108, 78), (330, y, 600, 20), border_radius=8)
            pygame.draw.rect(s, (126, 90, 64), (330, y + 14, 600, 6), border_radius=4)
        # little flowers
        for _ in range(40):
            x, y = rnd.randint(0, SCREEN_W), rnd.randint(8, h - 4)
            if 320 < x < 940 and 30 < y < 150:
                continue
            c = [(248, 176, 200), (252, 230, 150), (214, 196, 246)][rnd.randint(0, 2)]
            pygame.draw.circle(s, c, (x, y), 3)
            pygame.draw.circle(s, (255, 250, 230), (x, y), 1)
        # fence along the top edge of the field
        for x in range(0, SCREEN_W, 46):
            pygame.draw.rect(s, (196, 150, 104), (x + 4, 2, 7, 26), border_radius=2)
            pygame.draw.rect(s, (160, 116, 78), (x + 4, 2, 7, 26), 1, border_radius=2)
        pygame.draw.rect(s, (206, 162, 114), (0, 8, SCREEN_W, 5))
        pygame.draw.rect(s, (206, 162, 114), (0, 18, SCREEN_W, 4))
        self._ground = s
        return s

    # ---------------------------------------------------------- update / draw
    def update(self, dt, t):
        for c in self.clouds:
            c["x"] += c["s"] * dt
            if c["x"] > SCREEN_W + 40:
                c["x"] = -220
        for p in self.petals:
            p["x"] += (p["vx"] + math.sin(t * 1.3 + p["p"]) * 14) * dt
            p["y"] += p["vy"] * dt
            if p["y"] > SCREEN_H + 10 or p["x"] > SCREEN_W + 10:
                p["y"] = random.uniform(-60, -10)
                p["x"] = random.uniform(-100, SCREEN_W)
        self._smoke_t += dt
        if self._smoke_t > 0.5:
            self._smoke_t = 0.0
            self.smoke.append([0.0, random.uniform(-3, 3)])
        for s in self.smoke:
            s[0] += dt
        self.smoke = [s for s in self.smoke if s[0] < 4.0]

    def draw(self, surf, t):
        top, bot = _sky_at(t)
        warm = _warmth(t)
        # sky gradient (bands)
        H = 560
        band = 8
        for y in range(0, H, band):
            f = y / H
            pygame.draw.rect(surf, _lerp(top, bot, f), (0, y, SCREEN_W, band))
        # sun: rises back up at day, sinks + reddens toward sunset
        ph = (t % _CYCLE) / _CYCLE
        sy = 110 + int(math.sin(ph * math.pi) * 170)
        sx = 1110 - int(ph * 90)
        scol = _lerp((255, 236, 150), (255, 150, 110), warm)
        g = assets.hud.glow(110, scol, 90)
        surf.blit(g, (sx - 110, sy - 110))
        pygame.draw.circle(surf, scol, (sx, sy), 42)
        pygame.draw.circle(surf, _lerp(scol, (255, 255, 240), 0.5), (sx - 10, sy - 10), 16)
        # clouds (tinted warm by blending alpha)
        for c in self.clouds:
            surf.blit(self._cloud_surfs[c["k"]], (int(c["x"]), int(c["y"])))
        # parallax hills
        for i, (base, amps, cday, csun, spd) in enumerate(_HILLS):
            col = _lerp(cday, csun, warm * 0.55)
            prof = self._hill_pts[i]
            off = (t * spd) % SCREEN_W
            n = len(prof) - 1
            pts = []
            for j in range(n + 2):
                x = j * 16 - off
                pts.append((x, prof[j % n]))
            # wrap: draw twice so the strip covers the screen
            for shift in (0, SCREEN_W):
                poly = [(x + shift, y) for x, y in pts]
                if poly[0][0] > SCREEN_W or poly[-1][0] < 0:
                    continue
                poly = [(poly[0][0], SCREEN_H)] + poly + [(poly[-1][0], SCREEN_H)]
                pygame.draw.polygon(surf, col, poly)
            if i == 0:           # a few distant trees on the far hill
                for k in range(9):
                    tx = (k * 157 - off * 1.0) % (SCREEN_W + 60) - 30
                    ty = prof[int((tx + off) % SCREEN_W) // 16] + 6
                    tc = _lerp((110, 170, 120), (150, 120, 140), warm * 0.5)
                    pygame.draw.rect(surf, (140, 110, 90), (tx - 2, ty - 10, 4, 12))
                    pygame.draw.circle(surf, tc, (int(tx), int(ty - 16)), 11)
        # farmhouse on the near hill (left) + chimney smoke
        house = self._house_surf()
        hx, hy = 70, 560 - house.get_height() + 14
        surf.blit(assets.hud.soft_shadow(house.get_width() + 20, 24, 60),
                  (hx - 10, 560 + 2))
        surf.blit(house, (hx, hy))
        cx, cy = hx + int(house.get_width() * 0.70) + 7, hy + 4
        for age, dx in self.smoke:
            r = int(5 + age * 5)
            a = max(0, int(150 * (1 - age / 4.0)))
            puff = assets.hud.glow(max(4, r), (250, 250, 250), a)
            surf.blit(puff, (cx + int(dx + age * 10) - puff.get_width() // 2,
                             cy - int(age * 26) - puff.get_height() // 2))
        # foreground meadow + crop rows
        gy = 560
        surf.blit(self._ground_surf(), (0, gy))
        for r in range(3):
            y = gy + 46 + r * 34
            for k in range(14):
                x = 350 + k * 42
                sway = math.sin(t * 2 + k * 0.6 + r) * 2.5
                pygame.draw.line(surf, (74, 134, 70), (x, y + 4), (x + sway, y - 8), 3)
                pygame.draw.ellipse(surf, (112, 186, 96), (x + sway - 7, y - 12, 8, 5))
                pygame.draw.ellipse(surf, (112, 186, 96), (x + sway, y - 13, 8, 5))
                if (k + r) % 3 == 0:
                    col = [(236, 120, 96), (246, 204, 96), (206, 128, 214)][r]
                    pygame.draw.circle(surf, col, (int(x + sway), y - 14), 4)
        # the two farmers + a heart floating between them
        frames = self._farmer_frames()
        fx0, fy = 1000, gy + 22
        for i, fl in enumerate(frames):
            fr = fl[0]
            bob = int(abs(math.sin(t * 2.2 + i * 1.3)) * 3)
            x = fx0 + i * 92
            surf.blit(assets.hud.soft_shadow(56, 16, 70), (x + 20, fy + fr.get_height() - 14))
            surf.blit(fr, (x, fy - bob))
        hb = (math.sin(t * 3) + 1) * 0.5
        hsz = int(18 + hb * 6)
        heart = assets.hud.heart_icon(hsz, (244, 104, 136))
        hx = fx0 + 92 // 2 + 48 - hsz // 2
        hy2 = fy - 14 - int(math.sin(t * 1.6) * 6)
        surf.blit(assets.hud.glow(hsz, (255, 150, 180), 70), (hx + hsz // 2 - hsz, hy2 + hsz // 2 - hsz))
        surf.blit(heart, (hx, hy2))
        # petals
        pcs = [(250, 190, 210), (255, 236, 244), (246, 214, 150)]
        for p in self.petals:
            w = 3 + int(abs(math.sin(t * 3 + p["p"])) * 3)
            pygame.draw.ellipse(surf, pcs[p["c"]], (int(p["x"]), int(p["y"]), w, 4))
