"""Isometric 3D furniture for the home view.

Everything is built from `_box(...)` -- an isometric prism over a rectangle given
in TILE space, from one height to another. Working in tile space (not pixels) keeps
every piece glued to the floor diamond and the two walls, and makes detailing easy
(a sofa back is just another small box over the back third of the footprint).

`draw(surf, P, gx, gy, fw, fh, kind, color)` renders one piece, where `P(tx, ty)`
projects a tile-space point to screen (supplied by homeiso so play and Build match).

Correctness rules (added in the rotation-fix pass):
* Every part is queued as an "op" with its real-space bounding box
  (tx0,ty0,tx1,ty1,z0,z1) and the whole piece is depth-sorted before drawing,
  so parts layer correctly in ALL four rotations (camera looks from +x,+y).
* Parts never interpenetrate: stacked parts share an exact z boundary, abutting
  parts share an exact x/y boundary. The sorter relies on this.
* Face detailing (drawers, doors, books, screens, fire) is only painted on a
  face that actually faces the camera for the current rotation; rotated-away
  pieces show a plain back, like real furniture against a wall.
  Canonical +x face is visible at rot 0,1; canonical +y face at rot 0,3.
"""
import functools
import math

import pygame


def _lt(c, f=1.16):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.74):
    return tuple(max(0, int(v * f)) for v in c)


def _up(p, h):
    return (p[0], p[1] - h)


# height (px) of the main body for each kind; used by the generic path too
HEIGHT = {
    "bed": 14, "sofa": 12, "armchair": 14, "chair": 29, "stool": 15, "bench": 12,
    "coffee_table": 5, "dining_table": 6, "nightstand": 22, "dresser": 26,
    "wardrobe": 46, "vanity": 24, "fridge": 46, "stove": 26, "counter": 24,
    "bookshelf": 42, "tv": 12, "plant": 12, "lamp": 8, "chest": 16,
    "fireplace": 30, "bin_decor": 16, "workbench": 22,
    "piano": 42, "piano_bench": 18, "aquarium": 37, "record_player": 20, "crib": 32,
    "toy_chest": 18, "sink": 24, "microwave": 40, "kitchen_island": 27,
    "easel": 48, "globe": 36, "cat_tower": 40, "standing_fan": 44,
}


def _box(surf, P, x0, y0, x1, y1, h, color, base=0, faces=True):
    """Iso prism over tile-rect [x0,x1]x[y0,y1] from `base` to `base+h` (px up).

    Always draws the two side faces that actually face the camera (the two edges
    meeting at the nearest/front corner), so the box stays solid in every rotation
    instead of going hollow when turned around."""
    pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
    Bp = [_up(p, base) for p in pts]
    Tp = [_up(p, base + h) for p in pts]
    ol = _dk(color, 0.5)
    if faces:
        fi = max(range(4), key=lambda i: pts[i][1])         # front corner (closest to viewer)
        cx = sum(p[0] for p in pts) / 4.0
        for i in ((fi - 1) % 4, fi):                        # the two faces meeting there
            j = (i + 1) % 4
            quad = [Tp[i], Tp[j], Bp[j], Bp[i]]
            mxp = (pts[i][0] + pts[j][0]) / 2.0
            pygame.draw.polygon(surf, _dk(color, 0.72 if mxp >= cx else 0.86), quad)
            pygame.draw.polygon(surf, ol, quad, 1)
    pygame.draw.polygon(surf, _lt(color), Tp)               # top face
    pygame.draw.polygon(surf, ol, Tp, 1)
    return tuple(Tp)


def _diamond(surf, P, x0, y0, x1, y1, color, h=0, border=None):
    pts = [_up(P(x0, y0), h), _up(P(x1, y0), h), _up(P(x1, y1), h), _up(P(x0, y1), h)]
    pygame.draw.polygon(surf, color, pts)
    if border:
        pygame.draw.polygon(surf, border, pts, 2)
    return pts


def _mid(a, b, t=0.5):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _rface(P, xc, ya, yb, h, base=0):
    """Return fp(u,v): maps [0,1]^2 onto the vertical face at tile-x = xc spanning
    tile-y [ya..yb] and height [base..base+h] (u: ya->yb, v: top->bottom). Used to
    paint drawer/door panels that follow the iso perspective."""
    a, at = _up(P(xc, ya), base), _up(P(xc, ya), base + h)
    b, bt = _up(P(xc, yb), base), _up(P(xc, yb), base + h)
    return lambda u, v: _mid(_mid(at, bt, u), _mid(a, b, u), v)


def _yface(P, yc, xa, xb, h, base=0):
    """Same as _rface but for the vertical face at tile-y = yc (u runs xa->xb)."""
    a, at = _up(P(xa, yc), base), _up(P(xa, yc), base + h)
    b, bt = _up(P(xb, yc), base), _up(P(xb, yc), base + h)
    return lambda u, v: _mid(_mid(at, bt, u), _mid(a, b, u), v)


def _op_cmp(a, b):
    """Painter's order for two part bounding boxes in REAL tile space.

    Camera looks from +x,+y (screen-down = +x+y), z is up. If the boxes are
    cleanly separated along an axis the farther one draws first; parts of one
    furniture piece are authored to never interpenetrate, so this is enough."""
    e = 1e-4
    A, B = a[0], b[0]
    if A[2] <= B[0] + e:
        return -1                       # A entirely at smaller x -> behind
    if B[2] <= A[0] + e:
        return 1
    if A[3] <= B[1] + e:
        return -1                       # A entirely at smaller y -> behind
    if B[3] <= A[1] + e:
        return 1
    if A[5] <= B[4] + e:
        return -1                       # A entirely below B -> first
    if B[5] <= A[4] + e:
        return 1
    ka = A[2] + A[3] + A[4] * 0.001     # fallback: front corner depth
    kb = B[2] + B[3] + B[4] * 0.001
    return -1 if ka < kb else (1 if ka > kb else 0)


# optional painter for a switched-on TV screen: fn(surf, quad) -- set by
# systems/home_system.py so the room's TV shows the channel being watched
TV_ART = None


def _tv_art(surf, quad):
    if TV_ART is None:
        return
    try:
        TV_ART(surf, quad)
    except Exception:
        from .systems import hooks as _hooks    # logged / strict like any hook
        _hooks._log_hook_error("_tv_world_art")
        if _hooks._STRICT:
            raise


# optional painter for LIVING pieces -- the aquarium's water box (real fish)
# and the growth stages of plant / cactus_small / vase_flowers:
# fn(surf, P, kind, where, base, color) -> True when it painted that part
# (False = stock art). ``where``: the tank's cells, or the piece's centre.
# Set by systems/homelife_system.py.
LIVE_ART = None


def _live_art(surf, P, kind, where, base, color):
    if LIVE_ART is None:
        return False
    try:
        return bool(LIVE_ART(surf, P, kind, where, base, color))
    except Exception:
        from .systems import hooks as _hooks    # logged / strict like any hook
        _hooks._log_hook_error("_life_art")
        if _hooks._STRICT:
            raise
        return False


def _item_tint(name):
    """Stable bright colour per item id (fridge shelf display)."""
    pal = ((226, 120, 120), (240, 196, 90), (150, 200, 120), (130, 170, 226),
           (200, 140, 210), (240, 160, 120), (170, 220, 220), (236, 222, 180))
    return pal[sum(map(ord, name)) % len(pal)]


def draw(surf, P, gx, gy, fw, fh, kind, color, rot=0, on=False, extra_ops=None,
         contents=None):
    """`extra_ops` lets callers slot extra drawables (e.g. a SEATED player)
    into this piece's own depth-sorted part list, so a sitter layers correctly
    between the backrest (behind) and the armrests/front edge (in front).
    `contents` (item ids) is what an OPEN fridge displays on its shelves."""
    # Author every piece in a canonical (un-rotated) frame [0..cw] x [0..ch] and
    # map it onto the real footprint through Pr(), rotating by rot*90 deg so the
    # piece visibly turns when the player rotates it in Build mode.
    rot = rot % 4
    cw, ch = (fw, fh) if rot % 2 == 0 else (fh, fw)
    _P0 = P                                    # the real projection (captured)

    def to_real(lx, ly):
        u = lx / cw if cw else 0.0
        v = ly / ch if ch else 0.0
        if rot == 0:
            return gx + u * fw, gy + v * fh
        if rot == 1:
            return gx + (1 - v) * fw, gy + u * fh
        if rot == 2:
            return gx + (1 - u) * fw, gy + (1 - v) * fh
        return gx + v * fw, gy + (1 - u) * fh

    def Pr(lx, ly):
        tx, ty = to_real(lx, ly)
        return _P0(tx, ty)

    P = Pr                                     # all drawing below goes through Pr
    x0, y0, x1, y1 = 0.0, 0.0, float(cw), float(ch)
    m = 0.08                                   # generic inset
    wood = (150, 110, 70)
    metal = (188, 192, 200)
    vx1 = rot in (0, 1)                        # canonical +x face visible?
    vy1 = rot in (0, 3)                        # canonical +y face visible?

    # ---- deferred, depth-sorted part list --------------------------------
    ops = []

    def _rrect(bx0, by0, bx1, by1, z0, z1):
        ax, ay = to_real(bx0, by0)
        bx, by = to_real(bx1, by1)
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), z0, z1)

    def box(bx0, by0, bx1, by1, h, col, base=0, decor=None):
        def fn():
            tp = _box(surf, P, bx0, by0, bx1, by1, h, col, base)
            if decor:
                decor(tp)
        ops.append((_rrect(bx0, by0, bx1, by1, base, base + h), fn))

    def op(bx0, by0, bx1, by1, z0, z1, fn):
        ops.append((_rrect(bx0, by0, bx1, by1, z0, z1), fn))

    # ---- pieces ----------------------------------------------------------
    if kind == "rug":                          # flat: draw immediately, no parts
        _diamond(surf, P, x0 + 0.04, y0 + 0.04, x1 - 0.04, y1 - 0.04, color,
                 border=_dk(color, 0.7))
        _diamond(surf, P, x0 + 0.22, y0 + 0.22, x1 - 0.22, y1 - 0.22, _lt(color, 1.2))
        return

    elif kind in ("coffee_table", "dining_table", "side_table"):
        toph = 5 if kind == "coffee_table" else 6
        legh = 17 if kind == "coffee_table" else 18
        for lx, ly in ((x0 + 0.10, y0 + 0.12), (x1 - 0.22, y0 + 0.12),
                       (x0 + 0.10, y1 - 0.24), (x1 - 0.22, y1 - 0.24)):
            box(lx, ly, lx + 0.12, ly + 0.12, legh, _dk(wood, 0.8))
        box(x0 + 0.05, y0 + 0.05, x1 - 0.05, y1 - 0.05, toph, color, base=legh)

    elif kind in ("chair", "stool"):           # slimmed: seat tucks under a table top
        legh = 11
        for lx, ly in ((x0 + 0.22, y0 + 0.22), (x1 - 0.32, y0 + 0.22),
                       (x0 + 0.22, y1 - 0.32), (x1 - 0.32, y1 - 0.32)):
            box(lx, ly, lx + 0.10, ly + 0.10, legh, _dk(color, 0.7))
        box(x0 + 0.20, y0 + 0.20, x1 - 0.20, y1 - 0.20, 4, color, base=legh)
        if kind == "chair":                    # backrest along the back edge
            box(x0 + 0.20, y0 + 0.20, x1 - 0.20, y0 + 0.30, 14, color, base=legh + 4)

    elif kind == "piano_bench":                # low backless seat, cushioned top
        legh = 11
        for lx, ly in ((x0 + 0.18, y0 + 0.18), (x1 - 0.30, y0 + 0.18),
                       (x0 + 0.18, y1 - 0.30), (x1 - 0.30, y1 - 0.30)):
            box(lx, ly, lx + 0.12, ly + 0.12, legh, _dk(wood, 0.8))
        box(x0 + 0.12, y0 + 0.20, x1 - 0.12, y1 - 0.20, 4, wood, base=legh)
        box(x0 + 0.16, y0 + 0.24, x1 - 0.16, y1 - 0.24, 3, color, base=legh + 4)

    elif kind == "bench":                      # backless padded bench
        seat_h = 14
        box(x0 + 0.10, y0 + 0.16, x1 - 0.10, y1 - 0.16, seat_h, _dk(color, 0.82))
        midx = (x0 + x1) / 2.0
        for ua, ub in ((x0 + 0.14, midx - 0.03), (midx + 0.03, x1 - 0.14)):
            box(ua, y0 + 0.18, ub, y1 - 0.18, 6, _lt(color, 1.1), base=seat_h)

    elif kind in ("sofa", "armchair"):
        seat_h = 12
        aw = 0.18                                                   # arm width
        ax0, ax1 = x0 + m + aw, x1 - m - aw                         # span between arms
        box(x0 + m, y0 + m, x0 + m + aw, y1 - m, seat_h + 9, _dk(color, 0.92))   # arms,
        box(x1 - m - aw, y0 + m, x1 - m, y1 - m, seat_h + 9, _dk(color, 0.92))   # full depth
        box(ax0, y0 + m, ax1, y0 + 0.32, seat_h + 18, color)        # backrest between arms
        box(ax0, y0 + 0.32, ax1, y1 - m, seat_h, color)             # seat base
        midx = (ax0 + ax1) / 2.0
        spans = (((ax0 + 0.04, midx - 0.02), (midx + 0.02, ax1 - 0.04))   # sofa: 2 seats
                 if (ax1 - ax0) >= 1.0 else ((ax0 + 0.04, ax1 - 0.04),))  # armchair: 1
        for ua, ub in spans:
            box(ua, y0 + 0.32, ub, y0 + 0.50, 11, _lt(color, 1.06), base=seat_h)  # back cushion
            box(ua, y0 + 0.50, ub, y1 - 0.14, 4, _lt(color, 1.12), base=seat_h)   # seat cushion

    elif kind == "bed":                        # head at one end, one pillow
        box(x0 + 0.04, y0 + 0.06, x0 + 0.16, y1 - 0.06, 26, _dk(color, 0.80))    # headboard
        box(x1 - 0.14, y0 + 0.06, x1 - 0.04, y1 - 0.06, 14, _dk(color, 0.82))    # footboard
        box(x0 + 0.16, y0 + 0.07, x1 - 0.14, y1 - 0.07, 10, wood)                # frame
        box(x0 + 0.16, y0 + 0.10, x1 - 0.14, y1 - 0.10, 5, (235, 232, 238), base=10)  # mattress
        box(x0 + 0.20, y0 + 0.20, x0 + 0.52, y1 - 0.20, 6, (248, 246, 250), base=15)  # pillow
        box(x0 + 0.56, y0 + 0.10, x1 - 0.14, y1 - 0.10, 5, color, base=15)            # blanket
        box(x0 + 0.56, y0 + 0.10, x0 + 0.68, y1 - 0.10, 2, _lt(color, 1.25), base=20)  # fold

    elif kind in ("dresser", "nightstand", "wardrobe", "fridge"):
        h = HEIGHT[kind]

        def _dec(tp):
            if not vx1:                                         # rotated away: plain back
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)           # the front face
            if kind == "wardrobe":                              # two tall doors
                for ua, ub in ((0.08, 0.49), (0.51, 0.92)):
                    quad = [fp(ua, 0.06), fp(ub, 0.06), fp(ub, 0.94), fp(ua, 0.94)]
                    pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                    pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                pygame.draw.line(surf, metal, fp(0.46, 0.42), fp(0.46, 0.62), 3)
                pygame.draw.line(surf, metal, fp(0.54, 0.42), fp(0.54, 0.62), 3)
            elif kind == "fridge":
                if on:                                          # door OPEN: lit interior,
                    quad = [fp(0.06, 0.06), fp(0.94, 0.06),     # shelves + the food inside
                            fp(0.94, 0.94), fp(0.06, 0.94)]
                    pygame.draw.polygon(surf, (228, 238, 242), quad)
                    pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                    for v in (0.36, 0.64):                      # shelf edges
                        pygame.draw.line(surf, (176, 190, 198), fp(0.10, v), fp(0.90, v), 2)
                    slots = [(u, v) for v in (0.32, 0.60, 0.88) for u in (0.24, 0.5, 0.76)]
                    for it, (u, v) in zip(contents or (), slots):
                        cc = _item_tint(it)
                        pd = fp(u, v)                           # little jars/bottles
                        pygame.draw.rect(surf, cc, (pd[0] - 2, pd[1] - 6, 5, 7),
                                         border_radius=1)
                        pygame.draw.line(surf, _dk(cc, 0.7), (pd[0] - 2, pd[1] - 6),
                                         (pd[0] + 2, pd[1] - 6), 1)
                else:                                           # fridge + freezer doors
                    for v0, v1 in ((0.06, 0.56), (0.60, 0.94)):
                        quad = [fp(0.08, v0), fp(0.92, v0), fp(0.92, v1), fp(0.08, v1)]
                        pygame.draw.polygon(surf, _lt(color, 1.04), quad)
                        pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                        pygame.draw.line(surf, metal, fp(0.8, v0 + 0.06), fp(0.8, v1 - 0.06), 3)
            else:                                               # dresser / nightstand drawers
                rows = (((0.10, 0.34), (0.40, 0.64), (0.70, 0.92)) if kind == "dresser"
                        else ((0.12, 0.46), (0.52, 0.90)))
                for v0, v1 in rows:
                    quad = [fp(0.08, v0), fp(0.92, v0), fp(0.92, v1), fp(0.08, v1)]
                    pygame.draw.polygon(surf, _lt(color, 1.06), quad)
                    pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                    vm = (v0 + v1) / 2
                    pygame.draw.line(surf, metal, fp(0.4, vm), fp(0.6, vm), 3)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)
        if kind == "fridge" and on and vx1:                     # the swung-open door
            box(x1 - 0.02, y0 + 0.06, x1 + 0.34, y0 + 0.16, h - 2, _lt(color, 1.05))

    elif kind == "stove":
        h = HEIGHT[kind]

        def _dec(tp):
            for fx, fy in ((0.32, 0.32), (0.68, 0.32), (0.32, 0.68), (0.68, 0.68)):
                c = _up(P(x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)), h)
                pygame.draw.ellipse(surf, (54, 54, 60), (c[0] - 6, c[1] - 4, 12, 8))
                pygame.draw.ellipse(surf, (84, 84, 92), (c[0] - 4, c[1] - 3, 8, 6), 1)
            if vx1:                                             # oven door + handle
                fp = _rface(P, x1 - m, y0 + m, y1 - m, h)
                quad = [fp(0.10, 0.30), fp(0.90, 0.30), fp(0.90, 0.92), fp(0.10, 0.92)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                win = [fp(0.22, 0.42), fp(0.78, 0.42), fp(0.78, 0.74), fp(0.22, 0.74)]
                pygame.draw.polygon(surf, (52, 50, 56), win)
                pygame.draw.line(surf, metal, fp(0.14, 0.20), fp(0.86, 0.20), 3)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)

    elif kind == "bookshelf":
        h = HEIGHT[kind]

        def _dec(tp):
            if not vx1:                                         # plain wooden back
                fp = _rface(P, x0 + m, y0 + m, y1 - m, h)
                quad = [fp(0.05, 0.05), fp(0.95, 0.05), fp(0.95, 0.95), fp(0.05, 0.95)]
                pygame.draw.polygon(surf, _dk(color, 0.82), quad)
                pygame.draw.polygon(surf, _dk(color, 0.55), quad, 1)
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)           # open shelf front
            pygame.draw.polygon(surf, _dk(color, 0.45),
                                [fp(0.06, 0.05), fp(0.94, 0.05), fp(0.94, 0.95), fp(0.06, 0.95)])
            books = [(208, 86, 84), (226, 150, 70), (228, 198, 92), (98, 186, 112),
                     (86, 134, 208), (150, 112, 202), (222, 142, 182), (110, 196, 196)]
            for r, (v0, v1) in enumerate(((0.10, 0.36), (0.40, 0.66), (0.70, 0.95))):
                du = 0.88 / 6
                for k in range(6):
                    u0 = 0.06 + k * du + 0.01
                    u1 = u0 + du * 0.82
                    vt = v0 + ((k * 7 + r * 3) % 4) * 0.012     # tiny height variation
                    bc = books[(k + r * 3) % len(books)]
                    quad = [fp(u0, vt), fp(u1, vt), fp(u1, v1), fp(u0, v1)]
                    pygame.draw.polygon(surf, bc, quad)
                    pygame.draw.polygon(surf, _dk(bc, 0.6), quad, 1)
                pygame.draw.line(surf, _dk(color, 0.55), fp(0.04, v1 + 0.01), fp(0.96, v1 + 0.01), 2)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)

    elif kind == "tv":
        box(x0 + 0.14, y0 + 0.30, x1 - 0.14, y1 - 0.30, 10, _dk(wood, 0.85))     # console

        def _dec(tp):
            if not vy1:                                          # seen from behind: plain
                return
            fp = _yface(P, y0 + 0.54, x0 + 0.13, x1 - 0.13, 26, base=10)
            quad = [fp(0.05, 0.10), fp(0.95, 0.10), fp(0.95, 0.82), fp(0.05, 0.82)]
            if on:                                               # glowing screen
                pygame.draw.polygon(surf, (88, 148, 198), quad)
                pygame.draw.line(surf, (170, 210, 240), fp(0.12, 0.22), fp(0.45, 0.22), 2)
                _tv_art(surf, quad)                              # the channel playing
                c = fp(0.88, 0.92)
                pygame.draw.circle(surf, (120, 220, 140), (int(c[0]), int(c[1])), 2)
            else:                                                # switched off
                pygame.draw.polygon(surf, (36, 38, 46), quad)
                pygame.draw.polygon(surf, (26, 28, 34), quad, 1)
                c = fp(0.88, 0.92)
                pygame.draw.circle(surf, (190, 70, 70), (int(c[0]), int(c[1])), 1)
        box(x0 + 0.10, y0 + 0.40, x1 - 0.10, y0 + 0.54, 26, (44, 46, 54),
            base=10, decor=_dec)                                  # panel on the console
        if on and not vy1:                      # screen hidden (rotated away):
            def _glow():                        # subtle top rim says "powered"
                tq = [_up(P(x0 + 0.10, y0 + 0.40), 36), _up(P(x1 - 0.10, y0 + 0.40), 36),
                      _up(P(x1 - 0.10, y0 + 0.54), 36), _up(P(x0 + 0.10, y0 + 0.54), 36)]
                pygame.draw.lines(surf, (150, 200, 240), True, tq, 2)
            op(x0 + 0.10, y0 + 0.40, x1 - 0.10, y0 + 0.54, 36, 37, _glow)

    elif kind == "plant":
        box(x0 + 0.32, y0 + 0.32, x1 - 0.32, y1 - 0.32, 12, (170, 116, 78))      # pot

        def _fol():
            c = _up(P((x0 + x1) / 2, (y0 + y1) / 2), 16)
            for dx, dy, r in ((0, -6, 11), (-7, 0, 8), (7, -1, 8), (0, 2, 9)):
                pygame.draw.circle(surf, (74, 160, 92), (int(c[0] + dx), int(c[1] + dy)), r)
            pygame.draw.circle(surf, (96, 188, 116), (int(c[0] - 3), int(c[1] - 8)), 5)
        op(x0 + 0.20, y0 + 0.20, x1 - 0.20, y1 - 0.20, 12, 34,
           lambda: _live_art(surf, _P0, kind, (gx + fw / 2.0, gy + fh / 2.0), 12, color)
           or _fol())

    elif kind == "lamp":
        box(x0 + 0.40, y0 + 0.40, x1 - 0.40, y1 - 0.40, 3, (76, 78, 86))         # base

        def _lp():
            b = _up(P((x0 + x1) / 2, (y0 + y1) / 2), 2)
            top = _up(b, 42)
            pygame.draw.line(surf, (110, 110, 118), b, top, 3)                   # pole
            pygame.draw.polygon(surf, color, [(top[0] - 12, top[1]), (top[0] + 12, top[1]),
                                              (top[0] + 7, top[1] - 16), (top[0] - 7, top[1] - 16)])
            if on:                                               # warm glow
                pygame.draw.circle(surf, (255, 222, 150), (int(top[0]), int(top[1] + 5)), 9)
                pygame.draw.circle(surf, (255, 244, 200), (int(top[0]), int(top[1] + 4)), 5)
            else:                                                # bulb off
                pygame.draw.circle(surf, (186, 184, 176), (int(top[0]), int(top[1] + 4)), 4)
        op(x0 + 0.30, y0 + 0.30, x1 - 0.30, y1 - 0.30, 3, 60, _lp)

    elif kind == "chest":
        box(x0 + 0.12, y0 + 0.12, x1 - 0.12, y1 - 0.12, 14, (150, 108, 64))

        def _dec(tp):
            if not vx1:
                return
            c = _up(P(x1 - 0.10, (y0 + y1) / 2), 16)             # latch on the front face
            pygame.draw.rect(surf, (214, 196, 110), (c[0] - 3, c[1] - 3, 6, 7), border_radius=1)
        box(x0 + 0.10, y0 + 0.10, x1 - 0.10, y1 - 0.10, 6, (172, 126, 78), base=14, decor=_dec)

    elif kind == "fireplace":
        h = HEIGHT[kind]

        def _dec(tp):
            if not vy1:                                          # back of the chimney
                return
            fp = _yface(P, y1 - m, x0 + m, x1 - m, h)
            quad = [fp(0.26, 0.34), fp(0.74, 0.34), fp(0.74, 0.97), fp(0.26, 0.97)]
            pygame.draw.polygon(surf, (40, 36, 40), quad)        # firebox opening
            pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
            for u in (0.42, 0.58):                               # logs
                c = fp(u, 0.93)
                pygame.draw.circle(surf, (110, 78, 52), (int(c[0]), int(c[1])), 3)
            if on:                                               # crackling fire
                c = fp(0.5, 0.95)
                pygame.draw.polygon(surf, (240, 150, 50),
                                    [(c[0], c[1] - 2), (c[0] - 7, c[1] - 15), (c[0] + 7, c[1] - 15)])
                pygame.draw.polygon(surf, (250, 214, 96),
                                    [(c[0], c[1] - 4), (c[0] - 3, c[1] - 11), (c[0] + 3, c[1] - 11)])
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)
        box(x0 + 0.02, y0 + 0.02, x1 - 0.02, y1 - 0.02, 4, _dk(color, 0.9), base=h)  # mantel

    elif kind == "bin_decor":                  # little bin with a rim
        box(x0 + 0.34, y0 + 0.34, x1 - 0.34, y1 - 0.34, 16, color)
        box(x0 + 0.31, y0 + 0.31, x1 - 0.31, y1 - 0.31, 3, _dk(color, 0.82), base=16)

    elif kind == "vanity":
        h = HEIGHT[kind]

        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)            # two drawers + knobs
            for v0, v1 in ((0.14, 0.50), (0.56, 0.90)):
                quad = [fp(0.10, v0), fp(0.90, v0), fp(0.90, v1), fp(0.10, v1)]
                pygame.draw.polygon(surf, _lt(color, 1.06), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                c = fp(0.5, (v0 + v1) / 2)
                pygame.draw.circle(surf, metal, (int(c[0]), int(c[1])), 2)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)

        def _mir():
            mc = _up(P((x0 + x1) / 2, y0 + 0.30), h)             # standing oval mirror
            pygame.draw.line(surf, _dk(color, 0.6), (mc[0], mc[1] + 2), (mc[0], mc[1] - 7), 3)
            pygame.draw.ellipse(surf, _dk(color, 0.7), (mc[0] - 12, mc[1] - 32, 24, 30))
            pygame.draw.ellipse(surf, (212, 234, 244), (mc[0] - 9, mc[1] - 29, 18, 24))
            pygame.draw.line(surf, (246, 250, 252), (mc[0] - 4, mc[1] - 24), (mc[0] + 3, mc[1] - 13), 2)
        op(x0 + 0.30, y0 + 0.16, x1 - 0.30, y0 + 0.44, h, h + 38, _mir)

    elif kind == "counter":
        h = HEIGHT[kind]

        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)            # two cupboard doors
            for ua, ub in ((0.08, 0.49), (0.51, 0.92)):
                quad = [fp(ua, 0.18), fp(ub, 0.18), fp(ub, 0.92), fp(ua, 0.92)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
            pygame.draw.line(surf, metal, fp(0.42, 0.30), fp(0.42, 0.44), 3)
            pygame.draw.line(surf, metal, fp(0.58, 0.30), fp(0.58, 0.44), 3)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)
        box(x0 + 0.04, y0 + 0.04, x1 - 0.04, y1 - 0.04, 3, (226, 224, 216), base=h)  # stone top

    elif kind == "workbench":
        h = HEIGHT[kind]

        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)            # tool drawer
            quad = [fp(0.12, 0.20), fp(0.88, 0.20), fp(0.88, 0.55), fp(0.12, 0.55)]
            pygame.draw.polygon(surf, _lt(wood, 1.08), quad)
            pygame.draw.polygon(surf, _dk(wood, 0.5), quad, 2)
            pygame.draw.line(surf, metal, fp(0.40, 0.37), fp(0.60, 0.37), 3)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, wood, decor=_dec)
        box(x0 + 0.04, y0 + 0.04, x1 - 0.04, y1 - 0.04, 3, _lt(wood, 1.12), base=h)   # worktop
        box(x1 - 0.50, y0 + 0.28, x1 - 0.30, y0 + 0.52, 6, metal, base=h + 3)         # vice

    elif kind == "piano":                      # upright piano
        box(x0 + 0.06, y0 + 0.08, x1 - 0.06, y0 + 0.52, 42, color)               # tall body
        for lx in (x0 + 0.14, x1 - 0.22):                                        # front legs
            box(lx, y0 + 0.76, lx + 0.08, y0 + 0.84, 22, _dk(color, 0.85))

        def _keys(tp):
            _diamond(surf, P, x0 + 0.12, y0 + 0.54, x1 - 0.12, y0 + 0.84,
                     (244, 242, 236), h=28, border=_dk(color, 0.6))               # white keys
            n = 12
            step = (x1 - x0 - 0.28) / n
            for k in range(n):                                                    # black keys
                if k % 4 == 0:
                    continue
                xk = x0 + 0.14 + k * step
                quad = [_up(P(xk, y0 + 0.56), 28), _up(P(xk + step * 0.5, y0 + 0.56), 28),
                        _up(P(xk + step * 0.5, y0 + 0.68), 28), _up(P(xk, y0 + 0.68), 28)]
                pygame.draw.polygon(surf, (36, 34, 40), quad)
            if vy1:                                                               # sheet music
                fp = _yface(P, y0 + 0.52, x0 + 0.06, x1 - 0.06, 42)
                quad = [fp(0.40, 0.12), fp(0.60, 0.12), fp(0.60, 0.30), fp(0.40, 0.30)]
                pygame.draw.polygon(surf, (246, 244, 238), quad)
                pygame.draw.line(surf, (120, 120, 130), fp(0.43, 0.17), fp(0.57, 0.17), 1)
                pygame.draw.line(surf, (120, 120, 130), fp(0.43, 0.22), fp(0.57, 0.22), 1)
        box(x0 + 0.10, y0 + 0.52, x1 - 0.10, y0 + 0.86, 6, color, base=22, decor=_keys)

    elif kind == "aquarium":
        box(x0 + 0.10, y0 + 0.10, x1 - 0.10, y1 - 0.10, 14, _dk(wood, 0.9))      # stand

        def _aq(tp):
            if vx1:
                fp = _rface(P, x1 - 0.12, y0 + 0.12, y1 - 0.12, 20, base=14)
            elif vy1:
                fp = _yface(P, y1 - 0.12, x0 + 0.12, x1 - 0.12, 20, base=14)
            else:
                fp = _rface(P, x0 + 0.12, y0 + 0.12, y1 - 0.12, 20, base=14)
            quad = [fp(0.04, 0.78), fp(0.96, 0.78), fp(0.96, 0.96), fp(0.04, 0.96)]
            pygame.draw.polygon(surf, (150, 132, 96), quad)                       # gravel
            pygame.draw.line(surf, (208, 234, 244), fp(0.04, 0.10), fp(0.96, 0.10), 2)  # waterline
            pygame.draw.line(surf, (96, 170, 110), fp(0.84, 0.78), fp(0.80, 0.30), 2)   # weed
            for u, v, r, fc in ((0.32, 0.42, 4, (236, 140, 64)), (0.60, 0.58, 3, (244, 196, 90))):
                c = fp(u, v)
                t = fp(u - 0.08, v)
                pygame.draw.polygon(surf, fc, [(c[0] - r + 1, c[1]),
                                               (t[0], t[1] - 3), (t[0], t[1] + 3)])
                pygame.draw.circle(surf, fc, (int(c[0]), int(c[1])), r)
            for u, v in ((0.45, 0.30), (0.49, 0.20)):                             # bubbles
                c = fp(u, v)
                pygame.draw.circle(surf, (220, 240, 248), (int(c[0]), int(c[1])), 1)
        def _tank():                                                          # water tank
            cells = frozenset((int(round(gx)) + i, int(round(gy)) + j)
                              for i in range(fw) for j in range(fh))
            if not _live_art(surf, _P0, kind, cells, 14, color):
                _aq(_box(surf, P, x0 + 0.12, y0 + 0.12, x1 - 0.12, y1 - 0.12, 20,
                         (118, 178, 206), base=14))
        op(x0 + 0.12, y0 + 0.12, x1 - 0.12, y1 - 0.12, 14, 34, _tank)
        box(x0 + 0.10, y0 + 0.10, x1 - 0.10, y1 - 0.10, 3, (60, 62, 70), base=34)  # lid

    elif kind == "record_player":
        def _dec(tp):
            c = _up(P((x0 + x1) / 2, (y0 + y1) / 2), 20)
            pygame.draw.ellipse(surf, (30, 30, 34), (c[0] - 13, c[1] - 7, 26, 14))   # vinyl
            pygame.draw.ellipse(surf, (70, 70, 76), (c[0] - 13, c[1] - 7, 26, 14), 1)
            pygame.draw.ellipse(surf, (200, 84, 84), (c[0] - 4, c[1] - 2, 8, 4))     # label
            if on:                                  # a glint sweeping round = spinning
                ang = (pygame.time.get_ticks() / 260.0) % math.tau
                for k, col in ((0.0, (150, 150, 160)), (0.35, (96, 96, 106))):
                    ex = c[0] + math.cos(ang - k) * 11
                    ey = c[1] + math.sin(ang - k) * 5.5
                    mx = c[0] + math.cos(ang - k) * 5
                    my = c[1] + math.sin(ang - k) * 2.5
                    pygame.draw.line(surf, col, (mx, my), (ex, ey), 1)
            a = _up(P(x1 - 0.24, y0 + 0.26), 21)                                     # tonearm
            tip = (c[0] + 8, c[1] - 3) if on else (a[0] + 2, a[1] + 9)           # on the record
            pygame.draw.line(surf, metal, a, tip, 2)                             # / at rest
            pygame.draw.circle(surf, (120, 124, 132), (int(a[0]), int(a[1])), 2)
            if vx1:
                k = _up(P(x1 - 0.14, y1 - 0.30), 10)                                 # knob
                pygame.draw.circle(surf, metal, (int(k[0]), int(k[1])), 2)
            if on:                                               # spinning: power light
                pygame.draw.ellipse(surf, (96, 96, 104), (c[0] - 13, c[1] - 7, 26, 14), 1)
                g_ = _up(P(x0 + 0.20, y1 - 0.26), 21)
                pygame.draw.circle(surf, (120, 230, 140), (int(g_[0]), int(g_[1])), 2)
        box(x0 + 0.14, y0 + 0.14, x1 - 0.14, y1 - 0.14, 20, wood, decor=_dec)

    elif kind == "crib":
        rail = _lt(wood, 1.08)
        box(x0 + 0.10, y0 + 0.10, x1 - 0.10, y1 - 0.10, 8, wood)                  # base
        box(x0 + 0.14, y0 + 0.14, x1 - 0.14, y1 - 0.14, 4, (240, 238, 244), base=8)   # mattress
        box(x0 + 0.18, y0 + 0.20, x0 + 0.44, y1 - 0.20, 3, (250, 250, 252), base=12)  # pillow
        box(x0 + 0.48, y0 + 0.16, x1 - 0.16, y1 - 0.16, 3, color, base=12)            # blanket
        for px_, py_ in ((x0 + 0.06, y0 + 0.06), (x1 - 0.16, y0 + 0.06),
                         (x0 + 0.06, y1 - 0.16), (x1 - 0.16, y1 - 0.16)):
            box(px_, py_, px_ + 0.10, py_ + 0.10, 24, _dk(wood, 0.85))            # corner posts
        box(x0 + 0.16, y0 + 0.06, x1 - 0.16, y0 + 0.14, 14, rail, base=8)         # rails
        box(x0 + 0.16, y1 - 0.14, x1 - 0.16, y1 - 0.06, 14, rail, base=8)
        box(x0 + 0.06, y0 + 0.16, x0 + 0.14, y1 - 0.16, 14, rail, base=8)
        box(x1 - 0.14, y0 + 0.16, x1 - 0.06, y1 - 0.16, 14, rail, base=8)

    elif kind == "toy_chest":
        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - 0.14, y0 + 0.16, y1 - 0.16, 13)
            for ua, ub, bc in ((0.16, 0.42, (224, 120, 110)), (0.56, 0.82, (110, 160, 220))):
                quad = [fp(ua, 0.28), fp(ub, 0.28), fp(ub, 0.78), fp(ua, 0.78)]
                pygame.draw.polygon(surf, bc, quad)                               # toy blocks
                pygame.draw.polygon(surf, _dk(bc, 0.6), quad, 1)
        box(x0 + 0.14, y0 + 0.16, x1 - 0.14, y1 - 0.16, 13, color, decor=_dec)
        box(x0 + 0.12, y0 + 0.14, x1 - 0.12, y1 - 0.14, 5, _lt(color, 1.15), base=13)  # lid

    elif kind == "sink":
        h = HEIGHT[kind]

        def _dec(tp):
            _diamond(surf, P, x0 + 0.24, y0 + 0.24, x1 - 0.24, y1 - 0.24,
                     (214, 226, 232), h=h, border=_dk(color, 0.6))                # basin rim
            _diamond(surf, P, x0 + 0.32, y0 + 0.32, x1 - 0.32, y1 - 0.32, (176, 196, 206), h=h)
            if vx1:                                                               # cupboard door
                fp = _rface(P, x1 - m, y0 + m, y1 - m, h)
                quad = [fp(0.12, 0.22), fp(0.88, 0.22), fp(0.88, 0.90), fp(0.12, 0.90)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                pygame.draw.line(surf, metal, fp(0.44, 0.32), fp(0.56, 0.32), 3)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)

        def _fau(tp):
            a = _up(P(x0 + 0.19, (y0 + y1) / 2), h + 8)                           # spout
            b = _up(P(x0 + 0.36, (y0 + y1) / 2), h + 6)
            pygame.draw.line(surf, metal, a, b, 3)
        box(x0 + 0.14, (y0 + y1) / 2 - 0.05, x0 + 0.24, (y0 + y1) / 2 + 0.05,
            8, metal, base=h, decor=_fau)                                         # faucet post

    elif kind == "microwave":
        for lx, ly in ((x0 + 0.16, y0 + 0.16), (x1 - 0.24, y0 + 0.16),
                       (x0 + 0.16, y1 - 0.24), (x1 - 0.24, y1 - 0.24)):
            box(lx, ly, lx + 0.08, ly + 0.08, 20, _dk(wood, 0.8))                 # stand legs
        box(x0 + 0.10, y0 + 0.10, x1 - 0.10, y1 - 0.10, 4, _dk(wood, 0.9), base=20)  # shelf

        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - 0.16, y0 + 0.20, y1 - 0.20, 16, base=24)
            win = [fp(0.10, 0.16), fp(0.62, 0.16), fp(0.62, 0.84), fp(0.10, 0.84)]
            if on:                                               # lit interior + dish
                pygame.draw.polygon(surf, (255, 214, 130), win)
                d = fp(0.36, 0.62)
                pygame.draw.ellipse(surf, (214, 120, 80), (d[0] - 4, d[1] - 2, 8, 4))
            else:
                pygame.draw.polygon(surf, (56, 58, 66), win)                      # door window
            pygame.draw.polygon(surf, _dk(color, 0.5), win, 1)
            pygame.draw.line(surf, metal, fp(0.72, 0.20), fp(0.72, 0.80), 2)      # handle
            for v in (0.30, 0.45):                                                # buttons
                c = fp(0.85, v)
                pygame.draw.circle(surf, (90, 92, 100), (int(c[0]), int(c[1])), 1)
        box(x0 + 0.16, y0 + 0.20, x1 - 0.16, y1 - 0.20, 16, color, base=24, decor=_dec)

    elif kind == "kitchen_island":
        h = 24

        def _dec(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - m, y0 + m, y1 - m, h)                             # two doors
            for ua, ub in ((0.10, 0.48), (0.52, 0.90)):
                quad = [fp(ua, 0.20), fp(ub, 0.20), fp(ub, 0.90), fp(ua, 0.90)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)
        box(x0 + 0.03, y0 + 0.03, x1 - 0.03, y1 - 0.03, 3, (226, 222, 214), base=h)   # stone top
        box(x0 + 0.30, y0 + 0.25, x0 + 0.80, y1 - 0.30, 2, (202, 162, 110), base=h + 3)  # board

        def _bowl():
            c = _up(P(x1 - 0.55, (y0 + y1) / 2), h + 4)
            pygame.draw.ellipse(surf, (208, 92, 80), (c[0] - 7, c[1] - 4, 14, 8))
            pygame.draw.ellipse(surf, (170, 60, 54), (c[0] - 5, c[1] - 3, 10, 5))
        op(x1 - 0.70, (y0 + y1) / 2 - 0.15, x1 - 0.40, (y0 + y1) / 2 + 0.15,
           h + 3, h + 11, _bowl)

    elif kind == "easel":
        def _fn():
            apex = _up(P((x0 + x1) / 2, y0 + 0.40 * (y1 - y0)), 44)
            f1 = P(x0 + 0.22, y1 - 0.26)
            f2 = P(x1 - 0.22, y1 - 0.26)
            bk = P((x0 + x1) / 2, y0 + 0.14)
            for ft in (f1, f2, bk):                                               # tripod legs
                pygame.draw.line(surf, _dk(wood, 0.75), ft, apex, 3)
            ca, cb = _mid(f1, apex, 0.26), _mid(f2, apex, 0.26)                   # canvas
            ct, cu = _mid(f1, apex, 0.80), _mid(f2, apex, 0.80)
            quad = [ca, cb, cu, ct]
            pygame.draw.polygon(surf, (246, 244, 238) if vy1 else (214, 204, 188), quad)
            pygame.draw.polygon(surf, _dk(wood, 0.7), quad, 2)
            if vy1:                                                               # paint daubs
                for t, cc in ((0.36, (208, 96, 90)), (0.52, (96, 150, 210)), (0.66, (228, 196, 92))):
                    c = _mid(_mid(ca, cb, t), _mid(ct, cu, t + 0.05), 0.5)
                    pygame.draw.circle(surf, cc, (int(c[0]), int(c[1])), 3)
        op(x0 + 0.12, y0 + 0.10, x1 - 0.12, y1 - 0.12, 0, 48, _fn)

    elif kind == "globe":
        def _fn():
            c0 = P((x0 + x1) / 2, (y0 + y1) / 2)
            pygame.draw.ellipse(surf, _dk(wood, 0.8), (c0[0] - 9, c0[1] - 5, 18, 10))  # base
            s = _up(c0, 24)
            pygame.draw.line(surf, _dk(wood, 0.7), c0, (s[0], s[1] + 8), 3)            # stem
            pygame.draw.circle(surf, (86, 140, 200), (int(s[0]), int(s[1])), 11)       # ocean
            for dx, dy, r in ((-4, -4, 4), (5, 1, 3), (-1, 6, 3)):                     # land
                pygame.draw.circle(surf, (110, 176, 120), (int(s[0] + dx), int(s[1] + dy)), r)
            pygame.draw.arc(surf, (190, 160, 90), (s[0] - 13, s[1] - 13, 26, 26),
                            -0.9, 1.8, 2)                                              # brass arc
            pygame.draw.circle(surf, (190, 160, 90), (int(s[0]), int(s[1] - 12)), 2)   # axis cap
        op(x0 + 0.25, y0 + 0.25, x1 - 0.25, y1 - 0.25, 0, 38, _fn)

    elif kind == "cat_tower":
        box(x0 + 0.12, y0 + 0.12, x1 - 0.12, y1 - 0.12, 4, _dk(color, 0.8))       # base

        def _hole(tp):
            if not vx1:
                return
            fp = _rface(P, x1 - 0.22, y0 + 0.22, y1 - 0.22, 16, base=4)
            c = fp(0.5, 0.55)
            pygame.draw.circle(surf, (40, 36, 40), (int(c[0]), int(c[1])), 5)     # den door
        box(x0 + 0.22, y0 + 0.22, x1 - 0.22, y1 - 0.22, 16, color, base=4, decor=_hole)
        box(x0 + 0.42, y0 + 0.42, x1 - 0.42, y1 - 0.42, 16, (212, 196, 168), base=20)  # post

        def _ball(tp):
            c = _up(P((x0 + x1) / 2, (y0 + y1) / 2), 42)
            pygame.draw.circle(surf, (230, 122, 122), (int(c[0]), int(c[1])), 3)  # toy ball
        box(x0 + 0.26, y0 + 0.26, x1 - 0.26, y1 - 0.26, 4, color, base=36, decor=_ball)

    elif kind == "standing_fan":
        box(x0 + 0.34, y0 + 0.34, x1 - 0.34, y1 - 0.34, 4, (90, 94, 102))         # base

        def _fn():
            b = _up(P((x0 + x1) / 2, (y0 + y1) / 2), 4)
            top = _up(b, 26)
            pygame.draw.line(surf, metal, b, top, 3)                              # pole
            hc = _up(top, 9)
            pygame.draw.circle(surf, (208, 212, 218), (int(hc[0]), int(hc[1])), 10)    # head
            if on:                                               # blades spin to a blur
                pygame.draw.circle(surf, (188, 206, 218), (int(hc[0]), int(hc[1])), 8)
                pygame.draw.circle(surf, (210, 224, 232), (int(hc[0]), int(hc[1])), 5)
            else:
                for ang in (90, 210, 330):                                        # 3 blades
                    ar = math.radians(ang)
                    tip = (hc[0] + math.cos(ar) * 8, hc[1] - math.sin(ar) * 6)
                    e1 = math.radians(ang + 24)
                    e2 = math.radians(ang - 24)
                    pygame.draw.polygon(surf, (164, 190, 206),
                                        [(int(hc[0]), int(hc[1])),
                                         (int(hc[0] + math.cos(e1) * 8), int(hc[1] - math.sin(e1) * 6)),
                                         (int(tip[0]), int(tip[1])),
                                         (int(hc[0] + math.cos(e2) * 8), int(hc[1] - math.sin(e2) * 6))])
            pygame.draw.circle(surf, (120, 124, 132), (int(hc[0]), int(hc[1])), 11, 2)  # cage
            pygame.draw.circle(surf, (70, 72, 80), (int(hc[0]), int(hc[1])), 2)         # hub
        op(x0 + 0.28, y0 + 0.28, x1 - 0.28, y1 - 0.28, 4, 52, _fn)

    else:                                      # generic cabinet / fallback
        h = HEIGHT.get(kind, 22)

        def _dec(tp):
            if not vx1:
                return
            for i in range(2):
                p = _up(_mid(P(x1 - m, y0 + 0.3), P(x1 - m, y1 - 0.3), 0.5), h - 8 - i * 9)
                pygame.draw.circle(surf, metal, (int(p[0]), int(p[1])), 2)
        box(x0 + m, y0 + m, x1 - m, y1 - m, h, color, decor=_dec)

    # ---- depth-sorted flush ----------------------------------------------
    flushed = sorted(ops, key=functools.cmp_to_key(_op_cmp))
    if extra_ops:
        # INSERT each extra op (seated player body / far-side legs) into the
        # already-sorted part list at the first part that should paint over it.
        # Never mix them into one global sort: a sitter's box can form a CYCLE
        # with the comparator (cushion < sitter < chair-leg < cushion) and
        # sorted() would then order arbitrarily.
        for ex in sorted(extra_ops, key=lambda e: e[0][4]):
            idx = len(flushed)
            for i, part in enumerate(flushed):
                if _op_cmp(part, ex) > 0:
                    idx = i
                    break
            flushed.insert(idx, ex)
    for _, fn in flushed:
        fn()


# ---------------------------------------------------------------- tabletop decor
# Small items (furniture layer "top") that sit ON a flat-topped piece. They are
# drawn at the support's top height, centred on a quarter-cell slot point.

TOPH = {"dining_table": 24, "coffee_table": 22, "counter": 27, "kitchen_island": 27,
        "dresser": 26, "nightstand": 22, "vanity": 24,
        "piano": 42, "aquarium": 37, "fireplace": 30, "bookshelf": 42, "wardrobe": 46}


def surface_height(kind):
    """Top height (px) of a piece tabletop decor can sit on (0 = no surface)."""
    return TOPH.get(kind, 0)


def draw_top(surf, P, x, y, kind, color, base, on=False, rot=0):
    """Draw one tabletop item centred on tile point (x, y), `base` px up.
    `rot` (0-3 quarter turns) turns items that have a front (frames, lamps,
    mirrors, mugs...): 0 faces +y (camera-left), 1 +x... like furniture."""
    if kind in ("cactus_small", "vase_flowers") and _live_art(surf, P, kind, (x, y), base,
                                                              color):
        return                                 # a growing plant (Placed.data)
    c = _up(P(x, y), base)
    cx, cy = int(c[0]), int(c[1])
    wood = (150, 110, 70)

    if kind == "paper_stack":                  # small messy stack of sheets
        for i, (jx, jy) in enumerate(((0.03, 0.02), (-0.02, 0.01), (0.01, -0.01))):
            _diamond(surf, P, x - 0.16 + jx, y - 0.12 + jy, x + 0.16 + jx, y + 0.12 + jy,
                     (246, 244, 238) if i == 2 else (228, 226, 218),
                     h=base + i, border=(186, 182, 172))
        for i in range(2):                     # a line or two of writing
            pygame.draw.line(surf, (150, 150, 160),
                             (cx - 5, cy - 2 - i * 2 - 2), (cx + 4, cy - 4 - i * 2), 1)

    elif kind == "pen_holder":                 # cup with two pens
        _box(surf, P, x - 0.07, y - 0.07, x + 0.07, y + 0.07, 7, color, base=base)
        pygame.draw.line(surf, (60, 70, 160), (cx - 1, cy - 6), (cx - 4, cy - 14), 2)
        pygame.draw.line(surf, (170, 60, 60), (cx + 2, cy - 6), (cx + 4, cy - 13), 2)

    elif kind == "desk_mirror":                # little vanity mirror on a foot
        _box(surf, P, x - 0.10, y - 0.06, x + 0.10, y + 0.06, 2, wood, base=base)
        pygame.draw.line(surf, _dk(color, 0.7), (cx, cy - 2), (cx, cy - 7), 2)
        pygame.draw.ellipse(surf, color, (cx - 6, cy - 22, 12, 16))
        pygame.draw.ellipse(surf, (205, 225, 235), (cx - 4, cy - 20, 8, 12))
        pygame.draw.line(surf, (238, 248, 252), (cx - 2, cy - 11), (cx + 2, cy - 17), 1)

    elif kind == "photo_frame":                # standing frame with a sunny photo
        _box(surf, P, x - 0.09, y - 0.05, x + 0.09, y + 0.05, 2, wood, base=base)
        fr = pygame.Rect(cx - 6, cy - 16, 12, 11)
        pygame.draw.rect(surf, wood, fr)
        pygame.draw.rect(surf, (150, 200, 230), fr.inflate(-4, -4))
        pygame.draw.circle(surf, (250, 220, 120), (fr.right - 4, fr.y + 4), 2)
        pygame.draw.rect(surf, _dk(wood, 0.7), fr, 1)

    elif kind == "candle_small":               # candle (lit only when switched on)
        _box(surf, P, x - 0.06, y - 0.06, x + 0.06, y + 0.06, 6, (240, 236, 224),
             base=base)
        pygame.draw.line(surf, (140, 130, 110), (cx, cy - 6), (cx, cy - 8), 1)
        if on:
            pygame.draw.circle(surf, (255, 210, 120), (cx, cy - 10), 3)
            pygame.draw.circle(surf, (255, 245, 200), (cx, cy - 10), 1)

    elif kind == "book_stack":                 # three stacked books
        for i, bc in enumerate(((200, 90, 80), (90, 140, 200), (220, 190, 100))):
            inset = 0.13 - i * 0.015
            _box(surf, P, x - inset, y - 0.10, x + inset, y + 0.10, 3, bc,
                 base=base + i * 3)

    elif kind == "vase_flowers":               # little vase with three blooms
        _box(surf, P, x - 0.07, y - 0.07, x + 0.07, y + 0.07, 8, color, base=base)
        for dx, dy, fc in ((-4, -3, (236, 120, 130)), (4, -2, (250, 210, 110)),
                           (0, -6, (190, 130, 220))):
            pygame.draw.line(surf, (96, 160, 96), (cx, cy - 8),
                             (cx + dx, cy - 14 + dy), 1)
            pygame.draw.circle(surf, fc, (cx + dx, cy - 15 + dy), 3)
            pygame.draw.circle(surf, (255, 244, 200), (cx + dx, cy - 15 + dy), 1)

    elif kind == "fruit_bowl":                 # bowl of fruit
        pygame.draw.ellipse(surf, _dk(color, 0.8), (cx - 8, cy - 4, 16, 8))
        pygame.draw.ellipse(surf, color, (cx - 7, cy - 5, 14, 6))
        for dx, fc in ((-4, (220, 80, 70)), (0, (240, 180, 70)), (4, (130, 190, 90))):
            pygame.draw.circle(surf, fc, (cx + dx, cy - 6), 3)

    elif kind == "coffee_mug":                 # steaming mug
        _box(surf, P, x - 0.05, y - 0.05, x + 0.05, y + 0.05, 6, color, base=base)
        pygame.draw.arc(surf, _dk(color, 0.7), (cx + 2, cy - 5, 6, 6), -1.4, 1.4, 2)
        for i in (0, 1):                       # steam wisps
            pygame.draw.arc(surf, (228, 232, 238),
                            (cx - 3 + i * 3, cy - 14 - i * 3, 4, 6), 0.4, 2.6, 1)

    elif kind == "desk_lamp":                  # small lamp with a warm glow
        _box(surf, P, x - 0.08, y - 0.06, x + 0.08, y + 0.06, 2, (90, 94, 102),
             base=base)
        pygame.draw.line(surf, (120, 124, 132), (cx, cy - 2), (cx + 3, cy - 12), 2)
        pygame.draw.polygon(surf, color, [(cx - 2, cy - 12), (cx + 8, cy - 12),
                                          (cx + 6, cy - 18), (cx, cy - 18)])
        if on:
            pygame.draw.circle(surf, (255, 222, 150), (cx + 3, cy - 10), 5)
            pygame.draw.circle(surf, (255, 238, 170), (cx + 3, cy - 10), 3)

    elif kind == "cactus_small":               # potted mini cactus
        _box(surf, P, x - 0.06, y - 0.06, x + 0.06, y + 0.06, 5, (190, 120, 80),
             base=base)
        pygame.draw.rect(surf, (96, 168, 96), (cx - 2, cy - 14, 5, 10),
                         border_radius=2)
        pygame.draw.rect(surf, (96, 168, 96), (cx - 6, cy - 11, 4, 3), border_radius=2)
        pygame.draw.circle(surf, (236, 150, 170), (cx, cy - 15), 2)   # tiny flower

    elif kind == "music_sheet":                # sheet of music (great on the piano)
        _diamond(surf, P, x - 0.15, y - 0.11, x + 0.15, y + 0.11,
                 (248, 246, 240), h=base, border=(190, 186, 176))
        for i in range(3):                     # staff lines
            pygame.draw.line(surf, (150, 150, 160),
                             (cx - 6, cy - 1 - i * 2), (cx + 6, cy - 3 - i * 2), 1)
        pygame.draw.circle(surf, (60, 60, 70), (cx - 2, cy - 3), 1)   # notes
        pygame.draw.circle(surf, (60, 60, 70), (cx + 3, cy - 5), 1)

    else:                                      # unknown tabletop kind: tiny box
        _box(surf, P, x - 0.10, y - 0.10, x + 0.10, y + 0.10, 5, color, base=base)


# ---------------------------------------------------------------- merged groups
#
# Mergeable furniture (furniture.MERGE) placed side by side in the same colour
# renders as ONE continuous piece (Sims counters / Minecraft double chests),
# L/T shapes included: the group's cells are traced into a rectilinear outline
# and extruded as a single prism, so no seams appear between the pieces.

def _outline(cells):
    """Trace the boundary of a set of unit cells into ordered loops.
    Each loop is a list of integer (x, y) corners walked with the interior on
    the RIGHT, so the inward normal of an edge (dx, dy) is (-dy, dx)."""
    edges = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for (x, y) in cells:
        if (x, y - 1) not in cells:
            add((x, y), (x + 1, y))
        if (x + 1, y) not in cells:
            add((x + 1, y), (x + 1, y + 1))
        if (x, y + 1) not in cells:
            add((x + 1, y + 1), (x, y + 1))
        if (x - 1, y) not in cells:
            add((x, y + 1), (x, y))
    loops = []
    while edges:
        start = next(iter(edges))
        cur, prev = start, None
        loop = []
        while True:
            outs = edges.get(cur)
            if not outs:
                break
            if len(outs) == 1 or prev is None:
                nxt = outs.pop(0)
            else:
                # pinch vertex (cells meeting only diagonally): take the
                # tightest right turn so each loop stays a simple polygon
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                outs.sort(key=lambda p: (p[0] - cur[0]) * dy - (p[1] - cur[1]) * dx)
                nxt = outs.pop(0)
            if not outs:
                del edges[cur]
            loop.append(cur)
            prev, cur = cur, nxt
            if cur == start:
                break
        n = len(loop)
        if n >= 4:
            # drop collinear midpoints, keep true corners only
            loops.append([p for i, p in enumerate(loop)
                          if (loop[i - 1][0] == p[0]) != (p[0] == loop[(i + 1) % n][0])])
    return loops


def _shrink(loop, d):
    """Inset a rectilinear loop by d (interior on the right of the walk)."""
    n = len(loop)
    out = []
    for i in range(n):
        px, py = float(loop[i][0]), float(loop[i][1])
        for a, b in ((loop[i - 1], loop[i]), (loop[i], loop[(i + 1) % n])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            px += -dy / L * d                       # inward normal = (-dy, dx)
            py += dx / L * d
        out.append((px, py))
    return out


def _poly(surf, P, loop, color, h=0, width=0):
    pts = [_up(P(x, y), h) for (x, y) in loop]
    if len(pts) >= 3:
        pygame.draw.polygon(surf, color, pts, width)
    return pts


def _prism(surf, P, loops, h, color, base=0):
    """_box generalised to an arbitrary rectilinear region: extrude `loops`
    from base to base+h, drawing the camera-facing side faces (outward normal
    +x or +y) far-to-near, then the top."""
    ol = _dk(color, 0.5)
    faces = []
    for loop in loops:
        n = len(loop)
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            outx, outy = dy, -dx                    # outward normal
            if outx > 1e-9 or outy > 1e-9:          # faces the camera
                faces.append(((a[0] + b[0] + a[1] + b[1]) / 2.0, a, b, outx > 1e-9))
    faces.sort(key=lambda f: f[0])
    for _, a, b, is_x in faces:
        pa, pb = P(a[0], a[1]), P(b[0], b[1])
        quad = [_up(pa, base + h), _up(pb, base + h), _up(pb, base), _up(pa, base)]
        pygame.draw.polygon(surf, _dk(color, 0.72 if is_x else 0.86), quad)
        pygame.draw.polygon(surf, ol, quad, 1)
    for loop in loops:
        _poly(surf, P, loop, _lt(color), h=base + h)
        _poly(surf, P, loop, ol, h=base + h, width=1)


def _convex_corners(cells):
    """Outline vertices touching exactly ONE cell -> (vx, vy, cx, cy)."""
    out = []
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    for vx in range(min(xs), max(xs) + 2):
        for vy in range(min(ys), max(ys) + 2):
            ins = [c for c in ((vx - 1, vy - 1), (vx, vy - 1),
                               (vx - 1, vy), (vx, vy)) if c in cells]
            if len(ins) == 1:
                out.append((vx, vy, ins[0][0], ins[0][1]))
    return out


def _gbox(surf, P, x0, y0, x1, y1, h, color, base=0, seam=(), gaps=None):
    """_box for one part of a merged group, in REAL tile space. Sides named in
    `seam` run on flush into a same-height part: a far side ('x0'/'y0') loses
    its top edge and the vertical edge where the camera-facing faces meet it;
    a near side ('x1'/'y1') is an interface the part in front covers, so its
    face, its top edge and the front corner edge are skipped. `gaps` {far side:
    [(a, b), ...]} leaves only those spans of a far top edge un-outlined (where
    a chaise joins the seat). Other near sides need nothing: the part in front
    is drawn later and its fill covers the line."""
    gaps = gaps or {}
    A, B, C, D = P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)
    zt = base + h
    ol = _dk(color, 0.5)
    corner = "x1" not in seam and "y1" not in seam
    for (p, q, side, far, shade) in ((B, C, "x1", "y0", 0.72), (C, D, "y1", "x0", 0.86)):
        if side in seam:
            continue
        quad = [_up(p, zt), _up(q, zt), _up(q, base), _up(p, base)]
        pygame.draw.polygon(surf, _dk(color, shade), quad)
        pygame.draw.line(surf, ol, quad[0], quad[1])
        pygame.draw.line(surf, ol, quad[2], quad[3])
        if corner:
            pygame.draw.line(surf, ol, _up(C, zt), _up(C, base))  # front corner
        end = p if far == "y0" else q                           # the far end
        if far not in seam:
            pygame.draw.line(surf, ol, _up(end, zt), _up(end, base))
    top = [_up(A, zt), _up(B, zt), _up(C, zt), _up(D, zt)]
    pygame.draw.polygon(surf, _lt(color), top)

    def edge(side, a, b, fixed):
        """Outline one top edge, minus the spans listed in gaps[side]."""
        if side in seam:
            return
        segs = [(a, b)]
        for g0, g1 in gaps.get(side, ()):
            nxt = []
            for s0, s1 in segs:
                if g1 <= s0 or g0 >= s1:
                    nxt.append((s0, s1))
                    continue
                if g0 > s0:
                    nxt.append((s0, g0))
                if g1 < s1:
                    nxt.append((g1, s1))
            segs = nxt
        for s0, s1 in segs:
            if side in ("y0", "y1"):
                pa, pb = P(s0, fixed), P(s1, fixed)
            else:
                pa, pb = P(fixed, s0), P(fixed, s1)
            pygame.draw.line(surf, ol, _up(pa, zt), _up(pb, zt))

    edge("y0", x0, x1, y0)
    edge("x0", y0, y1, x0)
    edge("x1", y0, y1, x1)
    edge("y1", x0, x1, y1)


def _flush_ops(ops, extra_ops=None, P=None):
    """Depth-sort a part list and draw it; extra ops (seated players) are
    INSERTED at the first part that should paint over them -- the same rule
    draw() uses (a sitter box mixed into one global sort can form a cycle).
    With `P`, only parts whose screen footprint meets the extra's are asked:
    in a long merged group a far-off armrest that is x-separated from the
    sitter (but y-behind it) must not drag the sitter in front of the whole
    rest of the couch -- it can't overlap it on screen, so it has no say."""
    flushed = sorted(ops, key=functools.cmp_to_key(_op_cmp))

    def srect(b, pad=0):
        pts = [P(x, y) for x in (b[0], b[2]) for y in (b[1], b[3])]
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        return pygame.Rect(min(xs) - pad, min(ys) - b[5] - pad,
                           max(xs) - min(xs) + 2 * pad,
                           max(ys) - min(ys) + b[5] - b[4] + 2 * pad)
    for ex in sorted(extra_ops or (), key=lambda e: e[0][4]):
        er = srect(ex[0], 10) if P else None
        idx = len(flushed)
        for i, part in enumerate(flushed):
            if er is not None and not er.colliderect(srect(part[0])):
                continue
            if _op_cmp(part, ex) > 0:
                idx = i
                break
        flushed.insert(idx, ex)
    for _, fn in flushed:
        fn()


def draw_group(surf, P, kind, color, cells, rot=0, on=False, extra_ops=None):
    """Render a merged group of `kind` over `cells` as one seamless piece.
    `rot` is the group's facing (majority rot of its pieces) -- only kinds with
    a real front like the sofa use it; symmetric cabinets ignore it. `on` is
    the group's power state (a merged TV is one big screen). `extra_ops`
    (seated players, see draw()) are depth-sorted INTO the seat groups (sofa,
    bench); any other kind just paints them afterwards."""
    cells = set(cells)
    if extra_ops and kind not in ("sofa", "bench"):
        draw_group(surf, P, kind, color, cells, rot, on)
        for _, fn in extra_ops:
            fn()
        return
    wood = (150, 110, 70)
    metal = (188, 192, 200)
    loops = _outline(cells)
    if not loops:
        return

    def detail_faces():
        """One detail face (cx, cy, side) per module, all facing the SAME way:
        the group's long visible side (+x or +y, whichever has more exposed
        module faces; ties -> +x like a single piece at rot 0). A module whose
        primary side is covered falls back to its other exposed face (so the
        arms of an L face outward, Sims-style). Far-to-near order."""
        nx = sum(1 for c in cells if (c[0] + 1, c[1]) not in cells)
        ny = sum(1 for c in cells if (c[0], c[1] + 1) not in cells)
        prim = "x" if nx >= ny else "y"
        out = []
        for (cx, cy) in sorted(cells, key=lambda c: c[0] + c[1]):
            xs = (cx + 1, cy) not in cells
            ys = (cx, cy + 1) not in cells
            if prim == "x" and xs or prim == "y" and ys:
                out.append((cx, cy, prim))
            elif xs or ys:
                out.append((cx, cy, "x" if xs else "y"))
        return out

    def face_fp(cx, cy, side, h):
        """Perspective mapper for a module's +x or +y face (see _rface/_yface)."""
        if side == "x":
            return _rface(P, cx + 0.92, cy + 0.08, cy + 0.92, h)
        return _yface(P, cy + 0.92, cx + 0.08, cx + 0.92, h)

    if kind == "rug":                               # flat: border ring + light centre
        for lp in loops:
            _poly(surf, P, _shrink(lp, 0.04), color)
        for lp in loops:
            _poly(surf, P, _shrink(lp, 0.04), _dk(color, 0.7), width=2)
        for lp in loops:
            _poly(surf, P, _shrink(lp, 0.22), _lt(color, 1.2))

    elif kind == "chest":                           # Minecraft-style big chest
        _prism(surf, P, [_shrink(lp, 0.12) for lp in loops], 14, (150, 108, 64))
        _prism(surf, P, [_shrink(lp, 0.10) for lp in loops], 6, (172, 126, 78), base=14)
        for (cx, cy, side) in detail_faces():       # one gold latch per chest front
            c = (_up(P(cx + 0.90, cy + 0.5), 16) if side == "x"
                 else _up(P(cx + 0.5, cy + 0.90), 16))
            pygame.draw.rect(surf, (214, 196, 110),
                             (c[0] - 3, c[1] - 3, 6, 7), border_radius=1)

    elif kind in ("counter", "kitchen_island"):     # continuous worktop run
        h = 24
        stone = (226, 224, 216) if kind == "counter" else (226, 222, 214)
        _prism(surf, P, [_shrink(lp, 0.08) for lp in loops], h, color)
        for (cx, cy, side) in detail_faces():       # cupboard doors per module
            fp = face_fp(cx, cy, side, h)
            for ua, ub in ((0.08, 0.49), (0.51, 0.92)):
                quad = [fp(ua, 0.18), fp(ub, 0.18), fp(ub, 0.92), fp(ua, 0.92)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
            pygame.draw.line(surf, metal, fp(0.42, 0.30), fp(0.42, 0.44), 3)
            pygame.draw.line(surf, metal, fp(0.58, 0.30), fp(0.58, 0.44), 3)
        _prism(surf, P, [_shrink(lp, 0.04) for lp in loops], 3, stone, base=h)

    elif kind == "bookshelf":                       # one long wall of books
        h = HEIGHT[kind]
        _prism(surf, P, [_shrink(lp, 0.08) for lp in loops], h, color)
        books = [(208, 86, 84), (226, 150, 70), (228, 198, 92), (98, 186, 112),
                 (86, 134, 208), (150, 112, 202), (222, 142, 182), (110, 196, 196)]
        for (cx, cy, side) in detail_faces():
            fp = face_fp(cx, cy, side, h)
            pygame.draw.polygon(surf, _dk(color, 0.45),
                                [fp(0.06, 0.05), fp(0.94, 0.05), fp(0.94, 0.95), fp(0.06, 0.95)])
            for r, (v0, v1) in enumerate(((0.10, 0.36), (0.40, 0.66), (0.70, 0.95))):
                du = 0.88 / 6
                for k in range(6):
                    u0 = 0.06 + k * du + 0.01
                    u1 = u0 + du * 0.82
                    vt = v0 + ((k * 7 + r * 3 + cx + cy) % 4) * 0.012
                    bc = books[(k + r * 3 + cx) % len(books)]
                    quad = [fp(u0, vt), fp(u1, vt), fp(u1, v1), fp(u0, v1)]
                    pygame.draw.polygon(surf, bc, quad)
                    pygame.draw.polygon(surf, _dk(bc, 0.6), quad, 1)
                pygame.draw.line(surf, _dk(color, 0.55),
                                 fp(0.04, v1 + 0.01), fp(0.96, v1 + 0.01), 2)

    elif kind in ("dresser", "nightstand"):         # one long chest of drawers
        h = HEIGHT[kind]
        rows = (((0.10, 0.34), (0.40, 0.64), (0.70, 0.92)) if kind == "dresser"
                else ((0.12, 0.46), (0.52, 0.90)))
        _prism(surf, P, [_shrink(lp, 0.08) for lp in loops], h, color)
        for (cx, cy, side) in detail_faces():       # drawer rows per module,
            fp = face_fp(cx, cy, side, h)           # all on the same front side
            for v0, v1 in rows:
                quad = [fp(0.08, v0), fp(0.92, v0), fp(0.92, v1), fp(0.08, v1)]
                pygame.draw.polygon(surf, _lt(color, 1.06), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
                k = fp(0.5, (v0 + v1) / 2)          # knob
                pygame.draw.circle(surf, metal, (int(k[0]), int(k[1])), 2)

    elif kind in ("dining_table", "coffee_table"):  # one long table top
        toph, legh = (6, 18) if kind == "dining_table" else (5, 17)
        for (vx, vy, cx, cy) in sorted(_convex_corners(cells), key=lambda v: v[0] + v[1]):
            lx = vx + 0.10 if cx == vx else vx - 0.22
            ly = vy + 0.12 if cy == vy else vy - 0.24
            _prism(surf, P,
                   [[(lx, ly), (lx + 0.12, ly), (lx + 0.12, ly + 0.12), (lx, ly + 0.12)]],
                   legh, _dk(wood, 0.8))
        _prism(surf, P, [_shrink(lp, 0.05) for lp in loops], toph, color, base=legh)

    elif kind == "tv":                              # video wall: one WIDE screen per run
        # screen faces opposite the back side, same rot mapping as the sofa
        d = ((0, -1), (1, 0), (0, 1), (-1, 0))[rot % 4]
        ax = 0 if d[0] == 0 else 1

        def band(cx, cy, t0, t1, mlo, mhi):
            if d == (0, -1):
                return (cx + mlo, cy + t0, cx + 1 - mhi, cy + t1)
            if d == (0, 1):
                return (cx + mlo, cy + 1 - t1, cx + 1 - mhi, cy + 1 - t0)
            if d == (-1, 0):
                return (cx + t0, cy + mlo, cx + t1, cy + 1 - mhi)
            return (cx + 1 - t1, cy + mlo, cx + 1 - t0, cy + 1 - mhi)

        def run_rect(seg, t0, t1, m):
            a = band(*seg[0], t0, t1, m, m)
            b = band(*seg[-1], t0, t1, m, m)
            return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

        def rect_prism(r, hh, colr, base=0):
            _prism(surf, P, [[(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]],
                   hh, colr, base=base)

        runs, segs = {}, []
        for c in cells:
            runs.setdefault(c[1 - ax], []).append(c)
        for key, rcs in sorted(runs.items()):
            rcs.sort()
            seg = [rcs[0]]
            for c in rcs[1:]:
                if c[ax] == seg[-1][ax] + 1:
                    seg.append(c)
                else:
                    segs.append(seg)
                    seg = [c]
            segs.append(seg)
        for seg in sorted(segs, key=lambda s: s[0][0] + s[0][1]):
            rect_prism(run_rect(seg, 0.30, 0.70, 0.14), 10, _dk(wood, 0.85))   # console
            rp = run_rect(seg, 0.40, 0.54, 0.10)
            rect_prism(rp, 26, (44, 46, 54), base=10)                          # panel
            if on and d not in ((0, -1), (-1, 0)):   # screen hidden: top rim only
                tq = [_up(P(rp[0], rp[1]), 36), _up(P(rp[2], rp[1]), 36),
                      _up(P(rp[2], rp[3]), 36), _up(P(rp[0], rp[3]), 36)]
                pygame.draw.lines(surf, (150, 200, 240), True, tq, 2)
            if d == (0, -1):                        # screen on the camera-facing side
                fp = _yface(P, rp[3], rp[0], rp[2], 26, base=10)
            elif d == (-1, 0):
                fp = _rface(P, rp[2], rp[1], rp[3], 26, base=10)
            else:
                fp = None                           # turned away: plain back
            if fp:
                quad = [fp(0.05, 0.10), fp(0.95, 0.10), fp(0.95, 0.82), fp(0.05, 0.82)]
                if on:                                                         # one WIDE picture
                    pygame.draw.polygon(surf, (88, 148, 198), quad)
                    pygame.draw.line(surf, (170, 210, 240), fp(0.10, 0.22), fp(0.38, 0.22), 2)
                    _tv_art(surf, quad)
                    c = fp(0.94, 0.92)
                    pygame.draw.circle(surf, (120, 220, 140), (int(c[0]), int(c[1])), 2)
                else:
                    pygame.draw.polygon(surf, (36, 38, 46), quad)
                    pygame.draw.polygon(surf, (26, 28, 34), quad, 1)
                    c = fp(0.94, 0.92)
                    pygame.draw.circle(surf, (190, 70, 70), (int(c[0]), int(c[1])), 1)

    elif kind == "aquarium":                        # one long tank, fish per module
        _prism(surf, P, [_shrink(lp, 0.10) for lp in loops], 14, _dk(wood, 0.9))
        live = _live_art(surf, P, kind, frozenset(cells), 14, color)
        if not live:
            _prism(surf, P, [_shrink(lp, 0.12) for lp in loops], 20, (118, 178, 206), base=14)
        for (cx, cy, side) in (() if live else detail_faces()):
            if side == "x":
                lo = 0.12 if (cx, cy - 1) not in cells else 0.0
                hi = 0.12 if (cx, cy + 1) not in cells else 0.0
                fp = _rface(P, cx + 0.88, cy + lo, cy + 1 - hi, 20, base=14)
            else:
                lo = 0.12 if (cx - 1, cy) not in cells else 0.0
                hi = 0.12 if (cx + 1, cy) not in cells else 0.0
                fp = _yface(P, cy + 0.88, cx + lo, cx + 1 - hi, 20, base=14)
            quad = [fp(0.02, 0.78), fp(0.98, 0.78), fp(0.98, 0.96), fp(0.02, 0.96)]
            pygame.draw.polygon(surf, (150, 132, 96), quad)                    # gravel
            pygame.draw.line(surf, (208, 234, 244), fp(0.02, 0.10), fp(0.98, 0.10), 2)
            pygame.draw.line(surf, (96, 170, 110),                             # weed
                             fp(0.84, 0.78), fp(0.80, 0.30), 2)
            seed = cx * 7 + cy * 13                 # vary each module's fish a little
            for u, v, r, fc in ((0.22 + 0.06 * (seed % 3), 0.38 + 0.04 * (seed % 2), 4,
                                 (236, 140, 64)),
                                (0.52 + 0.05 * ((seed // 3) % 3), 0.58, 3, (244, 196, 90))):
                c = fp(u, v)
                t = fp(u - 0.08, v)
                pygame.draw.polygon(surf, fc, [(c[0] - r + 1, c[1]),
                                               (t[0], t[1] - 3), (t[0], t[1] + 3)])
                pygame.draw.circle(surf, fc, (int(c[0]), int(c[1])), r)
            for u, v in ((0.45, 0.30), (0.49, 0.20)):                          # bubbles
                c = fp(u, v)
                pygame.draw.circle(surf, (220, 240, 248), (int(c[0]), int(c[1])), 1)
        _prism(surf, P, [_shrink(lp, 0.10) for lp in loops], 3, (60, 62, 70), base=34)

    elif kind == "wardrobe":                        # one long closet wall
        h = HEIGHT[kind]
        _prism(surf, P, [_shrink(lp, 0.08) for lp in loops], h, color)
        for (cx, cy, side) in detail_faces():       # two tall doors per module
            fp = face_fp(cx, cy, side, h)
            for ua, ub in ((0.08, 0.49), (0.51, 0.92)):
                quad = [fp(ua, 0.06), fp(ub, 0.06), fp(ub, 0.94), fp(ua, 0.94)]
                pygame.draw.polygon(surf, _lt(color, 1.05), quad)
                pygame.draw.polygon(surf, _dk(color, 0.5), quad, 2)
            pygame.draw.line(surf, metal, fp(0.46, 0.42), fp(0.46, 0.62), 3)
            pygame.draw.line(surf, metal, fp(0.54, 0.42), fp(0.54, 0.62), 3)

    elif kind == "bench":                           # one long padded bench
        seat_h = 14
        # depth-sorted like a single piece so seated players layer correctly:
        # the base is one seamless prism under everything (its box spans the
        # whole group, so every pad / sitter body z-sorts above it)
        blo = [_shrink(lp, 0.12) for lp in loops]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        ops = [((min(xs) + 0.12, min(ys) + 0.12, max(xs) + 0.88, max(ys) + 0.88,
                 0, seat_h),
                lambda: _prism(surf, P, blo, seat_h, _dk(color, 0.82)))]
        for (cx, cy) in cells:                      # one pad per cell
            r = [(cx + 0.18, cy + 0.18), (cx + 0.82, cy + 0.18),
                 (cx + 0.82, cy + 0.82), (cx + 0.18, cy + 0.82)]
            ops.append(((cx + 0.18, cy + 0.18, cx + 0.82, cy + 0.82, seat_h, seat_h + 6),
                        lambda r=r: _prism(surf, P, [r], 6, _lt(color, 1.1), base=seat_h)))
        _flush_ops(ops, extra_ops, P)

    elif kind == "sofa":                            # sectional / L-couch
        # Built from the SAME parts as a single sofa -- backrest strip, seat
        # base, armrests, back + seat cushions -- as real boxes that never
        # interpenetrate, then depth-sorted with _op_cmp (seated players are
        # slotted in like draw() does). Consecutive cells along the back fuse
        # into one strip / one base box, so a straight couch has no seams; a
        # chaise (cell with sofa behind it) gets its own base box that runs
        # 0.06 back under the seat edge and hides the join line (_gbox).
        seat_h, aw = 12, 0.18
        # back side follows the group's facing, same mapping the single piece
        # gets from its rotation: rot 0 back at -y, 1 at +x, 2 at +y, 3 at -x
        d = ((0, -1), (1, 0), (0, 1), (-1, 0))[rot % 4]
        ax = 0 if d[0] == 0 else 1                  # back runs along x (0) or y (1)
        lo_side = "x0" if ax == 0 else "y0"         # lateral lo side (always far)
        back_side = {(0, -1): "y0", (0, 1): "y1", (-1, 0): "x0", (1, 0): "x1"}[d]
        front_side = {"y0": "y1", "y1": "y0", "x0": "x1", "x1": "x0"}[back_side]

        def band(cx, cy, t0, t1, mlo=0.06, mhi=0.06):
            """Tile-rect strip t0..t1 deep from the BACK edge of cell (cx,cy),
            inset mlo/mhi at the lateral (run-axis) lo/hi sides."""
            if d == (0, -1):
                return (cx + mlo, cy + t0, cx + 1 - mhi, cy + t1)
            if d == (0, 1):
                return (cx + mlo, cy + 1 - t1, cx + 1 - mhi, cy + 1 - t0)
            if d == (-1, 0):
                return (cx + t0, cy + mlo, cx + t1, cy + 1 - mhi)
            return (cx + 1 - t1, cy + mlo, cx + 1 - t0, cy + 1 - mhi)

        def run_rect(seg, t0, t1, mlo, mhi):
            a = band(*seg[0], t0, t1, mlo, mhi)
            b = band(*seg[-1], t0, t1, mlo, mhi)
            return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

        def nb(c, s):                               # neighbour along the run axis
            return (c[0] + s, c[1]) if ax == 0 else (c[0], c[1] + s)

        def runs(cs):
            """Maximal runs of consecutive cells along the back's axis."""
            rows, out = {}, []
            for c in cs:
                rows.setdefault(c[1 - ax], []).append(c)
            for key in sorted(rows):
                rcs = sorted(rows[key], key=lambda c: c[ax])
                seg = [rcs[0]]
                for c in rcs[1:]:
                    if c[ax] == seg[-1][ax] + 1:
                        seg.append(c)
                    else:
                        out.append(seg)
                        seg = [c]
                out.append(seg)
            return out

        ops = []

        def add(r, z0, hh, colr, **kw):
            def fn(r=r, z0=z0, hh=hh, colr=colr, kw=kw):
                _gbox(surf, P, r[0], r[1], r[2], r[3], hh, colr, base=z0, **kw)
            ops.append(((r[0], r[1], r[2], r[3], z0, z0 + hh), fn))

        backed = {c for c in cells if (c[0] + d[0], c[1] + d[1]) not in cells}
        bases = []                                  # (seg, rect, is_chaise, lo_open)
        for seg in runs(backed):
            lo_open = nb(seg[0], -1) in cells       # run continues into a chaise
            hi_open = nb(seg[-1], 1) in cells       # ...otherwise: an armrest
            llo = 0.0 if lo_open else 0.04 + aw
            lhi = 0.0 if hi_open else 0.04 + aw
            add(run_rect(seg, 0.06, 0.32, llo, lhi), 0, seat_h + 18, color)    # backrest
            bases.append((seg, run_rect(seg, 0.32, 0.94, llo, lhi), False, lo_open))
            if not lo_open:                         # armrests at the open run ends
                add(band(*seg[0], 0.06, 0.94, 0.04, 1 - 0.04 - aw), 0, seat_h + 9,
                    _dk(color, 0.92))
            if not hi_open:
                add(band(*seg[-1], 0.06, 0.94, 1 - 0.04 - aw, 0.04), 0, seat_h + 9,
                    _dk(color, 0.92))
            for c in seg:                           # back + seat cushion per cell
                mlo = 0.26 if (c == seg[0] and not lo_open) else 0.10
                mhi = 0.26 if (c == seg[-1] and not hi_open) else 0.10
                add(band(*c, 0.32, 0.50, mlo, mhi), seat_h, 11, _lt(color, 1.06))
                add(band(*c, 0.50, 0.90, mlo, mhi), seat_h, 4, _lt(color, 1.12))
        for seg in runs(cells - backed):            # chaise cells: base + one pad
            lo_open = nb(seg[0], -1) in cells
            hi_open = nb(seg[-1], 1) in cells
            bases.append((seg, run_rect(seg, -0.06, 0.94, 0.0 if lo_open else 0.06,
                                        0.0 if hi_open else 0.06), True, lo_open))
            for c in seg:
                add(band(*c, 0.10, 0.90, 0.10, 0.10), seat_h, 4, _lt(color, 1.12))
        # seat bases: hide the join lines between neighbouring base boxes. The
        # FAR depth side (the back at rot 0/3, the front at rot 1/2) either
        # continues flush into an identical box (a chaise two deep -> full
        # seam) or only its top edge is skipped where another box joins.
        far_back = back_side in ("x0", "y0")
        far_side = back_side if far_back else front_side
        near_side = {"x0": "x1", "y0": "y1"}[far_side]
        fdir = d if far_back else (-d[0], -d[1])
        lat = (0, 2) if ax == 0 else (1, 3)
        for seg, r, chaise, lo_open in bases:
            seam = [lo_side] if lo_open else []
            gaps = {}
            behind = [(c[0] + fdir[0], c[1] + fdir[1]) for c in seg]
            ahead = [(c[0] - fdir[0], c[1] - fdir[1]) for c in seg]

            def twin(cs):                           # same-width base box there?
                r2 = next((r2 for s2, r2, _, _ in bases if s2 == cs), None)
                return r2 is not None and all(abs(r2[i] - r[i]) < 1e-6 for i in lat)
            if twin(ahead):
                seam.append(near_side)              # flush into the box in front
            if twin(behind):
                seam.append(far_side)
            elif far_back and chaise:
                gaps[far_side] = [(-1e9, 1e9)]      # joins the seat behind it
            elif not far_back:
                spans = [(c[ax], c[ax] + 1) for c, bc in zip(seg, behind) if bc in cells]
                if spans:
                    gaps[far_side] = spans          # a chaise joins in front
            add(r, 0, seat_h, color, seam=tuple(seam), gaps=gaps)
        _flush_ops(ops, extra_ops, P)

    else:                                           # generic merged cabinet
        _prism(surf, P, [_shrink(lp, 0.08) for lp in loops], HEIGHT.get(kind, 22), color)
