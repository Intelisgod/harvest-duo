"""Living home art: the house cat's sprite sheet, the aquarium's swimming fish
and the growing house plants -- pure procedural pygame drawing, no game state.

Owner: Home Life (2026-09-28). Used by ``systems/homelife_system.py`` (which
owns the rules) and, through ``isofurn.LIVE_ART``, by the iso room renderer:

* ``cat_frame(pose, facing, frame)``  -> cached Surface, feet at (CAT_AX, CAT_AY)
* ``paint_tank(surf, P, cells, fish, t, feed)``  -> a glass tank in the room
  with real fish swimming in 3D (depth-sorted inside the glass box)
* ``paint_plant / paint_cactus / paint_vase``  -> growth-stage art (stage 0 is
  the stock isofurn art, so pieces with empty ``Placed.data`` look unchanged)
"""
import math
import random
import zlib

import pygame

# --------------------------------------------------------------------- palette
FUR = (250, 245, 236)          # Mochi: a cream-white calico
FUR_SH = (226, 216, 204)
FUR_DK = (204, 192, 180)
PATCH = (238, 168, 100)
PATCH_SH = (214, 142, 78)
DARK = (104, 92, 94)
LINE = (92, 66, 62)
PINK = (242, 152, 164)
BLUSH = (250, 190, 196)
EYE = (52, 42, 46)
WHISKER = (200, 190, 186)

CAT_W, CAT_H = 34, 30
CAT_AX, CAT_AY = 17, 27        # feet anchor inside a frame
_OX, _OY = 1, 3                # design space (feet at y=24) -> canvas offset

POSES = ("walk", "sit", "sleep", "groom", "stretch", "happy", "hop")
FRAMES = {"walk": 4, "sit": 2, "sleep": 2, "groom": 2, "stretch": 1, "happy": 2, "hop": 1}


def _lt(c, f=1.16):
    return tuple(min(255, int(v * f)) for v in c[:3])


def _dk(c, f=0.74):
    return tuple(max(0, int(v * f)) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ===================================================================== the cat
class _Pen:
    """Draws in the cat's design space (feet on y=24) onto the frame canvas."""

    def __init__(self, s):
        self.s = s

    def e(self, col, x, y, w, h):
        pygame.draw.ellipse(self.s, col, (x + _OX, y + _OY, w, h))

    def c(self, col, x, y, r):
        pygame.draw.circle(self.s, col, (x + _OX, y + _OY), r)

    def r(self, col, x, y, w, h, br=1):
        pygame.draw.rect(self.s, col, (x + _OX, y + _OY, w, h), border_radius=br)

    def poly(self, col, pts):
        pygame.draw.polygon(self.s, col, [(x + _OX, y + _OY) for x, y in pts])

    def line(self, col, pts, w=1):
        pygame.draw.lines(self.s, col, False, [(x + _OX, y + _OY) for x, y in pts], w)

    def px(self, col, x, y):
        if 0 <= x + _OX < CAT_W and 0 <= y + _OY < CAT_H:
            self.s.set_at((x + _OX, y + _OY), col)


def _tail(pen, pts, w=3):
    pen.line(FUR_SH, pts, w + 1)
    pen.line(FUR, pts, w)
    tx, ty = pts[-1]
    pen.c(DARK, tx, ty, 2)


def _head(pen, cx, cy, face, eyes="open", tilt=0):
    """Round head + ears; face=False shows the back of the head."""
    # ears (drawn first so the head overlaps their base)
    le = [(cx - 5, cy - 2), (cx - 4 + tilt, cy - 8), (cx - 1, cy - 4)]
    re = [(cx + 1, cy - 4), (cx + 4 + tilt, cy - 8), (cx + 5, cy - 2)]
    pen.poly(PATCH, le)
    pen.poly(FUR, re)
    if face:
        pen.poly(PINK, [(cx - 4, cy - 3), (cx - 4 + tilt, cy - 6), (cx - 2, cy - 4)])
        pen.poly(PINK, [(cx + 2, cy - 4), (cx + 4 + tilt, cy - 6), (cx + 4, cy - 3)])
    pen.c(FUR, cx, cy, 6)
    pen.e(FUR_SH, cx - 5, cy + 2, 10, 4)          # jaw shade
    pen.e(FUR, cx - 5, cy + 1, 10, 4)
    pen.e(PATCH, cx - 6, cy - 6, 6, 5)            # orange patch over one ear
    if not face:
        pen.e(PATCH_SH, cx - 4, cy - 2, 5, 4)     # back of the head: more patch
        pen.e(DARK, cx + 1, cy - 5, 5, 4)
        return
    if eyes == "open":
        for ex in (cx - 3, cx + 2):
            pen.r(EYE, ex, cy - 1, 2, 3, 0)
            pen.px((255, 255, 255), ex, cy - 1)
    elif eyes == "closed":                        # sleepy / content: little arcs
        for ex in (cx - 3, cx + 2):
            pen.px(EYE, ex, cy + 1)
            pen.px(EYE, ex + 1, cy + 1)
    elif eyes == "happy":                         # ^ ^
        for ex in (cx - 3, cx + 2):
            pen.px(EYE, ex, cy + 1)
            pen.px(EYE, ex + 1, cy)
            pen.px(EYE, ex + 2, cy + 1)
    pen.px(PINK, cx, cy + 2)                      # nose
    pen.px(PINK, cx - 1, cy + 2)


def _face_extras(pen, cx, cy, face, eyes="open", mouth="w"):
    """Blush, mouth and whiskers (painted AFTER the outline)."""
    if not face:
        return
    pen.px(BLUSH, cx - 5, cy + 2)
    pen.px(BLUSH, cx + 4, cy + 2)
    if mouth == "w":
        pen.px(EYE, cx - 2, cy + 3)
        pen.px(EYE, cx, cy + 3)
        pen.px(EYE, cx + 1, cy + 3)
    elif mouth == "open":
        pen.px(PINK, cx - 1, cy + 3)
        pen.px(PINK, cx, cy + 3)
        pen.px((210, 110, 120), cx, cy + 4)
    pen.line(WHISKER, [(cx + 6, cy + 2), (cx + 8, cy + 1)])
    pen.line(WHISKER, [(cx - 7, cy + 2), (cx - 9, cy + 1)])


def _legs(pen, spec):
    """spec: [(x, top, h, col)] paws get a lighter toe bean row."""
    for x, top, h, col in spec:
        pen.r(col, x, top, 3, h, 1)
        pen.r(_lt(col, 1.04), x, top + h - 1, 3, 1, 0)


def _outline(s):
    """1px LINE outline around the silhouette (cute and readable on any floor)."""
    m = pygame.mask.from_surface(s)
    out = pygame.mask.Mask(s.get_size())
    for off in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.draw(m, off)
    out.erase(m, (0, 0))
    out.to_surface(s, setcolor=LINE, unsetcolor=None)


def _draw_cat(pose, face, frame):
    s = pygame.Surface((CAT_W, CAT_H), pygame.SRCALPHA)
    pen = _Pen(s)
    hx = hy = 0
    eyes, mouth = "open", "w"
    if pose in ("walk", "hop"):
        strides = ((1, -1, -1, 1), (0, 0, 0, 0), (-1, 1, 1, -1), (0, 0, 0, 0))
        lifts = ((0, 0, 0, 0), (1, 0, 0, 1), (0, 0, 0, 0), (0, 1, 1, 0))
        sx, ly = strides[frame % 4], lifts[frame % 4]
        b = -1 if frame % 2 else 0
        if pose == "hop":                          # legs flung out, body stretched
            sx, ly, b = (-2, 2, -2, 2), (1, 2, 1, 2), -1
        _tail(pen, [(8, 14 + b), (5, 11 + b), (4, 7 + b), (5, 4 + b), (7, 3 + b)])
        _legs(pen, [(8 + sx[0], 17, 7 - ly[0], FUR_DK), (18 + sx[1], 17, 7 - ly[1], FUR_DK)])
        pen.e(FUR_SH, 6, 11 + b, 19, 10)          # body
        pen.e(FUR, 6, 10 + b, 19, 9)
        pen.e(PATCH, 10, 10 + b, 9, 5)            # calico back patch
        pen.e(DARK, 13, 11 + b, 6, 4)
        _legs(pen, [(11 + sx[2], 18, 6 - ly[2], FUR), (21 + sx[3], 18, 6 - ly[3], FUR)])
        hx, hy = 24, 8 + b
        _head(pen, hx, hy, face)
    elif pose in ("sit", "happy", "groom"):
        sw = frame % 2
        tail = [(10, 21), (6, 22), (7, 24), (13, 25), (19, 24 + sw), (22, 23 - sw)]
        if not face:                               # from behind: tail curls up the back
            tail = [(10, 21), (7, 19), (6 - sw, 15), (7 - sw, 11)]
        _tail(pen, tail)
        pen.e(FUR_SH, 7, 13, 15, 11)               # haunch
        pen.e(FUR, 7, 12, 15, 11)
        pen.e(PATCH, 8, 13, 7, 6)
        pen.e(DARK, 9, 14, 5, 4)
        pen.e(FUR_SH, 15, 9, 10, 14)               # chest
        pen.e(FUR, 15, 9, 9, 13)
        _legs(pen, [(16, 17, 7, FUR_DK), (20, 17, 7, FUR)])
        hx, hy = 21, 7
        if pose == "groom":
            hy = 8 + sw
            eyes = "closed"
            mouth = "open"
        elif pose == "happy":
            eyes, mouth = "happy", "open"
            hy = 7 - sw
        _head(pen, hx, hy, face, eyes)
        if pose == "groom" and face:               # licking a raised paw
            pen.e(FUR, hx - 1, hy + 3 - sw, 4, 5)
            pen.e(_lt(FUR_SH, 1.05), hx - 1, hy + 6 - sw, 4, 2)
    elif pose == "sleep":
        br = frame % 2
        pen.e(FUR_SH, 5, 13 - br, 23, 10 + br)     # curled loaf
        pen.e(FUR, 5, 12 - br, 23, 10 + br)
        pen.e(PATCH, 8, 12 - br, 10, 6)
        pen.e(DARK, 11, 13 - br, 6, 4)
        hx, hy = 22, 16
        eyes = "closed" if face else "open"
        _head(pen, hx, hy, face, eyes)
        _tail(pen, [(6, 18), (8, 22), (15, 23), (22, 23), (26, 21)])
        mouth = ""
    elif pose == "stretch":
        _tail(pen, [(7, 11), (5, 7), (5, 3), (7, 1)])
        _legs(pen, [(7, 15, 9, FUR_DK), (11, 15, 9, FUR)])
        pen.e(FUR_SH, 5, 9, 12, 10)                # rear up high
        pen.e(FUR, 5, 8, 12, 10)
        pen.e(FUR_SH, 12, 13, 13, 8)               # chest down low
        pen.e(FUR, 12, 12, 13, 8)
        pen.e(PATCH, 7, 8, 7, 5)
        pen.r(FUR_DK, 20, 21, 9, 3, 1)             # front legs reaching forward
        pen.r(FUR, 21, 22, 9, 3, 1)
        hx, hy = 24, 15
        eyes, mouth = "happy", "open"
        _head(pen, hx, hy, face, eyes)
    _outline(s)
    if pose != "sleep":
        _face_extras(pen, hx, hy, face, eyes, mouth)
    elif face:
        pen.px(BLUSH, hx - 5, hy + 2)
        pen.px(BLUSH, hx + 4, hy + 2)
    return s


_CAT_CACHE = {}
# grid facing -> (face visible?, mirrored?) -- camera looks from +x,+y:
#   +x = screen down-right, +y = down-left, -x = up-left, -y = up-right
FACING_VIEW = {(1, 0): (True, False), (0, 1): (True, True),
               (0, -1): (False, False), (-1, 0): (False, True)}


def cat_frame(pose, facing, frame=0):
    """Cached cat frame for ``pose`` facing grid direction ``facing``."""
    face, flip = FACING_VIEW.get(tuple(facing), (True, False))
    if pose not in FRAMES:
        pose = "sit"
    frame %= FRAMES[pose]
    key = (pose, face, flip, frame)
    s = _CAT_CACHE.get(key)
    if s is None:
        s = _draw_cat(pose, face, frame)
        if flip:
            s = pygame.transform.flip(s, True, False)
        _CAT_CACHE[key] = s
    return s


def cat_portrait(pose="sit", frame=0, scale=4):
    key = ("portrait", pose, frame, scale)
    s = _CAT_CACHE.get(key)
    if s is None:
        base = cat_frame(pose, (1, 0), frame)
        s = pygame.transform.scale(base, (base.get_width() * scale, base.get_height() * scale))
        _CAT_CACHE[key] = s
    return s


def draw_cat(scr, sx, sy, pose, facing, frame, shadow_y=None, alpha=255):
    """Blit the cat with its feet at screen (sx, sy); soft shadow at shadow_y."""
    sh_y = sy if shadow_y is None else shadow_y
    sh = pygame.Surface((22, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (24, 20, 34, 60 if sh_y == sy else 40), (0, 0, 22, 8))
    scr.blit(sh, (int(sx) - 11, int(sh_y) - 4))
    img = cat_frame(pose, facing, frame)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    scr.blit(img, (int(sx) - CAT_AX, int(sy) - CAT_AY))


# ===================================================================== fish
def fish_color(fish_id):
    try:
        from .assets import FISH_LOOK
        c = FISH_LOOK.get(fish_id)
        if c:
            return tuple(c[:3])
    except Exception:
        pass
    h = sum(ord(ch) * (i + 3) for i, ch in enumerate(fish_id))
    pal = ((236, 140, 64), (244, 196, 90), (120, 176, 220), (150, 200, 120),
           (220, 120, 150), (180, 150, 220))
    return pal[h % len(pal)]


_BIG = {"sturgeon", "swordfish", "golden_swordfish", "tuna", "abyssal_tuna", "halibut",
        "coelacanth", "the_legend", "crimson_bass", "glacier_pike", "the_leviathan",
        "catfish", "salmon", "pike", "unseeing_maw"}
_TINY = {"anchovy", "sardine", "herring", "bluegill", "sunfish"}
_GLOW_FISH = {"void_eel", "phantom_carp", "unseeing_maw", "kraken_spawn",
              "maelstrom_ray", "the_leviathan", "abyssal_tuna", "the_legend"}


def fish_size(fish_id):
    if fish_id in _BIG:
        return 8, 4
    if fish_id in _TINY:
        return 5, 3
    return 6, 3


def draw_fish(surf, x, y, fish_id, right, wig, scale=1, alpha=255):
    """A tiny side-view fish centred on (x, y). ``wig`` (-1..1) waves the tail."""
    col = fish_color(fish_id)
    w, h = fish_size(fish_id)
    w, h = w * scale, h * scale
    d = 1 if right else -1
    x, y = int(round(x)), int(round(y))
    if fish_id in ("eel", "void_eel"):             # long wavy eel
        pts = []
        for i in range(6):
            px = x - d * (i * 1.6 * scale - 3 * scale)
            pts.append((px, y + math.sin(wig * 2 + i * 1.3) * 1.2 * scale))
        pygame.draw.lines(surf, _dk(col, 0.7), False, pts, 2 * scale + 1)
        pygame.draw.lines(surf, col, False, pts, max(1, 2 * scale - 1))
        surf.set_at((int(pts[0][0]), int(pts[0][1])), (30, 30, 36))
        return
    if fish_id == "pufferfish":
        r = 2 * scale
        pygame.draw.circle(surf, _dk(col, 0.75), (x, y), r + 1)
        pygame.draw.circle(surf, col, (x, y), r)
        surf.set_at((x + d * r // 2, y - 1), (30, 30, 36))
        return
    tail = [(x - d * (w // 2), y), (x - d * (w // 2 + 2 * scale), y - h // 2 - 1 + int(wig)),
            (x - d * (w // 2 + 2 * scale), y + h // 2 + 1 + int(wig))]
    pygame.draw.polygon(surf, _dk(col, 0.8), tail)
    body = pygame.Rect(0, 0, w + 1, h + 1)
    body.center = (x, y)
    col = _lt(col, 1.12)
    pygame.draw.ellipse(surf, col, body)
    pygame.draw.line(surf, _dk(col, 0.72), (body.x + 1, body.y), (body.right - 2, body.y), 1)
    if h >= 3:                                     # a lighter belly
        pygame.draw.line(surf, _lt(col, 1.25), (body.x + 2, body.bottom - 1),
                         (body.right - 3, body.bottom - 1), 1)
    if fish_id in ("swordfish", "golden_swordfish"):
        pygame.draw.line(surf, _dk(col, 0.7), (x + d * (w // 2), y), (x + d * (w // 2 + 4), y - 1), 1)
    ex = x + d * max(1, w // 2 - 1)
    surf.set_at((ex, y - (1 if h >= 3 else 0)), (26, 26, 32))


# ===================================================================== aquarium
TANK_Z0, TANK_Z1, TANK_WL = 14, 34, 31          # floor, rim, waterline (px up)
TANK_CAP = 6
_WATER_BACK = (46, 112, 158)
_WATER_DEEP = (36, 92, 140)
_WATER_FLOOR = (58, 128, 170)                      # the tank floor seen THROUGH the water
_SAND = (222, 198, 146)
_SAND_DK = (182, 156, 112)


def _fish_params(fish_id, k, cell):
    # a STABLE seed (str hash() is salted per process: host and client differ)
    rnd = random.Random(zlib.crc32(f"{fish_id}|{k}|{cell[0]}|{cell[1]}".encode()))
    return (rnd.uniform(0.28, 0.46), rnd.uniform(0, math.tau), rnd.uniform(0, math.tau),
            rnd.uniform(0, math.tau), rnd.uniform(0.62, 0.86), rnd.uniform(-2.5, 2.5))


def fish_pos(fish_id, k, cell, box, t, feed_k=0.0, panes=(True, True)):
    """3D point (x, y, z, screen-dx) of fish k in the tank ``box`` (x0, y0,
    x1, y1). The fish swim a lane hugging the front panes -- ``panes`` =
    (has +x pane, has +y pane) -- the only water the lid doesn't hide from
    the iso camera. ``feed_k`` 0..1 pulls them up to the flakes."""
    w, p1, p2, p3, r2, zc = _fish_params(fish_id, k, cell)
    x0, y0, x1, y1 = box
    has_x, has_y = panes
    d = 0.13 + 0.09 * (0.5 + 0.5 * math.sin(w * r2 * t + p2))    # depth behind the glass
    osc = 0.5 + 0.5 * math.sin(w * t + p1)
    dosc = 0.5 * w * math.cos(w * t + p1)
    if feed_k > 0:                                 # crowd the flakes mid-pane, by the glass
        goal = (0.26 if k % 2 == 0 else 0.74) + 0.07 * math.sin(k * 2.3 + t * 2.4)
        osc += (goal - osc) * feed_k * 0.85
        dosc = dosc * (1 - feed_k) + math.cos(k * 2.3 + t * 2.4) * feed_k
        d += (0.08 - d) * feed_k
    if has_x and has_y:                            # an L round the front corner
        la = max(0.05, (x1 - d) - (x0 + 0.12))
        lb = max(0.05, (y1 - d) - (y0 + 0.12))
        s_ = osc * (la + lb)
        ds = dosc * (la + lb)
        if s_ <= la:
            x, y, dx, dy = x0 + 0.12 + s_, y1 - d, ds, 0.0
        else:
            x, y, dx, dy = x1 - d, y1 - d - (s_ - la), 0.0, -ds
    elif has_y:
        span = (x1 - 0.12) - (x0 + 0.12)
        x, y, dx, dy = x0 + 0.12 + osc * span, y1 - d, dosc * span, 0.0
    elif has_x:
        span = (y1 - 0.12) - (y0 + 0.12)
        x, y, dx, dy = x1 - d, y0 + 0.12 + osc * span, 0.0, dosc * span
    else:                                          # an inner cell of a big group
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x = cx + ((x1 - x0) / 2 - 0.13) * math.sin(w * t + p1)
        y = cy + ((y1 - y0) / 2 - 0.13) * math.sin(w * r2 * t + p2)
        dx = math.cos(w * t + p1)
        dy = 0.0
    z = 23.5 + zc + 3.0 * math.sin(w * 1.4 * t + p3)
    if feed_k > 0:
        z += (TANK_WL - 5 + math.sin(t * 5 + k) - z) * feed_k
    return x, y, z, dx - dy


def feed_curve(age):
    """0..1 'rush to the surface' strength ``age`` seconds after feeding."""
    if age is None or age < 0 or age > 9.0:
        return 0.0
    if age < 0.9:
        k = age / 0.9
        return k * k * (3 - 2 * k)
    if age > 7.0:
        k = (9.0 - age) / 2.0
        return k * k * (3 - 2 * k)
    return 1.0


def _cell_box(cx, cy, cells, inset=0.12):
    return (cx + (inset if (cx - 1, cy) not in cells else 0.0),
            cy + (inset if (cx, cy - 1) not in cells else 0.0),
            cx + 1 - (inset if (cx + 1, cy) not in cells else 0.0),
            cy + 1 - (inset if (cx, cy + 1) not in cells else 0.0))


def paint_tank(surf, P, cells, fish, t, feed=None):
    """The water box of an aquarium over ``cells`` (tile ints). From the iso
    camera the lid hides everything but the two front panes, so the tank is
    painted as a lit diorama seen THROUGH them: water (deep at the bottom,
    bright under the surface), back plants and a rock, the sand bed, then the
    fish depth-sorted inside the glass (they swim a lane just behind the
    panes), food flakes, bubbles and finally the glass itself.
    ``fish`` = {cell: [fish ids]}, ``feed`` = {cell: seconds since feeding},
    ``P`` = the room projection."""
    cells = set(cells)
    feed = feed or {}

    def U(x, y, z):
        p = P(x, y)
        return (p[0], p[1] - z)

    Z0, Z1, WL = TANK_Z0, TANK_Z1, TANK_WL
    bed = Z0 + 3
    for cell in sorted(cells, key=lambda c: (c[0] + c[1], c[0])):
        cx, cy = cell
        x0, y0, x1, y1 = _cell_box(cx, cy, cells)
        has_x, has_y = (cx + 1, cy) not in cells, (cx, cy + 1) not in cells
        panes = []                                 # (a, b) floor points of each front pane
        if has_y:
            panes.append(((x0, y1), (x1, y1)))
        if has_x:
            panes.append(((x1, y0), (x1, y1)))

        def band(a, b, z0, z1, col):
            pygame.draw.polygon(surf, col, [U(a[0], a[1], z0), U(b[0], b[1], z0),
                                            U(b[0], b[1], z1), U(a[0], a[1], z1)])
        # -- water: a vertical gradient, darker toward the sand
        for a, b in panes:
            for z in range(Z0, WL):
                k = (z - Z0) / float(WL - Z0)
                band(a, b, z, z + 1, _mix(_WATER_DEEP, (92, 176, 214), k * k))
            band(a, b, WL, Z1, (206, 236, 246))                   # air under the lid
            for i, u in enumerate((0.28, 0.66)):                  # soft light shafts
                sh = 0.08 * math.sin(t * 0.6 + i * 2)
                pa = (a[0] + (b[0] - a[0]) * (u + sh), a[1] + (b[1] - a[1]) * (u + sh))
                pb = (a[0] + (b[0] - a[0]) * (u + sh - 0.1), a[1] + (b[1] - a[1]) * (u + sh - 0.1))
                pygame.draw.line(surf, _mix(_WATER_BACK, (150, 210, 236), 0.55),
                                 U(pa[0], pa[1], WL - 1), U(pb[0], pb[1], bed + 2), 1)
        # -- back plants + a rock, set back from the glass
        roots = []
        if has_y:
            roots.append((x0 + 0.14, y1 - 0.2))
        if has_x:
            roots.append((x1 - 0.2, y0 + 0.14))
        for ri, (rx, ry) in enumerate(roots):
            base = U(rx, ry, bed)
            for j, (bh, ph) in enumerate(((11, 0.0), (8, 1.7), (12, 3.1))):
                pts = []
                for i in range(6):
                    k = i / 5
                    sway = math.sin(t * 1.7 + ph + k * 2.4 + ri) * 2.0 * k
                    pts.append((base[0] - 3 + j * 3 + sway, base[1] - k * bh))
                pygame.draw.lines(surf, (46, 118, 76), False, pts, 3)
                pygame.draw.lines(surf, (104, 190, 112), False, pts, 1)
        if panes:
            (a, b) = panes[-1]
            rk = U(a[0] + (b[0] - a[0]) * 0.72 - (0.3 if b[0] == a[0] else 0),
                   a[1] + (b[1] - a[1]) * 0.72 - (0.3 if b[1] == a[1] else 0), bed)
            pygame.draw.ellipse(surf, (112, 116, 130), (rk[0] - 4, rk[1] - 4, 9, 6))
            pygame.draw.ellipse(surf, (150, 156, 170), (rk[0] - 3, rk[1] - 4, 5, 3))
        # -- the sand bed along the glass, with pebbles
        rnd = random.Random(cx * 131 + cy * 17)
        for a, b in panes:
            band(a, b, Z0, bed, _SAND)
            pygame.draw.line(surf, _lt(_SAND, 1.08), U(a[0], a[1], bed), U(b[0], b[1], bed), 1)
            for _ in range(4):
                u = rnd.uniform(0.08, 0.92)
                q = U(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, Z0 + rnd.uniform(1, 2.5))
                pc = rnd.choice(((176, 150, 120), (150, 160, 170), (196, 120, 110),
                                 (240, 228, 200)))
                pygame.draw.rect(surf, pc, (int(q[0]) - 1, int(q[1]) - 1, 2, 2))
        # -- fish, far first
        box = (x0, y0, x1, y1)
        fk = feed_curve(feed.get(cell))
        rows = []
        for k, fid in enumerate(fish.get(cell, ())):
            x, y, z, sdx = fish_pos(fid, k, cell, box, t, fk, (has_x, has_y))
            rows.append((x + y, fid, x, y, z, sdx, k))
        rows.sort()
        for _d, fid, x, y, z, sdx, k in rows:
            sp = U(x, y, z)
            wig = math.sin(t * (7 + 5 * fk) + k * 1.7)
            if fid in _GLOW_FISH:
                g = pygame.Surface((14, 10), pygame.SRCALPHA)
                pygame.draw.ellipse(g, (*_lt(fish_color(fid), 1.3), 70), (0, 0, 14, 10))
                surf.blit(g, (sp[0] - 7, sp[1] - 5))
            draw_fish(surf, sp[0], sp[1], fid, sdx >= 0, wig)
        # -- food flakes sinking after a feed
        age = feed.get(cell)
        if age is not None and 0 <= age < 6.5 and panes:
            rnd = random.Random(cx * 7 + cy)
            for i in range(7):
                a, b = panes[i % len(panes)]
                u = rnd.uniform(0.2, 0.8)
                fz = WL - 0.5 - age * rnd.uniform(1.2, 2.4)
                if fz < bed + 1 or age > 4.5 + i * 0.25:
                    continue
                q = U(a[0] + (b[0] - a[0]) * u - 0.1, a[1] + (b[1] - a[1]) * u - 0.1, fz)
                surf.set_at((int(q[0] + math.sin(age * 2 + i)), int(q[1])), (240, 176, 96))
        # -- bubbles rising by the front corner
        if panes:
            a, b = panes[0]
            bx, by = a[0] + (b[0] - a[0]) * 0.82 - 0.08, a[1] + (b[1] - a[1]) * 0.82 - 0.08
            span = WL - bed - 2
            for i in range(4):
                z = bed + 1 + ((t * 7.0 + i * span / 4) % span)
                q = U(bx, by, z)
                qx = q[0] + math.sin(t * 3 + i) * 1.2
                if z < bed + span * 0.5:
                    surf.set_at((int(qx), int(q[1])), (226, 244, 250))
                else:
                    pygame.draw.circle(surf, (226, 244, 250), (int(qx), int(q[1])), 2, 1)
        # -- the glass: waterline, glints, rims
        for a, b in panes:
            pygame.draw.line(surf, (240, 252, 255), U(a[0], a[1], WL), U(b[0], b[1], WL), 1)
            g0 = U(a[0] + (b[0] - a[0]) * 0.16, a[1] + (b[1] - a[1]) * 0.16, bed + 3)
            g1 = U(a[0] + (b[0] - a[0]) * 0.26, a[1] + (b[1] - a[1]) * 0.26, WL - 3)
            pygame.draw.line(surf, (214, 240, 250), g0, g1, 1)
            pygame.draw.lines(surf, (196, 228, 240), True,
                              [U(a[0], a[1], Z0), U(b[0], b[1], Z0), U(b[0], b[1], Z1),
                               U(a[0], a[1], Z1)], 1)
        if has_x and has_y:                        # the bright front corner edge
            pygame.draw.line(surf, (236, 250, 255), U(x1, y1, Z0 + 1), U(x1, y1, Z1 - 1), 1)


# ===================================================================== plants
PLANT_STAGES = 4                                   # 0 = as bought (stock art) .. 3 = in bloom
GROW_AT = (1, 3, 5)                                # growth points for stages 1, 2, 3
STAGE_NAME = ("young", "lush", "tall", "in bloom")
_BLOOM = ((250, 150, 176), (252, 214, 110), (196, 150, 236), (255, 250, 244),
          (250, 138, 112), (150, 196, 250))


def stage_of(growth):
    st = 0
    for i, g in enumerate(GROW_AT):
        if growth >= g:
            st = i + 1
    return st


def bloom_color(seed):
    return _BLOOM[seed % len(_BLOOM)]


def _leaf(surf, base, ang, ln, wd, col, edge=None):
    ca, sa = math.cos(ang), math.sin(ang)
    tip = (base[0] + ca * ln, base[1] + sa * ln)
    mid = (base[0] + ca * ln * 0.45, base[1] + sa * ln * 0.45)
    l = (mid[0] - sa * wd, mid[1] + ca * wd)
    r = (mid[0] + sa * wd, mid[1] - ca * wd)
    pygame.draw.polygon(surf, col, [base, l, tip, r])
    if edge:
        pygame.draw.line(surf, edge, base, (base[0] + ca * ln * 0.8, base[1] + sa * ln * 0.8), 1)


def _flower(surf, x, y, col, r=2, center=(255, 226, 120)):
    x, y = int(x), int(y)
    for a in range(5):
        ang = a * math.tau / 5 - math.pi / 2
        pygame.draw.circle(surf, col, (int(x + math.cos(ang) * r), int(y + math.sin(ang) * r)),
                           max(1, r - 0))
    pygame.draw.circle(surf, center, (x, y), max(1, r - 1))


def paint_plant(surf, P, cx, cy, stage, t=0.0, seed=0):
    """Foliage of the big floor plant at growth ``stage`` 1..3 (the pot is
    isofurn's). (cx, cy) = the piece centre in tile space."""
    base = P(cx, cy)
    c = (base[0], base[1] - 16)
    dk, md, lt = (52, 128, 72), (74, 160, 92), (104, 190, 116)
    sway = math.sin(t * 1.1 + seed) * 0.6
    if stage == 1:                                 # lush: a fuller, wider bush
        for dx, dy, r in ((0, -8, 12), (-9, -1, 9), (9, -2, 9), (-4, 3, 9), (5, 3, 9)):
            pygame.draw.circle(surf, dk, (int(c[0] + dx), int(c[1] + dy + 1)), r)
        for dx, dy, r in ((0, -9, 11), (-8, -2, 8), (8, -3, 8), (-3, 2, 8), (4, 2, 8)):
            pygame.draw.circle(surf, md, (int(c[0] + dx), int(c[1] + dy)), r)
        for ang in (-2.6, -2.0, -1.2, -0.5):
            _leaf(surf, (c[0], c[1] - 4), ang + sway * 0.05, 17, 4, md, dk)
        pygame.draw.circle(surf, lt, (int(c[0] - 4), int(c[1] - 12)), 5)
        pygame.draw.circle(surf, lt, (int(c[0] + 6), int(c[1] - 7)), 3)
        return
    # tall (2) and blooming (3): arching leaves climbing a little trellis
    for dx, dy, r in ((-6, 0, 8), (6, -1, 8), (0, 2, 8)):
        pygame.draw.circle(surf, dk, (int(c[0] + dx), int(c[1] + dy)), r)
    stem_top = (c[0] + sway, c[1] - 30)
    pygame.draw.line(surf, (70, 118, 64), (c[0], c[1] + 2), stem_top, 2)
    leaves = ((-2.8, 16, 5), (-0.35, 16, 5), (-2.4, 19, 5), (-0.75, 19, 5), (-1.9, 15, 4),
              (-1.25, 15, 4))
    for i, (ang, ln, wd) in enumerate(leaves):
        by = c[1] - 4 - i * 4
        _leaf(surf, (c[0] + sway * (i / 6), by), ang + sway * 0.04, ln, wd,
              md if i % 2 else dk, lt)
    for dx, dy, r in ((-4, -2, 7), (4, -3, 7), (0, -14, 7), (-3, -24, 5), (3, -22, 5)):
        pygame.draw.circle(surf, md, (int(c[0] + dx + sway * 0.5), int(c[1] + dy)), r)
    pygame.draw.circle(surf, lt, (int(c[0] - 3 + sway), int(c[1] - 27)), 4)
    pygame.draw.circle(surf, lt, (int(c[0] - 5), int(c[1] - 6)), 3)
    col = bloom_color(seed)
    spots = ((-8, -18), (7, -14), (0, -31), (-6, -6), (8, -26), (-10, -28))
    if stage == 2:                                 # buds
        for dx, dy in spots[:4]:
            bud = _mix(col, (232, 128, 160), 0.45)
            pygame.draw.circle(surf, _dk(bud, 0.85), (int(c[0] + dx + sway), int(c[1] + dy)), 2)
            surf.set_at((int(c[0] + dx + sway), int(c[1] + dy) - 1), _lt(bud, 1.15))
            pygame.draw.line(surf, dk, (c[0] + dx + sway, c[1] + dy + 2),
                             (c[0] + dx + sway, c[1] + dy + 4), 1)
    else:
        for i, (dx, dy) in enumerate(spots):
            _flower(surf, c[0] + dx + sway, c[1] + dy, col if i % 3 else _lt(col, 1.1),
                    r=3 if i < 3 else 2)
        tw = (t * 1.6 + seed) % 3.0
        if tw < 0.35:                              # a twinkle now and then
            sx, sy = c[0] + spots[int(t) % 6][0], c[1] + spots[int(t) % 6][1] - 5
            k = int(3 * (1 - abs(tw - 0.175) / 0.175)) + 1
            pygame.draw.line(surf, (255, 252, 220), (sx - k, sy), (sx + k, sy), 1)
            pygame.draw.line(surf, (255, 252, 220), (sx, sy - k), (sx, sy + k), 1)


def paint_cactus(surf, P, x, y, base, stage, t=0.0, seed=0):
    """Tabletop mini cactus at stage 1..3 (pot included)."""
    from .isofurn import _box
    _box(surf, P, x - 0.07, y - 0.07, x + 0.07, y + 0.07, 5, (190, 120, 80), base=base)
    q = P(x, y)
    cx, cy = int(q[0]), int(q[1] - base)
    g, gd, gl = (96, 168, 96), (70, 136, 76), (132, 196, 120)
    if stage == 1:                                 # taller, two little arms
        pygame.draw.rect(surf, gd, (cx - 3, cy - 18, 7, 14), border_radius=3)
        pygame.draw.rect(surf, g, (cx - 2, cy - 18, 5, 14), border_radius=3)
        pygame.draw.rect(surf, g, (cx - 7, cy - 13, 5, 3), border_radius=2)
        pygame.draw.rect(surf, g, (cx - 7, cy - 16, 3, 5), border_radius=2)
        pygame.draw.rect(surf, g, (cx + 3, cy - 10, 4, 3), border_radius=2)
        pygame.draw.line(surf, gl, (cx - 1, cy - 16), (cx - 1, cy - 7), 1)
        pygame.draw.circle(surf, (236, 150, 170), (cx, cy - 19), 2)
        return
    tall = 22 if stage == 2 else 23
    pygame.draw.ellipse(surf, gd, (cx - 5, cy - tall, 11, tall - 2))
    pygame.draw.ellipse(surf, g, (cx - 4, cy - tall, 9, tall - 3))
    for ax, ay, ah in ((-9, -15, 8), (6, -12, 7)):  # raised arms
        pygame.draw.rect(surf, gd, (cx + ax, cy + ay, 4, ah), border_radius=2)
        pygame.draw.rect(surf, g, (cx + ax, cy + ay - 1, 3, ah), border_radius=2)
        pygame.draw.rect(surf, g, (cx + ax + (2 if ax < 0 else -1), cy + ay + ah - 3, 5, 3),
                         border_radius=1)
    pygame.draw.line(surf, gl, (cx - 1, cy - tall + 3), (cx - 1, cy - 5), 1)
    for i in range(6):                              # spines
        sx = cx - 3 + (i % 3) * 3
        sy = cy - tall + 5 + (i // 3) * 7
        surf.set_at((sx, sy), (240, 236, 210))
    if stage == 3:                                  # crowned with blooms
        col = (244, 120, 160) if seed % 2 == 0 else (252, 170, 90)
        _flower(surf, cx, cy - tall - 1, col, r=3)
        _flower(surf, cx - 8, cy - 17, _lt(col, 1.1), r=2)
        _flower(surf, cx + 7, cy - 14, _lt(col, 1.1), r=2)
    else:
        pygame.draw.circle(surf, (236, 150, 170), (cx, cy - tall - 1), 2)


def paint_vase(surf, P, x, y, base, color, stage, wilt=False, t=0.0, fcol=None, seed=0):
    """Tabletop flower vase: bouquet grows fuller with ``stage`` 1..3; a
    ``wilt`` bouquet droops, faded, with a petal fallen on the table."""
    from .isofurn import _box
    _box(surf, P, x - 0.07, y - 0.07, x + 0.07, y + 0.07, 8, color, base=base)
    q = P(x, y)
    cx, cy = int(q[0]), int(q[1] - base)
    top = cy - 8
    stem = (96, 160, 96) if not wilt else (140, 130, 80)
    base_cols = [(236, 120, 130), (250, 210, 110), (190, 130, 220), (255, 244, 236),
                 (250, 160, 120)]
    if fcol:
        base_cols = [tuple(fcol), _lt(fcol, 1.12), _dk(fcol, 0.88)] + base_cols[:2]
    if wilt:
        for i, dx in enumerate((-5, -1, 3, 6)):
            tip = (cx + dx + (4 if dx > 0 else -4), top - 5 + i % 2 * 2)
            pygame.draw.line(surf, stem, (cx, top), (cx + dx, top - 7), 1)
            pygame.draw.line(surf, stem, (cx + dx, top - 7), tip, 1)
            fc = _mix(base_cols[i % len(base_cols)], (150, 120, 96), 0.6)
            pygame.draw.circle(surf, fc, (int(tip[0]), int(tip[1]) + 1), 2)
        pygame.draw.ellipse(surf, _mix(base_cols[0], (150, 120, 96), 0.6),
                            (cx + 6, cy - 2, 3, 2))            # fallen petal
        return
    n = (5, 7, 9)[max(0, min(2, stage - 1))]
    rnd = random.Random(seed * 13 + 7)
    blooms = []
    for i in range(n):
        ang = -math.pi / 2 + (i - (n - 1) / 2) * (0.34 if stage < 3 else 0.3)
        ln = rnd.uniform(9, 13) + stage * 1.5
        sway = math.sin(t * 1.3 + i) * 0.4
        fx = cx + math.cos(ang) * ln * 0.7 + sway
        fy = top + math.sin(ang) * ln
        blooms.append((fx, fy, base_cols[i % len(base_cols)], i))
        pygame.draw.line(surf, stem, (cx, top), (fx, fy + 2), 1)
    for i in range(2 + stage):                      # leaves around the rim
        side = -1 if i % 2 else 1
        _leaf(surf, (cx, top + 1), -math.pi / 2 + side * (0.9 + i * 0.12), 7 + stage, 2,
              (86, 156, 90))
    if stage >= 2:                                  # baby's breath
        for i in range(6 + stage * 2):
            bx = cx + rnd.uniform(-9, 9)
            by = top - rnd.uniform(6, 14 + stage * 2)
            surf.set_at((int(bx), int(by)), (252, 252, 246))
    for fx, fy, fc, i in blooms:
        r = 3 if (stage == 3 and i % 3 == 0) else 2
        _flower(surf, fx, fy, fc, r=r, center=(255, 240, 180) if r == 2 else (250, 214, 110))
