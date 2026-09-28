"""Furniture expansion pack (2026-09-28): the iso 3D models and the tabletop
models of ~45 new catalogue pieces, kept in their own module so the shared
isofurn.py only gains two small dispatch branches.

Same rules as isofurn (read its docstring):
* ground pieces are authored in the canonical rot-0 frame through isofurn.draw's
  own `box` / `op` closures, so every part is depth-sorted with _op_cmp and
  turns with the piece; parts never interpenetrate (shared z / x / y bounds);
* face detail only on faces that really face the camera (vx1 / vy1);
* 1x1 cabinets face canonical +x like the dresser/fridge, 2x1 pieces face +y
  like the piano/fireplace, figures (teddy) face +y like the seats.

Round things (pots, vases, tubs, cakes...) use `lathe()`: a body of revolution
from a (z, radius) profile, silhouette + cylinder shading bands + lit top, so
they read as real volumes instead of flat circles.

Tabletop items (layer "top") are drawn by `draw_top()` through a tiny local
frame `_T` (l = across, f = toward the item's FRONT) that honours `rot`
(0-3 quarter turns; TOP_FRONT says where each rot points) and depth-sorts its
own parts the same way.
"""
import functools
import math

import pygame

from .isofurn import _box, _diamond, _rface, _yface, _up, _lt, _dk, _mid, _op_cmp

WOOD = (150, 110, 70)
WOOD_LT = (196, 152, 104)
METAL = (188, 192, 200)
BRASS = (214, 176, 92)
GOLD = (240, 200, 96)
CREAM = (246, 240, 226)
LEAF = (64, 146, 82)
LEAF_LT = (104, 184, 112)
LEAF_DK = (38, 100, 58)
U_PX = 35.78                      # screen length of one tile edge (64x32 iso)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _ticks():
    return pygame.time.get_ticks()


def _ceramic(color):
    """Glazed-porcelain tint of a palette colour (bath fixtures, vases)."""
    return _mix(color, (250, 250, 252), 0.68)


# ------------------------------------------------------------------ primitives
def _ring(P, cx, cy, rx, ry, z, n=24, p=2.0):
    """Screen points of a horizontal (super)ellipse at height z (tile radii)."""
    out = []
    e = 2.0 / p
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        if p != 2.0:
            c = math.copysign(abs(c) ** e, c)
            s = math.copysign(abs(s) ** e, s)
        out.append(_up(P(cx + rx * c, cy + ry * s), z))
    return out


def _arcs(ring):
    """(front, back) halves of a projected ring, both running left -> right."""
    n = len(ring)
    iL = min(range(n), key=lambda i: (ring[i][0], ring[i][1]))
    iR = max(range(n), key=lambda i: (ring[i][0], -ring[i][1]))
    fw = [ring[(iL + k) % n] for k in range((iR - iL) % n + 1)]
    bw = [ring[(iL - k) % n] for k in range((iL - iR) % n + 1)]
    fy = sum(p[1] for p in fw) / len(fw)
    by = sum(p[1] for p in bw) / len(bw)
    return (fw, bw) if fy >= by else (bw, fw)


def _at(arc, t):
    """Point a fraction t (0 left .. 1 right) along an arc (index-uniform)."""
    if len(arc) == 1:
        return arc[0]
    f = max(0.0, min(1.0, t)) * (len(arc) - 1)
    i = min(int(f), len(arc) - 2)
    return _mid(arc[i], arc[i + 1], f - i)


def _seg(arc, t0, t1):
    """The sub-arc between fractions t0 and t1 (in that order)."""
    n = len(arc) - 1
    if n <= 0:
        return [arc[0]]
    lo, hi = sorted((t0, t1))
    pts = [_at(arc, lo)] + [arc[i] for i in range(n + 1) if lo * n < i < hi * n] + [_at(arc, hi)]
    return pts if t0 <= t1 else pts[::-1]


def lathe(surf, P, cx, cy, prof, col, asp=1.0, n=24, p=2.0, top=True, outline=True,
          shade=True):
    """Body of revolution at tile point (cx, cy): `prof` = [(z px, radius
    tiles), ...] bottom -> top; `asp` squashes the y radius, `p` > 2 makes the
    rings rounded squares. Draws a shaded silhouette (lit left, dark right)
    and, with `top`, the lit top cap. Returns the rings (screen points)."""
    # a profile entry may carry a centre offset (z, r, dx, dy): rings that
    # drift sideways as they rise (a bean bag's back, a leaning sack)
    rings = [_ring(P, cx + (e[2] if len(e) > 2 else 0.0), cy + (e[3] if len(e) > 3 else 0.0),
                   e[1], e[1] * asp, e[0], n, p) for e in prof]
    arcs = [_arcs(rg) for rg in rings]
    left = [a[0][0] for a in arcs]
    right = [a[0][-1] for a in arcs]
    sil = (list(arcs[0][0]) + right[1:] + list(reversed(arcs[-1][1]))[1:]
           + list(reversed(left))[1:-1])
    if len(sil) >= 3:
        pygame.draw.polygon(surf, _dk(col, 0.80) if shade else col, sil)
        if shade and len(arcs) > 1:
            for t0, t1, f in ((0.0, 0.56, 0.90), (0.10, 0.30, 0.99), (0.80, 1.0, 0.70)):
                band = (_seg(arcs[0][0], t0, t1)
                        + [_at(a[0], t1) for a in arcs[1:-1]]
                        + _seg(arcs[-1][0], t1, t0)
                        + [_at(a[0], t0) for a in reversed(arcs[1:-1])])
                if len(band) >= 3:
                    pygame.draw.polygon(surf, _dk(col, f), band)
        if outline == "nobase":                # flows out of the part below it
            nb = len(arcs[0][0])
            pygame.draw.lines(surf, _dk(col, 0.5), False, sil[nb - 1:] + [sil[0]], 1)
        elif outline:
            pygame.draw.polygon(surf, _dk(col, 0.5), sil, 1)
    if top and len(rings[-1]) >= 3:
        pygame.draw.polygon(surf, _lt(col, 1.12), rings[-1])
        if outline:
            pygame.draw.polygon(surf, _dk(col, 0.5), rings[-1], 1)
    return rings


def _poly(surf, col, pts, width=0):
    if len(pts) >= 3:
        pygame.draw.polygon(surf, col, pts, width)


def _apoly(surf, rgba, pts):
    """Translucent polygon (glass, water, glow) via a small alpha layer."""
    if len(pts) < 3:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)) - 1, int(min(ys)) - 1
    w, h = int(max(xs)) - x0 + 2, int(max(ys)) - y0 + 2
    if w <= 0 or h <= 0:
        return
    lay = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(lay, rgba, [(x - x0, y - y0) for x, y in pts])
    surf.blit(lay, (x0, y0))


def _glow(surf, c, r, col, a=70):
    """Soft round light pool centred on screen point c."""
    r = int(r)
    if r <= 0:
        return
    lay = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
    for i in range(6, 0, -1):
        rr = r * i / 6
        pygame.draw.circle(lay, col + (int(a * (1 - i / 7) ** 1.5),), (r + 1, r + 1), int(rr))
    surf.blit(lay, (int(c[0]) - r - 1, int(c[1]) - r - 1))


def _clipped(surf, clip, draw_fn):
    """Run draw_fn(layer, shift) and keep only what lands inside polygon
    `clip` (a tub's opening, a bowl rim...). shift(pts) maps screen points
    into the layer."""
    if len(clip) < 3:
        return
    xs = [p[0] for p in clip]
    ys = [p[1] for p in clip]
    x0, y0 = int(min(xs)) - 2, int(min(ys)) - 2
    w, h = int(max(xs)) - x0 + 4, int(max(ys)) - y0 + 4
    lay = pygame.Surface((w, h), pygame.SRCALPHA)

    def shift(pts):
        return [(x - x0, y - y0) for x, y in pts]
    draw_fn(lay, shift)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), shift(clip))
    lay.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(lay, (x0, y0))


def _puff(surf, c, r, a, col=(248, 250, 252)):
    """A soft translucent round puff (steam, mist)."""
    r = max(1, int(r))
    lay = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
    pygame.draw.circle(lay, col + (max(0, min(255, int(a))),), (r + 1, r + 1), r)
    surf.blit(lay, (int(c[0]) - r - 1, int(c[1]) - r - 1))


def _px(surf, p, col):
    """One pixel (eyes, glints) -- safe off-surface."""
    x, y = int(round(p[0])), int(round(p[1]))
    if 0 <= x < surf.get_width() and 0 <= y < surf.get_height():
        surf.set_at((x, y), col)


def _star(c, r, r2=None, n=5, rot=-math.pi / 2):
    r2 = r * 0.45 if r2 is None else r2
    pts = []
    for i in range(2 * n):
        a = rot + i * math.pi / n
        rr = r if i % 2 == 0 else r2
        pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr))
    return pts


def _heart(c, s):
    pts = []
    for i in range(24):
        t = i / 24 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((c[0] + x * s / 16, c[1] - y * s / 16))
    return pts


def _quad(fp, u0, v0, u1, v1):
    return [fp(u0, v0), fp(u1, v0), fp(u1, v1), fp(u0, v1)]


def _ellipse_on(fp, uc, vc, ru, rv, n=18):
    """An ellipse painted on a face mapper fp(u, v)."""
    return [fp(uc + math.cos(a) * ru, vc + math.sin(a) * rv)
            for a in (i * 2 * math.pi / n for i in range(n))]


def _ipt(p):
    return (int(round(p[0])), int(round(p[1])))


# ================================================================= GROUND
class _G:
    """Everything a ground model needs (isofurn.draw's closures + state)."""
    __slots__ = ("surf", "P", "box", "op", "x0", "y0", "x1", "y1", "color", "on",
                 "rot", "vx1", "vy1")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def xface(self, xc, ya, yb, h, base=0):
        """Mapper for the canonical +x-facing face at x = xc (see _rface)."""
        return _rface(self.P, xc, ya, yb, h, base)

    def yface(self, yc, xa, xb, h, base=0):
        return _yface(self.P, yc, xa, xb, h, base)

    def S(self, x, y, z=0):
        """Screen point of canonical (x, y) lifted z px."""
        return _up(self.P(x, y), z)

    def front_dir(self):
        """Screen direction (unit) of the canonical +y side (a figure's face)."""
        a = self.P(0.5, 0.5)
        b = self.P(0.5, 1.5)
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L


_GROUND = {}


def _ground(*kinds):
    def deco(fn):
        for k in kinds:
            _GROUND[k] = fn
        return fn
    return deco


GROUND = _GROUND                      # kind -> model fn (filled below)
FLAT = {"bath_mat"}                   # floor-layer: drawn flat, no parts


def draw_ground(kind, **kw):
    """Called by isofurn.draw for pack kinds. Returns True for flat (floor)
    pieces that drew immediately (the caller then skips its part sort)."""
    g = _G(**kw)
    _GROUND[kind](g)
    return kind in FLAT


# ---------------------------------------------------------------- living
@_ground("side_table")
def _side_table(g):
    col, legc = g.color, _dk(WOOD, 0.8)
    for lx, ly in ((0.20, 0.20), (0.70, 0.20), (0.20, 0.70), (0.70, 0.70)):
        g.box(lx, ly, lx + 0.10, ly + 0.10, 5, legc)                    # lower legs
        g.box(lx, ly, lx + 0.10, ly + 0.10, 7, legc, base=7)            # upper legs
    g.box(0.17, 0.17, 0.83, 0.83, 2, _dk(col, 0.86), base=5)           # low shelf

    def _drawer(tp):
        if not g.vx1:
            return
        fp = g.xface(0.80, 0.20, 0.80, 6, base=14)
        q = _quad(fp, 0.16, 0.16, 0.84, 0.86)
        pygame.draw.polygon(g.surf, _lt(col, 1.08), q)
        pygame.draw.polygon(g.surf, _dk(col, 0.5), q, 1)
        pygame.draw.circle(g.surf, BRASS, _ipt(fp(0.5, 0.52)), 1)
    g.box(0.20, 0.20, 0.80, 0.80, 6, col, base=14, decor=_drawer)     # drawer apron
    g.box(0.15, 0.15, 0.85, 0.85, 3, col, base=20)                     # top


@_ground("writing_desk")
def _writing_desk(g):
    col, top = g.color, WOOD_LT
    ink = _dk(col, 0.5)

    def _drawers(tp):
        if not g.vy1:
            return
        fp = g.yface(0.88, 0.08, 0.70, 21)
        for v0, v1 in ((0.08, 0.36), (0.40, 0.66), (0.70, 0.94)):
            q = _quad(fp, 0.10, v0, 0.90, v1)
            pygame.draw.polygon(g.surf, _lt(col, 1.06), q)
            pygame.draw.polygon(g.surf, ink, q, 1)
            pygame.draw.line(g.surf, BRASS, fp(0.40, (v0 + v1) / 2), fp(0.60, (v0 + v1) / 2), 2)
    g.box(0.08, 0.12, 0.70, 0.88, 21, col, decor=_drawers)             # drawer pedestal
    legc = _dk(col, 0.82)
    g.box(1.80, 0.14, 1.90, 0.24, 17, legc)                            # right legs
    g.box(1.80, 0.76, 1.90, 0.86, 17, legc)
    g.box(0.70, 0.14, 1.80, 0.20, 11, _dk(col, 0.86), base=6)          # modesty panel

    def _mid_drawer(tp):
        if not g.vy1:
            return
        fp = g.yface(0.88, 0.70, 1.92, 4, base=17)
        q = _quad(fp, 0.14, 0.10, 0.86, 0.92)
        pygame.draw.polygon(g.surf, _lt(col, 1.05), q)
        pygame.draw.polygon(g.surf, ink, q, 1)
        pygame.draw.line(g.surf, BRASS, fp(0.44, 0.5), fp(0.56, 0.5), 2)
    g.box(0.70, 0.12, 1.92, 0.88, 4, col, base=17, decor=_mid_drawer)  # apron
    g.box(0.04, 0.06, 1.96, 0.94, 3, top, base=21)                     # wooden top


@_ground("bean_bag")
def _bean_bag(g):
    col = g.color

    # one squashy teardrop: a wide seat whose rings drift toward the back
    # (canonical -y) as they rise into a slumped backrest
    seat = [(0, 0.34), (3, 0.41), (7, 0.42), (10, 0.40)]
    rise = [(10, 0.40, 0, -0.02), (14, 0.35, 0, -0.10), (18, 0.29, 0, -0.17),
            (22, 0.22, 0, -0.21), (24.5, 0.14, 0, -0.23), (25.5, 0.05, 0, -0.24)]

    def _body():
        lathe(g.surf, g.P, 0.5, 0.52, seat + rise[1:], col, top=False, n=28)
        dent = _ring(g.P, 0.5, 0.66, 0.23, 0.19, 10)               # the sat-in hollow
        pygame.draw.polygon(g.surf, _lt(col, 1.06), dent)
        pygame.draw.lines(g.surf, _dk(col, 0.78), False, _arcs(dent)[1], 1)
    g.op(0.08, 0.10, 0.92, 0.94, 0, 10, _body)
    if not g.vy1:
        # the backrest faces the camera: paint it again OVER an away-facing
        # sitter (the rest of the bag stays under them)
        def _back():
            lathe(g.surf, g.P, 0.5, 0.52, rise, col, top=False, n=28, outline="nobase")
        g.op(0.10, 0.05, 0.90, 0.38, 10, 25, _back)


@_ground("floor_cushion")
def _floor_cushion(g):
    col = g.color

    def _fn():
        lathe(g.surf, g.P, 0.5, 0.5, [(0, 0.30), (3, 0.36), (6, 0.35), (7, 0.30)],
              col, p=4.0, n=32)
        c = g.S(0.5, 0.5, 7)
        for dx, dy in ((0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)):  # tufting creases
            pygame.draw.line(g.surf, _dk(col, 0.85), c, g.S(0.5 + (dx - 0.5) * 0.5,
                                                              0.5 + (dy - 0.5) * 0.5, 7), 1)
        pygame.draw.circle(g.surf, _dk(col, 0.6), _ipt(c), 2)          # button
        pygame.draw.circle(g.surf, _lt(col, 1.3), (int(c[0]) - 1, int(c[1]) - 1), 1)
        for dx, dy in ((0.15, 0.15), (0.85, 0.15), (0.15, 0.85), (0.85, 0.85)):
            t = g.S(dx, dy, 3)                                       # corner tassels
            pygame.draw.circle(g.surf, GOLD, _ipt(t), 2)
            pygame.draw.circle(g.surf, _dk(GOLD, 0.6), _ipt(t), 2, 1)
    g.op(0.12, 0.12, 0.88, 0.88, 0, 7, _fn)


def _leaf(surf, base, ang, L, W, col, veins=True, holes=True):
    """A monstera-ish leaf in screen space from `base`, pointing at `ang`."""
    d = (math.cos(ang), math.sin(ang))
    nrm = (-d[1], d[0])
    right, left = [], []
    for i in range(13):
        a = i / 12
        w = W * math.sin(math.pi * min(1.0, a * 1.02)) ** 0.75 * (1.15 - 0.5 * a)
        px = base[0] + d[0] * a * L
        py = base[1] + d[1] * a * L
        right.append((px + nrm[0] * w, py + nrm[1] * w))
        left.append((px - nrm[0] * w, py - nrm[1] * w))
    pts = right + left[::-1]
    pygame.draw.polygon(surf, col, pts)
    pygame.draw.polygon(surf, _dk(col, 0.62), pts, 1)
    if veins:
        tip = (base[0] + d[0] * L * 0.92, base[1] + d[1] * L * 0.92)
        pygame.draw.line(surf, _lt(col, 1.25), base, tip, 1)
    if holes:                                  # the monstera splits
        for a in (0.34, 0.56, 0.76):
            for sgn in (1, -1):
                w = W * math.sin(math.pi * a) ** 0.75 * (1.15 - 0.5 * a)
                mx = base[0] + d[0] * a * L
                my = base[1] + d[1] * a * L
                p0 = (mx + sgn * nrm[0] * w * 0.45, my + sgn * nrm[1] * w * 0.45)
                p1 = (mx + sgn * nrm[0] * w * 1.02 + d[0] * 2,
                      my + sgn * nrm[1] * w * 1.02 + d[1] * 2)
                pygame.draw.line(surf, _dk(col, 0.55), p0, p1, 1)


@_ground("tall_plant")
def _tall_plant(g):
    col = g.color

    def _pot():
        rg = lathe(g.surf, g.P, 0.5, 0.5, [(0, 0.15), (11, 0.19), (12, 0.21), (15, 0.21)],
                   col, top=False)
        pygame.draw.polygon(g.surf, _lt(col, 1.1), rg[-1])
        pygame.draw.polygon(g.surf, _dk(col, 0.5), rg[-1], 1)
        soil = _ring(g.P, 0.5, 0.5, 0.17, 0.17, 14)
        pygame.draw.polygon(g.surf, (92, 66, 46), soil)
        a0, a1 = _arcs(rg[1])[0][0], _arcs(rg[1])[0][-1]            # rim band line
        pygame.draw.line(g.surf, _dk(col, 0.6), a0, a1, 1)
    g.op(0.29, 0.29, 0.71, 0.71, 0, 15, _pot)

    # (canonical dx, dy, z of the leaf base, length px, width px, shade)
    leaves = [(-0.20, -0.22, 40, 17, 8, 0.82), (0.24, -0.16, 36, 18, 8, 0.9),
              (-0.26, 0.10, 30, 16, 7, 1.0), (0.10, 0.22, 26, 17, 8, 1.06),
              (0.26, 0.14, 44, 15, 7, 0.96), (-0.06, -0.04, 50, 16, 7, 1.1),
              (0.02, 0.26, 38, 15, 7, 1.14)]

    def _leaves():
        stem0 = g.S(0.5, 0.5, 14)
        order = sorted(leaves, key=lambda L: g.P(0.5 + L[0], 0.5 + L[1])[1])
        for dx, dy, z, ln, w, sh in order:
            b = g.S(0.5 + dx * 0.45, 0.5 + dy * 0.45, z)
            pygame.draw.line(g.surf, _dk(LEAF, 0.8), stem0, b, 2)
            tip = g.S(0.5 + dx * 1.35, 0.5 + dy * 1.35, z - 8)
            ang = math.atan2(tip[1] - b[1], tip[0] - b[0])
            _leaf(g.surf, b, ang, ln, w, _mix(_dk(LEAF, sh), LEAF_LT, max(0, sh - 1.0) * 2))
    g.op(0.06, 0.06, 0.94, 0.94, 15, 62, _leaves)


@_ground("floor_vase")
def _floor_vase(g):
    col = _ceramic(g.color) if sum(g.color) > 600 else g.color

    def _vase():
        rg = lathe(g.surf, g.P, 0.5, 0.5,
                   [(0, 0.10), (3, 0.15), (10, 0.18), (17, 0.16), (23, 0.09),
                    (28, 0.065), (31, 0.075), (32, 0.085)], col, top=False)
        mouth = rg[-1]
        pygame.draw.polygon(g.surf, _lt(col, 1.12), mouth)
        pygame.draw.polygon(g.surf, (52, 44, 40), _ring(g.P, 0.5, 0.5, 0.06, 0.06, 32))
        pygame.draw.polygon(g.surf, _dk(col, 0.5), mouth, 1)
        band = _arcs(rg[2])[0]                                       # glaze band
        pygame.draw.lines(g.surf, _lt(col, 1.3), False, band, 2)
    g.op(0.30, 0.30, 0.70, 0.70, 0, 32, _vase)

    # (canonical tip dx, dy, height px above the mouth, plume length)
    stems = [(-0.30, -0.10, 26, 13), (0.22, -0.26, 30, 14), (0.02, 0.02, 34, 15),
             (0.30, 0.18, 24, 12), (-0.18, 0.26, 22, 12), (0.12, 0.30, 28, 13)]

    def _pampas():
        m = g.S(0.5, 0.5, 32)
        order = sorted(stems, key=lambda s: g.P(0.5 + s[0], 0.5 + s[1])[1])
        for i, (dx, dy, h, pl) in enumerate(order):
            tip = g.S(0.5 + dx, 0.5 + dy, 32 + h)
            pygame.draw.line(g.surf, (176, 150, 104), m, tip, 1)
            d = (tip[0] - m[0], tip[1] - m[1])
            L = math.hypot(*d) or 1.0
            d = (d[0] / L, d[1] / L)
            base = (tip[0] - d[0] * pl, tip[1] - d[1] * pl)
            for k in range(7):                                       # fluffy plume
                t = k / 6
                c = (base[0] + d[0] * pl * t, base[1] + d[1] * pl * t)
                r = 2.6 + 1.6 * math.sin(math.pi * min(1, t * 1.1))
                shade = (236, 222, 192) if (k + i) % 2 else (222, 202, 162)
                pygame.draw.circle(g.surf, shade, _ipt(c), int(r))
            for k in range(3):                                       # wisps
                t = 0.3 + 0.25 * k
                c = (base[0] + d[0] * pl * t, base[1] + d[1] * pl * t)
                pygame.draw.line(g.surf, (246, 238, 214), c,
                                 (c[0] - d[1] * 4 + d[0] * 2, c[1] + d[0] * 4 + d[1] * 2), 1)
    g.op(0.10, 0.10, 0.90, 0.90, 32, 70, _pampas)


@_ground("grandfather_clock")
def _grandfather_clock(g):
    col = g.color
    trim = _dk(col, 0.82)
    g.box(0.20, 0.18, 0.80, 0.82, 8, trim)                              # plinth

    def _trunk(tp):
        if not g.vx1:
            return
        fp = g.xface(0.72, 0.24, 0.76, 30, base=8)
        win = _quad(fp, 0.20, 0.08, 0.80, 0.88)
        pygame.draw.polygon(g.surf, (58, 44, 38), win)                 # the case window
        # brass weights on their chains, behind the pendulum
        for u, v in ((0.33, 0.30), (0.67, 0.40)):
            pygame.draw.line(g.surf, (150, 140, 110), fp(u, 0.08), fp(u, v), 1)
            q = _quad(fp, u - 0.06, v, u + 0.06, v + 0.20)
            pygame.draw.polygon(g.surf, BRASS, q)
            pygame.draw.polygon(g.surf, _dk(BRASS, 0.6), q, 1)
        sw = 0.16 * math.sin(_ticks() / 318.0) if g.on else 0.0     # ~1 s swing
        top = fp(0.5, 0.06)
        bob = fp(0.5 + sw, 0.72)
        pygame.draw.line(g.surf, (196, 170, 110), top, bob, 2)
        pygame.draw.circle(g.surf, GOLD, _ipt(bob), 4)
        pygame.draw.circle(g.surf, _dk(GOLD, 0.6), _ipt(bob), 4, 1)
        pygame.draw.circle(g.surf, (255, 244, 200), (int(bob[0]) - 1, int(bob[1]) - 1), 1)
        _apoly(g.surf, (220, 236, 246, 46), win)                       # glass sheen
        pygame.draw.line(g.surf, (236, 244, 250), fp(0.26, 0.20), fp(0.40, 0.10), 1)
        pygame.draw.polygon(g.surf, _dk(col, 0.5), win, 1)
    g.box(0.28, 0.24, 0.72, 0.76, 30, col, base=8, decor=_trunk)       # trunk

    def _dial(tp):
        if not g.vx1:
            return
        fp = g.xface(0.76, 0.20, 0.80, 18, base=38)
        ring = _ellipse_on(fp, 0.5, 0.5, 0.36, 0.40, 22)
        pygame.draw.polygon(g.surf, GOLD, ring)
        face = _ellipse_on(fp, 0.5, 0.5, 0.29, 0.32, 22)
        pygame.draw.polygon(g.surf, (250, 246, 234), face)
        for k in range(12):
            a = k * math.pi / 6
            p = fp(0.5 + math.cos(a) * 0.23, 0.5 + math.sin(a) * 0.26)
            pygame.draw.circle(g.surf, (70, 60, 60), _ipt(p), 1 if k % 3 else 1)
        pygame.draw.line(g.surf, (40, 34, 40), fp(0.5, 0.5), fp(0.38, 0.36), 2)   # 10:10
        pygame.draw.line(g.surf, (40, 34, 40), fp(0.5, 0.5), fp(0.66, 0.34), 1)
        pygame.draw.polygon(g.surf, _dk(GOLD, 0.55), ring, 1)
    g.box(0.24, 0.20, 0.76, 0.80, 18, col, base=38, decor=_dial)       # hood
    g.box(0.20, 0.16, 0.80, 0.84, 3, trim, base=56)                    # cornice
    g.box(0.34, 0.30, 0.66, 0.70, 4, col, base=59)                     # crest

    def _finial():
        c = g.S(0.5, 0.5, 66)
        pygame.draw.circle(g.surf, GOLD, _ipt(c), 3)
        pygame.draw.circle(g.surf, _dk(GOLD, 0.6), _ipt(c), 3, 1)
        pygame.draw.circle(g.surf, (255, 246, 210), (int(c[0]) - 1, int(c[1]) - 1), 1)
    g.op(0.44, 0.44, 0.56, 0.56, 63, 69, _finial)


@_ground("tv_stand")
def _tv_stand(g):
    col = g.color
    legc = _dk(WOOD, 0.75)
    for lx, ly in ((0.16, 0.20), (1.76, 0.20), (0.16, 0.72), (1.76, 0.72)):
        g.box(lx, ly, lx + 0.08, ly + 0.08, 5, legc)

    def _front(tp):
        if not g.vy1:
            return
        fp = g.yface(0.86, 0.06, 1.94, 12, base=5)
        ink = _dk(col, 0.5)
        for u0, u1 in ((0.03, 0.33), (0.67, 0.97)):                   # slatted doors
            q = _quad(fp, u0, 0.12, u1, 0.90)
            pygame.draw.polygon(g.surf, _lt(col, 1.05), q)
            for k in range(1, 8):
                u = u0 + (u1 - u0) * k / 8
                pygame.draw.line(g.surf, _dk(col, 0.84), fp(u, 0.16), fp(u, 0.86), 1)
            pygame.draw.polygon(g.surf, ink, q, 1)
        pygame.draw.circle(g.surf, BRASS, _ipt(fp(0.31, 0.5)), 1)
        pygame.draw.circle(g.surf, BRASS, _ipt(fp(0.69, 0.5)), 1)
        cub = _quad(fp, 0.36, 0.12, 0.64, 0.90)                        # open cubby
        pygame.draw.polygon(g.surf, _dk(col, 0.42), cub)
        pygame.draw.polygon(g.surf, (238, 238, 242), _quad(fp, 0.39, 0.56, 0.50, 0.88))  # console
        pygame.draw.circle(g.surf, (120, 200, 240), _ipt(fp(0.47, 0.64)), 1)
        for k, bc in enumerate(((208, 96, 90), (96, 140, 208), (230, 196, 92))):  # records
            q = _quad(fp, 0.53 + k * 0.035, 0.30, 0.56 + k * 0.035, 0.88)
            pygame.draw.polygon(g.surf, bc, q)
        pygame.draw.polygon(g.surf, ink, cub, 1)
    g.box(0.06, 0.14, 1.94, 0.86, 12, col, base=5, decor=_front)
    g.box(0.04, 0.12, 1.96, 0.88, 2, WOOD_LT, base=17)


# ---------------------------------------------------------------- bedroom
@_ground("floor_mirror")
def _floor_mirror(g):
    col = g.color
    g.box(0.30, 0.22, 0.70, 0.30, 2, _dk(col, 0.7))                   # feet
    g.box(0.30, 0.70, 0.70, 0.78, 2, _dk(col, 0.7))
    g.box(0.32, 0.46, 0.44, 0.54, 30, _dk(col, 0.75), base=2)         # back strut

    def _glass(tp):
        if g.vx1:
            fp = g.xface(0.56, 0.20, 0.80, 52, base=2)
            pts = []
            for k in range(13):                                      # arched top
                a = math.pi * k / 12
                pts.append(fp(0.5 - 0.37 * math.cos(a), 0.22 - 0.15 * math.sin(a)))
            pts += [fp(0.87, 0.94), fp(0.13, 0.94)]
            pygame.draw.polygon(g.surf, (178, 206, 222), pts)
            refl = [fp(0.20, 0.30), fp(0.52, 0.10), fp(0.70, 0.10), fp(0.34, 0.60),
                    fp(0.20, 0.72)]
            pygame.draw.polygon(g.surf, (206, 228, 238), refl)
            pygame.draw.line(g.surf, (246, 250, 252), fp(0.26, 0.40), fp(0.52, 0.16), 2)
            pygame.draw.line(g.surf, (236, 246, 250), fp(0.62, 0.86), fp(0.80, 0.62), 1)
            pygame.draw.polygon(g.surf, _dk(col, 0.5), pts, 1)
        else:
            fp = g.xface(0.44, 0.20, 0.80, 52, base=2)               # the backing board
            q = _quad(fp, 0.10, 0.08, 0.90, 0.94)
            pygame.draw.polygon(g.surf, (176, 150, 116), q)
            pygame.draw.polygon(g.surf, (120, 98, 72), q, 1)
    g.box(0.44, 0.20, 0.56, 0.80, 52, col, base=2, decor=_glass)

    def _crown():
        c = g.S(0.5, 0.5, 58)
        pygame.draw.polygon(g.surf, _lt(col, 1.25), _heart((c[0], c[1] + 1), 4))
        pygame.draw.polygon(g.surf, _dk(col, 0.5), _heart((c[0], c[1] + 1), 4), 1)
    g.op(0.46, 0.44, 0.54, 0.56, 54, 62, _crown)


@_ground("shoe_rack")
def _shoe_rack(g):
    col = g.color
    for px in (0.26, 0.68):                                          # corner posts
        for py in (0.14, 0.80):
            g.box(px, py, px + 0.06, py + 0.06, 24, _dk(col, 0.9))
    shelf = _dk(col, 0.96)

    def _slats(tp):
        for t in (0.25, 0.5, 0.75):
            pygame.draw.line(g.surf, _dk(shelf, 0.72), _mid(tp[0], tp[1], t),
                             _mid(tp[3], tp[2], t), 1)
    g.box(0.26, 0.20, 0.74, 0.80, 2, shelf, base=1, decor=_slats)
    g.box(0.26, 0.20, 0.74, 0.80, 2, shelf, base=12, decor=_slats)
    g.box(0.24, 0.12, 0.76, 0.88, 2, col, base=24)                     # top board
    pairs = [(1 + 2, 0.25, (244, 244, 248), (214, 76, 76)),          # sneakers
             (1 + 2, 0.53, (150, 96, 60), (110, 70, 44)),            # boots
             (12 + 2, 0.25, (236, 150, 176), (214, 120, 150)),       # flats
             (12 + 2, 0.53, (90, 120, 190), (240, 240, 244))]        # trainers
    for z, y0, c1, c2 in pairs:
        for k in range(2):
            ya = y0 + k * 0.11
            yb = ya + 0.09
            tall = 7 if c1 == (150, 96, 60) else 3

            def _laces(tp, ya=ya, yb=yb, z=z, c2=c2):
                a = g.S(0.50, (ya + yb) / 2, z + 4)
                b = g.S(0.62, (ya + yb) / 2, z + 4)
                pygame.draw.line(g.surf, c2, a, b, 1)
            g.box(0.34, ya, 0.66, yb, 4, c1, base=z, decor=_laces)
            g.box(0.34, ya, 0.44, yb, tall, c2 if tall == 3 else c1, base=z + 4)   # heel / shaft


@_ground("laundry_basket")
def _laundry_basket(g):
    col = g.color
    wick = (206, 170, 116)

    def _fn():
        rg = lathe(g.surf, g.P, 0.5, 0.5, [(0, 0.22), (7, 0.245), (14, 0.265), (20, 0.28)],
                   wick, top=False)
        for i in (1, 2):                                             # woven rows
            pygame.draw.lines(g.surf, _dk(wick, 0.72), False, _arcs(rg[i])[0], 1)
        fb, ft = _arcs(rg[0])[0], _arcs(rg[-1])[0]
        for k in range(1, 9):                                        # upright ribs
            t = k / 9
            pygame.draw.line(g.surf, _dk(wick, 0.8), _at(fb, t), _at(ft, t), 1)
        rim = _ring(g.P, 0.5, 0.5, 0.29, 0.29, 21)
        pygame.draw.polygon(g.surf, _lt(wick, 1.1), rim)
        pygame.draw.polygon(g.surf, _dk(wick, 0.5), rim, 1)
        pygame.draw.polygon(g.surf, (96, 76, 52), _ring(g.P, 0.5, 0.5, 0.24, 0.24, 21))
        # a soft heap of washing, a white shirt on top of the coloured pile
        lumps = [(0.38, 0.40, 22, 9, 5, col), (0.60, 0.38, 23, 8, 5, (244, 244, 248)),
                 (0.40, 0.60, 22, 8, 5, _lt(col, 1.25)), (0.58, 0.58, 23, 10, 6, col),
                 (0.50, 0.48, 25, 8, 5, (236, 214, 150))]
        for x, y, z, w, h, c in sorted(lumps, key=lambda L: g.P(L[0], L[1])[1]):
            p = g.S(x, y, z)
            r = pygame.Rect(0, 0, w * 2, h * 2)
            r.center = _ipt(p)
            pygame.draw.ellipse(g.surf, _dk(c, 0.82), r)
            pygame.draw.ellipse(g.surf, c, r.inflate(-3, -3).move(-1, -1))
            pygame.draw.ellipse(g.surf, _dk(c, 0.55), r, 1)
            pygame.draw.arc(g.surf, _dk(c, 0.7), r.inflate(-6, -4), 3.5, 5.6, 1)   # fold
        # a striped towel flopped over the front rim
        fr = _arcs(rim)[0]
        a, b = _at(fr, 0.30), _at(fr, 0.52)
        pts = [a, b, (b[0] + 1, b[1] + 9), (a[0] + 1, a[1] + 8)]
        stripe = _lt(col, 1.3) if sum(col) < 600 else _dk(col, 0.8)
        pygame.draw.polygon(g.surf, (246, 246, 250), pts)
        for t in (0.35, 0.65):
            pygame.draw.line(g.surf, stripe, _mid(a, pts[3], t), _mid(b, pts[2], t), 2)
        pygame.draw.polygon(g.surf, (150, 150, 160), pts, 1)
        for side in (0.04, 0.96):                                    # handle slots
            h = _at(_arcs(rg[-1])[0], side)
            pygame.draw.ellipse(g.surf, (96, 76, 52), (h[0] - 2, h[1] + 2, 5, 3))
    g.op(0.20, 0.20, 0.80, 0.80, 0, 28, _fn)


def _bear(surf, g, cx, cy, s, fur, ribbon, pads):
    """A seated teddy (screen space) centred on canonical (cx, cy), scale s
    (1 = the giant floor bear). Faces canonical +y; seen from behind when
    that side turns away."""
    fdx, fdy = g.front_dir() if hasattr(g, "front_dir") else (0.0, 1.0)
    away = fdy < 0
    furd, furl = _dk(fur, 0.78), _lt(fur, 1.12)
    muzzle = _mix(fur, (250, 236, 214), 0.6)
    base = g.S(cx, cy, 0)

    def at(dx, dy, z):
        return (base[0] + dx * s, base[1] + dy * s - z * s)

    def blob(c, rx, ry, col, ol=True):
        r = pygame.Rect(0, 0, max(2, int(rx * 2 * s)), max(2, int(ry * 2 * s)))
        r.center = _ipt(c)
        pygame.draw.ellipse(surf, col, r)
        if ol:
            pygame.draw.ellipse(surf, _dk(col, 0.55), r, 1)
        return r
    side = fdx                                   # which way the face leans on screen
    parts = []
    # legs stick out toward the front; arms at the sides
    for k in (-1, 1):
        lx = k * 8 + fdx * 7
        ly = fdy * 6 + 2
        parts.append((ly + (0 if away else 10), "leg", (lx, ly)))
        ax = k * 12 + fdx * 2
        parts.append((fdy * 2 + k * fdx * -2 + 3, "arm", (ax, 0)))
    parts.append((0, "body", None))
    parts.sort(key=lambda p: p[0])
    for _, kind, pos in parts:
        if kind == "body":
            blob(at(0, 0, 13), 12, 12, fur)
            if not away:
                blob(at(fdx * 3, 1, 11), 7, 7, furl, ol=False)             # tummy
            else:
                blob(at(-fdx * 6, 3, 5), 3, 3, furl)                        # tail
            # head
            blob(at(0, 0, 32), 11, 10, fur)
            for k in (-1, 1):
                e = at(k * 8 - fdx * (1 if away else 0), 0, 40)
                blob(e, 4, 4, fur)
                if not away:
                    blob(e, 2, 2, muzzle, ol=False)
            if not away:
                m = at(fdx * 4, 2, 28)
                blob(m, 5, 4, muzzle)
                pygame.draw.circle(surf, (50, 36, 34), _ipt((m[0] + fdx * 1, m[1] - 2 * s)),
                                   max(1, int(1.6 * s)))
                for k in (-1, 1):
                    ex = at(k * 4.5 + fdx * 3.5, 0, 34)
                    pygame.draw.circle(surf, (36, 28, 30), _ipt(ex), max(1, int(1.4 * s)))
                    _px(surf, (ex[0] + 0.5, ex[1] - 0.8), (250, 250, 250))
                for k in (-1, 1):                                             # rosy cheeks
                    ck = at(k * 7 + fdx * 3, 1, 30)
                    _apoly(surf, (240, 130, 140, 110),
                           [(ck[0] - 2 * s, ck[1]), (ck[0], ck[1] - 1.2 * s),
                            (ck[0] + 2 * s, ck[1]), (ck[0], ck[1] + 1.2 * s)])
            # ribbon bow at the neck
            n = at(fdx * 3, 1, 24)
            if not away:
                for k in (-1, 1):
                    pygame.draw.polygon(surf, ribbon, [n, (n[0] + k * 5 * s, n[1] - 3 * s),
                                                       (n[0] + k * 5 * s, n[1] + 3 * s)])
                    pygame.draw.polygon(surf, _dk(ribbon, 0.6),
                                        [n, (n[0] + k * 5 * s, n[1] - 3 * s),
                                         (n[0] + k * 5 * s, n[1] + 3 * s)], 1)
                pygame.draw.circle(surf, _dk(ribbon, 0.85), _ipt(n), max(1, int(1.6 * s)))
        elif kind == "leg":
            c = at(pos[0], pos[1], 5)
            blob(c, 5, 4.5, furd if away else fur)
            if not away:
                blob((c[0] + fdx * 2 * s, c[1] + 1 * s), 3, 3, pads)
        else:
            blob(at(pos[0], pos[1], 16), 4, 6.5, fur)


@_ground("teddy_giant")
def _teddy_giant(g):
    def _fn():
        _bear(g.surf, g, 0.5, 0.5, 1.0, (196, 146, 100), g.color, (238, 206, 176))
    g.op(0.14, 0.14, 0.86, 0.86, 0, 48, _fn)


# ---------------------------------------------------------------- kitchen
@_ground("coffee_machine")
def _coffee_machine(g):
    col = g.color
    steel = (200, 202, 210)

    def _door(tp):
        if not g.vx1:
            return
        fp = g.xface(0.88, 0.12, 0.88, 22)
        for u0, u1 in ((0.08, 0.49), (0.51, 0.92)):
            q = _quad(fp, u0, 0.10, u1, 0.92)
            pygame.draw.polygon(g.surf, _lt(col, 1.05), q)
            pygame.draw.polygon(g.surf, _dk(col, 0.5), q, 1)
        pygame.draw.line(g.surf, METAL, fp(0.42, 0.22), fp(0.42, 0.36), 2)
        pygame.draw.line(g.surf, METAL, fp(0.58, 0.22), fp(0.58, 0.36), 2)
    g.box(0.12, 0.12, 0.88, 0.88, 22, col, decor=_door)                # cabinet
    g.box(0.10, 0.10, 0.90, 0.90, 2, WOOD_LT, base=22)                 # butcher-block top

    def _face(tp):
        if not g.vx1:
            return
        fp = g.xface(0.56, 0.20, 0.80, 16, base=24)
        pnl = _quad(fp, 0.10, 0.08, 0.90, 0.40)
        pygame.draw.polygon(g.surf, (60, 62, 70), pnl)                 # control strip
        c = fp(0.28, 0.24)                                           # pressure gauge
        pygame.draw.circle(g.surf, (246, 244, 236), _ipt(c), 3)
        pygame.draw.line(g.surf, (200, 60, 60), c, (c[0] + 2, c[1] - 1), 1)
        for u in (0.52, 0.64):
            pygame.draw.circle(g.surf, (220, 220, 226), _ipt(fp(u, 0.24)), 1)
        led = (120, 236, 140) if g.on else (150, 60, 60)
        pygame.draw.circle(g.surf, led, _ipt(fp(0.80, 0.24)), 1)
        gh = fp(0.5, 0.56)                                           # group head
        pygame.draw.circle(g.surf, (150, 152, 160), _ipt(gh), 3)
        pygame.draw.circle(g.surf, (90, 92, 100), _ipt(gh), 3, 1)
    g.box(0.22, 0.20, 0.56, 0.80, 16, steel, base=24, decor=_face)     # espresso machine
    g.box(0.20, 0.18, 0.58, 0.82, 2, (74, 76, 84), base=40)            # cup-warmer lid
    for cy in (0.30, 0.58):                                          # warming cups
        g.box(0.30, cy, 0.40, cy + 0.10, 3, (246, 244, 240), base=42)
    g.box(0.56, 0.32, 0.74, 0.68, 2, (70, 72, 80), base=24)            # drip tray

    def _cup(tp):
        if g.on:                                                     # espresso pouring
            a = g.S(0.62, 0.50, 34)
            pygame.draw.line(g.surf, (120, 76, 44), a, (a[0], a[1] + 6), 1)
    g.box(0.58, 0.44, 0.68, 0.56, 4, (246, 244, 240), base=26, decor=_cup)
    g.box(0.56, 0.46, 0.66, 0.54, 2, (44, 42, 46), base=34)            # portafilter

    if g.on:
        def _steam():
            t = _ticks() / 1000.0
            for k in range(3):
                ph = (t * 0.7 + k / 3) % 1.0
                c = g.S(0.63, 0.50, 38 + ph * 16)
                a = int(150 * (1 - ph))
                dx = math.sin(t * 3 + k * 2) * 3
                _puff(g.surf, (c[0] + dx, c[1]), 2 + ph * 2, a)
        g.op(0.58, 0.44, 0.68, 0.56, 36, 58, _steam)


@_ground("bar_cart")
def _bar_cart(g):
    col = g.color
    for px, py in ((0.16, 0.16), (0.78, 0.16), (0.16, 0.78), (0.78, 0.78)):
        g.box(px - 0.01, py - 0.01, px + 0.07, py + 0.07, 3, (60, 58, 64))     # wheels
        g.box(px, py, px + 0.06, py + 0.06, 23, BRASS, base=3)                 # posts
    g.box(0.22, 0.22, 0.78, 0.78, 2, col, base=4)                              # lower shelf

    def _bottles():
        # a ring of bottles round the lower shelf's rim (z 6): whichever way
        # the cart turns, the ones along the front edge show under the top
        wine = [(6, 0.05), (15, 0.05), (17, 0.025), (21, 0.02)]
        gin = [(6, 0.055), (13, 0.055), (15, 0.03), (18, 0.03)]
        tall = [(6, 0.045), (14, 0.045), (16, 0.02), (20, 0.018)]
        glass = [(6, 0.04), (11, 0.045)]
        bots = [(0.32, 0.32, wine, (52, 110, 70)), (0.68, 0.30, gin, (196, 130, 60)),
                (0.70, 0.52, tall, (186, 60, 84)), (0.68, 0.70, glass, (226, 236, 240)),
                (0.46, 0.70, wine, (120, 40, 60)), (0.30, 0.66, gin, (90, 140, 200)),
                (0.30, 0.48, glass, (226, 236, 240)), (0.50, 0.34, tall, (230, 190, 80))]
        for x, y, prof, c in sorted(bots, key=lambda b: g.P(b[0], b[1])[1]):
            lathe(g.surf, g.P, x, y, prof, c)
            hi = g.S(x - 0.025, y + 0.02, prof[0][0] + 6)
            pygame.draw.line(g.surf, _lt(c, 1.6), hi, (hi[0], hi[1] - 3), 1)
            if prof is wine:                                                    # label
                lb = g.S(x + 0.03, y + 0.03, 10)
                pygame.draw.rect(g.surf, CREAM, (lb[0] - 2, lb[1] - 2, 4, 3))
    g.op(0.24, 0.24, 0.76, 0.76, 6, 21, _bottles)
    g.box(0.14, 0.14, 0.86, 0.86, 2, col, base=26)                             # top shelf
    for py in (0.16, 0.78):                                                    # handle
        g.box(0.16, py, 0.22, py + 0.06, 6, BRASS, base=28)
    g.box(0.15, 0.15, 0.23, 0.85, 2, _lt(BRASS, 1.08), base=34)


# ---------------------------------------------------------------- bath
def _bowl_interior(surf, P, cx, cy, rx, ry, ztop, depth, p, wall, floor, water=None):
    """Inside of an open vessel: far wall + floor, clipped to the opening.
    With `water` (colour) the vessel is filled nearly to the brim."""
    opening = _ring(P, cx, cy, rx, ry, ztop, 32, p)

    def draw(lay, sh):
        pygame.draw.polygon(lay, wall, sh(opening))
        fl = _ring(P, cx, cy, rx * 0.82, ry * 0.78, ztop - depth, 32, p)
        pygame.draw.polygon(lay, floor, sh(fl))
        if water:
            wl = _ring(P, cx, cy, rx * 0.98, ry * 0.97, ztop - 2, 32, p)
            pygame.draw.polygon(lay, water, sh(wl))
            wl2 = _ring(P, cx - rx * 0.1, cy - ry * 0.1, rx * 0.55, ry * 0.45, ztop - 2, 32, p)
            pygame.draw.polygon(lay, _lt(water, 1.08), sh(wl2))
    _clipped(surf, opening, draw)
    return opening


@_ground("bathtub")
def _bathtub(g):
    col = g.color
    enamel = (242, 244, 248)
    for fx, fy in ((0.34, 0.26), (1.58, 0.26), (0.34, 0.66), (1.58, 0.66)):   # claw feet
        g.box(fx, fy, fx + 0.08, fy + 0.08, 4, GOLD)
    cx, cy, rx, ry, p = 1.0, 0.5, 0.86, 0.36, 3.2

    def _tub():
        prof = [(4, 0.80), (8, 0.92), (15, 0.98), (21, 1.0)]
        lathe(g.surf, g.P, cx, cy, [(z, rx * s) for z, s in prof], col, asp=ry / rx,
              n=40, p=p, top=False)
        rim = _ring(g.P, cx, cy, rx * 1.03, ry * 1.06, 23, 40, p)
        rim_lo = _ring(g.P, cx, cy, rx * 1.03, ry * 1.06, 21, 40, p)
        fr, _ = _arcs(rim_lo)
        fr2, bk2 = _arcs(rim)
        band = list(fr) + list(reversed(fr2))
        pygame.draw.polygon(g.surf, _dk(enamel, 0.86), band)               # rolled rim edge
        pygame.draw.polygon(g.surf, enamel, rim)
        pygame.draw.polygon(g.surf, _dk(col, 0.5), rim, 1)
        pygame.draw.lines(g.surf, _dk(col, 0.5), False, fr, 1)
        water = (150, 202, 230) if g.on else None
        _bowl_interior(g.surf, g.P, cx, cy, rx * 0.93, ry * 0.86, 23, 14, p,
                       (212, 220, 230), (228, 234, 240), water)
        if not g.on:
            d = g.S(0.40, 0.5, 11)                                      # plug hole
            pygame.draw.circle(g.surf, (160, 150, 120), _ipt(d), 2)
            return
        t = _ticks() / 1000.0
        # soap bubbles heaped along the tub, a rubber duck bobbing in them
        foam = [(0.62, 0.44, 5), (0.80, 0.56, 6), (1.00, 0.40, 5), (1.18, 0.58, 6),
                (1.36, 0.46, 5), (0.90, 0.30, 4), (1.26, 0.30, 4), (1.54, 0.54, 4),
                (0.70, 0.64, 4), (1.10, 0.66, 4)]
        for k, (fx, fy, r) in enumerate(sorted(foam, key=lambda f: g.P(f[0], f[1])[1])):
            c = g.S(fx, fy, 22 + math.sin(t * 2 + k) * 0.6)
            pygame.draw.circle(g.surf, (226, 236, 244), _ipt(c), r)
            pygame.draw.circle(g.surf, (250, 252, 255), _ipt((c[0] - 1, c[1] - 1)), r - 1)
            pygame.draw.circle(g.surf, (255, 255, 255), _ipt((c[0] - r * 0.4, c[1] - r * 0.4)), 1)
        dk = g.S(1.46, 0.36, 23 + math.sin(t * 2.4) * 1.0)
        pygame.draw.ellipse(g.surf, (250, 214, 70), (dk[0] - 5, dk[1] - 3, 10, 6))
        pygame.draw.circle(g.surf, (250, 214, 70), (int(dk[0]) - 2, int(dk[1]) - 5), 3)
        pygame.draw.polygon(g.surf, (240, 140, 60), [(dk[0] - 5, dk[1] - 5), (dk[0] - 8, dk[1] - 4),
                                                     (dk[0] - 5, dk[1] - 3)])
        _px(g.surf, (dk[0] - 3, dk[1] - 6), (40, 34, 30))
        for k in range(3):                                              # warm steam
            ph = (t * 0.35 + k / 3) % 1.0
            c = g.S(0.8 + k * 0.25, 0.5, 26 + ph * 20)
            dx = math.sin(t * 1.7 + k * 2.1) * 4
            _puff(g.surf, (c[0] + dx, c[1]), 3 + ph * 2, int(110 * (1 - ph)))
    g.op(0.12, 0.12, 1.88, 0.88, 4, 23, _tub)

    def _faucet():
        base = g.S(0.24, 0.5, 23)
        top = g.S(0.24, 0.5, 34)
        pygame.draw.line(g.surf, _dk(METAL, 0.7), base, top, 4)
        pygame.draw.line(g.surf, METAL, base, top, 2)
        prev = top
        for k in range(1, 7):                                          # goose-neck spout
            a = math.pi * k / 6
            p2 = g.S(0.24 + 0.10 * (1 - math.cos(a)), 0.5, 34 + 4 * math.sin(a))
            pygame.draw.line(g.surf, METAL, prev, p2, 2)
            prev = p2
        for dy, knob in ((-0.12, (220, 90, 90)), (0.12, (90, 140, 220))):  # hot / cold
            c = g.S(0.22, 0.5 + dy, 27)
            pygame.draw.line(g.surf, METAL, g.S(0.22, 0.5, 27), c, 2)
            pygame.draw.circle(g.surf, knob, _ipt(c), 2)
        if g.on:
            sp = prev
            pygame.draw.line(g.surf, (190, 224, 244), sp, (sp[0], sp[1] + 8), 1)
    g.op(0.14, 0.34, 0.40, 0.66, 23, 40, _faucet)


@_ground("bath_sink")
def _bath_sink(g):
    cer = _ceramic(g.color)

    def _ped():
        lathe(g.surf, g.P, 0.5, 0.5, [(0, 0.16), (2, 0.15), (5, 0.10), (16, 0.08), (20, 0.12)],
              cer, top=False)
    g.op(0.30, 0.30, 0.70, 0.70, 0, 20, _ped)

    def _basin():
        cx, cy, p = 0.54, 0.5, 2.6
        lathe(g.surf, g.P, cx, cy, [(20, 0.20), (23, 0.29), (26, 0.33), (27, 0.34)], cer,
              asp=1.1, n=32, p=p, top=False)
        rim = _ring(g.P, cx, cy, 0.34, 0.374, 27, 32, p)
        pygame.draw.polygon(g.surf, _lt(cer, 1.06), rim)
        pygame.draw.polygon(g.surf, _dk(cer, 0.55), rim, 1)
        _bowl_interior(g.surf, g.P, cx + 0.03, cy, 0.25, 0.28, 27, 6, p,
                       _dk(cer, 0.86), _dk(cer, 0.94))
        d = g.S(cx + 0.04, cy, 22)
        pygame.draw.circle(g.surf, (150, 150, 158), _ipt(d), 1)
    g.op(0.18, 0.12, 0.88, 0.88, 20, 27, _basin)

    def _tap():
        b = g.S(0.24, 0.5, 27)
        t = g.S(0.24, 0.5, 35)
        pygame.draw.line(g.surf, _dk(METAL, 0.7), b, t, 4)
        pygame.draw.line(g.surf, METAL, b, t, 2)
        s = g.S(0.36, 0.5, 34)
        pygame.draw.line(g.surf, METAL, t, s, 2)
        pygame.draw.line(g.surf, METAL, s, (s[0], s[1] + 2), 2)
        for dy, knob in ((-0.13, (220, 90, 90)), (0.13, (90, 140, 220))):
            c = g.S(0.23, 0.5 + dy, 29)
            pygame.draw.circle(g.surf, METAL, _ipt(c), 2)
            pygame.draw.circle(g.surf, knob, _ipt(c), 1)
    g.op(0.20, 0.34, 0.40, 0.66, 27, 37, _tap)

    def _soap():
        lathe(g.surf, g.P, 0.30, 0.20, [(27, 0.04), (32, 0.04), (33, 0.02)], g.color)
        pump = g.S(0.30, 0.20, 33)
        pygame.draw.line(g.surf, (240, 240, 244), pump, (pump[0], pump[1] - 3), 2)
        pygame.draw.line(g.surf, (240, 240, 244), (pump[0], pump[1] - 3), (pump[0] + 2, pump[1] - 3), 1)
    g.op(0.25, 0.15, 0.35, 0.25, 27, 37, _soap)


@_ground("toilet")
def _toilet(g):
    col = g.color
    cer = (244, 244, 248)
    g.box(0.18, 0.32, 0.36, 0.68, 16, _dk(cer, 0.96))                 # back block

    def _lever(tp):
        if g.vx1:
            fp = g.xface(0.36, 0.20, 0.80, 18, base=16)
            pygame.draw.line(g.surf, METAL, fp(0.16, 0.24), fp(0.30, 0.24), 2)
            pygame.draw.circle(g.surf, METAL, _ipt(fp(0.16, 0.24)), 2)
    g.box(0.12, 0.20, 0.36, 0.80, 18, cer, base=16, decor=_lever)     # cistern

    def _btn(tp):
        c = g.S(0.24, 0.5, 37)
        pygame.draw.ellipse(g.surf, METAL, (c[0] - 3, c[1] - 1, 6, 3))
    g.box(0.10, 0.18, 0.38, 0.82, 3, _lt(cer, 1.0), base=34, decor=_btn)

    def _bowl():
        cx, cy = 0.60, 0.5
        lathe(g.surf, g.P, cx, cy, [(0, 0.13), (6, 0.12), (9, 0.15)], cer, asp=0.85,
              top=False)
        lathe(g.surf, g.P, cx, cy, [(9, 0.17), (14, 0.22), (17, 0.235)], cer, asp=0.84,
              top=False)
        # the fluffy lid cover in the chosen colour, a little heart on it
        lathe(g.surf, g.P, cx, cy, [(17, 0.235), (19, 0.235), (20, 0.20)], col,
              asp=0.84, top=True)
        c = g.S(cx + 0.03, cy, 20)
        pygame.draw.polygon(g.surf, _lt(col, 1.3), _heart((c[0], c[1]), 3))
    g.op(0.36, 0.28, 0.84, 0.72, 0, 20, _bowl)


@_ground("shower_booth")
def _shower_booth(g):
    tile = _mix(g.color, (250, 250, 252), 0.62)
    g.box(0.06, 0.06, 0.94, 0.94, 4, (238, 240, 244))                  # tray

    def _tiles_x(tp):
        if not g.vx1:
            return
        fp = g.xface(0.14, 0.14, 0.94, 56, base=4)
        for k in range(1, 7):
            v = k / 7
            pygame.draw.line(g.surf, _dk(tile, 0.8), fp(0, v), fp(1, v), 1)
        for k in range(1, 4):
            pygame.draw.line(g.surf, _dk(tile, 0.8), fp(k / 4, 0), fp(k / 4, 1), 1)

    def _tiles_y(tp):
        if not g.vy1:
            return
        fp = g.yface(0.14, 0.14, 0.94, 56, base=4)
        for k in range(1, 7):
            v = k / 7
            pygame.draw.line(g.surf, _dk(tile, 0.8), fp(0, v), fp(1, v), 1)
        for k in range(1, 4):
            pygame.draw.line(g.surf, _dk(tile, 0.8), fp(k / 4, 0), fp(k / 4, 1), 1)
    g.box(0.06, 0.06, 0.14, 0.94, 56, tile, base=4, decor=_tiles_x)    # tiled walls
    g.box(0.14, 0.06, 0.94, 0.14, 56, tile, base=4, decor=_tiles_y)

    def _head():
        a = g.S(0.14, 0.40, 48)
        b = g.S(0.30, 0.40, 50)
        pygame.draw.line(g.surf, METAL, a, g.S(0.14, 0.40, 50), 2)
        pygame.draw.line(g.surf, METAL, g.S(0.14, 0.40, 50), b, 2)
        pygame.draw.ellipse(g.surf, _dk(METAL, 0.8), (b[0] - 5, b[1] - 1, 10, 5))
        pygame.draw.ellipse(g.surf, METAL, (b[0] - 5, b[1] - 2, 10, 4))
        k = g.S(0.14, 0.62, 30)                                           # mixer knob
        pygame.draw.circle(g.surf, METAL, _ipt(k), 3)
        pygame.draw.circle(g.surf, _dk(METAL, 0.6), _ipt(k), 3, 1)
    g.op(0.14, 0.30, 0.36, 0.70, 28, 54, _head)

    if g.on:
        def _water():
            t = _ticks() / 1000.0
            top = g.S(0.30, 0.40, 48)
            for k in range(7):
                ox = (k - 3) * 1.6
                ph = (t * 2.2 + k * 0.37) % 1.0
                y0 = top[1] + 2
                y1 = g.S(0.30, 0.40, 4)[1]
                ys = y0 + (y1 - y0) * ph
                pygame.draw.line(g.surf, (178, 214, 238), (top[0] + ox * (1 + ph * 1.4), y0),
                                 (top[0] + ox * 2.4, y1), 1)
                pygame.draw.circle(g.surf, (236, 246, 252), (int(top[0] + ox * (1 + ph * 1.4)),
                                                             int(ys)), 1)
            sp = g.S(0.30, 0.40, 4)
            _apoly(g.surf, (220, 236, 248, 120), [(sp[0] - 10, sp[1]), (sp[0], sp[1] - 3),
                                                  (sp[0] + 10, sp[1]), (sp[0], sp[1] + 4)])
            _apoly(g.surf, (240, 246, 252, 40), [(top[0] - 14, top[1]), (top[0] + 14, top[1]),
                                                 (sp[0] + 16, sp[1]), (sp[0] - 16, sp[1])])
        g.op(0.18, 0.20, 0.60, 0.60, 4, 46, _water)

    def _pane(x0_, y0_, x1_, y1_, xface):
        def fn():
            if xface:
                pts = [g.S(x0_, y0_, 60), g.S(x0_, y1_, 60), g.S(x0_, y1_, 4), g.S(x0_, y0_, 4)]
            else:
                pts = [g.S(x0_, y0_, 60), g.S(x1_, y0_, 60), g.S(x1_, y0_, 4), g.S(x0_, y0_, 4)]
            _apoly(g.surf, (206, 230, 242, 70), pts)
            pygame.draw.line(g.surf, (246, 250, 252), _mid(pts[0], pts[3], 0.25),
                             _mid(pts[1], pts[2], 0.05), 1)
            pygame.draw.polygon(g.surf, _dk(METAL, 0.8), pts, 1)
            pygame.draw.line(g.surf, METAL, pts[0], pts[1], 2)            # top rail
            if xface:
                h0, h1 = g.S(x0_, (y0_ + y1_) / 2 + 0.2, 36), g.S(x0_, (y0_ + y1_) / 2 + 0.2, 24)
                pygame.draw.line(g.surf, METAL, h0, h1, 2)              # door handle
        return fn
    g.op(0.90, 0.14, 0.94, 0.94, 4, 60, _pane(0.92, 0.14, 0.92, 0.92, True))
    g.op(0.14, 0.90, 0.90, 0.94, 4, 60, _pane(0.14, 0.92, 0.92, 0.92, False))


@_ground("bath_mat")
def _bath_mat(g):
    col = g.color
    cx, cy = (g.x0 + g.x1) / 2, (g.y0 + g.y1) / 2
    rx, ry = (g.x1 - g.x0) / 2 - 0.10, (g.y1 - g.y0) / 2 - 0.12
    outer = _ring(g.P, cx, cy, rx, ry, 0, 48, 5.0)
    pygame.draw.polygon(g.surf, _dk(col, 0.86), [(x, y + 1) for x, y in outer])
    pygame.draw.polygon(g.surf, col, outer)
    inner = _ring(g.P, cx, cy, rx - 0.10, ry - 0.08, 1, 48, 5.0)
    pygame.draw.polygon(g.surf, _lt(col, 1.12), inner)
    for i in range(9):                                                 # fluffy tufts
        for j in range(3):
            x = cx - rx + 0.2 + i * (2 * rx - 0.4) / 8
            y = cy - ry + 0.12 + j * (2 * ry - 0.24) / 2
            c = g.S(x, y, 1)
            pygame.draw.circle(g.surf, _lt(col, 1.26), _ipt(c), 1)
    pygame.draw.polygon(g.surf, _dk(col, 0.62), outer, 1)
    pygame.draw.polygon(g.surf, _dk(col, 0.9), inner, 1)


# ---------------------------------------------------------------- decor
@_ground("lantern")
def _lantern(g):
    frame = (70, 66, 74)
    g.box(0.30, 0.30, 0.70, 0.70, 3, frame)

    def _panes(tp):
        faces = [g.xface(0.67 if g.vx1 else 0.33, 0.33, 0.67, 20, base=3),
                 g.yface(0.67 if g.vy1 else 0.33, 0.33, 0.67, 20, base=3)]
        for fp in faces:
            q = _quad(fp, 0.16, 0.10, 0.84, 0.92)
            pygame.draw.polygon(g.surf, (255, 212, 130) if g.on else (78, 88, 100), q)
            if g.on:
                pygame.draw.polygon(g.surf, (255, 236, 180), _quad(fp, 0.30, 0.30, 0.70, 0.86))
            pygame.draw.line(g.surf, frame, fp(0.5, 0.10), fp(0.5, 0.92), 1)
            pygame.draw.polygon(g.surf, _dk(frame, 0.7), q, 1)
        c = g.S(0.5, 0.5, 4)                                         # the candle within
        pygame.draw.rect(g.surf, (240, 232, 214), (c[0] - 2, c[1] - 9, 4, 8))
        if g.on:
            fl = (c[0], c[1] - 12)
            pygame.draw.circle(g.surf, (255, 170, 70), _ipt(fl), 2)
            pygame.draw.circle(g.surf, (255, 246, 200), _ipt(fl), 1)
    g.box(0.33, 0.33, 0.67, 0.67, 20, frame, base=3, decor=_panes)

    def _roof():
        apex = g.S(0.5, 0.5, 31)
        cs = [g.S(0.28, 0.28, 23), g.S(0.72, 0.28, 23), g.S(0.72, 0.72, 23),
              g.S(0.28, 0.72, 23)]
        fi = max(range(4), key=lambda i: cs[i][1])
        cxm = sum(p[0] for p in cs) / 4
        pygame.draw.polygon(g.surf, _dk(frame, 0.8), cs)
        for i in ((fi - 1) % 4, fi):
            j = (i + 1) % 4
            mx = (cs[i][0] + cs[j][0]) / 2
            pygame.draw.polygon(g.surf, _lt(frame, 1.25) if mx < cxm else _lt(frame, 1.05),
                                [cs[i], cs[j], apex])
            pygame.draw.polygon(g.surf, _dk(frame, 0.6), [cs[i], cs[j], apex], 1)
        r = pygame.Rect(0, 0, 10, 9)
        r.midbottom = (int(apex[0]), int(apex[1]) + 1)
        pygame.draw.ellipse(g.surf, _dk(frame, 0.7), r, 2)              # carry ring
        if g.on:
            _glow(g.surf, g.S(0.5, 0.5, 14), 26, (255, 200, 120), a=60)
    g.op(0.28, 0.28, 0.72, 0.72, 23, 40, _roof)


@_ground("dollhouse")
def _dollhouse(g):
    col = g.color
    wall = (244, 232, 218)
    g.box(0.12, 0.10, 0.88, 0.90, 3, WOOD)

    def _rooms(tp):
        if g.vx1:
            fp = g.xface(0.78, 0.16, 0.84, 30, base=3)
            rooms = [((0.06, 0.06, 0.94, 0.47), (240, 200, 214)),     # upstairs
                     ((0.06, 0.53, 0.49, 0.95), (200, 228, 206)),
                     ((0.51, 0.53, 0.94, 0.95), (206, 220, 240))]
            for (u0, v0, u1, v1), wc in rooms:
                pygame.draw.polygon(g.surf, _dk(wc, 0.86), _quad(fp, u0, v0, u1, v1))
                pygame.draw.polygon(g.surf, wc, _quad(fp, u0, v0, u1, v0 + (v1 - v0) * 0.72))
            # tiny furniture: a bed upstairs, a table + lamp, a sofa
            pygame.draw.polygon(g.surf, (250, 250, 252), _quad(fp, 0.14, 0.32, 0.42, 0.44))
            pygame.draw.polygon(g.surf, col, _quad(fp, 0.24, 0.34, 0.42, 0.44))
            pygame.draw.polygon(g.surf, WOOD, _quad(fp, 0.12, 0.24, 0.16, 0.44))
            pygame.draw.polygon(g.surf, (250, 222, 120), _ellipse_on(fp, 0.72, 0.18, 0.07, 0.07, 10))
            pygame.draw.polygon(g.surf, WOOD, _quad(fp, 0.14, 0.78, 0.40, 0.82))
            pygame.draw.line(g.surf, WOOD, fp(0.18, 0.82), fp(0.18, 0.93), 1)
            pygame.draw.line(g.surf, WOOD, fp(0.36, 0.82), fp(0.36, 0.93), 1)
            pygame.draw.polygon(g.surf, (220, 110, 110), _quad(fp, 0.58, 0.80, 0.88, 0.93))
            pygame.draw.polygon(g.surf, (200, 90, 96), _quad(fp, 0.58, 0.72, 0.88, 0.80))
            for u0, v0, u1, v1 in ((0.0, 0.0, 1.0, 0.06), (0.0, 0.47, 1.0, 0.53),
                                   (0.0, 0.94, 1.0, 1.0), (0.0, 0.0, 0.06, 1.0),
                                   (0.94, 0.0, 1.0, 1.0), (0.49, 0.53, 0.51, 0.95)):
                pygame.draw.polygon(g.surf, (250, 246, 240), _quad(fp, u0, v0, u1, v1))
            pygame.draw.polygon(g.surf, _dk(wall, 0.55), _quad(fp, 0, 0, 1, 1), 1)
        else:
            fp = g.xface(0.22, 0.16, 0.84, 30, base=3)
            for u in (0.3, 0.7):
                for v in (0.2, 0.62):
                    q = _quad(fp, u - 0.1, v, u + 0.1, v + 0.2)
                    pygame.draw.polygon(g.surf, (150, 196, 226), q)
                    pygame.draw.polygon(g.surf, (250, 246, 240), q, 1)
        side = g.yface(0.84 if g.vy1 else 0.16, 0.22, 0.78, 30, base=3)
        for u in (0.3, 0.7):
            q = _quad(side, u - 0.12, 0.22, u + 0.12, 0.44)
            pygame.draw.polygon(g.surf, (150, 196, 226), q)
            pygame.draw.polygon(g.surf, (250, 246, 240), q, 1)
            pygame.draw.line(g.surf, (250, 246, 240), side(u, 0.22), side(u, 0.44), 1)
        door = _quad(side, 0.40, 0.66, 0.60, 1.0)
        pygame.draw.polygon(g.surf, col, door)
        pygame.draw.polygon(g.surf, _dk(col, 0.5), door, 1)
    g.box(0.22, 0.16, 0.78, 0.84, 30, wall, base=3, decor=_rooms)

    def _roof():
        z0, zr = 33, 50
        ends = (0.12, 0.88)
        R = _dk(col, 0.95)
        ridge = [g.S(0.5, ends[0], zr), g.S(0.5, ends[1], zr)]
        planes = []
        for xe in (0.16, 0.84):
            pts = [g.S(xe, ends[0], z0), g.S(xe, ends[1], z0), ridge[1], ridge[0]]
            planes.append((xe, pts))
        gab_y = ends[1] - 0.04 if g.vy1 else ends[0] + 0.04
        gable = [g.S(0.22, gab_y, 33), g.S(0.78, gab_y, 33), g.S(0.5, gab_y, 48)]
        far = 0.16 if g.vx1 else 0.84
        for xe, pts in planes:
            if xe == far:
                pygame.draw.polygon(g.surf, _dk(R, 0.8), pts)
                pygame.draw.polygon(g.surf, _dk(R, 0.5), pts, 1)
        pygame.draw.polygon(g.surf, wall, gable)
        pygame.draw.polygon(g.surf, _dk(wall, 0.6), gable, 1)
        ow = _mid(gable[2], _mid(gable[0], gable[1]), 0.55)
        pygame.draw.circle(g.surf, (150, 196, 226), _ipt(ow), 3)
        pygame.draw.circle(g.surf, (250, 246, 240), _ipt(ow), 3, 1)
        for xe, pts in planes:
            if xe != far:
                pygame.draw.polygon(g.surf, R, pts)
                for k in range(1, 4):                                      # shingle rows
                    a = _mid(pts[0], pts[3], k / 4)
                    b = _mid(pts[1], pts[2], k / 4)
                    pygame.draw.line(g.surf, _dk(R, 0.78), a, b, 1)
                pygame.draw.polygon(g.surf, _dk(R, 0.5), pts, 1)
    g.op(0.12, 0.12, 0.88, 0.88, 33, 50, _roof)


@_ground("guitar_stand")
def _guitar_stand(g):
    col = g.color
    stand = (60, 58, 66)

    def _fn():
        yoke = g.S(0.46, 0.5, 26)
        for fx, fy in ((0.62, 0.30), (0.62, 0.70), (0.26, 0.5)):
            pygame.draw.line(g.surf, stand, g.S(fx, fy, 0), yoke, 2)
        # guitar lies in a plane leaning back: x(z) slides toward -x as it rises
        def S(w, z, dx=0.0):
            x = 0.60 - 0.13 * (z - 4) / 60 + dx
            return g.S(x, 0.5 + w / U_PX, z)

        def prof(z):
            a = 169 - (z - 16) ** 2
            b = 100 - (z - 32) ** 2
            return math.sqrt(max(a, b, 0))
        zs = [3 + i * 0.5 for i in range(79)]
        outline = ([S(prof(z), z) for z in zs] + [S(-prof(z), z) for z in reversed(zs)])
        back = [S(w_ / 1, z_, -0.05) for w_, z_ in
                [(prof(z), z) for z in zs] + [(-prof(z), z) for z in reversed(zs)]]
        front = g.vx1
        pygame.draw.polygon(g.surf, _dk(col, 0.55), back)                # body depth
        pygame.draw.polygon(g.surf, _dk(col, 0.72) if front else _dk(WOOD, 0.9), outline)
        if front:
            inner = [S(prof(z) * 0.8, z) for z in zs[4:-4]] + \
                    [S(-prof(z) * 0.8, z) for z in reversed(zs[4:-4])]
            pygame.draw.polygon(g.surf, col, inner)                        # sunburst
            hole = [S(math.cos(a) * 4, 26 + math.sin(a) * 4) for a in
                    (i * 2 * math.pi / 16 for i in range(16))]
            pygame.draw.polygon(g.surf, (40, 30, 26), hole)
            pygame.draw.polygon(g.surf, _lt(col, 1.3), hole, 1)
            br = [S(-4, 11), S(4, 11), S(4, 9), S(-4, 9)]
            pygame.draw.polygon(g.surf, (60, 40, 30), br)                  # bridge
        pygame.draw.polygon(g.surf, _dk(col, 0.45), outline, 1)
        neck = [S(-2.6, 40), S(2.6, 40), S(2.2, 60), S(-2.2, 60)]
        pygame.draw.polygon(g.surf, (132, 90, 56) if front else (104, 70, 44), neck)
        pygame.draw.polygon(g.surf, (78, 52, 34), neck, 1)
        if front:
            for z in (46, 51, 56):                                          # frets
                pygame.draw.line(g.surf, (220, 214, 196), S(-2.2, z), S(2.2, z), 1)
        head = [S(-3.2, 60), S(3.2, 60), S(2.6, 68), S(-2.6, 68)]
        pygame.draw.polygon(g.surf, (70, 48, 34), head)
        pygame.draw.polygon(g.surf, (44, 30, 22), head, 1)
        for z in (62, 65):
            for w in (-4.2, 4.2):
                pygame.draw.circle(g.surf, METAL, _ipt(S(w, z)), 1)
        if front:                                                          # strings
            pygame.draw.line(g.surf, (238, 232, 214), S(0, 10), S(0, 60), 1)
        for w in (-9, 9):                                                  # cradle cups
            c = S(w, 4, 0.03)
            pygame.draw.circle(g.surf, (44, 42, 50), _ipt(c), 2)
    g.op(0.20, 0.14, 0.80, 0.86, 0, 66, _fn)


@_ground("christmas_tree")
def _christmas_tree(g):
    col = g.color
    green, green_dk = (52, 128, 76), (34, 94, 58)

    def _pot():
        rg = lathe(g.surf, g.P, 0.5, 0.5, [(0, 0.14), (9, 0.17), (10, 0.18)], col, top=False)
        pygame.draw.polygon(g.surf, _lt(col, 1.1), rg[-1])
        pygame.draw.polygon(g.surf, _dk(col, 0.5), rg[-1], 1)
        pygame.draw.lines(g.surf, GOLD, False, _arcs(_ring(g.P, 0.5, 0.5, 0.16, 0.16, 6))[0], 2)
        lathe(g.surf, g.P, 0.5, 0.5, [(10, 0.045), (15, 0.04)], (110, 76, 48))
    g.op(0.32, 0.32, 0.68, 0.68, 0, 15, _pot)

    tiers = [[(14, 0.34), (18, 0.30), (31, 0.09)],
             [(26, 0.27), (30, 0.23), (43, 0.07)],
             [(38, 0.19), (42, 0.15), (57, 0.0)]]

    def _tree():
        t = _ticks() / 1000.0
        pts_lights = []
        for i, prof in enumerate(tiers):
            rg = lathe(g.surf, g.P, 0.5, 0.5, prof, green, top=False, n=28)
            fr = _arcs(rg[0])[0]
            for k in range(len(fr) - 1):                              # ragged hem
                a, b = fr[k], fr[k + 1]
                m = _mid(a, b)
                pygame.draw.polygon(g.surf, green_dk if k % 2 else green,
                                    [a, b, (m[0], m[1] + 3)])
            # tinsel garland swag across the front
            mid = _arcs(rg[1])[0]
            sw = [(_at(mid, s)[0], _at(mid, s)[1] - 4 + 3 * math.sin(math.pi * s * 2))
                  for s in (j / 10 for j in range(11))]
            pygame.draw.lines(g.surf, (240, 206, 110), False, sw, 1)
            for s, c in ((0.22, (220, 70, 80)), (0.58, (90, 140, 230)),
                         (0.82, (240, 196, 80)), (0.40, (236, 130, 190))):
                if (i + int(s * 10)) % 2:
                    continue
                p = _at(mid, s)
                b = (p[0], p[1] - 6 + i)
                pygame.draw.circle(g.surf, c, _ipt(b), 2)
                _px(g.surf, (b[0] - 1, b[1] - 1), _lt(c, 1.5))
            for s in (0.12, 0.34, 0.50, 0.66, 0.88):
                p = _at(fr, s)
                pts_lights.append((p[0], p[1] - 3, len(pts_lights)))
        for x, y, k in pts_lights:                                     # fairy lights
            if g.on:
                lit = (int(t * 3) + k) % 3
                c = ((255, 236, 150), (255, 150, 150), (170, 220, 255))[lit]
                pygame.draw.circle(g.surf, c, (int(x), int(y)), 2)
                pygame.draw.circle(g.surf, (255, 255, 240), (int(x), int(y)), 1)
            else:
                pygame.draw.circle(g.surf, (120, 120, 110), (int(x), int(y)), 1)
        top = g.S(0.5, 0.5, 60)
        if g.on:
            _glow(g.surf, top, 16, (255, 226, 130), a=110)
        pygame.draw.polygon(g.surf, GOLD, _star(top, 6))
        pygame.draw.polygon(g.surf, _dk(GOLD, 0.6), _star(top, 6), 1)
        pygame.draw.circle(g.surf, (255, 250, 220), _ipt(top), 1)
    g.op(0.16, 0.16, 0.84, 0.84, 15, 66, _tree)

    def _gift(x0, y0, x1, y1, h, c, rib):
        def dec(tp):
            m = [_mid(tp[0], tp[1]), _mid(tp[2], tp[3])]
            n = [_mid(tp[1], tp[2]), _mid(tp[3], tp[0])]
            pygame.draw.line(g.surf, rib, m[0], m[1], 2)
            pygame.draw.line(g.surf, rib, n[0], n[1], 2)
            c0 = _mid(m[0], m[1])
            pygame.draw.circle(g.surf, rib, (int(c0[0]) - 2, int(c0[1]) - 1), 2)
            pygame.draw.circle(g.surf, rib, (int(c0[0]) + 2, int(c0[1]) - 1), 2)
        g.box(x0, y0, x1, y1, h, c, decor=dec)
    _gift(0.64, 0.74, 0.86, 0.94, 7, (214, 70, 76), (246, 214, 110))
    _gift(0.76, 0.50, 0.94, 0.68, 9, (90, 150, 214), (250, 250, 252))


# ================================================================= TABLETOP
# Where an item's FRONT points for each `rot` -- the same mapping as
# isofurn._FACE / the seats (0 faces +y, 1 -x, 2 -y, 3 +x), so an item keeps
# facing the same way when tabletop.carry_on_rotate turns it with its table.
TOP_FRONT = ((0, 1), (-1, 0), (0, -1), (1, 0))


class _T:
    """Local frame for one tabletop item: l runs across it, f toward its
    front, z px up from the surface. Parts are queued with real-space boxes
    and depth-sorted like isofurn.draw's."""

    def __init__(self, surf, P, x, y, base, rot, color, on):
        self.surf, self.P, self.x, self.y, self.base = surf, P, x, y, base
        self.F = TOP_FRONT[rot % 4]
        self.L = (self.F[1], -self.F[0])
        self.color, self.on = color, on
        self.front_vis = self.F in ((0, 1), (1, 0))
        self.ops = []

    def pt(self, l, f):
        return (self.x + l * self.L[0] + f * self.F[0],
                self.y + l * self.L[1] + f * self.F[1])

    def S(self, l, f, z=0):
        return _up(self.P(*self.pt(l, f)), self.base + z)

    def rect(self, l0, f0, l1, f1):
        a, b = self.pt(l0, f0), self.pt(l1, f1)
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def box(self, l0, f0, l1, f1, h, col, z0=0, decor=None):
        r = self.rect(l0, f0, l1, f1)

        def fn():
            tp = _box(self.surf, self.P, r[0], r[1], r[2], r[3], h, col, base=self.base + z0)
            if decor:
                decor(tp)
        self.ops.append((r + (self.base + z0, self.base + z0 + h), fn))

    def op(self, l0, f0, l1, f1, z0, z1, fn):
        self.ops.append((self.rect(l0, f0, l1, f1) + (self.base + z0, self.base + z1), fn))

    def flush(self):
        for _, fn in sorted(self.ops, key=functools.cmp_to_key(_op_cmp)):
            fn()
        self.ops = []

    def face(self, l0, l1, f, z0, h):
        """Mapper fp(u, v) for the vertical face at local depth f spanning
        l0..l1 (u) and z0..z0+h (v top -> bottom)."""
        a, b = self.pt(l0, f), self.pt(l1, f)
        if self.F[1] != 0:                          # the face lies along x
            return _yface(self.P, a[1], a[0], b[0], h, self.base + z0)
        return _rface(self.P, a[0], a[1], b[1], h, self.base + z0)

    def lathe(self, l, f, prof, col, **kw):
        cx, cy = self.pt(l, f)
        return lathe(self.surf, self.P, cx, cy, [(z + self.base, r) for z, r in prof], col, **kw)

    def ring(self, l, f, r, z, n=20, asp=1.0):
        cx, cy = self.pt(l, f)
        return _ring(self.P, cx, cy, r, r * asp, self.base + z, n)

    def flat(self, l0, f0, l1, f1, z, col, border=None):
        pts = [self.S(l0, f0, z), self.S(l1, f0, z), self.S(l1, f1, z), self.S(l0, f1, z)]
        pygame.draw.polygon(self.surf, col, pts)
        if border:
            pygame.draw.polygon(self.surf, border, pts, 1)
        return pts

    def disc(self, l, f, zc, rpx, n=18):
        """A vertical circle facing the item's front (clock faces, plates)."""
        return [self.S(l + math.cos(a) * rpx / U_PX, f, zc + math.sin(a) * rpx)
                for a in (i * 2 * math.pi / n for i in range(n))]

    def sdisc(self, l, f, zc, rpx, n=18):
        """A vertical circle facing SIDEWAYS (plates in a dish rack)."""
        return [self.S(l, f + math.cos(a) * rpx / U_PX, zc + math.sin(a) * rpx)
                for a in (i * 2 * math.pi / n for i in range(n))]

    def depth(self, l, f):
        return self.P(*self.pt(l, f))[1]

    def front_dir(self):
        a = self.P(*self.pt(0, 0))
        b = self.P(*self.pt(0, 1))
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L


def _hull(pts):
    pts = sorted(set((round(p[0], 2), round(p[1], 2)) for p in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _note(surf, c, col, a=255):
    """A little quaver floating up (radio, music box)."""
    lay = pygame.Surface((9, 11), pygame.SRCALPHA)
    pygame.draw.ellipse(lay, col + (a,), (0, 7, 5, 4))
    pygame.draw.line(lay, col + (a,), (4, 8), (4, 1), 1)
    pygame.draw.line(lay, col + (a,), (4, 1), (7, 3), 1)
    surf.blit(lay, (int(c[0]) - 2, int(c[1]) - 9))


_TOP = {}


def _top(*kinds):
    def deco(fn):
        for k in kinds:
            _TOP[k] = fn
        return fn
    return deco


TOP = _TOP                              # kind -> painter (filled below)


def draw_top(surf, P, x, y, kind, color, base, on=False, rot=0):
    """Called by isofurn.draw_top for pack kinds."""
    t = _T(surf, P, x, y, base, rot, color, on)
    _TOP[kind](t)
    t.flush()


@_top("laptop")
def _laptop(t):
    body = _mix(t.color, (214, 216, 224), 0.55)

    def _keys(tp):
        t.flat(-0.10, -0.075, 0.10, 0.015, 2, (58, 60, 68))
        for r in range(3):
            f = -0.06 + r * 0.025
            a, b = t.S(-0.09, f, 2), t.S(0.09, f, 2)
            for k in range(8):
                _px(t.surf, _mid(a, b, (k + 0.5) / 8), (140, 142, 152))
        t.flat(-0.04, 0.03, 0.04, 0.075, 2, _lt(body, 1.12), _dk(body, 0.7))
    t.box(-0.13, -0.09, 0.13, 0.09, 2, body, decor=_keys)

    def _lid(tp):
        if t.front_vis:
            fp = t.face(-0.13, 0.13, -0.08, 2, 14)
            q = _quad(fp, 0.08, 0.08, 0.92, 0.86)
            if t.on:
                pygame.draw.polygon(t.surf, (132, 188, 236), q)
                hill = [fp(0.08, 0.86), fp(0.08, 0.62), fp(0.36, 0.50), fp(0.62, 0.62),
                        fp(0.92, 0.54), fp(0.92, 0.86)]
                pygame.draw.polygon(t.surf, (120, 190, 110), hill)
                pygame.draw.polygon(t.surf, (236, 110, 140), _heart(fp(0.66, 0.30), 2.5))
                pygame.draw.circle(t.surf, (255, 236, 150), _ipt(fp(0.24, 0.24)), 2)
            else:
                pygame.draw.polygon(t.surf, (40, 42, 52), q)
                pygame.draw.line(t.surf, (86, 90, 106), fp(0.16, 0.20), fp(0.34, 0.14), 1)
            pygame.draw.polygon(t.surf, _dk(body, 0.5), q, 1)
        else:
            fp = t.face(-0.13, 0.13, -0.10, 2, 14)
            c = fp(0.5, 0.45)                               # a little leaf logo
            col = (236, 246, 255) if t.on else _lt(body, 1.2)
            pygame.draw.ellipse(t.surf, col, (c[0] - 2, c[1] - 3, 4, 6))
    t.box(-0.13, -0.10, 0.13, -0.08, 14, body, z0=2, decor=_lid)
    if t.on and t.front_vis:
        def _gl():
            _glow(t.surf, t.S(0, 0.0, 10), 16, (160, 200, 255), a=40)
        t.op(-0.13, -0.08, 0.13, 0.09, 16, 17, _gl)


@_top("alarm_clock")
def _alarm_clock(t):
    col = t.color

    def _fn():
        zc, r = 8, 5.5
        back = t.disc(0, -0.03, zc, r)
        front = t.disc(0, 0.03, zc, r)
        for s in (-1, 1):                                  # little feet
            pygame.draw.line(t.surf, _dk(col, 0.6), t.S(s * 0.07, 0, 3), t.S(s * 0.10, 0, 0), 2)
        for s in (-1, 1):                                  # twin bells + hammer
            b = t.S(s * 0.10, 0, 14)
            pygame.draw.circle(t.surf, GOLD, _ipt(b), 3)
            pygame.draw.circle(t.surf, _dk(GOLD, 0.6), _ipt(b), 3, 1)
        pygame.draw.polygon(t.surf, _dk(col, 0.72), _hull(back + front))
        near, far = (front, back) if t.front_vis else (back, front)
        pygame.draw.polygon(t.surf, col, near)
        pygame.draw.polygon(t.surf, _dk(col, 0.5), _hull(back + front), 1)
        if t.front_vis:
            face = t.disc(0, 0.035, zc, r - 1.5)
            pygame.draw.polygon(t.surf, (250, 248, 240), face)
            c = t.S(0, 0.035, zc)
            pygame.draw.line(t.surf, (40, 36, 44), c, t.S(0, 0.035, zc + 3), 1)
            pygame.draw.line(t.surf, (40, 36, 44), c, t.S(0.06, 0.035, zc), 1)
            _px(t.surf, t.S(0, 0.035, zc - 3), (200, 70, 70))
        else:
            k = t.S(0, -0.035, zc)
            pygame.draw.circle(t.surf, _dk(col, 0.55), _ipt(k), 2)
        top = t.S(0, 0, 15)
        pygame.draw.line(t.surf, _dk(GOLD, 0.7), t.S(0, 0, 13), top, 1)
        pygame.draw.circle(t.surf, GOLD, _ipt(top), 1)
    t.op(-0.10, -0.05, 0.10, 0.05, 0, 17, _fn)


@_top("teapot_set")
def _teapot_set(t):
    col = t.color
    t.box(-0.16, -0.12, 0.16, 0.12, 1, WOOD_LT)                       # tray

    def _pot():
        sp = (0.13, -0.02)
        hd = (-0.12, -0.02)

        def spout():
            pygame.draw.line(t.surf, _dk(col, 0.7), t.S(0.05, -0.02, 5), t.S(*sp, 10), 4)
            pygame.draw.line(t.surf, col, t.S(0.05, -0.02, 5), t.S(*sp, 10), 2)

        def handle():
            pts = [t.S(-0.06, -0.02, 9), t.S(-0.12, -0.02, 9), t.S(-0.12, -0.02, 4),
                   t.S(-0.07, -0.02, 3)]
            pygame.draw.lines(t.surf, _dk(col, 0.6), False, pts, 3)
            pygame.draw.lines(t.surf, col, False, pts, 1)

        def body():
            t.lathe(-0.02, -0.02, [(1, 0.05), (3, 0.075), (7, 0.08), (10, 0.06), (11, 0.04)], col)
            t.lathe(-0.02, -0.02, [(11, 0.03), (12, 0.028), (14, 0.012)], _lt(col, 1.1))
            c = t.S(-0.02, 0.06, 6) if t.front_vis else None
            if c:
                pygame.draw.circle(t.surf, (250, 246, 236), _ipt(c), 2)   # painted flower
                _px(t.surf, c, (240, 200, 90))
        parts = [(t.depth(*sp), spout), (t.depth(*hd), handle), (t.depth(-0.02, -0.02), body)]
        for _, fn in sorted(parts, key=lambda p: p[0]):
            fn()
    t.op(-0.13, -0.10, 0.14, 0.06, 1, 15, _pot)
    for cl, cf in ((0.09, 0.07), (-0.08, 0.08)):
        def _cup(cl=cl, cf=cf):
            s = t.ring(cl, cf, 0.045, 1)
            pygame.draw.polygon(t.surf, (240, 240, 244), s)            # saucer
            pygame.draw.polygon(t.surf, (170, 170, 180), s, 1)
            t.lathe(cl, cf, [(1, 0.022), (4, 0.03)], (248, 248, 250), top=False)
            pygame.draw.polygon(t.surf, (170, 110, 60), t.ring(cl, cf, 0.024, 4))  # tea
            pygame.draw.lines(t.surf, col, False, _arcs(t.ring(cl, cf, 0.03, 3))[0], 1)
        t.op(cl - 0.05, cf - 0.05, cl + 0.05, cf + 0.05, 1, 5, _cup)


@_top("snow_globe")
def _snow_globe(t):
    col = t.color

    def _fn():
        t.lathe(0, 0, [(0, 0.10), (3, 0.09), (5, 0.075)], _dk(col, 0.9))
        c = t.S(0, 0, 12)
        r = 7
        ground = pygame.Rect(0, 0, 12, 5)
        ground.center = (int(c[0]), int(c[1]) + 3)
        pygame.draw.ellipse(t.surf, (246, 248, 252), ground)
        h = (int(c[0]) - 1, int(c[1]))                              # a tiny cottage
        pygame.draw.rect(t.surf, (214, 96, 90), (h[0] - 3, h[1] - 3, 6, 4))
        pygame.draw.polygon(t.surf, (250, 250, 252), [(h[0] - 4, h[1] - 3), (h[0], h[1] - 7),
                                                     (h[0] + 4, h[1] - 3)])
        _px(t.surf, (h[0], h[1] - 1), (255, 220, 120))
        tr = (int(c[0]) + 4, int(c[1]) + 1)
        pygame.draw.polygon(t.surf, (60, 140, 90), [(tr[0] - 2, tr[1]), (tr[0] + 2, tr[1]),
                                                   (tr[0], tr[1] - 6)])
        tm = _ticks() / 1000.0
        for k in range(7):                                         # drifting snow
            a = k * 2.4
            ph = (tm * 0.12 + k / 7) % 1.0
            fx = c[0] + math.sin(a + tm * 0.8) * (r - 2) * 0.8
            fy = c[1] - r + 2 + ph * (2 * r - 4)
            _px(t.surf, (fx, fy), (255, 255, 255))
        _apoly(t.surf, (214, 236, 248, 70), [(c[0] + math.cos(a) * r, c[1] + math.sin(a) * r)
                                             for a in (i * math.pi / 10 for i in range(20))])
        pygame.draw.circle(t.surf, (200, 222, 236), _ipt(c), r, 1)
        pygame.draw.arc(t.surf, (255, 255, 255), (c[0] - r + 2, c[1] - r + 2, 2 * r - 4, 2 * r - 4),
                        1.9, 2.9, 1)
    t.op(-0.07, -0.07, 0.07, 0.07, 0, 18, _fn)


@_top("hourglass")
def _hourglass(t):
    wood = _dk(WOOD_LT, 0.9)
    sand = _mix(t.color, (236, 206, 130), 0.55)

    def _fn():
        t.lathe(0, 0, [(0, 0.10), (2, 0.10)], wood)
        posts = sorted(((s * 0.075, s * 0.04) for s in (-1, 1)), key=lambda p: t.depth(*p))
        pygame.draw.line(t.surf, _dk(wood, 0.8), t.S(*posts[0], 2), t.S(*posts[0], 18), 2)
        ph = (_ticks() / 30000.0) % 1.0                              # 30 s of sand
        c = t.S(0, 0, 10)
        top, bot = c[1] - 7, c[1] + 7
        w = 3.5
        glass = [(c[0] - w, top), (c[0] + w, top), (c[0] + 0.8, c[1]), (c[0] + w, bot),
                 (c[0] - w, bot), (c[0] - 0.8, c[1])]
        hb = 6 * (1 - ph)                                            # sand left above
        k = (w - 0.8) / 7
        pygame.draw.polygon(t.surf, sand, [(c[0] - 0.8 - k * hb, c[1] - hb),
                                           (c[0] + 0.8 + k * hb, c[1] - hb),
                                           (c[0] + 0.8, c[1] - 0.5), (c[0] - 0.8, c[1] - 0.5)])
        pile = 1 + 5 * ph
        pygame.draw.polygon(t.surf, sand, [(c[0] - w, bot), (c[0] + w, bot),
                                           (c[0] + 1, bot - pile), (c[0] - 1, bot - pile)])
        pygame.draw.line(t.surf, _dk(sand, 0.85), c, (c[0], bot - pile), 1)
        _apoly(t.surf, (220, 236, 244, 90), glass)
        pygame.draw.polygon(t.surf, (170, 196, 210), glass, 1)
        _px(t.surf, (c[0] - 2, top + 2), (255, 255, 255))
        pygame.draw.line(t.surf, wood, t.S(*posts[1], 2), t.S(*posts[1], 18), 2)
        t.lathe(0, 0, [(17, 0.10), (19, 0.10)], wood)
    t.op(-0.10, -0.10, 0.10, 0.10, 0, 19, _fn)


@_top("succulent")
def _succulent(t):
    def _fn():
        t.lathe(0, 0, [(0, 0.07), (5, 0.09), (6, 0.095)], t.color, top=False)
        pygame.draw.polygon(t.surf, (96, 70, 50), t.ring(0, 0, 0.082, 6))
        leaves = []
        for layer, (n, rad, z, L) in enumerate(((9, 0.07, 7, 6), (7, 0.042, 8, 5), (4, 0.016, 9, 4))):
            for k in range(n):
                a = 2 * math.pi * (k + layer * 0.5) / n
                tip_l, tip_f = math.cos(a) * (rad + 0.05), math.sin(a) * (rad + 0.05)
                leaves.append((t.depth(tip_l, tip_f) + layer * 0.3, layer, a, rad, z, L))
        for _, layer, a, rad, z, L in sorted(leaves):
            b = t.S(math.cos(a) * rad * 0.3, math.sin(a) * rad * 0.3, z)
            tip = t.S(math.cos(a) * (rad + 0.05), math.sin(a) * (rad + 0.05), z + 2 + layer)
            d = (tip[0] - b[0], tip[1] - b[1])
            n = (-d[1] * 0.35, d[0] * 0.35)
            pts = [b, (b[0] + d[0] * 0.5 + n[0], b[1] + d[1] * 0.5 + n[1]), tip,
                   (b[0] + d[0] * 0.5 - n[0], b[1] + d[1] * 0.5 - n[1])]
            c = (150, 196, 164) if layer == 0 else (132, 186, 150) if layer == 1 else (170, 210, 176)
            pygame.draw.polygon(t.surf, c, pts)
            pygame.draw.polygon(t.surf, _dk(c, 0.62), pts, 1)
            _px(t.surf, tip, (232, 140, 164))
    t.op(-0.07, -0.07, 0.07, 0.07, 0, 14, _fn)


@_top("jewelry_box")
def _jewelry_box(t):
    col = t.color
    velvet = (160, 44, 70)

    def _lid(tp):
        if t.front_vis:
            fp = t.face(-0.11, 0.11, -0.07, 6, 9)
            q = _quad(fp, 0.14, 0.16, 0.86, 0.84)
            pygame.draw.polygon(t.surf, (200, 222, 234), q)             # lid mirror
            pygame.draw.line(t.surf, (246, 250, 252), fp(0.24, 0.70), fp(0.44, 0.24), 1)
            pygame.draw.polygon(t.surf, GOLD, q, 1)
    t.box(-0.11, -0.09, 0.11, -0.07, 9, col, z0=6, decor=_lid)

    def _body(tp):
        t.flat(-0.09, -0.05, 0.09, 0.05, 6, velvet, _dk(velvet, 0.6))
        r = t.S(-0.04, 0.0, 7)                                     # a ring with a gem
        pygame.draw.ellipse(t.surf, GOLD, (r[0] - 3, r[1] - 2, 6, 4), 1)
        pygame.draw.circle(t.surf, (140, 220, 240), (int(r[0]), int(r[1]) - 2), 1)
        for k in range(5):                                         # pearl string
            p = t.S(0.01 + k * 0.016, -0.02 + (k % 2) * 0.02, 6.5)
            pygame.draw.circle(t.surf, (250, 248, 244), _ipt(p), 1)
        if t.front_vis:
            fp = t.face(-0.11, 0.11, 0.07, 0, 6)
            pygame.draw.rect(t.surf, GOLD, (*_ipt(fp(0.5, 0.2)), 2, 3))
            pygame.draw.line(t.surf, _lt(col, 1.25), fp(0.06, 0.55), fp(0.94, 0.55), 1)
    t.box(-0.11, -0.07, 0.11, 0.07, 6, col, decor=_body)


@_top("perfume_set")
def _perfume_set(t):
    col = t.color

    def _tray():
        rg = t.ring(0, 0, 0.12, 0, 28, asp=0.8)
        pygame.draw.polygon(t.surf, GOLD, rg)
        pygame.draw.polygon(t.surf, (214, 230, 238), t.ring(0, 0, 0.105, 1, 28, asp=0.78))
        pygame.draw.polygon(t.surf, _dk(GOLD, 0.6), rg, 1)
    t.op(-0.12, -0.10, 0.12, 0.10, 0, 1, _tray)
    tint = _mix(col, (250, 250, 255), 0.35)

    t.box(-0.09, -0.04, -0.03, 0.02, 9, tint, z0=1)                  # tall square bottle
    t.box(-0.075, -0.025, -0.045, 0.005, 4, GOLD, z0=10)

    def _round():
        t.lathe(0.035, -0.03, [(1, 0.03), (3, 0.045), (6, 0.04), (7, 0.02), (8, 0.015)],
                (236, 150, 176))
        tip = t.S(0.035, -0.03, 8)
        pygame.draw.line(t.surf, GOLD, tip, (tip[0], tip[1] - 3), 1)
        bulb = t.S(0.09, -0.04, 7)                                  # atomiser bulb + tassel
        pygame.draw.line(t.surf, (200, 180, 120), (tip[0], tip[1] - 3), bulb, 1)
        pygame.draw.circle(t.surf, (214, 90, 120), _ipt(bulb), 2)
        pygame.draw.line(t.surf, GOLD, (bulb[0], bulb[1] + 2), (bulb[0] + 1, bulb[1] + 6), 1)
    t.op(0.0, -0.075, 0.075, 0.015, 1, 12, _round)

    def _small():
        t.lathe(0.02, 0.055, [(1, 0.025), (5, 0.025), (6, 0.012)], (250, 214, 120))
        t.lathe(0.02, 0.055, [(6, 0.012), (8, 0.012)], (60, 50, 60))
    t.op(-0.01, 0.03, 0.05, 0.08, 1, 9, _small)


@_top("radio")
def _radio(t):
    col = t.color

    def _front(tp):
        if not t.front_vis:
            return
        fp = t.face(-0.12, 0.12, 0.06, 0, 11)
        g = _quad(fp, 0.07, 0.18, 0.50, 0.86)
        pygame.draw.polygon(t.surf, (230, 214, 180), g)            # cloth grille
        for k in range(1, 5):
            v = 0.18 + 0.68 * k / 5
            pygame.draw.line(t.surf, (170, 150, 116), fp(0.09, v), fp(0.48, v), 1)
        pygame.draw.polygon(t.surf, _dk(col, 0.5), g, 1)
        dial = _quad(fp, 0.56, 0.18, 0.93, 0.50)
        pygame.draw.polygon(t.surf, (255, 222, 140) if t.on else (236, 226, 200), dial)
        pygame.draw.line(t.surf, (200, 60, 60), fp(0.70, 0.20), fp(0.70, 0.48), 1)
        pygame.draw.polygon(t.surf, _dk(col, 0.5), dial, 1)
        for u in (0.64, 0.84):
            pygame.draw.circle(t.surf, (240, 236, 226), _ipt(fp(u, 0.70)), 2)
            pygame.draw.circle(t.surf, _dk(col, 0.5), _ipt(fp(u, 0.70)), 2, 1)
    t.box(-0.12, -0.06, 0.12, 0.06, 11, col, decor=_front)

    def _handle():
        pts = [t.S(-0.08, 0, 11), t.S(-0.06, 0, 15), t.S(0.06, 0, 15), t.S(0.08, 0, 11)]
        pygame.draw.lines(t.surf, (70, 56, 44), False, pts, 2)
        a = t.S(0.10, -0.04, 11)
        pygame.draw.line(t.surf, METAL, a, t.S(0.15, -0.07, 22), 1)       # antenna
        pygame.draw.circle(t.surf, METAL, _ipt(t.S(0.15, -0.07, 22)), 1)
        if t.on:                                                            # music!
            tm = _ticks() / 1000.0
            for k in range(2):
                ph = (tm * 0.5 + k * 0.5) % 1.0
                c = t.S(-0.02 + 0.06 * k, 0.04, 14 + ph * 16)
                _note(t.surf, (c[0] + math.sin(tm * 3 + k) * 3, c[1]),
                      (90, 70, 150) if k else (200, 80, 120), int(255 * (1 - ph)))
    t.op(-0.12, -0.08, 0.16, 0.06, 11, 30, _handle)


@_top("teddy_bear")
def _teddy_bear(t):
    class _Adapt:
        def S(self, cx, cy, z=0):
            return t.S(0, 0, z)

        def front_dir(self):
            return t.front_dir()

    def _fn():
        _bear(t.surf, _Adapt(), 0, 0, 0.42, (206, 160, 112), t.color, (240, 214, 186))
    t.op(-0.08, -0.08, 0.08, 0.08, 0, 20, _fn)


@_top("lava_lamp")
def _lava_lamp(t):
    liquid = _lt(t.color, 1.25) if t.on else _dk(t.color, 0.75)
    blob = _mix(_lt(t.color, 1.5), (255, 230, 150), 0.4) if t.on else _dk(t.color, 0.95)

    def _fn():
        if t.on:
            _glow(t.surf, t.S(0, 0, 13), 18, _lt(t.color, 1.4), a=60)
        t.lathe(0, 0, [(0, 0.09), (5, 0.06), (6, 0.055)], (170, 174, 186))
        t.lathe(0, 0, [(6, 0.055), (10, 0.08), (15, 0.07), (20, 0.04)], liquid, top=False)
        c = t.S(0, 0, 0)
        tm = _ticks() / 1000.0
        if t.on:
            for k, (sp, r) in enumerate(((0.35, 2.5), (0.23, 2), (0.5, 1.5))):
                ph = 0.5 + 0.5 * math.sin(tm * sp + k * 2.1)
                z = 8 + ph * 10
                pygame.draw.circle(t.surf, blob, (int(c[0] + math.sin(k * 3 + tm * 0.3)),
                                                  int(c[1] - z)), int(r))
        else:
            pygame.draw.ellipse(t.surf, blob, (c[0] - 3, c[1] - 9, 6, 3))
        pygame.draw.line(t.surf, (255, 255, 255), t.S(-0.02, 0.02, 9), t.S(-0.015, 0.02, 16), 1)
        t.lathe(0, 0, [(20, 0.04), (23, 0.028), (24, 0.015)], (170, 174, 186))
    t.op(-0.09, -0.09, 0.09, 0.09, 0, 24, _fn)


@_top("cake_stand")
def _cake_stand(t):
    frost = _mix(t.color, (255, 255, 255), 0.45)

    def _fn():
        t.lathe(0, 0, [(0, 0.07), (1, 0.07)], (238, 240, 244))
        t.lathe(0, 0, [(1, 0.022), (6, 0.022)], (238, 240, 244))
        t.lathe(0, 0, [(6, 0.125), (7, 0.14)], (246, 246, 250))
        rg = t.lathe(0, 0, [(7, 0.105), (15, 0.105)], frost, top=False)
        fr = _arcs(rg[0])[0]
        mid = [_up(p, 4) for p in fr]
        pygame.draw.lines(t.surf, (250, 240, 220), False, mid, 2)       # cream layer
        top = rg[-1]
        pygame.draw.polygon(t.surf, _lt(frost, 1.06), top)
        pygame.draw.polygon(t.surf, _dk(frost, 0.6), top, 1)
        ft = _arcs(top)[0]
        for k in range(1, 7):                                           # icing drips
            p = _at(ft, k / 7)
            pygame.draw.line(t.surf, _lt(frost, 1.06), p, (p[0], p[1] + 2 + (k % 2) * 2), 2)
        for k in range(5):                                              # strawberries
            a = k * 2 * math.pi / 5
            s = t.S(math.cos(a) * 0.07, math.sin(a) * 0.07, 16)
            pygame.draw.circle(t.surf, (214, 50, 64), _ipt(s), 2)
            _px(t.surf, (s[0], s[1] - 2), (90, 170, 90))
        c = t.S(0, 0, 15)                                               # one candle
        pygame.draw.line(t.surf, (250, 230, 140), c, (c[0], c[1] - 5), 2)
        pygame.draw.circle(t.surf, (255, 190, 90), (int(c[0]), int(c[1]) - 7), 1)
    t.op(-0.14, -0.14, 0.14, 0.14, 0, 22, _fn)


@_top("board_game")
def _board_game(t):
    def _board():
        t.flat(-0.16, -0.16, 0.16, 0.16, 0, _dk(WOOD_LT, 0.85))
        t.flat(-0.155, -0.155, 0.155, 0.155, 1, (246, 238, 220), (170, 150, 120))
        for (l0, f0), c in (((-0.15, -0.15), (220, 80, 80)), ((0.05, -0.15), (80, 130, 220)),
                            ((0.05, 0.05), (240, 196, 80)), ((-0.15, 0.05), (96, 180, 110))):
            t.flat(l0, f0, l0 + 0.10, f0 + 0.10, 1, c)
        t.flat(-0.05, -0.05, 0.05, 0.05, 1, t.color)
        for k in range(-4, 5):                                          # track squares
            _px(t.surf, t.S(k * 0.03, 0, 1), (150, 140, 120))
            _px(t.surf, t.S(0, k * 0.03, 1), (150, 140, 120))
    t.op(-0.16, -0.16, 0.16, 0.16, 0, 1, _board)
    for l, f, c in ((-0.10, -0.10, (200, 60, 60)), (0.10, 0.10, (230, 180, 60)),
                    (0.03, -0.08, (70, 110, 210))):
        def _pawn(l=l, f=f, c=c):
            t.lathe(l, f, [(1, 0.018), (4, 0.01)], c)
            p = t.S(l, f, 5)
            pygame.draw.circle(t.surf, c, _ipt(p), 2)
            _px(t.surf, (p[0] - 1, p[1] - 1), _lt(c, 1.5))
        t.op(l - 0.02, f - 0.02, l + 0.02, f + 0.02, 1, 7, _pawn)
    for l, f in ((0.08, -0.02), (0.11, 0.03)):
        def _pips(tp):
            c = _mid(tp[0], tp[2])
            _px(t.surf, c, (40, 40, 50))
        t.box(l - 0.015, f - 0.015, l + 0.015, f + 0.015, 3, (250, 250, 252), z0=1, decor=_pips)


@_top("trophy")
def _trophy(t):
    def _plaque(tp):
        if t.front_vis:
            fp = t.face(-0.07, 0.07, 0.07, 0, 4)
            pygame.draw.polygon(t.surf, GOLD, _quad(fp, 0.2, 0.25, 0.8, 0.75))
    t.box(-0.07, -0.07, 0.07, 0.07, 4, (70, 50, 40), decor=_plaque)

    def _cup():
        t.lathe(0, 0, [(4, 0.035), (7, 0.02), (9, 0.045)], GOLD)
        rg = t.lathe(0, 0, [(9, 0.05), (12, 0.07), (16, 0.09), (17, 0.095)], GOLD, top=False)
        pygame.draw.polygon(t.surf, _lt(GOLD, 1.1), rg[-1])
        pygame.draw.polygon(t.surf, _dk(GOLD, 0.62), t.ring(0, 0, 0.078, 17))
        pygame.draw.polygon(t.surf, _dk(GOLD, 0.5), rg[-1], 1)
        for s in (-1, 1):                                               # handles
            pts = [t.S(s * 0.085, 0, 15), t.S(s * 0.13, 0, 15), t.S(s * 0.11, 0, 10),
                   t.S(s * 0.06, 0, 10)]
            pygame.draw.lines(t.surf, _dk(GOLD, 0.7), False, pts, 2)
        if t.front_vis:
            s = t.S(0, 0.08, 13)
            pygame.draw.polygon(t.surf, (255, 248, 210), _star(s, 3))
    t.op(-0.13, -0.10, 0.13, 0.10, 4, 18, _cup)


@_top("music_box")
def _music_box(t):
    body = WOOD_LT
    vel = t.color

    def _lid(tp):
        if t.front_vis:
            fp = t.face(-0.10, 0.10, -0.07, 6, 10)
            q = _quad(fp, 0.12, 0.14, 0.88, 0.86)
            pygame.draw.polygon(t.surf, (206, 226, 236), q)
            pygame.draw.polygon(t.surf, GOLD, q, 1)
    t.box(-0.10, -0.09, 0.10, -0.07, 10, body, z0=6, decor=_lid)

    def _top_(tp):
        t.flat(-0.085, -0.055, 0.085, 0.055, 6, vel, _dk(vel, 0.6))
        if t.front_vis:
            fp = t.face(-0.10, 0.10, 0.07, 0, 6)
            for u in (0.2, 0.8):                                         # painted flowers
                pygame.draw.circle(t.surf, (240, 150, 170), _ipt(fp(u, 0.5)), 1)
            pygame.draw.rect(t.surf, GOLD, (*_ipt(fp(0.5, 0.15)), 2, 2))
    t.box(-0.10, -0.07, 0.10, 0.07, 6, body, decor=_top_)

    def _dancer():
        c = t.S(0, 0, 6)
        tm = _ticks() / 1000.0
        w = math.cos(tm * 4) if t.on else 1.0                           # pirouette
        pygame.draw.line(t.surf, GOLD, c, (c[0], c[1] - 2), 1)
        skirt = [(c[0] - 4 * w, c[1] - 4), (c[0] + 4 * w, c[1] - 4), (c[0], c[1] - 8)]
        pygame.draw.polygon(t.surf, (250, 190, 210), skirt)
        pygame.draw.line(t.surf, (250, 226, 214), (c[0], c[1] - 8), (c[0], c[1] - 10), 1)
        pygame.draw.line(t.surf, (250, 226, 214), (c[0] - 3 * w, c[1] - 11), (c[0] + 3 * w, c[1] - 11), 1)
        pygame.draw.circle(t.surf, (250, 226, 214), (int(c[0]), int(c[1]) - 12), 1)
        pygame.draw.line(t.surf, METAL, t.S(0.10, 0, 3), t.S(0.14, 0, 3), 1)  # wind-up key
        pygame.draw.circle(t.surf, METAL, _ipt(t.S(0.14, 0, 4)), 2, 1)
        if t.on:
            for k in range(2):
                ph = (tm * 0.45 + k * 0.5) % 1.0
                p = t.S(0.04 - 0.08 * k, 0, 12 + ph * 14)
                _note(t.surf, (p[0] + math.sin(tm * 2 + k) * 3, p[1]), (200, 110, 150),
                      int(255 * (1 - ph)))
    t.op(-0.04, -0.04, 0.15, 0.04, 6, 20, _dancer)


@_top("bonsai")
def _bonsai(t):
    def _soil(tp):
        t.flat(-0.105, -0.055, 0.105, 0.055, 4, (84, 64, 46))
        for l, f in ((-0.06, 0.02), (0.05, -0.03), (0.07, 0.03)):
            pygame.draw.circle(t.surf, (104, 160, 90), _ipt(t.S(l, f, 4)), 1)      # moss
    t.box(-0.12, -0.07, 0.12, 0.07, 4, t.color, decor=_soil)

    def _tree():
        trunk = [(0.02, 0, 4), (-0.02, 0.01, 8), (0.01, 0.0, 12), (0.05, -0.01, 15)]
        pts = [t.S(*p) for p in trunk]
        pygame.draw.lines(t.surf, (96, 66, 44), False, pts, 3)
        pygame.draw.lines(t.surf, (132, 94, 64), False, pts, 1)
        pygame.draw.line(t.surf, (96, 66, 44), t.S(-0.01, 0.0, 10), t.S(-0.08, 0.01, 13), 2)
        pads = [(0.06, -0.01, 17, 7, 4), (-0.08, 0.01, 14, 6, 3), (0.0, 0.0, 20, 6, 3),
                (0.08, 0.03, 13, 5, 3)]
        for l, f, z, rx, ry in sorted(pads, key=lambda p: t.depth(p[0], p[1]) + p[2] * 0.01):
            c = t.S(l, f, z)
            r = pygame.Rect(0, 0, rx * 2, ry * 2)
            r.center = _ipt(c)
            pygame.draw.ellipse(t.surf, (52, 118, 70), r)
            pygame.draw.ellipse(t.surf, (86, 158, 96), r.inflate(-3, -2).move(-1, -1))
            pygame.draw.ellipse(t.surf, (34, 84, 50), r, 1)
    t.op(-0.12, -0.06, 0.13, 0.07, 4, 24, _tree)


@_top("fish_bowl")
def _fish_bowl(t):
    def _fn():
        c = t.S(0, 0, 8)
        r = 8
        circ = [(c[0] + math.cos(a) * r, c[1] + math.sin(a) * r * 0.96)
                for a in (i * 2 * math.pi / 28 for i in range(28))]
        wl = c[1] - 4
        water = [p for p in circ if p[1] >= wl]
        _apoly(t.surf, (120, 190, 230, 170), water)
        for k, pc in enumerate(((236, 120, 120), (240, 220, 140), (140, 190, 240), (250, 250, 250))):
            _px(t.surf, (c[0] - 4 + k * 2.5, c[1] + 6 - (k % 2)), pc)          # pebbles
        pygame.draw.line(t.surf, (80, 170, 100), (c[0] + 3, c[1] + 6), (c[0] + 4, c[1] + 1), 1)
        tm = _ticks() / 1000.0
        dx = math.sin(tm * 0.9) * 3
        d = 1 if math.cos(tm * 0.9) > 0 else -1
        fx, fy = c[0] + dx, c[1] + 1 + math.sin(tm * 2.1)
        pygame.draw.ellipse(t.surf, (246, 140, 50), (fx - 3, fy - 2, 6, 4))
        pygame.draw.polygon(t.surf, (250, 170, 80), [(fx - 3 * d, fy), (fx - 6 * d, fy - 2),
                                                     (fx - 6 * d, fy + 2)])
        _px(t.surf, (fx + 1.5 * d, fy - 0.5), (30, 30, 36))
        ph = (tm * 0.6) % 1.0
        _px(t.surf, (fx + 3 * d, fy - 2 - ph * 4), (230, 246, 255))
        pygame.draw.line(t.surf, (206, 236, 250), (c[0] - 7, wl), (c[0] + 7, wl), 1)
        _apoly(t.surf, (230, 244, 252, 50), circ)
        pygame.draw.polygon(t.surf, (170, 206, 224), circ, 1)
        rim = pygame.Rect(0, 0, 10, 3)
        rim.center = (int(c[0]), int(c[1] - r + 1))
        pygame.draw.ellipse(t.surf, (214, 236, 246), rim, 1)
        pygame.draw.arc(t.surf, (255, 255, 255), (c[0] - r + 2, c[1] - r + 2, 2 * r - 4, 2 * r - 4),
                        1.9, 2.8, 1)
    t.op(-0.09, -0.09, 0.09, 0.09, 0, 17, _fn)


@_top("dish_rack")
def _dish_rack(t):
    wire = (200, 204, 212)

    t.box(-0.14, -0.08, 0.14, 0.08, 2, (176, 180, 190))

    def _plates():
        plates = [(-0.10 + k * 0.045, (250, 250, 252) if k % 2 == 0 else _mix(t.color, (255, 255, 255), 0.3))
                  for k in range(5)]
        for l, c in sorted(plates, key=lambda p: t.depth(p[0], 0)):
            ring = t.sdisc(l, 0, 8, 6)
            pygame.draw.polygon(t.surf, c, ring)
            pygame.draw.polygon(t.surf, _dk(c, 0.62), ring, 1)
            inner = t.sdisc(l, 0, 8, 3.5)
            pygame.draw.polygon(t.surf, _dk(c, 0.93), inner)
        for l in (-0.13, 0.13):                                          # wire ends
            for f in (-0.07, 0.07):
                pygame.draw.line(t.surf, wire, t.S(l, f, 2), t.S(l, f, 8), 1)
            pygame.draw.line(t.surf, wire, t.S(l, -0.07, 8), t.S(l, 0.07, 8), 1)
    t.op(-0.14, -0.08, 0.14, 0.08, 2, 15, _plates)
