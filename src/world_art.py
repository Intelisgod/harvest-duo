"""Procedural art for the World domain (Chat 5, 2026-09 "level-up").

Farm beautification props, the Flower Meadow (Promise Tree, lookout, flower
fields), mine hazards (lava pools / void rifts), ancient-ruins decor and the
outdoor-decor catalogue sprites.  Everything is drawn with pygame primitives in
the same cosy pastel pixel style as ``src/assets`` and cached on first use.

Seasonal props read the module-level ``SEASON`` (set every frame by
``WorldMixin``); the Promise Tree reads ``CARVE`` (both players' initials once
the couple has made their first promise).  Cache keys include those values, so a
change simply picks (or builds once) another cached surface.

Registered as props from ``systems/world_system.py`` via ``assets.register_prop``.
"""
import math
import random
import pygame
from .settings import TILE

SEASON = "Spring"      # updated by WorldMixin (Spring/Summer/Fall/Winter)
CARVE = ""             # "A+B" once the Promise Tree has been carved
TIER = 0               # Promise Tree adornment: 1 = ribbons (7 promises), 2 = lanterns (30),
                       # 3 = golden blossoms (100) -- set by WorldMixin

_cache = {}


def _surf(w=TILE, h=TILE):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _dk(c, f=0.75):
    return tuple(max(0, int(v * f)) for v in c[:3])


def _lt(c, f=1.2):
    return tuple(min(255, int(v * f)) for v in c[:3])


def _cached(key, fn):
    s = _cache.get(key)
    if s is None:
        s = fn()
        _cache[key] = s
    return s


def _flower(s, x, y, col, r=2):
    for a in range(0, 360, 72):
        rad = math.radians(a)
        pygame.draw.circle(s, col, (int(x + math.cos(rad) * r), int(y + math.sin(rad) * r)), r)
    pygame.draw.circle(s, (255, 246, 206), (int(x), int(y)), max(1, r - 1))


_FLOWER_COLS = [(246, 170, 196), (252, 224, 140), (206, 186, 244), (250, 250, 250),
                (170, 214, 250), (255, 186, 150)]


# ============================================================ farm / meadow ground
def cobble(variant=0):
    """Flat stepping-stone path decal (laid on the COBBLE tile colour)."""
    def mk():
        s = _surf()
        rng = random.Random(40 + variant)
        stones = [(10, 11, 15, 11), (30, 9, 14, 12), (19, 26, 16, 12), (38, 28, 12, 11),
                  (6, 32, 12, 11), (27, 40, 14, 8), (8, 44, 10, 5)]
        for (x, y, w, h) in stones:
            x += rng.randint(-2, 2)
            y += rng.randint(-2, 2)
            base = rng.choice([(214, 206, 190), (204, 198, 186), (222, 214, 196)])
            pygame.draw.ellipse(s, _dk(base, 0.78), (x - w // 2, y - h // 2 + 1, w, h))
            pygame.draw.ellipse(s, base, (x - w // 2, y - h // 2, w, h - 1))
            pygame.draw.ellipse(s, _lt(base, 1.08), (x - w // 2 + 2, y - h // 2 + 1, w // 2, 3))
        return s
    return _cached(("cobble", variant), mk)


def dock():
    """Weathered plank decking for the farm pond's little fishing dock."""
    def mk():
        s = _surf()
        for i in range(4):
            x = 4 + i * 10
            c = (184, 140, 92) if i % 2 == 0 else (168, 126, 82)
            pygame.draw.rect(s, (120, 86, 56), (x, 0, 10, TILE))
            pygame.draw.rect(s, c, (x + 1, 0, 8, TILE))
            pygame.draw.circle(s, (110, 80, 52), (x + 5, 6), 1)
            pygame.draw.circle(s, (110, 80, 52), (x + 5, TILE - 7), 1)
        for x in (1, TILE - 5):                                   # side posts
            pygame.draw.rect(s, (104, 74, 48), (x, 8, 4, 12), border_radius=1)
            pygame.draw.rect(s, (104, 74, 48), (x, 30, 4, 12), border_radius=1)
        return s
    return _cached("dock", mk)


def lily_pad(flower=False):
    def mk():
        s = _surf()
        for (x, y, r) in ((14, 16, 8), (34, 30, 10), (18, 38, 6)):
            pygame.draw.circle(s, (70, 140, 86), (x, y + 1), r)
            pygame.draw.circle(s, (108, 184, 110), (x, y), r)
            pygame.draw.polygon(s, (62, 116, 188), [(x, y), (x + r, y - 3), (x + r, y + 3)])
            pygame.draw.line(s, (140, 206, 138), (x - r + 3, y), (x, y), 1)
        if flower:
            _flower(s, 34, 27, (250, 176, 206), 3)
            pygame.draw.circle(s, (255, 236, 150), (34, 27), 2)
        return s
    return _cached(("lily", flower), mk)


def reeds():
    def mk():
        s = _surf(TILE, TILE + 14)
        oy = TILE + 14
        rng = random.Random(3)
        for i in range(7):
            x = 8 + i * 5 + rng.randint(-1, 1)
            h = rng.randint(22, 38)
            lean = rng.randint(-3, 3)
            pygame.draw.line(s, (96, 150, 84), (x, oy - 3), (x + lean, oy - h), 2)
            if i % 2 == 0:
                pygame.draw.rect(s, (136, 96, 62), (x + lean - 2, oy - h - 1, 4, 9), border_radius=2)
        for i in range(5):                                  # blade leaves
            x = 6 + i * 9
            pygame.draw.polygon(s, (120, 178, 100), [(x, oy - 2), (x + 3, oy - 2), (x + 6, oy - 22)])
        return s
    return _cached("reeds", mk)


def fence(kind="h"):
    """Low decorative split-rail fence piece (h = along a row, v = down a column,
    p = lone post).  Drawn flat so the rail reads as a border line.  Winter adds
    little snow caps."""
    snowy = SEASON == "Winter"

    def mk():
        s = _surf()
        wood, wdk, whi = (178, 136, 92), (128, 94, 62), (206, 168, 120)
        if kind == "h":
            for py in (14, 26):
                pygame.draw.rect(s, wdk, (0, py + 1, TILE, 4))
                pygame.draw.rect(s, wood, (0, py, TILE, 4))
                pygame.draw.line(s, whi, (0, py), (TILE, py), 1)
            for px in (4, TILE - 10):
                pygame.draw.rect(s, wdk, (px, 6, 7, 30), border_radius=2)
                pygame.draw.rect(s, wood, (px, 5, 6, 30), border_radius=2)
                pygame.draw.rect(s, whi, (px + 1, 5, 2, 28))
        elif kind == "v":
            for px in (18, 28):
                pygame.draw.rect(s, wdk, (px + 1, 0, 3, TILE))
                pygame.draw.rect(s, wood, (px, 0, 3, TILE))
            pygame.draw.rect(s, wdk, (20, 8, 7, 26), border_radius=2)
            pygame.draw.rect(s, wood, (20, 7, 6, 26), border_radius=2)
        else:
            pygame.draw.rect(s, wdk, (20, 8, 8, 28), border_radius=2)
            pygame.draw.rect(s, wood, (20, 7, 7, 28), border_radius=2)
            pygame.draw.rect(s, whi, (21, 7, 2, 26))
        if snowy:
            snow = (246, 249, 255)
            if kind == "h":
                pygame.draw.line(s, snow, (0, 13), (TILE, 13), 2)
                for px in (4, TILE - 10):
                    pygame.draw.ellipse(s, snow, (px - 1, 2, 9, 5))
            elif kind == "v":
                pygame.draw.ellipse(s, snow, (19, 4, 9, 5))
                for px in (18, 28):
                    pygame.draw.line(s, snow, (px, 0), (px, TILE), 1)
            else:
                pygame.draw.ellipse(s, snow, (19, 4, 10, 5))
        return s
    return _cached(("fence", kind, snowy), mk)


def fruit_tree():
    """Orchard tree -- blossom in spring, red apples in summer, amber leaves with
    ripe fruit in fall, bare snowy branches in winter."""
    season = SEASON

    def mk():
        s = _surf(TILE, TILE * 2)
        cx = TILE // 2
        pygame.draw.ellipse(s, (0, 0, 0, 50), (cx - 16, TILE * 2 - 10, 32, 9))
        pygame.draw.rect(s, (144, 104, 72), (cx - 5, TILE + 16, 10, TILE - 20), border_radius=2)
        pygame.draw.rect(s, (120, 86, 60), (cx - 5, TILE + 16, 4, TILE - 20), border_radius=2)
        if season == "Winter":
            for (dx, dy, ex, ey) in ((0, TILE + 18, -14, TILE - 6), (0, TILE + 14, 13, TILE - 8),
                                     (0, TILE + 20, 2, TILE - 16), (-8, TILE + 4, -16, TILE - 10)):
                pygame.draw.line(s, (120, 90, 66), (cx + dx, dy), (cx + ex, ey), 3)
            for (x, y) in ((cx - 14, TILE - 8), (cx + 13, TILE - 10), (cx + 2, TILE - 18)):
                pygame.draw.ellipse(s, (246, 248, 252), (x - 6, y - 2, 12, 5))
            return s
        leaf = {"Spring": ((150, 200, 140), (178, 220, 164), (206, 236, 196)),
                "Summer": ((96, 162, 100), (120, 186, 118), (156, 210, 148)),
                "Fall": ((214, 140, 72), (232, 172, 88), (246, 204, 120))}.get(
            season, ((108, 172, 112), (130, 192, 134), (162, 214, 162)))
        pygame.draw.circle(s, leaf[0], (cx, TILE + 2), 20)
        pygame.draw.circle(s, leaf[1], (cx - 9, TILE - 3), 14)
        pygame.draw.circle(s, leaf[1], (cx + 9, TILE - 1), 14)
        pygame.draw.circle(s, leaf[2], (cx - 1, TILE - 10), 10)
        if season == "Spring":
            for (x, y) in ((cx - 12, TILE - 4), (cx + 6, TILE - 12), (cx + 12, TILE + 6),
                           (cx - 4, TILE + 10), (cx - 14, TILE + 8), (cx + 2, TILE)):
                _flower(s, x, y, (250, 196, 216), 2)
        else:
            fruit = (222, 70, 70) if season == "Summer" else (240, 150, 50)
            for (x, y) in ((cx - 11, TILE + 2), (cx + 8, TILE - 6), (cx + 12, TILE + 8),
                           (cx - 3, TILE + 12), (cx - 6, TILE - 8)):
                pygame.draw.circle(s, _dk(fruit, 0.75), (x, y + 1), 4)
                pygame.draw.circle(s, fruit, (x, y), 4)
                pygame.draw.circle(s, (255, 236, 220), (x - 1, y - 2), 1)
        return s
    return _cached(("fruit_tree", season), mk)


def wildflowers(variant=0):
    season = SEASON

    def mk():
        s = _surf()
        rng = random.Random(90 + variant)
        if season == "Winter":
            for _ in range(4):
                x, y = rng.randint(8, 40), rng.randint(10, 40)
                pygame.draw.ellipse(s, (236, 242, 250), (x - 7, y - 3, 14, 7))
                pygame.draw.ellipse(s, (255, 255, 255), (x - 5, y - 3, 9, 4))
            return s
        cols = _FLOWER_COLS if season != "Fall" else [(236, 150, 70), (220, 110, 90),
                                                      (246, 204, 110), (196, 150, 210)]
        for _ in range(9):
            x, y = rng.randint(6, 42), rng.randint(8, 42)
            pygame.draw.line(s, (104, 160, 96), (x, y + 2), (x, y + 7), 1)
            _flower(s, x, y, rng.choice(cols), 2)
        return s
    return _cached(("wildflowers", variant, season), mk)


def meadow_flowers(variant=0, layout=0):
    """Dense pastel flower-field patch for the meadow (seasonal).  ``variant`` =
    colour band, ``layout`` = scatter pattern (several so drifts never look stamped)."""
    season = SEASON

    def mk():
        s = _surf()
        rng = random.Random(200 + variant * 17 + layout * 101)
        if season == "Winter":
            for _ in range(5):
                x, y = rng.randint(6, 42), rng.randint(8, 42)
                pygame.draw.ellipse(s, (228, 236, 248), (x - 8, y - 3, 16, 7))
                pygame.draw.ellipse(s, (255, 255, 255), (x - 6, y - 3, 10, 4))
            if variant % 2 == 0:                               # a hardy snowdrop
                pygame.draw.line(s, (110, 160, 110), (24, 30), (24, 22), 1)
                pygame.draw.ellipse(s, (250, 252, 255), (21, 18, 6, 6))
            return s
        pal = {"Spring": [(250, 190, 214), (255, 232, 150), (214, 196, 248), (255, 255, 255)],
               "Summer": [(250, 150, 170), (255, 214, 96), (170, 206, 250), (255, 176, 120)],
               "Fall": [(238, 150, 72), (214, 102, 96), (250, 206, 110), (190, 150, 214)]}
        cols = pal.get(season, _FLOWER_COLS)
        main = cols[variant % len(cols)]
        for _ in range(9 + layout * 2):
            x, y = rng.randint(3, 45), rng.randint(5, 44)
            pygame.draw.line(s, (98, 158, 92), (x, y + 2), (x + rng.randint(-1, 1), y + 8), 1)
            c = main if rng.random() < 0.6 else rng.choice(cols)
            _flower(s, x, y, c, 2 if rng.random() < 0.7 else 3)
        for _ in range(3):                                   # grass tufts between blooms
            x, y = rng.randint(4, 44), rng.randint(10, 44)
            pygame.draw.line(s, (116, 170, 106), (x, y), (x - 1, y - 5), 1)
            pygame.draw.line(s, (116, 170, 106), (x + 2, y), (x + 3, y - 4), 1)
        return s
    return _cached(("mflowers", variant, layout, season), mk)


def stump():
    def mk():
        s = _surf()
        pygame.draw.ellipse(s, (0, 0, 0, 50), (8, 34, 32, 10))
        pygame.draw.rect(s, (136, 98, 66), (12, 20, 24, 20), border_radius=4)
        pygame.draw.rect(s, (112, 80, 54), (12, 20, 7, 20), border_radius=3)
        pygame.draw.ellipse(s, (206, 172, 124), (11, 14, 26, 12))
        pygame.draw.ellipse(s, (170, 134, 92), (15, 16, 18, 8), 1)
        pygame.draw.ellipse(s, (170, 134, 92), (20, 18, 8, 4), 1)
        pygame.draw.circle(s, (130, 190, 120), (34, 36), 4)        # tiny moss
        return s
    return _cached("stump", mk)


def boulder():
    def mk():
        s = _surf()
        pygame.draw.ellipse(s, (0, 0, 0, 50), (5, 34, 38, 10))
        pygame.draw.ellipse(s, (128, 130, 142), (6, 14, 36, 28))
        pygame.draw.ellipse(s, (164, 166, 178), (8, 12, 32, 24))
        pygame.draw.ellipse(s, (196, 198, 210), (14, 15, 14, 7))
        pygame.draw.line(s, (128, 130, 142), (24, 22), (30, 32), 1)
        pygame.draw.circle(s, (132, 188, 120), (12, 36), 4)
        return s
    return _cached("boulder", mk)


def lamp_post():
    def mk():
        s = _surf(TILE, TILE * 2)
        cx, oy = TILE // 2, TILE * 2
        iron, idk = (74, 72, 86), (50, 48, 60)
        pygame.draw.ellipse(s, (0, 0, 0, 50), (cx - 11, oy - 9, 22, 7))
        pygame.draw.rect(s, idk, (cx - 7, oy - 10, 14, 6), border_radius=2)
        pygame.draw.rect(s, iron, (cx - 2, oy - 58, 5, 50))
        pygame.draw.line(s, (110, 108, 124), (cx - 1, oy - 56), (cx - 1, oy - 12), 1)
        pygame.draw.polygon(s, iron, [(cx - 11, oy - 62), (cx + 11, oy - 62), (cx, oy - 72)])
        pygame.draw.rect(s, (255, 226, 150), (cx - 7, oy - 62, 14, 14), border_radius=2)
        pygame.draw.rect(s, (255, 246, 206), (cx - 4, oy - 60, 6, 9), border_radius=2)
        pygame.draw.rect(s, idk, (cx - 8, oy - 63, 16, 16), 2, border_radius=2)
        pygame.draw.rect(s, idk, (cx - 9, oy - 48, 18, 3))
        return s
    return _cached("lamp_post", mk)


def picnic_blanket():
    def mk():
        s = _surf(TILE * 2, TILE)
        W = TILE * 2
        pygame.draw.rect(s, (0, 0, 0, 40), (6, 10, W - 10, 34), border_radius=4)
        pygame.draw.rect(s, (250, 244, 236), (4, 7, W - 10, 34), border_radius=4)
        for i in range(0, W - 10, 10):
            pygame.draw.rect(s, (232, 110, 116), (4 + i, 7, 5, 34))
        for j in range(0, 34, 10):
            r = pygame.Rect(4, 7 + j, W - 10, 5)
            ov = _surf(r.w, r.h)
            ov.fill((232, 110, 116, 150))
            s.blit(ov, r.topleft)
        pygame.draw.rect(s, (200, 90, 96), (4, 7, W - 10, 34), 1, border_radius=4)
        # basket + a little plate of fruit
        pygame.draw.rect(s, (186, 138, 84), (58, 14, 22, 15), border_radius=3)
        pygame.draw.arc(s, (140, 100, 60), (60, 5, 18, 18), 0, math.pi, 2)
        for k in range(4):
            pygame.draw.line(s, (150, 108, 64), (60 + k * 5, 15), (60 + k * 5, 28), 1)
        pygame.draw.ellipse(s, (255, 255, 255), (16, 22, 18, 10))
        pygame.draw.circle(s, (222, 70, 70), (22, 26), 3)
        pygame.draw.circle(s, (250, 200, 80), (28, 26), 3)
        return s
    return _cached("picnic_blanket", mk)


def bench(width=2):
    """Wooden park bench, ``width`` tiles wide (2 = picnic / couple bench)."""
    def mk():
        W = TILE * width
        s = _surf(W, TILE)
        wood, wdk, whi = (176, 128, 84), (126, 90, 58), (206, 164, 116)
        pygame.draw.ellipse(s, (0, 0, 0, 45), (4, 36, W - 8, 9))
        for lx in (8, W - 14):
            pygame.draw.rect(s, (84, 76, 88), (lx, 28, 5, 13))
        pygame.draw.rect(s, wdk, (4, 8, W - 8, 5), border_radius=2)        # backrest rails
        pygame.draw.rect(s, wood, (4, 7, W - 8, 4), border_radius=2)
        pygame.draw.rect(s, wood, (4, 16, W - 8, 4), border_radius=2)
        pygame.draw.rect(s, wdk, (4, 26, W - 8, 5), border_radius=2)       # seat
        pygame.draw.rect(s, whi, (4, 24, W - 8, 4), border_radius=2)
        for lx in (8, W - 14):
            pygame.draw.rect(s, (84, 76, 88), (lx, 6, 4, 22))
        if width >= 2:                                                      # heart carving
            hx, hy = W // 2, 13
            pygame.draw.circle(s, (236, 130, 150), (hx - 2, hy), 2)
            pygame.draw.circle(s, (236, 130, 150), (hx + 2, hy), 2)
            pygame.draw.polygon(s, (236, 130, 150), [(hx - 4, hy + 1), (hx + 4, hy + 1), (hx, hy + 5)])
        return s
    return _cached(("bench", width), mk)


def tree_swing():
    def mk():
        s = _surf(TILE, TILE * 2)
        rope = (206, 184, 140)
        pygame.draw.line(s, rope, (12, 0), (12, TILE + 26), 2)
        pygame.draw.line(s, rope, (36, 0), (36, TILE + 26), 2)
        pygame.draw.rect(s, (126, 90, 58), (7, TILE + 26, 34, 6), border_radius=2)
        pygame.draw.rect(s, (178, 132, 86), (7, TILE + 24, 34, 5), border_radius=2)
        _flower(s, 12, 20, (250, 190, 210), 2)
        _flower(s, 36, 34, (255, 230, 150), 2)
        pygame.draw.ellipse(s, (0, 0, 0, 40), (8, TILE * 2 - 9, 32, 6))
        return s
    return _cached("tree_swing", mk)


def swing_frame(off=0):
    """Rope swing with the seat pushed ``off`` px sideways (animated by WorldMixin)."""
    off = max(-10, min(10, int(off)))

    def mk():
        s = _surf(TILE, TILE * 2)
        rope = (206, 184, 140)
        by = TILE + 26
        pygame.draw.line(s, rope, (12, 0), (12 + off, by), 2)
        pygame.draw.line(s, rope, (36, 0), (36 + off, by), 2)
        pygame.draw.rect(s, (126, 90, 58), (7 + off, by, 34, 6), border_radius=2)
        pygame.draw.rect(s, (178, 132, 86), (7 + off, by - 2, 34, 5), border_radius=2)
        _flower(s, 12 + off // 3, 20, (250, 190, 210), 2)
        _flower(s, 36 + off // 2, 34, (255, 230, 150), 2)
        pygame.draw.ellipse(s, (0, 0, 0, 40), (8 + off // 2, TILE * 2 - 9, 32, 6))
        return s
    return _cached(("swing", off), mk)


def hill_edge(side="s"):
    """Soft grassy slope that makes the meadow's lookout read as a raised hill:
    a shaded gradient on the tile's south (s) / west (w) edge (sw = corner)."""
    season = SEASON

    def mk():
        s = _surf()
        if season == "Winter":
            steps = [(214, 222, 238, 70), (200, 210, 228, 110), (186, 198, 220, 150)]
            lip = (255, 255, 255, 170)
        else:
            steps = [(96, 150, 92, 45), (86, 138, 84, 80), (76, 126, 76, 115)]
            lip = (196, 232, 182, 150)
        band = 24
        for i, c in enumerate(steps):
            d = band - i * 8                         # deeper shade toward the foot
            if "s" in side:
                ov = _surf(TILE, d)
                ov.fill(c)
                s.blit(ov, (0, TILE - d))
            if "w" in side:
                ov = _surf(d, TILE)
                ov.fill(c)
                s.blit(ov, (0, 0))
        if "s" in side:
            pygame.draw.line(s, lip, (0, TILE - band), (TILE, TILE - band), 1)
            for x in range(4, TILE, 9):
                pygame.draw.line(s, lip, (x, TILE - band + 1), (x + 1, TILE - band + 5), 1)
        if "w" in side:
            pygame.draw.line(s, lip, (band, 0), (band, TILE), 1)
        return s
    return _cached(("hill", side, season), mk)


def text_sign(text, arrow=""):
    """Little wooden direction sign with a painted label (+ optional arrow)."""
    def mk():
        if not pygame.font.get_init():
            pygame.font.init()
        f = pygame.font.SysFont("consolas,arial", 10, bold=True)
        t = f.render(text, True, (70, 46, 28))
        W = max(TILE, t.get_width() + (22 if arrow else 12))
        s = _surf(W, TILE + 6)
        oy = TILE + 6
        cx = W // 2
        pygame.draw.ellipse(s, (0, 0, 0, 45), (cx - 10, oy - 7, 20, 6))
        pygame.draw.rect(s, (120, 86, 56), (cx - 2, oy - 30, 5, 27))
        pygame.draw.rect(s, (110, 78, 50), (1, oy - 44, W - 2, 18), border_radius=4)
        pygame.draw.rect(s, (214, 178, 124), (2, oy - 45, W - 4, 16), border_radius=4)
        s.blit(t, (6, oy - 43))
        if arrow:
            ax, ay = W - 10, oy - 37
            pts = {">": [(ax - 3, ay - 4), (ax + 3, ay), (ax - 3, ay + 4)],
                   "^": [(ax - 4, ay + 3), (ax, ay - 3), (ax + 4, ay + 3)]}.get(arrow)
            if pts:
                pygame.draw.polygon(s, (170, 70, 70), pts)
        _flower(s, cx + 6, oy - 6, (250, 190, 210), 2)
        return s
    return _cached(("text_sign", text, arrow), mk)


def lookout():
    """Wooden viewing deck with a brass telescope (2 tiles wide)."""
    def mk():
        W, H = TILE * 2, TILE + 30
        s = _surf(W, H)
        oy = H
        pygame.draw.rect(s, (0, 0, 0, 45), (4, oy - 26, W - 8, 24), border_radius=3)
        pygame.draw.rect(s, (150, 110, 72), (2, oy - 30, W - 4, 24), border_radius=3)
        for i in range(0, W - 4, 8):
            pygame.draw.line(s, (126, 90, 58), (2 + i, oy - 30), (2 + i, oy - 7), 1)
        pygame.draw.rect(s, (122, 88, 58), (2, oy - 44, W - 4, 4))          # rail
        for px in range(4, W, 14):
            pygame.draw.rect(s, (122, 88, 58), (px, oy - 44, 3, 16))
        # telescope on a tripod
        tx = W - 26
        for dx in (-7, 0, 7):
            pygame.draw.line(s, (70, 64, 70), (tx, oy - 50), (tx + dx, oy - 24), 2)
        pygame.draw.line(s, (214, 176, 90), (tx - 12, oy - 46), (tx + 12, oy - 60), 6)
        pygame.draw.line(s, (240, 214, 130), (tx - 12, oy - 47), (tx + 12, oy - 61), 2)
        pygame.draw.circle(s, (180, 220, 246), (tx + 13, oy - 61), 3)
        return s
    return _cached("lookout", mk)


def promise_tree():
    """The meadow's big old Promise Tree (3 tiles wide, 4 tall) -- seasonal canopy,
    fairy lights, and (once carved) a heart with both players' initials."""
    season, carve, tier = SEASON, CARVE, TIER

    def mk():
        W, H = TILE * 3, TILE * 4
        s = _surf(W, H)
        cx, oy = W // 2, H
        pygame.draw.ellipse(s, (0, 0, 0, 55), (cx - 56, oy - 18, 112, 18))
        bark, bdk, bhi = (150, 108, 76), (116, 82, 58), (178, 136, 98)
        # roots + thick trunk
        pygame.draw.polygon(s, bark, [(cx - 30, oy - 6), (cx - 14, oy - 22), (cx - 14, oy - 70),
                                      (cx + 14, oy - 70), (cx + 14, oy - 22), (cx + 30, oy - 6)])
        pygame.draw.polygon(s, bdk, [(cx - 30, oy - 6), (cx - 14, oy - 22), (cx - 14, oy - 70),
                                     (cx - 6, oy - 70), (cx - 8, oy - 20), (cx - 18, oy - 6)])
        pygame.draw.line(s, bhi, (cx + 6, oy - 66), (cx + 8, oy - 24), 2)
        for (x1, y1, x2, y2) in ((cx - 8, oy - 68, cx - 44, oy - 104), (cx + 8, oy - 68, cx + 46, oy - 100),
                                 (cx, oy - 70, cx + 4, oy - 118)):
            pygame.draw.line(s, bark, (x1, y1), (x2, y2), 9)
        if carve:
            hx, hy = cx, oy - 44
            hc = (238, 200, 156)
            pygame.draw.circle(s, bdk, (hx - 6, hy - 3), 8)
            pygame.draw.circle(s, bdk, (hx + 6, hy - 3), 8)
            pygame.draw.polygon(s, bdk, [(hx - 14, hy), (hx + 14, hy), (hx, hy + 14)])
            pygame.draw.circle(s, hc, (hx - 6, hy - 3), 7)
            pygame.draw.circle(s, hc, (hx + 6, hy - 3), 7)
            pygame.draw.polygon(s, hc, [(hx - 12, hy), (hx + 12, hy), (hx, hy + 12)])
            if not pygame.font.get_init():
                pygame.font.init()
            f = pygame.font.SysFont("consolas,arial", 10, bold=True)
            t = f.render(carve[:5], True, (110, 70, 48))
            s.blit(t, (hx - t.get_width() // 2, hy - 7))
        if season == "Winter":
            for (x, y, r) in ((cx - 44, oy - 106, 10), (cx + 46, oy - 102, 10), (cx + 4, oy - 122, 12)):
                pygame.draw.ellipse(s, (244, 248, 254), (x - r, y - 4, r * 2, 8))
            for (x, y) in ((cx - 30, oy - 96), (cx + 30, oy - 92), (cx, oy - 110)):
                pygame.draw.circle(s, (255, 214, 120), (x, y), 2)
            return s
        pal = {"Spring": ((238, 172, 198), (248, 198, 216), (255, 222, 234)),
               "Summer": ((110, 176, 118), (136, 198, 136), (172, 222, 164)),
               "Fall": ((222, 134, 78), (238, 170, 96), (250, 206, 128))}.get(
            season, ((110, 176, 118), (136, 198, 136), (172, 222, 164)))
        blobs = [(-44, -118, 34), (40, -114, 34), (0, -140, 40), (-20, -104, 30),
                 (24, -100, 30), (-56, -96, 22), (58, -94, 22), (0, -108, 30)]
        for (dx, dy, r) in blobs:
            pygame.draw.circle(s, _dk(pal[0], 0.86), (cx + dx, oy + dy + 3), r)
        for (dx, dy, r) in blobs:
            pygame.draw.circle(s, pal[0], (cx + dx, oy + dy), r)
        for (dx, dy, r) in ((-30, -128, 18), (26, -126, 18), (0, -152, 20), (-2, -118, 16)):
            pygame.draw.circle(s, pal[1], (cx + dx, oy + dy), r)
        for (dx, dy, r) in ((-34, -136, 8), (18, -138, 8), (-6, -160, 9)):
            pygame.draw.circle(s, pal[2], (cx + dx, oy + dy), r)
        # warm fairy lights looped through the canopy
        pts = [(cx - 64, oy - 92), (cx - 36, oy - 84), (cx - 8, oy - 90), (cx + 20, oy - 82),
               (cx + 48, oy - 88), (cx + 64, oy - 94)]
        pygame.draw.lines(s, (120, 100, 80), False, pts, 1)
        for i, (x, y) in enumerate(pts):
            c = [(255, 226, 140), (255, 180, 200), (200, 230, 255)][i % 3]
            pygame.draw.circle(s, c, (x, y + 2), 3)
            pygame.draw.circle(s, (255, 255, 240), (x, y + 1), 1)
        if season == "Spring":
            rng = random.Random(5)
            for _ in range(10):
                pygame.draw.circle(s, (255, 236, 244), (cx + rng.randint(-60, 60),
                                                        oy - rng.randint(96, 170)), 2)
        _promise_adorn(s, cx, oy, tier)
        return s
    return _cached(("promise_tree", season, carve, tier), mk)


def _promise_adorn(s, cx, oy, tier):
    """Milestone decorations the couple earns by returning to the tree."""
    if tier >= 1:                                    # red ribbons tied on the boughs
        for (x, y) in ((cx - 40, oy - 100), (cx + 40, oy - 96)):
            pygame.draw.polygon(s, (214, 60, 80), [(x, y), (x - 6, y - 4), (x - 6, y + 4)])
            pygame.draw.polygon(s, (214, 60, 80), [(x, y), (x + 6, y - 4), (x + 6, y + 4)])
            pygame.draw.line(s, (190, 44, 66), (x, y), (x - 3, y + 10), 2)
            pygame.draw.line(s, (190, 44, 66), (x, y), (x + 3, y + 10), 2)
            pygame.draw.circle(s, (240, 110, 120), (x, y), 2)
    if tier >= 2:                                    # paper lanterns under the canopy
        for i, x in enumerate((cx - 52, cx + 2, cx + 54)):
            y = oy - 80 + (i % 2) * 6
            c = [(250, 150, 150), (255, 214, 120), (190, 170, 250)][i]
            pygame.draw.line(s, (110, 90, 70), (x, y - 8), (x, y), 1)
            pygame.draw.ellipse(s, c, (x - 5, y, 10, 13))
            pygame.draw.ellipse(s, (255, 246, 220), (x - 2, y + 3, 4, 6))
    if tier >= 3:                                    # golden blossoms + a little plaque
        rng = random.Random(9)
        for _ in range(14):
            x, y = cx + rng.randint(-62, 62), oy - rng.randint(100, 172)
            _flower(s, x, y, (255, 214, 96), 2)
        pygame.draw.rect(s, (150, 110, 70), (cx + 20, oy - 20, 22, 12), border_radius=2)
        pygame.draw.rect(s, (236, 200, 110), (cx + 22, oy - 18, 18, 8), border_radius=2)


# ============================================================ mine: hazards & ruins
def lava_frames():
    def mk():
        out = []
        for f in range(4):
            s = _surf()
            ph = f / 4 * math.tau
            # near full-tile pool so neighbouring lava tiles read as one pool
            pygame.draw.rect(s, (74, 38, 36), (1, 2, 46, 45), border_radius=16)   # crust rim
            pygame.draw.rect(s, (206, 56, 30), (4, 5, 40, 39), border_radius=14)
            pygame.draw.rect(s, (246, 100, 40), (7, 8, 34, 32), border_radius=13)
            for k in range(3):                                                # molten swirls
                sx = 10 + k * 11 + int(math.sin(ph + k * 2.1) * 3)
                sy = 14 + (k * 9) % 20 + int(math.cos(ph + k) * 2)
                pygame.draw.ellipse(s, (255, 140, 56), (sx, sy, 12, 6))
            pygame.draw.ellipse(s, (255, 176, 84), (17 + int(math.sin(ph) * 3), 19, 14, 9))
            for k in range(3):                                                # bubbles
                bx = 12 + k * 11 + int(math.sin(ph + k) * 2)
                by = 22 + int(math.cos(ph * 1.3 + k * 2) * 9)
                pygame.draw.circle(s, (255, 214, 150), (bx, by), 2 if (f + k) % 2 else 1)
            pygame.draw.arc(s, (110, 56, 44), (1, 2, 46, 45), 0.4, 2.7, 2)
            out.append(s)
        return out
    return _cached("lava_frames", mk)


def rift_frames():
    def mk():
        out = []
        for f in range(4):
            s = _surf()
            ph = f / 4 * math.tau
            glow = _surf()
            pygame.draw.ellipse(glow, (150, 80, 230, 70), (4, 10, 40, 30))
            s.blit(glow, (0, 0))
            pts = [(6, 26), (14, 20), (20, 28), (27, 17), (34, 27), (42, 22)]
            pts2 = [(x, y + 6) for (x, y) in reversed(pts)]
            pygame.draw.polygon(s, (22, 10, 36), pts + pts2)
            pygame.draw.lines(s, (196, 140, 255), False, pts, 2)
            pygame.draw.lines(s, (120, 70, 200), False, [(x, y + 6) for (x, y) in pts], 1)
            for k in range(4):
                sx = 8 + k * 10 + int(math.sin(ph + k * 1.7) * 3)
                sy = 14 + int(math.cos(ph + k) * 8)
                pygame.draw.circle(s, (230, 200, 255), (sx, sy), 1 + (f + k) % 2)
            out.append(s)
        return out
    return _cached("rift_frames", mk)


def ruin_pillar(broken=False):
    def mk():
        H = TILE if broken else TILE * 2
        s = _surf(TILE, H)
        cx, oy = TILE // 2, H
        stone, sdk, shi = (206, 190, 158), (160, 144, 116), (228, 216, 188)
        pygame.draw.ellipse(s, (0, 0, 0, 55), (cx - 17, oy - 10, 34, 9))
        pygame.draw.rect(s, sdk, (cx - 15, oy - 12, 30, 8), border_radius=2)       # plinth
        pygame.draw.rect(s, stone, (cx - 15, oy - 14, 30, 7), border_radius=2)
        top = oy - (34 if broken else 78)
        pygame.draw.rect(s, stone, (cx - 10, top, 20, oy - 12 - top))
        for fx in (-6, -1, 4):                                                    # fluting
            pygame.draw.line(s, sdk, (cx + fx, top + 3), (cx + fx, oy - 14), 1)
        pygame.draw.line(s, shi, (cx - 8, top + 2), (cx - 8, oy - 15), 2)
        if broken:
            pygame.draw.polygon(s, stone, [(cx - 10, top), (cx - 4, top - 7), (cx + 3, top - 2),
                                           (cx + 10, top - 9), (cx + 10, top)])
            pygame.draw.circle(s, sdk, (cx + 14, oy - 8), 4)                     # fallen chunk
            pygame.draw.circle(s, stone, (cx + 13, oy - 9), 3)
        else:
            pygame.draw.rect(s, sdk, (cx - 14, top - 8, 28, 9), border_radius=2)   # capital
            pygame.draw.rect(s, stone, (cx - 14, top - 10, 28, 8), border_radius=2)
            pygame.draw.line(s, sdk, (cx + 3, top + 14), (cx - 2, top + 30), 1)    # crack
            pygame.draw.line(s, sdk, (cx - 2, top + 30), (cx + 4, top + 40), 1)
        for (mx, my) in ((cx - 9, oy - 18), (cx + 7, top + 6)):                    # moss
            pygame.draw.circle(s, (120, 170, 110), (mx, my), 3)
        return s
    return _cached(("ruin_pillar", broken), mk)


def ruin_statue():
    def mk():
        s = _surf(TILE, TILE * 2)
        cx, oy = TILE // 2, TILE * 2
        stone, sdk = (188, 184, 170), (140, 136, 124)
        pygame.draw.ellipse(s, (0, 0, 0, 55), (cx - 17, oy - 10, 34, 9))
        pygame.draw.rect(s, sdk, (cx - 15, oy - 20, 30, 16), border_radius=2)
        pygame.draw.rect(s, stone, (cx - 13, oy - 22, 26, 14), border_radius=2)
        pygame.draw.polygon(s, stone, [(cx - 11, oy - 22), (cx + 11, oy - 22), (cx + 7, oy - 60),
                                       (cx - 7, oy - 60)])
        pygame.draw.polygon(s, sdk, [(cx - 11, oy - 22), (cx - 3, oy - 22), (cx - 4, oy - 60),
                                     (cx - 7, oy - 60)])
        pygame.draw.circle(s, stone, (cx, oy - 68), 9)
        pygame.draw.circle(s, sdk, (cx, oy - 68), 9, 1)
        pygame.draw.circle(s, (120, 220, 200), (cx - 3, oy - 69), 1)            # faint eyes
        pygame.draw.circle(s, (120, 220, 200), (cx + 3, oy - 69), 1)
        pygame.draw.line(s, sdk, (cx + 4, oy - 50), (cx - 1, oy - 36), 1)
        pygame.draw.circle(s, (120, 170, 110), (cx + 9, oy - 22), 3)
        return s
    return _cached("ruin_statue", mk)


def ruin_rubble():
    def mk():
        s = _surf()
        rng = random.Random(77)
        for _ in range(6):
            x, y = rng.randint(8, 40), rng.randint(14, 40)
            w, h = rng.randint(6, 12), rng.randint(4, 8)
            pygame.draw.rect(s, (150, 136, 110), (x, y + 1, w, h), border_radius=2)
            pygame.draw.rect(s, (200, 186, 156), (x, y, w, h - 1), border_radius=2)
        return s
    return _cached("ruin_rubble", mk)


def ruin_glyph():
    def mk():
        s = _surf()
        c = (120, 230, 210)
        pygame.draw.circle(s, (80, 170, 160), (24, 26), 14, 1)
        pygame.draw.circle(s, c, (24, 26), 9, 1)
        pygame.draw.line(s, c, (24, 14), (24, 38), 1)
        pygame.draw.line(s, c, (14, 26), (34, 26), 1)
        pygame.draw.polygon(s, c, [(24, 20), (29, 26), (24, 32), (19, 26)], 1)
        return s
    return _cached("ruin_glyph", mk)


def abyss_shard():
    def mk():
        s = _surf(TILE, TILE + 16)
        oy = TILE + 16
        pygame.draw.ellipse(s, (0, 0, 0, 60), (8, oy - 10, 32, 8))
        for (x, h, w, c) in ((16, 40, 9, (86, 60, 140)), (28, 52, 11, (110, 76, 176)),
                             (36, 30, 8, (74, 52, 120))):
            pygame.draw.polygon(s, c, [(x - w // 2, oy - 6), (x + w // 2, oy - 6), (x, oy - h)])
            pygame.draw.line(s, (200, 170, 255), (x, oy - h + 3), (x - 2, oy - 10), 1)
        return s
    return _cached("abyss_shard", mk)


# ============================================================ outdoor decor catalogue
# name -> (label, price, solid, glow).  Price is what you pay; selling refunds half.
DECOR = [
    ("wood_fence", "Wood Fence", 20, True, False),
    ("stone_fence", "Stone Fence", 35, True, False),
    ("stone_path", "Stone Path", 10, False, False),
    ("brick_path", "Brick Path", 15, False, False),
    ("flower_bed", "Flower Bed", 40, False, False),
    ("lamp_post", "Lamp Post", 120, True, True),
    ("bench", "Bench", 80, True, False),
    ("garden_arch", "Garden Arch", 150, False, False),
    ("bird_bath", "Bird Bath", 90, True, False),
    ("garden_gnome", "Garden Gnome", 60, True, False),
    ("pumpkin_stack", "Pumpkin Stack", 50, True, False),
    ("lantern_string", "Lantern String", 70, False, True),
    ("picnic_blanket", "Picnic Blanket", 45, False, False),
    ("scarecrow_deluxe", "Deluxe Scarecrow", 200, True, False),
]
DECOR_INFO = {k: {"label": l, "price": p, "solid": s, "glow": g} for (k, l, p, s, g) in DECOR}
FLAT_DECOR = {"stone_path", "brick_path", "picnic_blanket", "flower_bed"}


def _d_wood_fence():
    s = _surf(TILE, TILE + 8)
    oy = TILE + 8
    wood, wdk, whi = (182, 138, 94), (128, 94, 62), (210, 172, 124)
    for py in (oy - 34, oy - 20):
        pygame.draw.rect(s, wdk, (0, py + 2, TILE, 5))
        pygame.draw.rect(s, wood, (0, py, TILE, 5))
        pygame.draw.line(s, whi, (0, py), (TILE, py), 1)
    for px in (5, TILE - 12):
        pygame.draw.rect(s, wdk, (px, oy - 44, 8, 40), border_radius=2)
        pygame.draw.rect(s, wood, (px, oy - 45, 7, 40), border_radius=2)
        pygame.draw.polygon(s, whi, [(px, oy - 45), (px + 7, oy - 45), (px + 3, oy - 49)])
    return s


def _d_stone_fence():
    s = _surf(TILE, TILE + 4)
    oy = TILE + 4
    rng = random.Random(8)
    pygame.draw.rect(s, (120, 118, 128), (1, oy - 30, TILE - 2, 26), border_radius=4)
    for row in range(3):
        x = -(row % 2) * 8
        while x < TILE:
            w = rng.randint(12, 18)
            c = rng.choice([(186, 184, 194), (170, 168, 180), (200, 198, 206)])
            pygame.draw.rect(s, c, (max(2, x + 1), oy - 29 + row * 8, min(w - 2, TILE - 3 - max(2, x + 1)), 7),
                             border_radius=2)
            x += w
    pygame.draw.rect(s, (214, 212, 220), (2, oy - 32, TILE - 4, 5), border_radius=2)
    pygame.draw.circle(s, (130, 186, 120), (8, oy - 30), 3)
    return s


def _d_wood_fence_v():
    """Wood fence running up/down: rails span the tile so a column connects."""
    s = _surf(TILE, TILE + 8)
    oy = TILE + 8
    wood, wdk, whi = (182, 138, 94), (128, 94, 62), (210, 172, 124)
    for px in (18, 27):
        pygame.draw.rect(s, wdk, (px + 1, 0, 3, oy - 6))
        pygame.draw.rect(s, wood, (px, 0, 3, oy - 6))
        pygame.draw.line(s, whi, (px, 0), (px, oy - 7), 1)
    pygame.draw.rect(s, wdk, (19, oy - 44, 9, 40), border_radius=2)
    pygame.draw.rect(s, wood, (19, oy - 45, 8, 40), border_radius=2)
    pygame.draw.rect(s, whi, (20, oy - 45, 2, 38))
    pygame.draw.polygon(s, whi, [(19, oy - 45), (27, oy - 45), (23, oy - 50)])
    return s


def _d_stone_fence_v():
    s = _surf(TILE, TILE + 4)
    oy = TILE + 4
    pygame.draw.rect(s, (120, 118, 128), (12, 0, 24, oy - 4), border_radius=4)
    for row in range((oy - 4) // 8):
        off = 0 if row % 2 == 0 else 6
        for k in range(2):
            x = 13 + off + k * 11
            w = min(10, 35 - x)
            if w > 2:
                c = ((186, 184, 194), (170, 168, 180), (200, 198, 206))[(row + k) % 3]
                pygame.draw.rect(s, c, (x, 1 + row * 8, w, 7), border_radius=2)
    pygame.draw.rect(s, (214, 212, 220), (13, 0, 22, 3), border_radius=1)
    pygame.draw.circle(s, (130, 186, 120), (15, oy - 10), 3)
    return s


def _d_brick_path():
    s = _surf()
    pygame.draw.rect(s, (170, 104, 88), (1, 1, TILE - 2, TILE - 2), border_radius=3)
    for row in range(4):
        off = 0 if row % 2 == 0 else 11
        for col in range(-1, 3):
            x = col * 22 + off + 2
            r = pygame.Rect(x, 2 + row * 11, 20, 9).clip(pygame.Rect(2, 2, TILE - 4, TILE - 4))
            if r.w > 2:
                pygame.draw.rect(s, (208, 132, 110), r, border_radius=2)
                pygame.draw.line(s, (226, 158, 136), r.topleft, (r.right - 2, r.top), 1)
    return s


def _d_flower_bed():
    s = _surf()
    pygame.draw.rect(s, (118, 84, 54), (3, 20, TILE - 6, 24), border_radius=5)
    pygame.draw.rect(s, (150, 108, 72), (5, 22, TILE - 10, 20), border_radius=4)
    rng = random.Random(12)
    for i in range(7):
        x, y = 9 + (i * 6) % 32, 24 + (i * 7) % 14
        pygame.draw.line(s, (96, 150, 88), (x, y + 2), (x, y + 6), 1)
        _flower(s, x, y, _FLOWER_COLS[i % len(_FLOWER_COLS)], 2 + (i % 2))
    return s


def _d_bench():
    s = _surf()
    wood, wdk, whi = (176, 128, 84), (126, 90, 58), (206, 164, 116)
    pygame.draw.ellipse(s, (0, 0, 0, 45), (4, 36, 40, 9))
    for lx in (7, 37):
        pygame.draw.rect(s, (84, 76, 88), (lx, 26, 4, 14))
        pygame.draw.rect(s, (84, 76, 88), (lx, 6, 4, 22))
    pygame.draw.rect(s, wood, (3, 8, 42, 4), border_radius=2)
    pygame.draw.rect(s, wood, (3, 16, 42, 4), border_radius=2)
    pygame.draw.rect(s, wdk, (3, 27, 42, 5), border_radius=2)
    pygame.draw.rect(s, whi, (3, 25, 42, 4), border_radius=2)
    return s


def _d_garden_arch():
    s = _surf(TILE, TILE * 2)
    oy = TILE * 2
    white, wdk = (246, 244, 236), (190, 186, 176)
    for px in (5, TILE - 10):
        pygame.draw.rect(s, wdk, (px + 1, oy - 70, 5, 68))
        pygame.draw.rect(s, white, (px, oy - 70, 5, 68))
    pygame.draw.arc(s, white, (4, oy - 92, TILE - 8, 44), 0, math.pi, 5)
    rng = random.Random(4)
    for _ in range(16):                                       # climbing roses
        a = rng.uniform(0.1, math.pi - 0.1)
        x = TILE // 2 + math.cos(a) * (TILE // 2 - 6)
        y = oy - 70 - math.sin(a) * 20
        if rng.random() < 0.5:
            x, y = rng.choice((7, TILE - 8)), rng.randint(oy - 66, oy - 12)
        pygame.draw.circle(s, (98, 160, 92), (int(x), int(y)), 4)
        pygame.draw.circle(s, rng.choice([(240, 120, 150), (250, 190, 210), (255, 240, 244)]),
                           (int(x) + 1, int(y) - 1), 2)
    return s


def _d_bird_bath():
    s = _surf(TILE, TILE + 12)
    oy = TILE + 12
    st, sdk = (214, 212, 222), (164, 162, 176)
    pygame.draw.ellipse(s, (0, 0, 0, 45), (10, oy - 9, 28, 7))
    pygame.draw.rect(s, sdk, (14, oy - 10, 20, 6), border_radius=2)
    pygame.draw.rect(s, st, (20, oy - 34, 8, 26))
    pygame.draw.ellipse(s, sdk, (4, oy - 42, 40, 14))
    pygame.draw.ellipse(s, st, (4, oy - 44, 40, 13))
    pygame.draw.ellipse(s, (130, 190, 230), (9, oy - 42, 30, 8))
    pygame.draw.line(s, (200, 230, 250), (14, oy - 39), (24, oy - 39), 1)
    pygame.draw.circle(s, (120, 150, 210), (36, oy - 46), 4)                # a little bluebird
    pygame.draw.circle(s, (120, 150, 210), (40, oy - 49), 3)
    pygame.draw.polygon(s, (240, 190, 90), [(42, oy - 49), (46, oy - 48), (42, oy - 47)])
    return s


def _d_garden_gnome():
    s = _surf()
    pygame.draw.ellipse(s, (0, 0, 0, 45), (12, 38, 24, 7))
    pygame.draw.ellipse(s, (70, 120, 200), (14, 24, 20, 18))                 # coat
    pygame.draw.circle(s, (250, 214, 186), (24, 22), 6)                      # face
    pygame.draw.polygon(s, (246, 246, 250), [(17, 24), (31, 24), (24, 36)])  # beard
    pygame.draw.polygon(s, (220, 70, 70), [(16, 20), (32, 20), (24, 3)])     # hat
    pygame.draw.circle(s, (240, 150, 140), (24, 24), 2)                      # nose
    pygame.draw.rect(s, (90, 60, 40), (15, 40, 7, 3))
    pygame.draw.rect(s, (90, 60, 40), (26, 40, 7, 3))
    return s


def _d_pumpkin_stack():
    s = _surf(TILE, TILE + 6)
    oy = TILE + 6
    pygame.draw.ellipse(s, (0, 0, 0, 45), (4, oy - 10, 40, 8))
    for (x, y, rw, rh, c) in ((13, oy - 16, 22, 16, (232, 136, 50)), (35, oy - 15, 20, 15, (240, 160, 70)),
                              (24, oy - 30, 22, 17, (226, 124, 44))):
        pygame.draw.ellipse(s, _dk(c, 0.8), (x - rw // 2, y - rh // 2 + 1, rw, rh))
        pygame.draw.ellipse(s, c, (x - rw // 2, y - rh // 2, rw, rh - 1))
        pygame.draw.line(s, _dk(c, 0.8), (x, y - rh // 2 + 2), (x, y + rh // 2 - 2), 1)
        pygame.draw.rect(s, (110, 140, 70), (x - 1, y - rh // 2 - 4, 3, 5))
    pygame.draw.ellipse(s, (120, 170, 90), (26, oy - 44, 10, 5))
    return s


def _d_lantern_string():
    s = _surf(TILE, TILE * 2)
    oy = TILE * 2
    pygame.draw.rect(s, (120, 88, 60), (4, oy - 76, 4, 74))
    pygame.draw.rect(s, (120, 88, 60), (TILE - 8, oy - 76, 4, 74))
    pts = [(6 + i * 6, oy - 72 + int(math.sin(i / 6 * math.pi) * 10)) for i in range(7)]
    pygame.draw.lines(s, (90, 76, 64), False, pts, 1)
    for i, (x, y) in enumerate(pts[1:-1]):
        c = [(250, 130, 130), (255, 214, 110), (150, 210, 160), (170, 190, 250), (240, 160, 220)][i % 5]
        pygame.draw.line(s, (90, 76, 64), (x, y), (x, y + 3), 1)
        pygame.draw.ellipse(s, c, (x - 3, y + 3, 7, 9))
        pygame.draw.ellipse(s, (255, 250, 220), (x - 1, y + 5, 3, 4))
    return s


def _d_picnic_blanket():
    s = _surf()
    pygame.draw.rect(s, (250, 244, 236), (3, 8, TILE - 6, 34), border_radius=4)
    for i in range(0, TILE - 6, 10):
        pygame.draw.rect(s, (120, 170, 230), (3 + i, 8, 5, 34))
    for j in range(0, 34, 10):
        ov = _surf(TILE - 6, 5)
        ov.fill((120, 170, 230, 150))
        s.blit(ov, (3, 8 + j))
    pygame.draw.rect(s, (90, 140, 200), (3, 8, TILE - 6, 34), 1, border_radius=4)
    return s


def _d_scarecrow_deluxe():
    s = _surf(TILE, TILE + 30)
    cx, oy = TILE // 2, TILE + 30
    pygame.draw.ellipse(s, (0, 0, 0, 45), (cx - 12, oy - 8, 24, 6))
    pygame.draw.rect(s, (140, 100, 62), (cx - 2, oy - 56, 4, 54))
    pygame.draw.rect(s, (140, 100, 62), (cx - 18, oy - 44, 36, 4))
    pygame.draw.rect(s, (110, 150, 210), (cx - 10, oy - 46, 20, 20), border_radius=3)   # overalls
    pygame.draw.rect(s, (220, 90, 90), (cx - 10, oy - 46, 20, 7), border_radius=3)      # plaid shirt
    pygame.draw.line(s, (250, 220, 120), (cx - 10, oy - 43), (cx + 10, oy - 43), 1)
    for hx in (cx - 18, cx + 18):
        pygame.draw.circle(s, (230, 200, 120), (hx, oy - 42), 3)
    pygame.draw.circle(s, (236, 206, 130), (cx, oy - 54), 9)
    pygame.draw.circle(s, (40, 32, 28), (cx - 3, oy - 55), 1)
    pygame.draw.circle(s, (40, 32, 28), (cx + 3, oy - 55), 1)
    pygame.draw.arc(s, (150, 90, 60), (cx - 4, oy - 54, 8, 5), 3.4, 6.0, 1)
    pygame.draw.ellipse(s, (170, 120, 70), (cx - 16, oy - 62, 32, 7))                   # sun hat
    pygame.draw.rect(s, (190, 140, 84), (cx - 8, oy - 72, 16, 11), border_radius=3)
    pygame.draw.rect(s, (220, 90, 90), (cx - 8, oy - 65, 16, 3))
    _flower(s, cx + 6, oy - 68, (255, 230, 150), 2)
    pygame.draw.circle(s, (60, 60, 70), (cx + 16, oy - 50), 3)                          # crow buddy
    pygame.draw.polygon(s, (240, 190, 90), [(cx + 19, oy - 50), (cx + 22, oy - 49), (cx + 19, oy - 48)])
    return s


_DECOR_PAINTERS = {
    "wood_fence": _d_wood_fence, "stone_fence": _d_stone_fence,
    "stone_path": lambda: cobble(1), "brick_path": _d_brick_path,
    "flower_bed": _d_flower_bed, "lamp_post": lamp_post, "bench": _d_bench,
    "garden_arch": _d_garden_arch, "bird_bath": _d_bird_bath,
    "garden_gnome": _d_garden_gnome, "pumpkin_stack": _d_pumpkin_stack,
    "lantern_string": _d_lantern_string, "picnic_blanket": _d_picnic_blanket,
    "scarecrow_deluxe": _d_scarecrow_deluxe,
}


_DECOR_VERTICAL = {"wood_fence": _d_wood_fence_v, "stone_fence": _d_stone_fence_v}
CONNECTS = set(_DECOR_VERTICAL)          # decor that joins up with its neighbours


def decor_sprite(name, variant=""):
    """Sprite for an outdoor decor piece (bottom-anchored to its tile).
    ``variant`` "v" = the up/down run of a connecting fence."""
    if variant == "v" and name in _DECOR_VERTICAL:
        return _cached(("decor", name, "v"), _DECOR_VERTICAL[name])
    return _cached(("decor", name), lambda: _DECOR_PAINTERS.get(name, _d_garden_gnome)())


def decor_icon(name, size=40):
    """The decor sprite scaled to fit a catalogue slot."""
    def mk():
        spr = decor_sprite(name)
        w, h = spr.get_size()
        k = min(size / w, size / h)
        return pygame.transform.smoothscale(spr, (max(1, int(w * k)), max(1, int(h * k))))
    return _cached(("decor_icon", name, size), mk)


def ghost(name, ok):
    """Translucent green/red placement ghost of a decor sprite."""
    def mk():
        spr = decor_sprite(name).copy()
        tint = _surf(*spr.get_size())
        tint.fill((90, 230, 120, 255) if ok else (240, 80, 80, 255))
        spr.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        spr.set_alpha(170)
        return spr
    return _cached(("decor_ghost", name, ok), mk)


# ============================================================ prop registry
# meadow flower prop kinds: MFLOWER_KINDS[colour band][layout]
MFLOWER_KINDS = [[("mflowers" if b == 0 else f"mflowers{b + 1}") + ("" if l == 0 else chr(97 + l))
                  for l in range(3)] for b in range(4)]


def prop_painters():
    """kind -> painter() for every prop World places in area.props."""
    return {
        "cobble": lambda: cobble(0), "cobble2": lambda: cobble(1), "cobble3": lambda: cobble(2),
        "lily_pad": lambda: lily_pad(False), "lily_flower": lambda: lily_pad(True),
        "reeds": reeds, "dock": dock,
        "hill_s": lambda: hill_edge("s"), "hill_w": lambda: hill_edge("w"),
        "hill_sw": lambda: hill_edge("sw"),
        "sign_tree": lambda: text_sign("Promise Tree", "^"),
        "sign_lookout": lambda: text_sign("Lookout", ">"),
        "fence_h": lambda: fence("h"), "fence_v": lambda: fence("v"), "fence_post": lambda: fence("p"),
        "fruit_tree": fruit_tree,
        "wildflowers": lambda: wildflowers(0), "wildflowers2": lambda: wildflowers(1),
        **{MFLOWER_KINDS[b][l]: (lambda b=b, l=l: meadow_flowers(b, l))
           for b in range(4) for l in range(3)},
        "stump": stump, "boulder": boulder, "lamp_post": lamp_post,
        "picnic_blanket": picnic_blanket, "picnic_bench": lambda: bench(2),
        "love_bench": lambda: bench(2), "tree_swing": tree_swing, "lookout": lookout,
        "promise_tree": promise_tree,
        "ruin_pillar": lambda: ruin_pillar(False), "ruin_broken": lambda: ruin_pillar(True),
        "ruin_statue": ruin_statue, "ruin_rubble": ruin_rubble, "ruin_glyph": ruin_glyph,
        "abyss_shard": abyss_shard,
    }
