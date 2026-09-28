"""Redrawn 28x28 icons for the core items: tools, the everyday fish, every crop,
the basic materials and the original dishes.

Owner: "UI & Rendering" chat. This file is the "second pass" art that replaced
the first flat shapes so these icons match the later forage / gem / artisan art:
a soft volume shade, a lit rim, and a 1px *selective* outline (each outline pixel
is a darkened version of the colour it touches) so every icon reads the same way
on the dark hotbar and on cream parchment.

``items.item_icon`` / ``items.tool_icon`` look here first (``ITEM_ART`` /
``TOOL_ART``); anything not listed still falls through to the original chain.
Every painter draws onto a fresh transparent IC x IC surface and is cached by
the caller, so nothing here runs per frame.
"""
import math
import random
import pygame

IC = 28

# ------------------------------------------------------------------ colour
def _cl(v):
    return max(0, min(255, int(v)))


def lt(c, f=1.22, add=14):
    return tuple(_cl(v * f + add) for v in c[:3])


def dk(c, f=0.7):
    return tuple(_cl(v * f) for v in c[:3])


def mix(a, b, t):
    return tuple(_cl(a[i] + (b[i] - a[i]) * t) for i in range(3))


WHITE = (255, 255, 252)
INK = (34, 24, 32)
EYE = (28, 24, 34)
WOOD = (150, 102, 60)
WOOD_DK = (108, 70, 40)
STEEL = (196, 204, 216)
STEEL_DK = (124, 132, 148)
LEAF = (104, 176, 84)
LEAF_DK = (70, 130, 60)


# ------------------------------------------------------------------ core helpers
def _ic():
    return pygame.Surface((IC, IC), pygame.SRCALPHA)


def _mask(surf, thr=40):
    return pygame.mask.from_surface(surf, thr)


def _paint(dst, m, col):
    if m.count():
        dst.blit(m.to_surface(setcolor=tuple(col) + (() if len(col) == 4 else (255,)),
                              unsetcolor=(0, 0, 0, 0)), (0, 0))


def clip(layer, m):
    """Keep only the pixels of ``layer`` that fall inside mask ``m``."""
    layer.blit(m.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)),
               (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return layer


def shape(draw):
    """Mask of whatever ``draw(surface, colour)`` paints."""
    t = _ic()
    draw(t, (255, 255, 255))
    return _mask(t)


def vol(s, draw, base, shade=None, hi=None, depth=2, rim=True, d=(1, 1)):
    """Fill a shape with ``base``, shade its far (bottom-right) edge and put a lit
    rim on its near (top-left) edge. ``draw(surface, colour)`` paints the shape.
    Returns the shape's mask so callers can clip details into it."""
    m = shape(draw)
    _paint(s, m, base)
    lit = m.overlap_mask(m, (-depth * d[0], -depth * d[1]))
    sh = m.copy()
    sh.erase(lit, (0, 0))
    _paint(s, sh, shade or dk(base, 0.74))
    if rim:
        inner = m.overlap_mask(m, (d[0], d[1]))
        r = m.copy()
        r.erase(inner, (0, 0))
        r.erase(sh, (0, 0))
        _paint(s, r, hi or lt(base))
    return m


def finish(s, thr=90):
    """Selective 1px outline: every empty pixel touching the icon becomes a deep
    shade of the colour it touches (the house style of the newer icon art)."""
    src = s.copy()
    w, h = src.get_size()
    for y in range(h):
        for x in range(w):
            if src.get_at((x, y))[3] >= thr:
                continue
            best = None
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    c = src.get_at((nx, ny))
                    if c[3] >= thr:
                        o = (_cl(c[0] * 0.36 + 16), _cl(c[1] * 0.32 + 10), _cl(c[2] * 0.36 + 20))
                        if best is None or sum(o) < sum(best):
                            best = o
            if best is not None:
                s.set_at((x, y), best + (255,))
    return s


def sparkle(s, x, y, col=(255, 252, 220), r=2):
    pygame.draw.line(s, col, (x - r, y), (x + r, y), 1)
    pygame.draw.line(s, col, (x, y - r), (x, y + r), 1)
    s.set_at((x, y), WHITE + (255,))


def shine(s, x, y, n=2, col=WHITE):
    """A tiny specular stroke (n px long, falling to the lower-left)."""
    for i in range(n):
        s.set_at((x - i, y + i), tuple(col) + (255,))


def _poly(pts):
    return lambda t, c: pygame.draw.polygon(t, c, [(round(x), round(y)) for x, y in pts])


def _ell(r):
    return lambda t, c: pygame.draw.ellipse(t, c, r)


def _circ(cx, cy, r):
    return lambda t, c: pygame.draw.circle(t, c, (cx, cy), r)


def _line(a, b, w):
    return lambda t, c: pygame.draw.line(t, c, a, b, w)


def _many(*fns):
    def d(t, c):
        for f in fns:
            f(t, c)
    return d


def leaf(s, x, y, ang, ln=7, wd=3, col=LEAF):
    ca, sa = math.cos(ang), math.sin(ang)
    tip = (x + ca * ln, y + sa * ln)
    mid = (x + ca * ln * 0.45, y + sa * ln * 0.45)
    pts = [(x, y), (mid[0] - sa * wd, mid[1] + ca * wd), tip, (mid[0] + sa * wd, mid[1] - ca * wd)]
    vol(s, _poly(pts), col, depth=1)
    pygame.draw.line(s, dk(col, 0.78), (round(x), round(y)),
                     (round(x + ca * ln * 0.8), round(y + sa * ln * 0.8)), 1)


# ================================================================== TOOLS
def _tool_hoe(s):
    vol(s, _line((6, 26), (19, 6), 3), WOOD, WOOD_DK, depth=1)
    vol(s, _line((10, 5), (21, 4), 2), STEEL_DK, depth=1)                           # neck
    vol(s, _poly([(4, 4), (12, 3), (13, 13), (4, 15)]), STEEL, STEEL_DK)            # hanging blade
    pygame.draw.line(s, WHITE, (5, 14), (12, 12), 1)                                # honed edge
    finish(s)


def _tool_can(s):
    can, can_dk = (74, 150, 214), (44, 98, 160)
    pygame.draw.arc(s, can_dk, (5, 4, 12, 14), 0.2, 2.95, 3)                        # handle
    vol(s, _poly([(15, 19), (23, 9), (25, 11), (17, 22)]), can, can_dk, depth=1)    # spout
    vol(s, _poly([(21, 7), (25, 5), (27, 9), (24, 11)]), (120, 190, 236), can_dk, depth=1)  # rose
    vol(s, _poly([(5, 11), (17, 11), (18, 24), (3, 24)]), can, can_dk, depth=2)     # body
    pygame.draw.line(s, can_dk, (4, 16), (17, 16), 1)                               # seam
    pygame.draw.line(s, lt(can, 1.3), (6, 13), (5, 21), 1)
    finish(s)
    for dx, dy in ((26, 13), (24, 15)):                                             # droplets
        pygame.draw.circle(s, (160, 214, 246), (dx, dy), 1)


def _tool_pick(s):
    vol(s, _line((9, 26), (15, 6), 3), WOOD, WOOD_DK, depth=1)
    head = [(2, 11), (6, 6), (12, 3), (18, 3), (24, 6), (26, 11), (21, 8), (15, 6), (9, 7), (5, 9)]
    vol(s, _poly(head), STEEL, STEEL_DK)
    vol(s, lambda t, c: pygame.draw.rect(t, c, (12, 3, 6, 5), border_radius=1), STEEL_DK, depth=1)
    pygame.draw.line(s, WHITE, (8, 6), (12, 4), 1)
    finish(s)


def _tool_axe(s):
    vol(s, _line((7, 26), (16, 5), 3), WOOD, WOOD_DK, depth=1)
    vol(s, _poly([(11, 5), (14, 3), (16, 9), (12, 10)]), STEEL_DK, depth=1)          # poll
    blade = [(14, 4), (19, 3), (24, 1), (26, 7), (25, 14), (21, 13), (16, 10)]
    vol(s, _poly(blade), STEEL, STEEL_DK)
    pygame.draw.line(s, WHITE, (24, 3), (25, 10), 1)                                 # honed edge
    finish(s)


def _diag_blade(s):
    u = (1 / math.sqrt(2), -1 / math.sqrt(2))
    p = (1 / math.sqrt(2), 1 / math.sqrt(2))
    B, T = (10, 18), (25, 3)
    tb = (T[0] - u[0] * 4, T[1] - u[1] * 4)
    w = 2.3
    blade = [(B[0] - p[0] * w, B[1] - p[1] * w), (tb[0] - p[0] * w, tb[1] - p[1] * w), T,
             (tb[0] + p[0] * w, tb[1] + p[1] * w), (B[0] + p[0] * w, B[1] + p[1] * w)]
    return u, p, B, T, blade


def _tool_sword(s):
    u, p, B, T, blade = _diag_blade(s)
    vol(s, _poly(blade), STEEL, STEEL_DK, depth=1)
    pygame.draw.line(s, lt(STEEL, 1.1), (round(B[0] + 1), round(B[1] - 1)),
                     (round(T[0] - 3), round(T[1] + 3)), 1)                          # fuller glint
    grip_end = (B[0] - u[0] * 6, B[1] - u[1] * 6)
    vol(s, _line((round(B[0]), round(B[1])), (round(grip_end[0]), round(grip_end[1])), 3),
        (122, 74, 52), depth=1)
    g1 = (round(B[0] - p[0] * 5), round(B[1] - p[1] * 5))
    g2 = (round(B[0] + p[0] * 5), round(B[1] + p[1] * 5))
    vol(s, _line(g1, g2, 3), (222, 180, 84), depth=1)                                # guard
    vol(s, _circ(round(grip_end[0] - u[0]), round(grip_end[1] - u[1]), 2), (222, 180, 84), depth=1)
    finish(s)


def _tool_rod(s):
    pygame.draw.line(s, (240, 240, 244), (23, 4), (23, 16), 1)                       # line
    vol(s, _line((6, 25), (23, 4), 2), (176, 124, 70), WOOD_DK, depth=1)             # rod
    vol(s, _line((4, 27), (9, 21), 4), (214, 180, 128), depth=1)                     # cork grip
    vol(s, _circ(11, 21, 3), (150, 158, 172), depth=1)                               # reel
    pygame.draw.circle(s, (80, 86, 100), (11, 21), 1)
    finish(s)
    pygame.draw.circle(s, (232, 70, 64), (23, 18), 3)                                # bobber
    pygame.draw.rect(s, WHITE, (20, 19, 7, 3))
    pygame.draw.circle(s, (96, 30, 30), (23, 18), 3, 1)
    s.set_at((22, 16), WHITE + (255,))


TOOL_ART = {"hoe": _tool_hoe, "watering_can": _tool_can, "pickaxe": _tool_pick,
            "axe": _tool_axe, "sword": _tool_sword, "fishing_rod": _tool_rod}


# ================================================================== FISH
# Every everyday fish has its own silhouette + markings instead of one recoloured
# shape. Fish face LEFT. Keys:
#   L body length, up/lo half-heights above/below the midline, a/b profile
#   bluntness (head / tail), tail (fork|round|fan|lunate|square|hetero|point),
#   tl tail length, th tail half-height, dorsal (t0, t1, height, style),
#   back/belly/fin colours, pat pattern list, mouth (small|big|under|snout|duck)
FISH_ART = {
    "anchovy":  dict(L=15, up=3, lo=2.8, back=(92, 120, 150), body=(176, 190, 206), belly=(236, 240, 246),
                     tail="fork", tl=5, th=4, dorsal=(0.42, 0.56, 2, "tri"), fin=(150, 170, 196),
                     pat=[("band", (236, 242, 250))], eye=2),
    "sardine":  dict(L=19, up=4, lo=4, back=(70, 128, 150), body=(180, 196, 206), belly=(238, 242, 246),
                     tail="fork", tl=6, th=5, dorsal=(0.38, 0.55, 3, "tri"), fin=(150, 172, 190),
                     pat=[("row", (36, 60, 84))]),
    "herring":  dict(L=20, up=5, lo=4.5, back=(46, 84, 140), body=(170, 190, 214), belly=(242, 244, 248),
                     tail="fork", tl=6, th=5, dorsal=(0.40, 0.58, 4, "tri"), fin=(160, 176, 196),
                     pat=[("sheen", (206, 220, 236))]),
    "carp":     dict(L=18, up=6.5, lo=5.5, back=(118, 132, 70), body=(178, 170, 92), belly=(236, 214, 150),
                     tail="fork", tl=7, th=6, dorsal=(0.30, 0.78, 3, "long"), fin=(200, 138, 76),
                     pat=[("scales", None)], mouth="under", barbel=True),
    "bluegill": dict(L=16, up=7, lo=7, a=0.55, back=(52, 92, 132), body=(96, 150, 190), belly=(244, 190, 96),
                     tail="square", tl=6, th=6, dorsal=(0.22, 0.86, 3, "spiny"), fin=(78, 120, 160),
                     pat=[("bars", (60, 100, 140), 5), ("ear", (30, 34, 60))], eye=2),
    "sunfish":  dict(L=16, up=7, lo=7, a=0.55, back=(186, 150, 60), body=(236, 196, 84), belly=(246, 150, 70),
                     tail="square", tl=6, th=6, dorsal=(0.22, 0.86, 3, "spiny"), fin=(214, 170, 70),
                     pat=[("squig", (86, 160, 200)), ("ear", (214, 50, 50))]),
    "perch":    dict(L=19, up=6, lo=4.5, back=(96, 118, 60), body=(196, 196, 96), belly=(240, 234, 190),
                     tail="fork", tl=6, th=5, dorsal=(0.22, 0.62, 5, "spiny"), fin=(232, 132, 62),
                     pat=[("bars", (70, 86, 44), 6)]),
    "bass":     dict(L=19, up=5.5, lo=5, back=(64, 104, 62), body=(118, 160, 100), belly=(226, 232, 190),
                     tail="square", tl=6, th=5, dorsal=(0.25, 0.75, 4, "notch"), fin=(96, 132, 84),
                     pat=[("blotch", (46, 74, 44))], mouth="big"),
    "salmon":   dict(L=20, up=5, lo=4.5, back=(120, 128, 150), body=(226, 144, 128), belly=(242, 222, 214),
                     tail="square", tl=6, th=5, dorsal=(0.38, 0.54, 4, "tri"), fin=(170, 110, 110),
                     pat=[("dots", (60, 60, 76), 0.3, 0.85, 0.3), ("adipose", None)], mouth="hook"),
    "pike":     dict(L=22, up=3.8, lo=3.6, a=0.25, back=(66, 104, 64), body=(120, 164, 110), belly=(226, 232, 190),
                     tail="fork", tl=5, th=4, dorsal=(0.70, 0.84, 3, "tri"), fin=(150, 140, 90),
                     pat=[("dots", (220, 230, 170), 0.2, 0.9, 0.5)], mouth="duck"),
    "catfish":  dict(L=20, up=4.5, lo=5, a=0.3, back=(84, 70, 54), body=(130, 110, 84), belly=(214, 202, 176),
                     tail="round", tl=6, th=5, dorsal=(0.24, 0.34, 4, "tri"), fin=(104, 88, 68),
                     pat=[("speckle", (86, 72, 56))], mouth="wide", whisker=True),
    "sturgeon": dict(L=22, up=3.8, lo=3.8, a=0.35, back=(84, 94, 104), body=(128, 138, 148), belly=(214, 218, 222),
                     tail="hetero", tl=6, th=5, dorsal=(0.72, 0.84, 3, "tri"), fin=(104, 112, 124),
                     pat=[("scutes", (218, 222, 226))], mouth="snout", barbel=True),
    "rainbow_trout": dict(L=20, up=5, lo=4.5, back=(104, 128, 110), body=(196, 190, 214), belly=(240, 236, 244),
                     tail="square", tl=6, th=5, dorsal=(0.38, 0.54, 4, "tri"), fin=(170, 150, 170),
                     pat=[("band", (236, 118, 146)), ("dots", (50, 50, 60), 0.15, 0.95, 0.35), ("adipose", None)]),
    "mackerel": dict(L=21, up=4.5, lo=4, back=(52, 120, 132), body=(110, 170, 178), belly=(232, 240, 242),
                     tail="fork", tl=6, th=6, dorsal=(0.30, 0.44, 4, "spiny"), fin=(90, 140, 150),
                     pat=[("tiger", (24, 52, 64)), ("finlets", (190, 210, 214))]),
    "tuna":     dict(L=20, up=5.5, lo=5, a=0.4, back=(40, 64, 124), body=(96, 128, 184), belly=(226, 232, 242),
                     tail="lunate", tl=6, th=7, dorsal=(0.30, 0.44, 4, "tri"), fin=(66, 90, 150),
                     pat=[("finlets", (246, 210, 70))]),
    "cod":      dict(L=20, up=5, lo=5, back=(120, 116, 82), body=(170, 164, 122), belly=(236, 230, 206),
                     tail="square", tl=5, th=5, dorsal=(0.25, 0.85, 3, "triple"), fin=(140, 134, 98),
                     pat=[("speckle", (110, 100, 70)), ("lateral", (236, 230, 206))], barbel=True),
    "red_snapper": dict(L=18, up=6.5, lo=5.5, back=(176, 52, 56), body=(226, 96, 92), belly=(250, 188, 180),
                     tail="fork", tl=6, th=6, dorsal=(0.22, 0.80, 4, "spiny"), fin=(214, 74, 78),
                     pat=[("sheen", (246, 156, 150))], eyecol=(214, 40, 40)),
    "abyssal_tuna": dict(L=20, up=5.5, lo=5, a=0.4, back=(18, 36, 60), body=(40, 76, 104), belly=(84, 120, 140),
                     tail="lunate", tl=6, th=7, dorsal=(0.30, 0.44, 4, "tri"), fin=(30, 56, 84),
                     pat=[("photo", (110, 246, 236))], eyecol=(110, 246, 236), glow=(110, 246, 236)),
    # ---- legendaries: the same anatomy, dressed up -------------------------------
    "crimson_bass": dict(L=19, up=6, lo=5, back=(150, 30, 42), body=(214, 66, 66), belly=(250, 186, 150),
                     tail="fan", tl=7, th=7, dorsal=(0.18, 0.80, 6, "crown"), fin=(250, 196, 80),
                     pat=[("blotch", (130, 22, 34))], mouth="big", sparkle=((6, 4), (24, 23))),
    "glacier_pike": dict(L=22, up=4, lo=3.8, a=0.25, back=(96, 160, 196), body=(170, 222, 240), belly=(240, 250, 255),
                     tail="fork", tl=5, th=5, dorsal=(0.30, 0.84, 4, "ice"), fin=(210, 240, 252),
                     pat=[("dots", (255, 255, 255), 0.2, 0.9, 0.45)], mouth="duck",
                     sparkle=((4, 6), (22, 24))),
    "the_legend": dict(L=18, up=7, lo=6, back=(206, 146, 40), body=(248, 208, 90), belly=(255, 244, 196),
                     tail="fan", tl=8, th=9, dorsal=(0.20, 0.82, 6, "crown"), fin=(222, 66, 92),
                     pat=[("scales", None)], barbel=True, sparkle=((5, 4), (25, 3), (4, 24))),
    "phantom_carp": dict(L=18, up=6.5, lo=5.5, back=(110, 130, 180), body=(170, 190, 226), belly=(226, 236, 252),
                     tail="fan", tl=8, th=7, dorsal=(0.30, 0.78, 3, "long"), fin=(200, 214, 246),
                     pat=[("scales", None)], barbel=True, alpha=170, eyecol=(120, 240, 255),
                     glow=(140, 230, 255)),
}


def _fish_geom(sp):
    L = sp["L"]
    tl = sp.get("tl", 6)
    x0 = max(2, round((IC - (L + tl)) / 2))
    if sp.get("mouth") in ("duck", "snout"):
        x0 = max(3, x0)
    cy = 14 if sp["up"] < 7 else 14.5
    a, b = sp.get("a", 0.45), sp.get("b", 0.85)
    N = 18
    raw = [(t ** a) * ((1 - t) ** b) for t in [i / N for i in range(N + 1)]]
    mx = max(raw)
    ped = 0.24
    prof = []
    for i, r in enumerate(raw):
        t = i / N
        g = r / mx
        if t > 0.55:
            g = max(g, ped)
        prof.append((x0 + t * L, g))
    return x0, cy, prof, L


def _fish_pts(sp, x0, cy, prof):
    upper = [(x, cy - g * sp["up"]) for x, g in prof]
    lower = [(x, cy + g * sp["lo"]) for x, g in reversed(prof)]
    return upper + lower, upper


def _at(prof, t, sp, cy, side=-1):
    i = min(len(prof) - 1, max(0, round(t * (len(prof) - 1))))
    x, g = prof[i]
    return x, cy + side * g * (sp["up"] if side < 0 else sp["lo"])


def _draw_fish(s, name):
    sp = FISH_ART[name]
    x0, cy, prof, L = _fish_geom(sp)
    body_pts, upper = _fish_pts(sp, x0, cy, prof)
    fin = sp["fin"]
    fin_dk = dk(fin, 0.72)
    xt = x0 + L
    tl, th = sp.get("tl", 6), sp.get("th", 5)
    alpha = sp.get("alpha", 255)
    art = _ic()

    # ---- tail (behind the body)
    tail = sp.get("tail", "fork")
    ex = min(26, xt + tl)
    if tail == "fork":
        tp = [(xt - 2, cy - 1.5), (ex, cy - th), (ex - 3, cy), (ex, cy + th), (xt - 2, cy + 1.5)]
    elif tail == "lunate":
        tp = [(xt - 2, cy - 1.2), (ex - 1, cy - th - 1), (ex, cy - th + 1), (ex - 3, cy),
              (ex, cy + th - 1), (ex - 1, cy + th + 1), (xt - 2, cy + 1.2)]
    elif tail == "round":
        tp = [(xt - 2, cy - 1.5)] + [(xt + tl * 0.55 + math.cos(a) * tl * 0.5, cy + math.sin(a) * th)
                                      for a in [(-90 + i * 30) * math.pi / 180 for i in range(7)]] + [(xt - 2, cy + 1.5)]
    elif tail == "fan":
        tp = [(xt - 2, cy - 1.5), (ex - 1, cy - th), (ex, cy - th + 3), (ex - 2, cy), (ex, cy + th - 3),
              (ex - 1, cy + th), (xt - 2, cy + 1.5)]
    elif tail == "hetero":
        tp = [(xt - 2, cy - 1.5), (ex, cy - th - 1), (ex - 1, cy - th + 2), (xt + 2, cy + 3), (xt - 2, cy + 1.5)]
    else:  # square
        tp = [(xt - 2, cy - 1.5), (ex, cy - th), (ex - 1, cy), (ex, cy + th), (xt - 2, cy + 1.5)]
    vol(art, _poly(tp), fin, fin_dk, depth=1)
    for k in (-0.5, 0, 0.5):                                                         # tail rays
        pygame.draw.line(art, fin_dk, (round(xt), round(cy)), (round(ex - 2), round(cy + k * th)), 1)

    # ---- dorsal fin
    d0, d1, dh, dst = sp.get("dorsal", (0.35, 0.55, 3, "tri"))
    ax, ay = _at(prof, d0, sp, cy)
    bx, by = _at(prof, d1, sp, cy)
    if dst == "tri":
        dp = [(ax, ay + 1), (ax + (bx - ax) * 0.35, ay - dh), (bx, by + 1)]
    elif dst in ("spiny", "crown", "ice"):
        n = max(3, round((bx - ax) / 2))
        dp = [(ax, ay + 1)]
        for i in range(n):
            t = (i + 0.5) / n
            px, py = _at(prof, d0 + (d1 - d0) * t, sp, cy)
            hh = dh * (1.0 - 0.45 * t) if dst != "crown" else dh * (0.7 + 0.3 * math.sin(t * math.pi))
            dp += [(px - 0.8, py - hh), (px + 0.8, py - hh * 0.55)]
        dp.append((bx, by + 1))
    elif dst == "notch":
        mx_, my_ = _at(prof, (d0 + d1) / 2, sp, cy)
        dp = [(ax, ay + 1), (ax + 2, ay - dh), (mx_, my_ - 1), (mx_ + 2, my_ - dh + 1), (bx, by + 1)]
    elif dst == "triple":
        dp = [(ax, ay + 1)]
        for k in range(3):
            q0 = d0 + (d1 - d0) * k / 3
            q1 = d0 + (d1 - d0) * (k + 1) / 3
            px, py = _at(prof, (q0 + q1) / 2, sp, cy)
            ex_, ey_ = _at(prof, q1, sp, cy)
            dp += [(px, py - dh), (ex_, ey_ + 0.5)]
        dp.append((bx, by + 1))
    else:  # long
        mx_, my_ = _at(prof, d0 + (d1 - d0) * 0.25, sp, cy)
        dp = [(ax, ay + 1), (mx_, my_ - dh), (bx, by - dh * 0.4), (bx + 1, by + 1)]
    fcol = fin if dst != "ice" else (236, 250, 255)
    vol(art, _poly(dp), fcol, dk(fcol, 0.72), depth=1)

    # ---- anal / pelvic fins
    px_, py_ = _at(prof, 0.40, sp, cy, 1)
    vol(art, _poly([(px_ - 1, py_ - 1), (px_ + 1, py_ + 3), (px_ + 3, py_ - 1)]), fin, fin_dk, depth=1)
    qx, qy = _at(prof, 0.72, sp, cy, 1)
    vol(art, _poly([(qx - 2, qy - 1), (qx, qy + 2.5), (qx + 3, qy - 0.5)]), fin, fin_dk, depth=1)
    if any(p[0] == "adipose" for p in sp.get("pat", [])):
        zx, zy = _at(prof, 0.84, sp, cy)
        pygame.draw.circle(art, fin, (round(zx), round(zy)), 1)

    # ---- body: countershaded layer clipped to the silhouette
    body_m = shape(_poly(body_pts))
    layer = _ic()
    layer.fill(sp["body"])
    back_pts = [(x, y + (cy - y) * 0.42) for x, y in upper]
    pygame.draw.polygon(layer, sp["back"], [(round(x), round(y)) for x, y in
                                            [(x0 - 2, 0)] + back_pts + [(xt + 3, 0)]])
    pygame.draw.polygon(layer, sp["belly"], [(round(x), round(y)) for x, y in
                                             [(x0 + 1, cy + 1.2)] +
                                             [(x, cy + 1.2 + g * sp["lo"] * 0.2) for x, g in prof[2:-3]] +
                                             [(xt, cy + 8), (x0, cy + 8)]])
    rnd = random.Random(name)
    for pat in sp.get("pat", []):
        kind = pat[0]
        col = pat[1]
        if kind == "band":
            pygame.draw.line(layer, col, (x0 + 3, round(cy)), (xt, round(cy)), 2 if sp["up"] > 4 else 1)
        elif kind == "row":                                                         # spot row along the flank
            for x, g in prof[5:-4:2]:
                layer.set_at((round(x), round(cy - g * sp["up"] * 0.35)), col + (255,))
        elif kind == "sheen":
            pygame.draw.line(layer, col, (x0 + 4, round(cy - 1)), (xt - 3, round(cy - 1)), 1)
        elif kind == "lateral":
            pts = [(x, cy - g * sp["up"] * 0.35) for x, g in prof[4:-2]]
            pygame.draw.lines(layer, col, False, [(round(x), round(y)) for x, y in pts], 1)
        elif kind == "bars":
            n = pat[2]
            for i in range(n):
                t = 0.28 + 0.6 * i / max(1, n - 1)
                x, g = prof[round(t * (len(prof) - 1))]
                pygame.draw.line(layer, col, (round(x), round(cy - g * sp["up"])),
                                 (round(x - 1), round(cy + g * sp["lo"] * 0.35)), 1)
        elif kind == "dots":
            t0, t1, dens = pat[2], pat[3], pat[4]
            for x, g in prof:
                t = (x - x0) / L
                if t0 <= t <= t1:
                    for _ in range(2):
                        if rnd.random() < dens:
                            yy = cy - rnd.uniform(0.15, 0.85) * g * sp["up"]
                            layer.set_at((round(x), round(yy)), col)
        elif kind == "speckle":
            for _ in range(22):
                layer.set_at((rnd.randint(x0 + 3, round(xt)), rnd.randint(round(cy - sp["up"]), round(cy + 1))), col)
        elif kind == "blotch":
            pts = [(x, cy + math.sin((x - x0) * 0.9) * 0.8) for x, g in prof[4:-1]]
            pygame.draw.lines(layer, col, False, [(round(x), round(y)) for x, y in pts], 2)
        elif kind == "tiger":
            for i in range(6):
                x = x0 + 5 + i * 2.6
                pygame.draw.lines(layer, col, False, [(round(x), round(cy - sp["up"])), (round(x + 1), round(cy - 2.5)),
                                                      (round(x), round(cy - 1))], 1)
        elif kind == "squig":
            for yy in (cy - 2, cy + 1):
                pts = [(x0 + 4 + i, yy + (1 if i % 4 < 2 else 0)) for i in range(L - 6)]
                pygame.draw.lines(layer, col, False, [(round(x), round(y)) for x, y in pts], 1)
        elif kind == "ear":
            ex_, ey_ = _at(prof, 0.24, sp, cy)
            pygame.draw.ellipse(layer, col, (round(ex_) - 1, round(cy) - 3, 4, 3))
        elif kind == "scales":
            sc = dk(sp["body"], 0.8)
            for gx in range(round(x0 + 6), round(xt - 1), 3):
                for gy in range(round(cy - sp["up"]) + 1, round(cy + sp["lo"]), 3):
                    off = 1 if (gx // 3) % 2 else 0
                    pygame.draw.arc(layer, sc, (gx - 1, gy + off - 1, 4, 4), math.pi * 0.5, math.pi * 1.5, 1)
        elif kind == "scutes":
            for i in range(6):
                x, g = prof[4 + i * 2]
                layer.set_at((round(x), round(cy - g * sp["up"] * 0.55)), col)
                layer.set_at((round(x), round(cy + g * sp["lo"] * 0.2)), col)
    body_layer = clip(layer, body_m)
    # soft volume on the body silhouette itself (dark underside edge, lit back rim)
    lit = body_m.overlap_mask(body_m, (0, -2))
    sh = body_m.copy()
    sh.erase(lit, (0, 0))
    rim_in = body_m.overlap_mask(body_m, (0, 1))
    rim = body_m.copy()
    rim.erase(rim_in, (0, 0))
    art.blit(body_layer, (0, 0))
    _paint(art, sh, dk(sp["belly"], 0.78))
    _paint(art, rim, lt(sp["back"], 1.25))

    # ---- head details: gill, pectoral fin, mouth, eye
    gx_, gy_ = _at(prof, 0.24, sp, cy)
    gtop = cy - (cy - gy_) * 0.6
    pygame.draw.arc(art, dk(sp["body"], 0.62),
                    (round(gx_ - 3), round(gtop), 4, round((cy - gy_) * 0.6 + sp["lo"] * 0.6)),
                    -math.pi / 2, math.pi / 2, 1)
    fx, fy = _at(prof, 0.30, sp, cy, 1)
    pf = [(fx, cy + 0.5), (fx + 5, cy + 1.5), (fx + 4, cy + 3), (fx + 1, cy + 2.5)]
    pygame.draw.polygon(art, fin, [(round(x), round(y)) for x, y in pf])
    pygame.draw.line(art, fin_dk, (round(fx + 1), round(cy + 2)), (round(fx + 4), round(cy + 2)), 1)
    mouth = sp.get("mouth", "small")
    mx0, my0 = x0, cy
    mc = dk(sp["body"], 0.45)
    if mouth == "big":
        pygame.draw.line(art, mc, (round(mx0), round(my0 + 1)), (round(mx0 + 4), round(my0 + 1)), 1)
    elif mouth == "wide":
        pygame.draw.line(art, mc, (round(mx0), round(my0 + 1)), (round(mx0 + 3), round(my0 + 2)), 1)
    elif mouth == "hook":
        pygame.draw.line(art, mc, (round(mx0), round(my0)), (round(mx0 + 3), round(my0 + 1)), 1)
    elif mouth == "under":
        pygame.draw.line(art, mc, (round(mx0 + 1), round(my0 + 2)), (round(mx0 + 2), round(my0 + 2)), 1)
    elif mouth == "duck":
        vol(art, _poly([(x0 - 2, cy - 0.5), (x0 + 3, cy - 2), (x0 + 3, cy + 2), (x0 - 2, cy + 1)]),
            sp["body"], dk(sp["body"], 0.7), depth=1)
        pygame.draw.line(art, mc, (round(x0 - 2), round(cy + 0.5)), (round(x0 + 3), round(cy + 0.5)), 1)
    elif mouth == "snout":
        vol(art, _poly([(x0 - 2, cy), (x0 + 3, cy - 2), (x0 + 3, cy + 1)]), sp["back"], depth=1)
    else:
        art.set_at((round(mx0 + 1), round(my0 + 1)), mc + (255,))
    ex, ey = _at(prof, 0.12 if sp.get("a", 0.45) > 0.3 else 0.14, sp, cy)
    ey = cy - (cy - ey) * 0.4 - 0.5
    ex = round(ex + 1)
    ey = round(ey)
    er = sp.get("eye", 2)
    pygame.draw.circle(art, WHITE, (ex, ey), er)
    pygame.draw.circle(art, sp.get("eyecol", EYE), (ex, ey), 1)
    art.set_at((ex - 1, ey - 1), WHITE + (255,))
    if sp.get("barbel"):
        pygame.draw.line(art, dk(sp["body"], 0.55), (round(x0 + 1), round(cy + 1)), (round(x0 - 1), round(cy + 4)), 1)
    if sp.get("whisker"):
        wc = dk(sp["back"], 0.6)
        pygame.draw.lines(art, wc, False, [(x0 + 1, round(cy)), (x0 - 1, round(cy - 3)), (x0 - 1, round(cy - 6))], 1)
        pygame.draw.lines(art, wc, False, [(x0 + 1, round(cy + 1)), (x0 - 1, round(cy + 4)), (x0, round(cy + 7))], 1)
    for pat in sp.get("pat", []):
        if pat[0] == "finlets":
            for i in range(4):
                x, g = prof[12 + i]
                art.set_at((round(x), round(cy - g * sp["up"] - 1)), pat[1] + (255,))
                art.set_at((round(x), round(cy + g * sp["lo"] + 1)), pat[1] + (255,))

    finish(art)
    if alpha < 255:
        art.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(art, (0, 0))
    for pat in sp.get("pat", []):
        if pat[0] == "photo":                                                        # glowing photophores
            for i in range(5):
                x, g = prof[5 + i * 2]
                s.set_at((round(x), round(cy + g * sp["lo"] * 0.55)), pat[1] + (255,))
    if sp.get("glow"):
        s.set_at((ex, ey), sp["glow"] + (255,))
    for (sx, sy) in sp.get("sparkle", ()):
        sparkle(s, sx, sy)


def _fish_painter(name):
    return lambda s: _draw_fish(s, name)


# ---- bespoke odd-shaped catches (redrawn in the same style)
def _pufferfish(s):
    col = (232, 206, 110)
    for a in range(0, 360, 30):                                                      # spines
        r = math.radians(a)
        pygame.draw.line(s, (170, 140, 70), (round(14 + math.cos(r) * 7), round(15 + math.sin(r) * 7)),
                         (round(14 + math.cos(r) * 11), round(15 + math.sin(r) * 11)), 1)
    vol(s, _poly([(22, 15), (26, 11), (26, 19)]), (220, 180, 90), depth=1)          # tail
    m = vol(s, _circ(13, 15, 9), col, (196, 160, 80), depth=2)
    layer = _ic()
    pygame.draw.ellipse(layer, (250, 242, 214), (5, 16, 16, 9))                      # pale belly
    for (x, y) in ((10, 9), (15, 8), (18, 11), (12, 12)):
        pygame.draw.circle(layer, (150, 120, 60), (x, y), 1)
    s.blit(clip(layer, m), (0, 0))
    pygame.draw.circle(s, WHITE, (8, 12), 3)
    pygame.draw.circle(s, EYE, (7, 12), 2)
    s.set_at((7, 11), WHITE + (255,))
    pygame.draw.ellipse(s, (200, 90, 80), (4, 16, 4, 3))                            # pouty mouth
    finish(s)


def _halibut(s):
    col = (140, 128, 110)
    vol(s, _poly([(22, 15), (26, 10), (26, 21)]), (120, 108, 92), depth=1)          # tail fan
    m = vol(s, _ell((2, 7, 22, 16)), col, dk(col, 0.72))
    layer = _ic()
    rnd = random.Random("halibut")
    for _ in range(9):
        x, y = rnd.randint(6, 21), rnd.randint(9, 20)
        pygame.draw.circle(layer, (104, 94, 80) if rnd.random() < 0.6 else (190, 180, 160), (x, y), 1)
    pygame.draw.lines(layer, (170, 160, 140), False, [(7, 15), (12, 14), (18, 15), (22, 15)], 1)
    s.blit(clip(layer, m), (0, 0))
    for y in (7, 22):                                                                # fringe fins
        for x in range(6, 21, 2):
            s.set_at((x, y), (110, 100, 86, 255))
    for (x, y) in ((6, 11), (9, 10)):                                                # both eyes up top
        pygame.draw.circle(s, WHITE, (x, y), 2)
        s.set_at((x, y), EYE + (255,))
    pygame.draw.line(s, (80, 70, 60), (3, 14), (5, 15), 1)
    finish(s)


# ================================================================== CROPS
def _parsnip(s):
    for a in (-2.0, -1.6, -1.2):
        leaf(s, 11, 7, a, 7, 2, (110, 180, 80))
    m = vol(s, _poly([(7, 7), (15, 7), (16, 10), (12, 25), (10, 25), (6, 10)]), (238, 222, 170), (196, 172, 120))
    for y in (11, 15, 19):
        pygame.draw.line(s, (206, 186, 136), (8 + (y - 11) // 4, y), (13 - (y - 11) // 5, y), 1)
    shine(s, 9, 9, 3)
    finish(s)


def _potato(s):
    m = vol(s, _poly([(5, 12), (8, 7), (14, 5), (21, 7), (24, 13), (22, 20), (15, 23), (8, 21)]),
            (196, 156, 104), (150, 112, 72), depth=3)
    for (x, y) in ((10, 11), (17, 9), (19, 16), (12, 18), (15, 14)):
        pygame.draw.line(s, (130, 96, 60), (x, y), (x + 1, y), 1)
        s.set_at((x, y - 1), (224, 190, 140, 255))
    finish(s)


def _cauliflower(s):
    for a, x in ((-2.6, 7), (-0.5, 21), (2.2, 8), (0.9, 20)):
        leaf(s, 14, 16, a, 11, 4, (104, 170, 88))
    for (x, y, r) in ((10, 11, 4), (17, 10, 4), (14, 8, 4), (9, 15, 4), (19, 15, 4), (14, 14, 5)):
        vol(s, _circ(x, y, r), (244, 240, 222), (212, 204, 176), depth=1)
    for (x, y) in ((12, 9), (16, 12), (11, 14), (18, 9)):
        s.set_at((x, y), (218, 210, 184, 255))
    finish(s)


def _green_bean(s):
    col, cdk = (104, 186, 78), (62, 132, 50)
    for (ax, ay, bx, by, bend) in ((4, 22, 20, 4, 4), (9, 25, 25, 9, 4)):          # two curved pods
        pts = []
        for i in range(9):
            t = i / 8
            x = ax + (bx - ax) * t + bend * math.sin(t * math.pi) * 0.7
            y = ay + (by - ay) * t + bend * math.sin(t * math.pi) * 0.7
            pts.append((round(x), round(y)))
        vol(s, _many(*[_circ(x, y, 2 if 0 < i < 8 else 1) for i, (x, y) in enumerate(pts)]),
            col, cdk, depth=1)
        for x, y in pts[2:7:2]:
            s.set_at((x - 1, y - 1), lt(col, 1.18) + (255,))                        # bean bumps
        pygame.draw.line(s, (80, 130, 56), (bx, by), (bx + 2, by - 2), 1)           # stem tip
    finish(s)


def _melon(s):
    m = vol(s, _circ(14, 15, 10), (120, 196, 100), (76, 140, 66), depth=3)
    layer = _ic()
    for x in (6, 10, 14, 18, 22):
        pygame.draw.arc(layer, (54, 116, 52), (x - 7, 4, 14, 22), -1.2, 1.2, 2)
    s.blit(clip(layer, m), (0, 0))
    pygame.draw.line(s, (110, 90, 50), (14, 5), (15, 2), 2)
    leaf(s, 15, 4, -0.4, 6, 2)
    shine(s, 9, 9, 3)
    finish(s)


def _frost_melon(s):
    m = vol(s, _ell((3, 7, 22, 17)), (160, 216, 228), (104, 164, 190), depth=3)
    layer = _ic()
    for x in (8, 13, 18):
        pygame.draw.line(layer, (116, 176, 200), (x, 8), (x + 1, 23), 1)
    s.blit(clip(layer, m), (0, 0))
    pygame.draw.line(s, (120, 110, 90), (14, 7), (15, 3), 2)
    for (x, y) in ((8, 12), (19, 16)):                                               # frost flakes
        sparkle(s, x, y, (250, 255, 255), 1)
    shine(s, 8, 9, 2)
    finish(s)
    sparkle(s, 23, 5, (230, 250, 255), 2)


def _tomato(s):
    m = vol(s, _ell((4, 8, 20, 17)), (226, 72, 60), (170, 40, 40), depth=3)
    pygame.draw.arc(s, (190, 50, 46), (9, 9, 10, 15), 1.2, 2.0, 1)
    for a in range(0, 360, 72):                                                      # star calyx
        r = math.radians(a - 90)
        pygame.draw.line(s, (84, 150, 64), (14, 9), (round(14 + math.cos(r) * 4), round(9 + math.sin(r) * 2.2)), 2)
    pygame.draw.line(s, (84, 150, 64), (14, 9), (15, 5), 2)
    pygame.draw.ellipse(s, (255, 190, 176), (7, 12, 3, 4))
    finish(s)


def _blueberry(s):
    pygame.draw.line(s, (110, 90, 60), (14, 3), (9, 11), 1)
    pygame.draw.line(s, (110, 90, 60), (14, 3), (19, 10), 1)
    leaf(s, 14, 4, -0.5, 7, 2)
    for (x, y, r) in ((8, 15, 5), (19, 14, 5), (13, 21, 5)):
        vol(s, _circ(x, y, r), (86, 104, 206), (50, 58, 140), (150, 170, 240), depth=2)
        pygame.draw.circle(s, (170, 190, 240), (x - 2, y - 2), 1)                    # dusty bloom
        pygame.draw.line(s, (36, 40, 90), (x - 1, y + 1), (x + 1, y + 1), 1)         # star crown
        pygame.draw.line(s, (36, 40, 90), (x, y), (x, y + 2), 1)
    finish(s)


def _pepper(s):
    col = (240, 128, 44)
    m = vol(s, _poly([(6, 9), (11, 7), (14, 9), (17, 7), (22, 9), (23, 16), (20, 23), (16, 25),
                      (12, 25), (8, 23), (5, 16)]), col, (184, 86, 30), depth=3)
    pygame.draw.line(s, (206, 100, 34), (14, 10), (14, 22), 1)
    vol(s, _poly([(10, 8), (14, 5), (18, 8), (14, 10)]), (90, 150, 62), depth=1)
    vol(s, _line((14, 6), (16, 2), 2), (90, 150, 62), depth=1)
    pygame.draw.line(s, (255, 206, 150), (8, 12), (8, 16), 1)
    finish(s)


def _pumpkin(s):
    col, cdk = (240, 150, 50), (190, 100, 30)
    for r in ((3, 8, 10, 17), (15, 8, 10, 17)):
        vol(s, _ell(r), col, cdk, depth=2)
    vol(s, _ell((8, 7, 12, 18)), lt(col, 1.05), cdk, depth=2)
    pygame.draw.line(s, cdk, (9, 10), (9, 22), 1)
    pygame.draw.line(s, cdk, (19, 10), (19, 22), 1)
    vol(s, _poly([(12, 7), (14, 2), (17, 3), (15, 8)]), (110, 130, 60), depth=1)
    pygame.draw.arc(s, (96, 160, 70), (15, 1, 7, 6), 3.0, 6.0, 1)                    # curly vine
    shine(s, 11, 10, 3)
    finish(s)


def _corn(s):
    vol(s, _poly([(14, 25), (4, 13), (7, 10), (13, 19)]), (120, 180, 80), depth=1)   # husk leaves
    vol(s, _poly([(14, 25), (24, 12), (21, 10), (15, 19)]), (104, 164, 70), depth=1)
    m = vol(s, _ell((9, 3, 10, 21)), (246, 212, 80), (206, 166, 50), depth=2)
    layer = _ic()
    for y in range(4, 24, 2):
        for x in range(9, 20, 2):
            layer.set_at((x + (y // 2) % 2, y), (214, 172, 52, 255))
    s.blit(clip(layer, m), (0, 0))
    vol(s, _poly([(14, 25), (9, 14), (11, 13), (15, 22)]), (140, 198, 96), depth=1)
    pygame.draw.line(s, (170, 120, 70), (14, 3), (16, 0), 1)                         # silk
    finish(s)


def _cranberry(s):
    pygame.draw.lines(s, (110, 84, 60), False, [(5, 4), (11, 8), (15, 7), (21, 5)], 1)
    for a, x, y in ((-2.2, 8, 6), (-0.8, 18, 6)):
        leaf(s, x, y, a, 6, 2, (90, 150, 80))
    for (x, y, r) in ((9, 14, 4), (17, 13, 4), (13, 19, 4), (20, 20, 3), (7, 21, 3)):
        pygame.draw.line(s, (110, 84, 60), (x, y - r), (min(21, x + 1), 8), 1)
        vol(s, _circ(x, y, r), (206, 52, 72), (150, 30, 54), depth=2)
        s.set_at((x - 1, y - 2), (255, 176, 186, 255))
    finish(s)


def _eggplant(s):
    m = vol(s, _poly([(12, 7), (17, 7), (20, 12), (22, 19), (19, 24), (13, 25), (8, 22), (8, 16), (11, 11)]),
            (120, 74, 140), (80, 46, 100), depth=3)
    vol(s, _poly([(9, 8), (13, 4), (19, 6), (20, 10), (16, 8), (12, 10)]), (96, 150, 66), depth=1)
    vol(s, _line((15, 5), (17, 1), 2), (96, 150, 66), depth=1)
    pygame.draw.line(s, (196, 160, 214), (11, 14), (10, 19), 1)
    s.set_at((12, 13), WHITE + (255,))
    finish(s)


def _winter_root(s):
    col = (206, 176, 136)
    for a in (-1.9, -1.4):
        leaf(s, 14, 6, a, 5, 2, (130, 170, 110))
    vol(s, _poly([(9, 6), (19, 6), (21, 12), (17, 17), (11, 17), (7, 12)]), col, (160, 128, 90), depth=2)
    for pts in (((10, 16), (7, 22), (4, 25)), ((14, 17), (14, 23), (13, 26)), ((18, 16), (21, 22), (24, 24))):
        vol(s, _line(pts[0], pts[1], 3), col, (160, 128, 90), depth=1)
        pygame.draw.line(s, (170, 138, 100), pts[1], pts[2], 1)
    pygame.draw.line(s, (176, 144, 104), (10, 10), (18, 10), 1)
    pygame.draw.line(s, (176, 144, 104), (11, 13), (17, 13), 1)
    shine(s, 11, 8, 2)
    finish(s)
    for (x, y) in ((6, 8), (22, 9)):
        s.set_at((x, y), (240, 250, 255, 255))


def _snow_yam(s):
    m = vol(s, _poly([(4, 16), (7, 10), (13, 7), (20, 8), (24, 12), (23, 18), (17, 22), (9, 22)]),
            (226, 214, 236), (170, 150, 190), depth=3)
    layer = _ic()
    for (x, y, w) in ((9, 13, 5), (15, 16, 6), (18, 10, 4)):
        pygame.draw.ellipse(layer, (186, 150, 206), (x, y, w, 3))
    pygame.draw.ellipse(layer, (255, 255, 255), (8, 5, 14, 6))                       # snow cap
    s.blit(clip(layer, m), (0, 0))
    pygame.draw.line(s, (150, 120, 150), (23, 12), (26, 10), 1)                      # root tail
    pygame.draw.line(s, (150, 120, 150), (5, 17), (2, 19), 1)
    leaf(s, 11, 7, -2.3, 5, 2, (120, 180, 170))
    leaf(s, 13, 6, -1.4, 6, 2, (120, 180, 170))
    finish(s)
    sparkle(s, 21, 4, (240, 250, 255), 1)


def _crocus(s):
    for a in (-1.9, -1.3):
        leaf(s, 14, 26, a, 9, 1, (110, 176, 90))
    pygame.draw.line(s, (100, 170, 80), (14, 25), (14, 15), 2)
    col = (184, 140, 222)
    vol(s, _poly([(14, 4), (19, 8), (18, 15), (14, 17), (10, 15), (9, 8)]), col, (128, 90, 170), depth=2)
    vol(s, _poly([(9, 5), (12, 9), (11, 15), (7, 12)]), lt(col, 1.08), (128, 90, 170), depth=1)
    vol(s, _poly([(19, 5), (21, 12), (17, 15), (16, 9)]), lt(col, 1.08), (128, 90, 170), depth=1)
    pygame.draw.line(s, (250, 170, 60), (14, 9), (14, 13), 1)
    pygame.draw.line(s, (250, 170, 60), (12, 10), (13, 12), 1)
    pygame.draw.line(s, (250, 170, 60), (16, 10), (15, 12), 1)
    finish(s)


def _strawberry(s):
    col = (232, 70, 92)
    m = vol(s, _poly([(5, 10), (9, 7), (19, 7), (23, 10), (22, 16), (17, 23), (14, 25), (11, 23), (6, 16)]),
            col, (170, 36, 60), depth=3)
    rnd = random.Random("sb")
    for y in range(11, 23, 3):
        for x in range(7 + (y % 2), 22, 3):
            if m.get_at((x, y)):
                s.set_at((x, y), (252, 220, 120, 255))
    for a in (-2.6, -1.9, -1.2, -0.5):
        leaf(s, 14, 8, a, 6, 2, (96, 168, 76))
    pygame.draw.line(s, (96, 168, 76), (14, 7), (15, 2), 2)
    shine(s, 8, 11, 2)
    finish(s)


def _starfruit(s):
    col = (252, 214, 70)
    pts = []
    for i in range(10):
        r = 11 if i % 2 == 0 else 5
        a = math.radians(-90 + i * 36)
        pts.append((14 + math.cos(a) * r, 15 + math.sin(a) * r))
    vol(s, _poly(pts), col, (214, 160, 40), depth=2)
    for i in range(5):
        a = math.radians(-90 + i * 72)
        pygame.draw.line(s, (234, 186, 50), (14, 15), (round(14 + math.cos(a) * 8), round(15 + math.sin(a) * 8)), 1)
    s.set_at((14, 15), (200, 140, 30, 255))
    shine(s, 12, 7, 2)
    finish(s)
    sparkle(s, 23, 4)


def _grape(s):
    pygame.draw.lines(s, (120, 90, 60), False, [(14, 7), (15, 3), (18, 2)], 2)
    leaf(s, 16, 4, -0.2, 8, 3, (110, 170, 84))
    for (x, y) in ((9, 10), (14, 10), (19, 10), (11, 14), (16, 14), (21, 14), (13, 18), (18, 18), (15, 22)):
        vol(s, _circ(x, y, 3), (140, 88, 180), (96, 56, 130), depth=1)
        s.set_at((x - 1, y - 1), (214, 190, 236, 255))
    finish(s)


def _ice_berry(s):
    for (x, y, r) in ((9, 16, 5), (18, 15, 5), (14, 21, 4), (14, 10, 4)):
        vol(s, _circ(x, y, r), (176, 220, 250), (110, 164, 214), depth=2)
        pygame.draw.circle(s, (240, 252, 255), (x - 2, y - 2), 1)
    leaf(s, 16, 6, -0.6, 6, 2, (120, 190, 170))
    finish(s)
    sparkle(s, 5, 8, (250, 255, 255), 2)
    sparkle(s, 23, 22, (250, 255, 255), 1)


CROP_ART = {"parsnip": _parsnip, "potato": _potato, "cauliflower": _cauliflower,
            "green_bean": _green_bean, "melon": _melon, "tomato": _tomato,
            "blueberry": _blueberry, "pepper": _pepper, "pumpkin": _pumpkin, "corn": _corn,
            "cranberry": _cranberry, "eggplant": _eggplant, "winter_root": _winter_root,
            "snow_yam": _snow_yam, "crocus": _crocus, "frost_melon": _frost_melon,
            "strawberry": _strawberry, "starfruit": _starfruit, "grape": _grape,
            "ice_berry": _ice_berry}


def seed_packet(s, crop_icon):
    """Kraft seed packet with a window that shows a little picture of the crop."""
    vol(s, lambda t, c: pygame.draw.rect(t, c, (4, 4, 20, 22), border_radius=2),
        (214, 184, 132), (170, 138, 92), depth=2)
    for x in range(5, 24, 2):                                                        # crimped top
        s.set_at((x, 4), (170, 138, 92, 255))
    pygame.draw.line(s, (236, 212, 170), (5, 7), (22, 7), 1)
    pygame.draw.rect(s, (250, 244, 226), (7, 9, 14, 14), border_radius=2)
    mini = pygame.transform.smoothscale(crop_icon, (14, 14))
    s.blit(mini, (7, 9))
    finish(s)


# ================================================================== MATERIALS
def _stone(s):
    col = (140, 140, 152)
    vol(s, _poly([(4, 18), (7, 10), (13, 6), (20, 7), (24, 13), (23, 21), (15, 24), (7, 23)]),
        col, (96, 96, 110), depth=3)
    pygame.draw.polygon(s, (170, 170, 182), [(8, 11), (13, 7), (19, 8), (15, 12)])   # lit top face
    pygame.draw.lines(s, (104, 104, 118), False, [(15, 12), (13, 17), (16, 21)], 1)  # crack
    finish(s)


def _wood(s):
    bark, bark_dk = (150, 100, 60), (104, 66, 38)
    for (y, x) in ((15, 3), (7, 7)):
        vol(s, lambda t, c, y=y, x=x: pygame.draw.rect(t, c, (x, y, 18, 8), border_radius=3),
            bark, bark_dk, depth=2)
        pygame.draw.line(s, bark_dk, (x + 6, y + 3), (x + 13, y + 3), 1)
        vol(s, _ell((x + 14, y, 7, 8)), (232, 196, 140), (190, 150, 96), depth=1)    # end grain
        pygame.draw.ellipse(s, (196, 150, 96), (x + 16, y + 2, 3, 4), 1)
    finish(s)


def _slime_goo(s):
    col = (104, 208, 128)
    m = vol(s, _poly([(4, 22), (5, 15), (9, 9), (14, 7), (19, 9), (23, 15), (24, 22), (21, 25), (18, 23),
                      (14, 25), (10, 23), (7, 25)]), col, (60, 150, 90), depth=3)
    pygame.draw.ellipse(s, (190, 250, 200), (8, 10, 5, 3))
    s.set_at((16, 12), WHITE + (255,))
    pygame.draw.circle(s, (40, 80, 50), (11, 16), 1)
    pygame.draw.circle(s, (40, 80, 50), (17, 16), 1)
    pygame.draw.arc(s, (40, 80, 50), (12, 16, 4, 3), math.pi, 2 * math.pi, 1)
    finish(s)


def _bone(s):
    col = (242, 236, 216)
    d = _many(_line((8, 20), (20, 8), 4), _circ(6, 19, 3), _circ(9, 22, 3), _circ(19, 6, 3), _circ(22, 9, 3))
    vol(s, d, col, (200, 190, 164), depth=1)
    finish(s)


def _essence(s):
    glow = _ic()
    pygame.draw.circle(glow, (200, 150, 245, 70), (14, 14), 12)
    s.blit(glow, (0, 0))
    vol(s, _circ(14, 14, 7), (184, 124, 226), (130, 80, 180), depth=2)
    pygame.draw.circle(s, (236, 206, 252), (14, 14), 3)
    pygame.draw.arc(s, (240, 220, 255), (8, 8, 12, 12), 2.2, 3.6, 1)
    finish(s, thr=120)
    for (x, y) in ((4, 5), (23, 7), (6, 23)):
        sparkle(s, x, y, (236, 210, 255), 1)


def _void_essence(s):
    glow = _ic()
    pygame.draw.circle(glow, (110, 60, 170, 80), (14, 14), 12)
    s.blit(glow, (0, 0))
    vol(s, _circ(14, 14, 7), (70, 40, 110), (40, 20, 70), (130, 90, 190), depth=2)
    pygame.draw.arc(s, (170, 110, 230), (9, 9, 10, 10), 0.3, 3.4, 1)
    pygame.draw.circle(s, (20, 8, 34), (14, 14), 2)
    finish(s, thr=120)
    sparkle(s, 21, 6, (200, 160, 250), 1)


def _egg(col, spot=None):
    def p(s):
        vol(s, _ell((7, 4, 14, 20)), col, dk(col, 0.84), depth=2)
        if spot:
            for (x, y) in ((11, 12), (16, 9), (15, 17)):
                s.set_at((x, y), spot + (255,))
        pygame.draw.ellipse(s, WHITE, (10, 7, 3, 5))
        finish(s)
    return p


def _bottle(cap, label):
    def p(s):
        vol(s, lambda t, c: pygame.draw.rect(t, c, (11, 3, 6, 5), border_radius=1), cap, depth=1)
        glass = _many(lambda t, c: pygame.draw.rect(t, c, (7, 10, 14, 15), border_radius=3),
                      _poly([(11, 7), (17, 7), (21, 12), (7, 12)]))
        vol(s, glass, (248, 248, 252), (206, 212, 226), depth=2)
        pygame.draw.rect(s, label, (7, 15, 14, 5))
        pygame.draw.rect(s, WHITE, (11, 16, 6, 3))
        pygame.draw.line(s, WHITE, (9, 12), (9, 22), 1)
        finish(s)
    return p


def _wool(s):
    col = (246, 244, 250)
    d = _many(*[_circ(x, y, r) for x, y, r in ((9, 12, 5), (16, 9, 5), (20, 14, 5), (14, 17, 6), (8, 18, 4), (20, 20, 4))])
    vol(s, d, col, (208, 204, 222), depth=2)
    for (x, y) in ((10, 11), (15, 16), (19, 13)):
        pygame.draw.arc(s, (214, 210, 226), (x - 2, y - 2, 5, 5), 0.5, 3.0, 1)
    finish(s)


def _meat(s):
    col = (214, 96, 96)
    m = vol(s, _poly([(4, 14), (7, 8), (14, 6), (21, 8), (24, 14), (21, 21), (13, 23), (7, 20)]),
            col, (160, 60, 64), depth=3)
    layer = _ic()
    pygame.draw.lines(layer, (250, 214, 206), False, [(8, 12), (12, 14), (17, 12), (21, 14)], 1)   # marbling
    pygame.draw.lines(layer, (250, 214, 206), False, [(9, 18), (14, 17), (18, 19)], 1)
    pygame.draw.arc(layer, (252, 236, 226), (4, 6, 21, 18), 0.4, 2.8, 2)                          # fat cap
    s.blit(clip(layer, m), (0, 0))
    finish(s)


def _hide(s):
    col = (178, 132, 88)
    pts = [(6, 5), (10, 7), (18, 7), (22, 5), (22, 10), (20, 14), (23, 22), (19, 24), (14, 22),
           (9, 24), (5, 22), (8, 14), (6, 10)]
    vol(s, _poly(pts), col, (132, 92, 58), depth=2)
    for i in range(0, len(pts), 2):                                                  # stitching
        x, y = pts[i]
        s.set_at((round(x + (14 - x) * 0.25), round(y + (15 - y) * 0.25)), (240, 214, 170, 255))
    finish(s)


def _pelt(s):
    col = (150, 124, 104)
    pts = []
    for i in range(20):
        a = i / 20 * math.tau
        r = 10 if i % 2 == 0 else 8
        pts.append((14 + math.cos(a) * r, 14 + math.sin(a) * r * 0.9))
    vol(s, _poly(pts), col, (104, 84, 70), depth=2)
    for x in (10, 14, 18):
        pygame.draw.line(s, (104, 84, 70), (x, 8), (x - 1, 19), 2)
    pygame.draw.ellipse(s, (206, 184, 164), (8, 9, 5, 3))
    finish(s)


def _trophy(s):
    gold, gdk = (244, 206, 90), (190, 140, 50)
    pygame.draw.arc(s, gold, (3, 5, 8, 10), 1.4, 4.7, 2)
    pygame.draw.arc(s, gold, (17, 5, 8, 10), -1.6, 1.7, 2)
    vol(s, _poly([(8, 4), (20, 4), (19, 12), (16, 15), (12, 15), (9, 12)]), gold, gdk, depth=2)
    vol(s, lambda t, c: pygame.draw.rect(t, c, (12, 15, 4, 5)), gdk, depth=1)
    vol(s, lambda t, c: pygame.draw.rect(t, c, (7, 20, 14, 5), border_radius=1), (150, 100, 60), depth=1)
    pygame.draw.polygon(s, (120, 170, 214), [(11, 9), (15, 7), (17, 9), (15, 11)])  # fish emblem
    s.set_at((17, 9), (120, 170, 214, 255))
    shine(s, 11, 5, 2)
    finish(s)


MAT_ART = {"stone": _stone, "wood": _wood, "slime_goo": _slime_goo, "bone": _bone,
           "essence": _essence, "void_essence": _void_essence,
           "egg": _egg((250, 246, 232)), "duck_egg": _egg((222, 238, 222), (170, 196, 170)),
           "milk": _bottle((120, 170, 215), (120, 170, 215)),
           "goat_milk": _bottle((176, 150, 108), (176, 150, 108)),
           "wool": _wool, "meat": _meat, "hide": _hide, "pelt": _pelt, "fish_trophy": _trophy}


# ================================================================== FOOD
def _plate(s, y=17, h=9):
    vol(s, _ell((2, y, 24, h)), (236, 238, 244), (190, 194, 208), depth=2)
    pygame.draw.ellipse(s, (250, 250, 254), (6, y + 2, 16, h - 4))


def steam(s, xs=(10, 16)):
    for x in xs:
        pygame.draw.lines(s, (255, 255, 255), False, [(x, 9), (x + 1, 6), (x, 3)], 1)


def _bowl(s, soup, soup_dk=None, band=(208, 108, 90)):
    vol(s, _many(_ell((3, 11, 22, 9)), _poly([(3, 15), (25, 15), (22, 22), (18, 25), (10, 25), (6, 22)])),
        (236, 232, 222), (190, 180, 168), depth=2)
    pygame.draw.rect(s, band, (5, 20, 18, 2))                                        # glaze band
    pygame.draw.ellipse(s, soup_dk or dk(soup, 0.84), (5, 12, 18, 6))
    pygame.draw.ellipse(s, soup, (6, 12, 16, 5))


def _fried_egg(s):
    _plate(s)
    vol(s, _poly([(6, 18), (9, 14), (15, 13), (21, 15), (22, 19), (17, 22), (10, 22)]), (254, 254, 250),
        (224, 222, 214), depth=1)
    vol(s, _circ(14, 17, 3), (252, 196, 60), (224, 150, 30), depth=1)
    s.set_at((13, 16), WHITE + (255,))
    finish(s)


def _milk_tea(s):
    vol(s, lambda t, c: pygame.draw.rect(t, c, (7, 8, 13, 16), border_radius=2), (250, 250, 252),
        (206, 210, 224), depth=1)
    pygame.draw.rect(s, (208, 164, 116), (8, 11, 11, 12), border_radius=1)
    pygame.draw.line(s, (236, 214, 186), (9, 12), (17, 12), 1)
    for (x, y) in ((10, 20), (13, 21), (16, 20), (12, 18)):                          # boba pearls
        pygame.draw.circle(s, (70, 44, 34), (x, y), 1)
    pygame.draw.arc(s, (230, 232, 240), (17, 11, 7, 9), -1.4, 1.4, 2)                # handle
    pygame.draw.line(s, (240, 110, 120), (15, 3), (13, 12), 2)                       # straw
    finish(s)


def _veg_stew(s):
    _bowl(s, (170, 104, 60))
    for (x, y, c) in ((9, 14, (240, 140, 60)), (14, 13, (230, 214, 160)), (18, 15, (240, 140, 60)),
                      (12, 15, (110, 170, 80))):
        pygame.draw.rect(s, c, (x, y, 2, 2))
    finish(s)
    steam(s)


def _fish_dinner(s):
    _plate(s)
    body = [(5, 18), (10, 14), (17, 14), (20, 17), (17, 21), (10, 21)]
    vol(s, _many(_poly(body), _poly([(19, 17), (24, 13), (24, 21)])), (220, 158, 90), (170, 108, 60), depth=1)
    for x in (10, 13, 16):
        pygame.draw.line(s, (120, 70, 40), (x, 15), (x - 1, 20), 1)                  # grill marks
    s.set_at((7, 17), EYE + (255,))
    vol(s, _poly([(18, 21), (22, 19), (24, 22), (21, 24)]), (250, 230, 90), depth=1)  # lemon wedge
    finish(s)


def _pumpkin_soup(s):
    _bowl(s, (240, 150, 56))
    pygame.draw.arc(s, (252, 240, 220), (10, 12, 8, 5), 0.3, 4.5, 1)                 # cream swirl
    for (x, y) in ((8, 14), (19, 14)):
        pygame.draw.rect(s, (110, 150, 70), (x, y, 2, 1))
    finish(s)
    steam(s)


def _fruit_salad(s):
    _bowl(s, (250, 236, 210))
    for (x, y, c, r) in ((9, 12, (80, 96, 200), 2), (14, 11, (236, 80, 100), 2), (19, 12, (130, 210, 110), 2),
                         (12, 14, (250, 210, 80), 2), (17, 14, (240, 140, 60), 2)):
        vol(s, _circ(x, y, r), c, depth=1)
    leaf(s, 14, 10, -1.2, 4, 1, (110, 190, 90))
    finish(s)


def _roast_meat(s):
    _plate(s)
    vol(s, _many(_line((17, 12), (23, 6), 3), _circ(23, 5, 2), _circ(25, 7, 2)), (246, 238, 220), depth=1)
    m = vol(s, _ell((4, 10, 16, 12)), (184, 104, 58), (130, 66, 36), depth=2)
    pygame.draw.arc(s, (230, 160, 100), (6, 11, 10, 7), 1.6, 3.0, 1)
    shine(s, 9, 12, 2, (250, 214, 170))
    finish(s)


def _cheese(s):
    vol(s, lambda t, c: pygame.draw.rect(t, c, (3, 19, 22, 5), border_radius=2), (176, 124, 76),
        (130, 88, 52), depth=1)                                                      # board
    m = vol(s, _poly([(5, 19), (5, 12), (22, 7), (22, 19)]), (250, 212, 90), (214, 170, 60), depth=2)
    pygame.draw.polygon(s, (255, 234, 150), [(5, 12), (22, 7), (22, 9), (6, 13)])
    for (x, y, r) in ((10, 16, 2), (17, 13, 1), (18, 17, 1)):
        pygame.draw.circle(s, (220, 176, 60), (x, y), r)
    finish(s)


def _omelette(s):
    _plate(s)
    vol(s, lambda t, c: pygame.draw.ellipse(t, c, (4, 11, 20, 12)), (250, 214, 96), (222, 170, 60), depth=2)
    pygame.draw.line(s, (222, 170, 60), (5, 17), (23, 17), 1)
    for (x, y, c) in ((9, 14, (220, 70, 60)), (14, 13, (110, 176, 80)), (18, 14, (240, 130, 50))):
        pygame.draw.rect(s, c, (x, y, 2, 2))
    finish(s)


def _corn_soup(s):
    _bowl(s, (246, 214, 110))
    for (x, y) in ((9, 14), (12, 13), (15, 14), (18, 13), (13, 15)):
        pygame.draw.rect(s, (252, 190, 50), (x, y, 2, 1))
    pygame.draw.rect(s, (110, 170, 80), (17, 15, 2, 1))
    finish(s)
    steam(s)


def _steak_plate(s):
    _plate(s)
    vol(s, _poly([(4, 16), (7, 11), (15, 10), (18, 13), (16, 20), (8, 21)]), (150, 78, 56), (104, 50, 36), depth=2)
    for x in (8, 11, 14):
        pygame.draw.line(s, (80, 36, 26), (x, 12), (x + 2, 19), 1)
    vol(s, _circ(21, 16, 3), (236, 206, 140), depth=1)                               # potato
    vol(s, _poly([(18, 20), (22, 19), (24, 22)]), (240, 130, 50), depth=1)           # pepper
    leaf(s, 21, 13, -1.0, 3, 1)
    finish(s)


def _pumpkin_pie(s):
    _plate(s)
    vol(s, _poly([(4, 19), (22, 12), (23, 16), (6, 22)]), (220, 170, 100), (170, 120, 60), depth=1)  # crust side
    vol(s, _poly([(4, 19), (14, 9), (22, 12)]), (234, 140, 60), (200, 110, 40), depth=1)             # filling top
    pygame.draw.line(s, (240, 200, 140), (14, 9), (22, 12), 2)                                       # crust rim
    vol(s, _circ(13, 12, 3), (254, 250, 240), depth=1)                                               # cream
    finish(s)


def _custard(s):
    _plate(s)
    vol(s, _poly([(7, 21), (9, 10), (19, 10), (21, 21)]), (252, 222, 130), (220, 180, 80), depth=2)
    pygame.draw.ellipse(s, (170, 100, 40), (9, 8, 10, 4))                            # caramel top
    pygame.draw.line(s, (170, 100, 40), (9, 11), (9, 14), 1)
    pygame.draw.line(s, (170, 100, 40), (18, 11), (19, 13), 1)
    s.set_at((12, 9), (240, 190, 120, 255))
    finish(s)


def _goat_cheese(s):
    vol(s, lambda t, c: pygame.draw.rect(t, c, (3, 19, 22, 5), border_radius=2), (176, 124, 76),
        (130, 88, 52), depth=1)
    vol(s, lambda t, c: pygame.draw.rect(t, c, (4, 10, 13, 10), border_radius=4), (248, 246, 236),
        (212, 206, 190), depth=2)
    vol(s, _ell((15, 11, 8, 9)), (252, 250, 242), (212, 206, 190), depth=1)          # cut face
    for (x, y) in ((7, 13), (11, 15), (8, 17)):
        s.set_at((x, y), (120, 160, 90, 255))                                        # herbs
    leaf(s, 17, 9, -0.6, 5, 2, (110, 176, 90))
    finish(s)


def _spicy_curry(s):
    _bowl(s, (214, 120, 48), band=(200, 60, 50))
    vol(s, _ell((6, 11, 8, 5)), (252, 250, 242), (214, 210, 200), depth=1)           # rice mound
    vol(s, _poly([(16, 12), (21, 11), (22, 13), (17, 14)]), (220, 50, 40), depth=1)  # chili
    pygame.draw.line(s, (90, 150, 60), (21, 11), (23, 10), 1)
    finish(s)
    steam(s, (11, 17))


def _dumplings(s):
    _plate(s)
    for x in (3, 10, 17):
        vol(s, _many(_ell((x, 11, 9, 9)), lambda t, c, x=x: pygame.draw.rect(t, c, (x, 15, 9, 5))),
            (246, 226, 180), (206, 172, 116), depth=1)
        pygame.draw.ellipse(s, (180, 140, 90), (x, 11, 9, 9), 1)
        pygame.draw.line(s, (180, 140, 90), (x, 19), (x + 8, 19), 1)
        for k in range(3):                                                           # pleats
            s.set_at((x + 2 + k * 2, 12), (196, 160, 110, 255))
    for a in (-0.9, -2.3, 0.6):                                                      # lucky clover
        leaf(s, 23, 8, a, 4, 2, (90, 180, 90))
    finish(s)


def _miners_pie(s):
    vol(s, _ell((2, 15, 24, 10)), (150, 156, 170), (104, 110, 124), depth=1)         # pie tin
    m = vol(s, _ell((3, 8, 22, 14)), (228, 176, 96), (180, 124, 60), depth=2)
    layer = _ic()
    for x in (8, 13, 18):
        pygame.draw.line(layer, (182, 122, 58), (x, 8), (x + 2, 22), 1)              # lattice
    for y in (12, 16):
        pygame.draw.line(layer, (182, 122, 58), (3, y), (25, y), 1)
    s.blit(clip(layer, m), (0, 0))
    vol(s, _poly([(12, 5), (16, 4), (18, 8), (13, 9)]), (212, 124, 70), depth=1)     # copper nugget
    finish(s)
    sparkle(s, 20, 4, (255, 230, 190), 1)


def _sushi(s):
    vol(s, lambda t, c: pygame.draw.rect(t, c, (2, 17, 24, 6), border_radius=2), (196, 150, 96),
        (150, 108, 64), depth=1)                                                     # wooden geta
    for x in (7, 14, 21):
        vol(s, _circ(x, 13, 4), (44, 60, 52), depth=1)                               # nori
        pygame.draw.circle(s, (252, 250, 244), (x, 13), 3)                           # rice
        pygame.draw.circle(s, (244, 124, 96), (x, 13), 1)                            # salmon
        s.set_at((x + 1, 12), (250, 170, 150, 255))
    finish(s)


def _farmers_lunch(s):
    _plate(s)
    vol(s, _poly([(4, 18), (6, 14), (11, 13), (14, 16), (12, 21), (6, 21)]), (254, 254, 250),
        (224, 222, 214), depth=1)                                                    # egg
    vol(s, _circ(9, 17, 2), (252, 196, 60), depth=1)
    vol(s, _poly([(14, 13), (19, 12), (23, 20), (21, 21)]), (238, 222, 170), (196, 172, 120), depth=1)
    leaf(s, 16, 12, -2.0, 4, 1)
    leaf(s, 17, 12, -1.3, 4, 1)
    finish(s)


def _hero_stew(s):
    vol(s, _line((20, 13), (24, 3), 2), STEEL, STEEL_DK, depth=1)                    # tiny sword
    vol(s, _line((19, 6), (25, 8), 2), (222, 180, 84), depth=1)
    _bowl(s, (140, 64, 44), band=(90, 110, 170))
    for (x, y, c) in ((8, 13, (196, 116, 84)), (12, 14, (240, 150, 60)), (16, 13, (196, 116, 84))):
        pygame.draw.rect(s, c, (x, y, 3, 2))
    finish(s)


def _yam_porridge(s):
    _bowl(s, (234, 222, 240), band=(150, 120, 190))
    for (x, y) in ((9, 13), (14, 14), (17, 12)):
        pygame.draw.rect(s, (176, 136, 206), (x, y, 2, 2))
    vol(s, _line((17, 13), (23, 5), 2), (220, 206, 180), depth=1)                    # spoon
    finish(s)
    steam(s, (9,))


def _honey_tea(s):
    vol(s, lambda t, c: pygame.draw.rect(t, c, (6, 9, 13, 15), border_radius=3), (250, 250, 252),
        (206, 210, 224), depth=1)
    pygame.draw.rect(s, (232, 160, 60), (7, 12, 11, 11), border_radius=2)
    pygame.draw.line(s, (252, 204, 110), (8, 13), (16, 13), 1)
    pygame.draw.arc(s, (230, 232, 240), (16, 11, 7, 9), -1.4, 1.4, 2)
    vol(s, _line((12, 12), (20, 3), 1), (170, 110, 60), depth=1)                     # dipper
    vol(s, _ell((18, 1, 5, 5)), (240, 180, 60), (200, 130, 40), depth=1)
    finish(s)
    steam(s, (9,))


def _wild_salad(s):
    _bowl(s, (126, 190, 96), band=(110, 160, 90))
    for (x, y, c, a) in ((9, 13, (170, 222, 130), -2.4), (14, 12, (96, 160, 80), -1.5),
                         (19, 13, (150, 206, 120), -0.6)):
        leaf(s, x, y + 2, a, 5, 2, c)
    vol(s, _circ(16, 12, 2), (250, 206, 64), depth=1)                                # dandelion
    finish(s)


def _berry_tart(s):
    _plate(s)
    vol(s, _ell((4, 10, 20, 12)), (226, 176, 104), (180, 128, 66), depth=2)          # crust
    pygame.draw.ellipse(s, (110, 50, 110), (6, 11, 16, 8))                           # filling
    for (x, y) in ((9, 14), (13, 13), (17, 14), (11, 16), (15, 16), (19, 16)):
        vol(s, _circ(x, y, 1), (70, 36, 96), (40, 20, 60), depth=1)
        s.set_at((x - 1, y - 1), (180, 140, 210, 255))
    leaf(s, 16, 12, -1.0, 4, 2, (130, 210, 120))
    finish(s)


def _cookies(s):
    _plate(s)
    for (x, y) in ((8, 17), (19, 17), (14, 11)):
        vol(s, _circ(x, y, 5), (222, 170, 100), (176, 124, 70), depth=1)
        pygame.draw.circle(s, (150, 100, 56), (x, y), 5, 1)
        for (dx, dy) in ((-2, -1), (1, 1), (1, -3)):
            pygame.draw.rect(s, (110, 70, 40), (x + dx, y + dy, 2, 1))
    finish(s)


def _mushroom_soup(s):
    _bowl(s, (220, 190, 140), band=(170, 120, 70))
    vol(s, _ell((8, 11, 6, 4)), (240, 172, 72), depth=1)                             # chanterelles
    vol(s, _ell((14, 12, 6, 4)), (226, 150, 60), depth=1)
    pygame.draw.line(s, (100, 160, 80), (18, 14), (21, 13), 1)
    finish(s)
    steam(s)

FOOD_ART = {"spicy_curry": _spicy_curry, "lucky_dumplings": _dumplings, "miners_pie": _miners_pie,
            "sushi_roll": _sushi, "farmers_lunch": _farmers_lunch, "hero_stew": _hero_stew,
            "yam_porridge": _yam_porridge, "honey_tea": _honey_tea, "wild_salad": _wild_salad,
            "berry_tart": _berry_tart, "hazelnut_cookies": _cookies, "mushroom_soup": _mushroom_soup,
            "fried_egg": _fried_egg, "milk_tea": _milk_tea, "veg_stew": _veg_stew,
            "fish_dinner": _fish_dinner, "pumpkin_soup": _pumpkin_soup, "fruit_salad": _fruit_salad,
            "roast_meat": _roast_meat, "cheese": _cheese, "veggie_omelette": _omelette,
            "corn_soup": _corn_soup, "steak_plate": _steak_plate, "pumpkin_pie": _pumpkin_pie,
            "egg_custard": _custard, "goat_cheese": _goat_cheese}


ITEM_ART = {}
ITEM_ART.update({k: _fish_painter(k) for k in FISH_ART})
ITEM_ART.update({"pufferfish": _pufferfish, "halibut": _halibut})
ITEM_ART.update(CROP_ART)
ITEM_ART.update(MAT_ART)
ITEM_ART.update(FOOD_ART)

# legacy-drawn icons that only need the shared outline to match the new set
OUTLINE_ONLY = {"copper", "iron", "gold_ore", "iridium_ore", "sprinkler", "sprinkler2", "bat_wing",
                "swordfish", "golden_swordfish", "coelacanth", "kraken_spawn", "maelstrom_ray",
                "eel", "void_eel", "the_leviathan", "unseeing_maw"}
