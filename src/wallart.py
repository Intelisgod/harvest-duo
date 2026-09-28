"""3D wall-mounted decor for the iso HOME (paintings, windows, clocks, shelves...).

The old decor was a flat sprite sheared into the wall plane, so it read like a
sticker. Here every piece is MODELLED in wall space instead:

    u  0..1   across the wall cell (screen-left -> screen-right)
    d  tile   out of the wall toward the room (negative = into the wall)
    z  px     up from the floor

and projected with the room's own iso maths, so frames have a visible
thickness, shelves stick out with their top face lit, a window is a real
recess with a sill, and everything drops a soft shadow onto the wall.

Pieces are cached per (kind, colour, wall side, power, sky) as a small sprite;
only the clock hands are drawn live on top.
"""
import math

import pygame

TW, TH = 64, 32
U_PX = math.hypot(TW / 2, TH / 2)      # screen length of one tile edge (~35.8px)
SPR_W, SPR_H = 84, 124                 # local canvas per wall cell
ORG = (26, 96)                         # local position of the cell's wall-foot corner

_cache = {}


def _lt(c, f=1.18):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.74):
    return tuple(max(0, int(v * f)) for v in c)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class _Wall:
    """Projection + primitives for one wall side, drawing onto `s`."""

    def __init__(self, s, side):
        self.s = s
        self.back = side == "back"

    # ---- projection ----
    def L(self, u, d, z):
        if self.back:                   # wall along +x, room toward +y
            return (ORG[0] + TW / 2 * (u - d), ORG[1] + TH / 2 * (u + d) - z)
        return (ORG[0] + TW / 2 * (u + d), ORG[1] + TH / 2 * (d - u) - z)

    def poly(self, col, pts, width=0):
        q = [self.L(*p) for p in pts]
        if len(col) == 4:
            lay = pygame.Surface(self.s.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(lay, col, q, width)
            self.s.blit(lay, (0, 0))
        else:
            pygame.draw.polygon(self.s, col, q, width)

    def rect_pts(self, u0, u1, z0, z1, d):
        return [(u0, d, z1), (u1, d, z1), (u1, d, z0), (u0, d, z0)]

    def oval_pts(self, uc, zc, rpx, rz, d, n=28):
        """An ellipse lying IN the wall plane: rpx px across, rz px tall."""
        return [(uc + math.cos(a) * rpx / U_PX, d, zc + math.sin(a) * rz)
                for a in (i * 2 * math.pi / n for i in range(n))]

    def flat_oval(self, uc, dc, z, r, n=24):
        """A horizontal circle (radius r tiles) at height z -- lamp shades."""
        return [(uc + math.cos(a) * r, dc + math.sin(a) * r, z)
                for a in (i * 2 * math.pi / n for i in range(n))]

    # ---- solids ----
    def slab(self, u0, u1, z0, z1, d0, d1, col, outline=True):
        """A box on the wall: lit top, the one camera-facing end, the front."""
        ol = _dk(col, 0.5)
        ue = u1 if self.back else u0           # the end that faces the camera
        faces = (
            (_lt(col, 1.2), [(u0, d0, z1), (u1, d0, z1), (u1, d1, z1), (u0, d1, z1)]),
            (_dk(col, 0.78), [(ue, d0, z1), (ue, d1, z1), (ue, d1, z0), (ue, d0, z0)]),
            (col, self.rect_pts(u0, u1, z0, z1, d1)),
        )
        for c, pts in faces:
            self.poly(c, pts)
            if outline:
                self.poly(ol, pts, 1)

    def extrude(self, pts, d0, d1, side_col, front_col, outline=None):
        """Any wall-plane outline given thickness: stacked 1px layers in the
        side colour, then the front face (rims for round/oval pieces)."""
        steps = max(1, int(abs(d1 - d0) * U_PX))
        for i in range(steps):
            d = d0 + (d1 - d0) * i / steps
            self.poly(side_col, [(u, d, z) for u, _, z in pts])
        front = [(u, d1, z) for u, _, z in pts]
        self.poly(front_col, front)
        if outline:
            self.poly(outline, front, 1)

    def shadow(self, pts, a=58, du=0.05, dz=-3):
        """Soft contact shadow cast down-right onto the wall itself."""
        sh = [(u + (du if self.back else -du), 0, z + dz) for u, _, z in pts]
        self.poly((24, 18, 30, a // 2), [(u, d, z - 1) for u, d, z in sh])
        self.poly((24, 18, 30, a), sh)

    def glow(self, uc, zc, rpx, col, a=70):
        """A warm light pool on the wall around a lit fixture."""
        cx, cy = self.L(uc, 0, zc)
        lay = pygame.Surface(self.s.get_size(), pygame.SRCALPHA)
        for i in range(6, 0, -1):
            r = rpx * i / 6
            pygame.draw.ellipse(lay, col + (int(a * (1 - i / 7) ** 1.4),),
                                (cx - r, cy - r * 0.8, 2 * r, 1.6 * r))
        self.s.blit(lay, (0, 0))


# ------------------------------------------------------------------ skies
def sky_key(minutes, weather):
    """Coarse sky state for the window glass (keeps the sprite cache small)."""
    h = (minutes or 12 * 60) / 60.0
    tod = "night" if (h >= 20 or h < 5.5) else "dusk" if h >= 17.5 else "day"
    w = str(weather or "sunny")
    return tod, w


_SKY = {
    "day": ((126, 186, 236), (206, 232, 250)),
    "dusk": ((122, 108, 176), (250, 176, 138)),
    "night": ((22, 28, 62), (54, 62, 110)),
}


def _sky(W, u0, u1, z0, z1, d, key):
    tod, weather = key
    top, bot = _SKY[tod]
    if weather in ("rain", "storm", "fog", "snow"):
        grey = (120, 128, 142) if tod == "day" else (70, 74, 92)
        if weather == "storm":
            grey = _dk(grey, 0.7)
        if weather == "fog":
            grey = (196, 200, 206) if tod == "day" else (96, 100, 114)
        top, bot = _mix(top, grey, 0.8), _mix(bot, grey, 0.7)
    n = 8
    for i in range(n):
        za, zb = z1 - (z1 - z0) * i / n, z1 - (z1 - z0) * (i + 1) / n
        W.poly(_mix(top, bot, i / (n - 1)), W.rect_pts(u0, u1, zb, za, d))
    # far hills over the sill line
    hill = {"day": (118, 176, 110), "dusk": (96, 104, 120), "night": (30, 40, 62)}[tod]
    if weather == "snow":
        hill = (226, 232, 240) if tod != "night" else (120, 126, 150)
    pts = [(u0, d, z0)]
    for i in range(9):
        u = u0 + (u1 - u0) * i / 8
        pts.append((u, d, z0 + 5 + 3 * math.sin(i * 1.3)))
    pts.append((u1, d, z0))
    W.poly(hill, pts)
    rnd = [(0.21, 0.8), (0.63, 0.55), (0.42, 0.33), (0.82, 0.72), (0.3, 0.52),
           (0.72, 0.9), (0.52, 0.66), (0.12, 0.4)]
    if tod == "night" and weather in ("sunny", "windy"):
        for fu, fz in rnd:
            W.poly((250, 246, 220), W.rect_pts(u0 + (u1 - u0) * fu, u0 + (u1 - u0) * fu + 0.03,
                                              z0 + (z1 - z0) * fz, z0 + (z1 - z0) * fz + 1, d))
        m = W.oval_pts(u0 + (u1 - u0) * 0.74, z0 + (z1 - z0) * 0.78, 3, 3, d, 12)
        W.poly((250, 244, 206), m)
    elif tod == "day" and weather in ("sunny", "windy"):
        c = W.oval_pts(u0 + (u1 - u0) * 0.26, z0 + (z1 - z0) * 0.62, 4, 3, d, 12)
        W.poly((255, 255, 255), c)
        W.poly((255, 255, 255), W.oval_pts(u0 + (u1 - u0) * 0.36, z0 + (z1 - z0) * 0.64,
                                           4, 3, d, 12))
    if weather in ("rain", "storm"):
        for fu, fz in rnd:
            ua = u0 + (u1 - u0) * fu
            za = z0 + (z1 - z0) * fz
            W.poly((196, 214, 236), [(ua, d, za + 4), (ua - 0.04, d, za - 3)], 1)
    elif weather == "snow":
        for fu, fz in rnd:
            W.poly((255, 255, 255), W.rect_pts(u0 + (u1 - u0) * fu, u0 + (u1 - u0) * fu + 0.04,
                                              z0 + (z1 - z0) * fz, z0 + (z1 - z0) * fz + 2, d))


# ------------------------------------------------------------------ pieces
def _painting(W, color):
    frame = (158, 112, 64)
    fr = W.rect_pts(0.17, 0.83, 30, 58, 0)
    W.shadow(fr)
    W.slab(0.17, 0.83, 30, 58, 0, 0.07, frame)
    # canvas: a little landscape tinted by the chosen colour, set IN the frame
    u0, u1, z0, z1, d = 0.25, 0.75, 35, 53, 0.07
    sky = _mix(_lt(color, 1.35), (236, 240, 248), 0.45)
    W.poly(sky, W.rect_pts(u0, u1, z0, z1, d))
    W.poly((250, 232, 170), W.oval_pts(0.62, 48, 2.6, 2.6, d, 12))        # sun
    W.poly(_mix(color, (90, 150, 100), 0.35),
           [(u0, d, z0), (u0, d, 42), (0.38, d, 46), (0.52, d, 41), (0.62, d, 43),
            (u1, d, 39), (u1, d, z0)])                                    # hills
    W.poly(_dk(_mix(color, (70, 120, 80), 0.5), 0.8),
           [(u0, d, z0), (u0, d, 38), (0.45, d, 36), (u1, d, 38), (u1, d, z0)])
    # inner bevel: shaded top/left lip, lit bottom/right lip
    W.poly(_dk(frame, 0.55), [(u0, d, z1), (u1, d, z1)], 1)
    W.poly(_dk(frame, 0.55), [(u0, d, z1), (u0, d, z0)], 1)
    W.poly(_lt(frame, 1.35), [(u0, d, z0), (u1, d, z0)], 1)
    W.poly((255, 246, 220), [(0.19, 0.07, 56), (0.27, 0.07, 56)], 1)      # gilt glint


def _painting_art(W, color, art):
    """A Painting showing a gallery artwork (studio pixel art, 1 art pixel =
    1 screen column) in a slightly larger gilt frame. False = not art."""
    frame = (158, 112, 64)
    fr = W.rect_pts(0.07, 0.93, 26, 62, 0)
    W.shadow(fr)
    W.slab(0.07, 0.93, 26, 62, 0, 0.06, frame)
    d = 0.06
    W.poly((250, 246, 236), W.rect_pts(0.105, 0.895, 30, 58, d))              # the mat
    from . import studio
    u0, u1, z0, z1 = 0.125, 0.875, 32, 56
    if not studio.draw_on_face(W.s, W.L(u0, d, z1), W.L(u1, d, z1), W.L(u0, d, z0), art):
        return False
    W.poly(_dk(frame, 0.55), [(0.105, d, 58), (0.895, d, 58)], 1)              # inner bevel
    W.poly(_dk(frame, 0.55), [(0.105, d, 58), (0.105, d, 30)], 1)
    W.poly(_lt(frame, 1.35), [(0.105, d, 30), (0.895, d, 30)], 1)
    W.poly((236, 200, 110), W.rect_pts(0.44, 0.56, 27, 28.6, d + 0.004))        # brass plaque
    W.poly((255, 246, 220), [(0.09, d, 60), (0.19, d, 60)], 1)                 # gilt glint
    return True


def _clock(W, color):
    rim = W.oval_pts(0.5, 43, 12, 12, 0)
    W.shadow(rim)
    W.extrude(rim, 0, 0.09, _dk(color, 0.62), color, outline=_dk(color, 0.45))
    face = W.oval_pts(0.5, 43, 9, 9, 0.09)
    W.poly((248, 246, 240), face)
    W.poly(_dk(color, 0.7), face, 1)
    for k in range(12):                                   # hour ticks
        a = k * math.pi / 6
        big = k % 3 == 0
        r0, r1 = (6.2 if big else 7.2), 8.2
        W.poly((70, 64, 76) if big else (160, 156, 166),
               [(0.5 + math.cos(a) * r0 / U_PX, 0.09, 43 + math.sin(a) * r0),
                (0.5 + math.cos(a) * r1 / U_PX, 0.09, 43 + math.sin(a) * r1)], 1)
    W.poly((255, 255, 255), [(0.38, 0.09, 49), (0.43, 0.09, 51.5)], 1)    # glass glint


def clock_hands(W, minutes):
    h = (minutes / 60.0) % 12
    m = minutes % 60
    for ang, ln, col in ((h / 12 * 2 * math.pi, 5.0, (40, 36, 46)),
                         (m / 60 * 2 * math.pi, 7.4, (70, 64, 80))):
        W.poly(col, [(0.5, 0.09, 43),
                     (0.5 + math.sin(ang) * ln / U_PX, 0.09, 43 + math.cos(ang) * ln)], 2)
    W.poly((214, 88, 88), W.oval_pts(0.5, 43, 1.2, 1.2, 0.09, 8))


def _window(W, color, sky):
    u0, u1, z0, z1 = 0.15, 0.85, 27, 61
    rec = -0.10                                           # glass plane, inside the wall
    W.shadow(W.rect_pts(0.10, 0.90, 22, 65, 0), a=40)
    # the recess: glass + mullions at the glass plane, the visible reveal
    # faces, all clipped to the opening in the wall face
    lay = pygame.Surface(W.s.get_size(), pygame.SRCALPHA)
    L = _Wall(lay, "back" if W.back else "left")
    _sky(L, u0 - 0.1, u1 + 0.1, z0 - 4, z1 + 4, rec, sky)
    sash = _lt(color, 1.1)
    L.poly(sash, L.rect_pts(0.485, 0.515, z0 - 4, z1 + 4, rec))          # mullion
    L.poly(sash, L.rect_pts(u0 - 0.1, u1 + 0.1, 44, 46, rec))            # transom
    L.poly((255, 255, 255, 70), [(0.22, rec, 58), (0.34, rec, 58), (0.24, rec, 48),
                                 (0.18, rec, 48)])                        # glint
    jamb = u0 if W.back else u1                             # the side jamb we see
    reveal = _dk((226, 220, 210), 0.86)
    L.poly(_lt(reveal, 1.08), [(u0, rec, z0), (u1, rec, z0), (u1, 0, z0), (u0, 0, z0)])
    L.poly(reveal, [(jamb, rec, z0), (jamb, rec, z1), (jamb, 0, z1), (jamb, 0, z0)])
    L.poly(_dk(reveal, 0.8), [(u0, rec, z1), (u1, rec, z1), (u1, 0, z1), (u0, 0, z1)])
    mask = pygame.Surface(W.s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255),
                        [W.L(*p) for p in W.rect_pts(u0, u1, z0, z1, 0)])
    lay.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    W.s.blit(lay, (0, 0))
    # casing proud of the wall + a sill you could put a plant on
    trim = (246, 242, 236)
    W.slab(0.10, 0.90, z1, z1 + 4, 0, 0.05, trim)                          # head
    W.slab(0.10, u0, z0, z1, 0, 0.05, trim)                                # jambs
    W.slab(u1, 0.90, z0, z1, 0, 0.05, trim)
    W.slab(0.07, 0.93, z0 - 4, z0, 0, 0.17, trim)                          # sill


def _wall_shelf(W, color, bare=False):
    W.shadow(W.rect_pts(0.08, 0.92, 30, 37, 0), a=64, dz=-4)
    for bu in (0.20, 0.76):                                  # brackets (wedges)
        W.poly(_dk(color, 0.62), [(bu, 0, 34), (bu, 0.2, 34), (bu, 0, 26)])
        W.poly(_dk(color, 0.45), [(bu, 0, 34), (bu, 0.2, 34), (bu, 0, 26)], 1)
    W.slab(0.08, 0.92, 34, 37, 0, 0.30, color)
    if bare:                                  # the player's own things live here
        return
    items = [  # (u0, u1, d0, d1, z-height, colour) -- books + a plant pot
        (0.14, 0.20, 0.05, 0.25, 11, (196, 76, 76)),
        (0.20, 0.26, 0.05, 0.25, 9, (84, 126, 196)),
        (0.26, 0.32, 0.05, 0.25, 12, (92, 164, 100)),
        (0.33, 0.38, 0.05, 0.25, 8, (230, 196, 110)),
        (0.62, 0.76, 0.08, 0.22, 6, (196, 116, 80)),
    ]
    key = (lambda it: it[0] + it[2]) if W.back else (lambda it: -it[1] + it[2])
    for u0, u1, d0, d1, h, c in sorted(items, key=key):
        W.slab(u0, u1, 37, 37 + h, d0, d1, c)
        if c == (196, 116, 80):                              # the pot's plant
            for lu, lz, r in ((0.66, 47, 3.4), (0.73, 46, 3.0), (0.69, 50, 3.2)):
                W.poly((70, 150, 84), W.oval_pts(lu, lz, r, r, 0.15, 10))
                W.poly((104, 186, 110), W.oval_pts(lu - 0.01, lz + 1, r - 1.5, r - 1.5,
                                                   0.15, 8))
    W.poly((236, 200, 96), W.oval_pts(0.50, 39.5, 2.4, 2.4, 0.16, 10))   # trinket
    W.poly((255, 240, 180), W.oval_pts(0.49, 40.5, 0.9, 0.9, 0.16, 6))


def _wall_lamp(W, color, on):
    if on:
        W.glow(0.5, 42, 26, (255, 220, 150), a=90)
    plate = W.rect_pts(0.42, 0.58, 38, 51, 0)
    W.shadow(plate, a=50)
    W.slab(0.42, 0.58, 38, 51, 0, 0.03, (150, 148, 156))                  # back plate
    W.slab(0.48, 0.52, 44, 46, 0.03, 0.20, (120, 118, 128))               # arm
    # bell shade: wide rim below, narrow crown on top (a real cone)
    lo = W.flat_oval(0.5, 0.24, 39, 0.20)
    hi = W.flat_oval(0.5, 0.24, 51, 0.12)
    pts = [W.L(*p) for p in lo + hi]
    shade = _lt(color, 1.25) if on else color
    hull = _hull(pts)
    pygame.draw.polygon(W.s, _dk(shade, 0.86), hull)
    # lit half of the cone (the camera-left side catches the room light)
    half = [W.L(*p) for p in lo[len(lo) // 4: 3 * len(lo) // 4]]
    pygame.draw.polygon(W.s, shade, _hull(half + [W.L(0.5, 0.24, 51)]))
    pygame.draw.polygon(W.s, _dk(color, 0.5), hull, 1)
    front_rim = [W.L(*p) for p in lo[:len(lo) // 2 + 1]]                 # hem band
    pygame.draw.lines(W.s, _lt(shade, 1.3), False, front_rim, 2)
    for k in (0.3, 0.7):                                                  # pleats
        a = lo[int(len(lo) * (0.5 - k / 2)) % len(lo)]
        b = hi[int(len(hi) * (0.5 - k / 2)) % len(hi)]
        pygame.draw.line(W.s, _dk(shade, 0.8), W.L(*a), W.L(*b), 1)
    W.poly(_lt(shade, 1.12), hi)                                          # crown top
    W.poly(_dk(color, 0.5), hi, 1)
    if on:
        W.poly((255, 250, 222), W.flat_oval(0.5, 0.24, 38.5, 0.11))       # bulb glow
        lay = pygame.Surface(W.s.get_size(), pygame.SRCALPHA)
        a, b = W.L(0.3, 0.24, 38), W.L(0.7, 0.24, 38)
        c1, c2 = W.L(0.18, 0.1, 18), W.L(0.82, 0.1, 18)
        pygame.draw.polygon(lay, (255, 236, 170, 46), [a, b, c2, c1])     # light spill
        W.s.blit(lay, (0, 0))


def _wall_mirror(W, color):
    rim = W.oval_pts(0.5, 43, 10, 16, 0)
    W.shadow(rim)
    W.extrude(rim, 0, 0.07, _dk(color, 0.62), color, outline=_dk(color, 0.45))
    glass = W.oval_pts(0.5, 43, 7.5, 13, 0.07)
    W.poly((178, 204, 218), glass)
    W.poly((206, 226, 236), W.oval_pts(0.47, 46, 5.5, 9, 0.07))
    W.poly((236, 246, 250), [(0.38, 0.07, 44), (0.49, 0.07, 55), (0.52, 0.07, 53),
                             (0.41, 0.07, 41)])                          # glint band
    W.poly((250, 252, 255), [(0.55, 0.07, 36), (0.60, 0.07, 41)], 1)
    W.poly(_dk(color, 0.55), glass, 1)
    W.poly(_lt(color, 1.3), W.oval_pts(0.5, 60, 2, 2, 0.07, 10))          # top knot


def _neon(W, color, on):
    tube = _lt(color, 1.5) if on else (86, 88, 100)
    if on:
        W.glow(0.5, 43, 30, _lt(color, 1.3), a=80)
    board = W.rect_pts(0.12, 0.88, 31, 55, 0)
    W.shadow(board, a=46)
    W.slab(0.12, 0.88, 31, 55, 0, 0.03, (40, 40, 50))                     # acrylic
    # a heart bent from glass tube, standing off the board on little clips
    heart = []
    for i in range(36):
        t = i / 36 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        heart.append((0.5 + x * 0.62 / U_PX, 0.06, 44 + y * 0.62))
    lay = pygame.Surface(W.s.get_size(), pygame.SRCALPHA)
    q = [W.L(*p) for p in heart]
    if on:
        pygame.draw.lines(lay, tube + (70,), True, q, 5)
    pygame.draw.lines(lay, tube + (255,), True, q, 2)
    if on:
        pygame.draw.lines(lay, (255, 250, 255, 170), True, q, 1)
    W.s.blit(lay, (0, 0))
    for cu, cz in ((0.36, 50), (0.64, 50), (0.5, 35)):                    # clips
        W.poly((170, 170, 180), W.rect_pts(cu - 0.015, cu + 0.015, cz - 1, cz + 1, 0.04))


def _hull(pts):
    pts = sorted(set((round(x, 2), round(y, 2)) for x, y in pts))
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


# ---------------------------------------------- 2026-09 catalogue expansion
def _rot_rect(uc, zc, w_px, h_px, ang, d):
    """A rectangle in the wall plane (w/h in px), turned `ang` radians."""
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for x, y in ((-w_px / 2, h_px / 2), (w_px / 2, h_px / 2), (w_px / 2, -h_px / 2),
                 (-w_px / 2, -h_px / 2)):
        rx, ry = x * ca - y * sa, x * sa + y * ca
        out.append((uc + rx / U_PX, d, zc + ry))
    return out


def _by_depth(W, items, key_u):
    """Painter order for little pieces standing on a wall shelf."""
    return sorted(items, key=(lambda it: key_u(it)) if W.back else (lambda it: -key_u(it)))


def _spice_rack(W, color):
    W.shadow(W.rect_pts(0.10, 0.90, 26, 60, 0), a=50)
    W.slab(0.10, 0.90, 26, 60, 0, 0.03, _dk(color, 0.78))               # back board
    spices = [(196, 70, 50), (232, 184, 60), (98, 150, 80), (70, 58, 50),
              (240, 236, 226), (160, 96, 60), (214, 120, 60), (120, 160, 110)]
    for row, z in enumerate((28, 44)):
        W.slab(0.10, 0.90, z, z + 2, 0.03, 0.26, color)                   # shelf
        jars = [(0.16 + k * 0.19, spices[(k + row * 4) % len(spices)]) for k in range(4)]
        for u0, c in _by_depth(W, jars, lambda j: j[0]):
            glass = (226, 236, 240)
            W.slab(u0, u0 + 0.12, z + 2, z + 11, 0.07, 0.21, glass)
            W.poly(c, W.rect_pts(u0 + 0.01, u0 + 0.11, z + 3, z + 8, 0.21))  # contents
            W.poly((250, 246, 234), W.rect_pts(u0 + 0.03, u0 + 0.09, z + 4, z + 7, 0.21))
            W.slab(u0, u0 + 0.12, z + 11, z + 13, 0.07, 0.21, _dk(color, 0.7))  # lid
        W.slab(0.10, 0.90, z + 5, z + 6, 0.26, 0.29, _lt(color, 1.1))       # front rail
    for u in (0.10, 0.86):                                                 # side cheeks
        W.slab(u, u + 0.04, 26, 60, 0.03, 0.29, color)


def _towel_rack(W, color):
    W.shadow(W.rect_pts(0.16, 0.84, 20, 46, 0), a=44, du=0.04)
    metal = (196, 200, 208)
    for u in (0.16, 0.80):                                                 # wall posts
        W.slab(u, u + 0.04, 40, 46, 0, 0.18, metal)
    W.slab(0.14, 0.86, 42, 44, 0.14, 0.18, _lt(metal, 1.05))               # the rail
    stripe = _lt(color, 1.35) if sum(color) < 600 else _dk(color, 0.8)
    W.slab(0.24, 0.76, 22, 44, 0.18, 0.21, color, outline=True)           # towel, front
    W.slab(0.24, 0.76, 44, 46, 0.12, 0.21, _lt(color, 1.08))              # the fold over
    for z in (25, 28):
        W.poly(stripe, W.rect_pts(0.24, 0.76, z, z + 1.5, 0.21))
    for k in range(6):                                                    # fringe
        u = 0.27 + k * 0.09
        W.poly(_dk(color, 0.8), [(u, 0.21, 22), (u, 0.21, 19)], 1)
    W.slab(0.62, 0.70, 33, 35, 0.0, 0.10, metal)                          # hook + flannel
    W.slab(0.60, 0.72, 24, 34, 0.10, 0.13, (250, 250, 252))


def _string_lights(W, color, on):
    def z_at(u):
        return 60 - 6 * math.sin(math.pi * ((u * 2) % 1.0))
    wire = [(i / 40, 0.03, z_at(i / 40)) for i in range(41)]
    pygame.draw.lines(W.s, (70, 74, 66), False, [W.L(*p) for p in wire], 1)
    for u in (0.0, 0.5, 1.0):                                              # tacks
        W.poly((110, 110, 116), W.oval_pts(u, 60, 1.2, 1.2, 0.03, 8))
    warm = (255, 226, 150)
    cols = [color, warm, _mix(color, warm, 0.5), warm]
    for k, u in enumerate((0.12, 0.25, 0.38, 0.62, 0.75, 0.88)):
        z = z_at(u) - 3
        c = cols[k % len(cols)]
        if on:
            W.glow(u, z - 1, 9, _lt(c, 1.2), a=90)
        W.poly((96, 100, 92), W.rect_pts(u - 0.01, u + 0.01, z + 1, z + 3, 0.04))   # socket
        bulb = W.oval_pts(u, z - 1, 1.8, 2.6, 0.05, 10)
        W.poly(_lt(c, 1.25) if on else _mix(c, (120, 120, 126), 0.55), bulb)
        if on:
            W.poly((255, 252, 236), W.oval_pts(u - 0.005, z - 0.5, 0.7, 1.0, 0.05, 6))


def _wall_calendar(W, color):
    W.poly((150, 146, 150), [(0.5, 0.01, 62), (0.30, 0.01, 57), (0.70, 0.01, 57), (0.5, 0.01, 62)], 1)
    W.poly((120, 116, 124), W.oval_pts(0.5, 62, 1.2, 1.2, 0.02, 8))      # the nail
    page = W.rect_pts(0.26, 0.74, 24, 57, 0)
    W.shadow(page, a=50)
    W.slab(0.26, 0.74, 24, 57, 0, 0.02, (250, 248, 242))
    d = 0.02
    W.poly(_lt(color, 1.3), W.rect_pts(0.29, 0.71, 44, 55, d))             # the picture:
    W.poly(_mix(color, (90, 160, 100), 0.4), [(0.29, d, 44), (0.29, d, 48), (0.45, d, 51),
                                              (0.58, d, 47), (0.71, d, 50), (0.71, d, 44)])
    for fu in (0.40, 0.56):                                               # two flowers
        W.poly((250, 250, 252), W.oval_pts(fu, 49, 1.6, 1.6, d, 8))
        W.poly((250, 210, 90), W.oval_pts(fu, 49, 0.7, 0.7, d, 6))
    for k in range(7):                                                    # spiral binding
        W.poly((70, 70, 80), W.oval_pts(0.30 + k * 0.066, 56.5, 0.7, 0.9, d, 6))
    W.poly(color, W.rect_pts(0.29, 0.71, 41, 43, d))                      # month bar
    for r in range(5):                                                    # the days
        for cday in range(7):
            u = 0.31 + cday * 0.063
            z = 38 - r * 3
            W.poly((150, 146, 156), W.rect_pts(u, u + 0.025, z, z + 1, d))
    hu, hz = 0.31 + 4 * 0.063, 38 - 2 * 3                                  # a date to remember
    heart = []
    for i in range(20):
        t = i / 20 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        heart.append((hu + 0.012 + x * 0.16 / U_PX, d, hz + 0.5 + y * 0.16))
    W.poly((226, 70, 96), heart, 1)


def _memory_board(W, color):
    fr = W.rect_pts(0.08, 0.92, 26, 62, 0)
    W.shadow(fr)
    W.slab(0.08, 0.92, 26, 62, 0, 0.05, color)                            # frame
    cork = (198, 152, 100)
    d = 0.05
    W.poly(cork, W.rect_pts(0.13, 0.87, 29, 59, d))
    for k in range(14):                                                    # cork speckle
        u = 0.15 + (k * 0.37) % 0.70
        z = 31 + (k * 7.3) % 26
        W.poly(_dk(cork, 0.82), W.rect_pts(u, u + 0.012, z, z + 1, d))
    W.poly(_dk(color, 0.6), W.rect_pts(0.13, 0.87, 29, 59, d), 1)
    photos = [(0.30, 48, -0.12, ((240, 170, 190), "heart")),
              (0.58, 50, 0.10, ((150, 200, 236), "sun")),
              (0.42, 36, 0.06, ((170, 214, 170), "us"))]
    for uc, zc, ang, (bg, what) in photos:
        W.poly((250, 250, 248), _rot_rect(uc, zc, 11, 12, ang, d + 0.01))   # polaroid
        W.poly(bg, _rot_rect(uc, zc + 1, 8.5, 8, ang, d + 0.01))
        if what == "heart":
            h = []
            for i in range(16):
                t = i / 16 * 2 * math.pi
                x = 16 * math.sin(t) ** 3
                y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
                h.append((uc + x * 0.17 / U_PX, d + 0.01, zc + 1 + y * 0.17))
            W.poly((220, 60, 90), h)
        elif what == "sun":
            W.poly((250, 214, 90), W.oval_pts(uc + 0.03, zc + 2, 2, 2, d + 0.01, 8))
            W.poly((110, 176, 110), _rot_rect(uc, zc - 2, 8.5, 2.5, ang, d + 0.01))
        else:
            for k, hc in ((-1, (90, 60, 40)), (1, (230, 190, 90))):          # two little faces
                W.poly((250, 218, 190), W.oval_pts(uc + k * 0.05, zc + 1, 1.8, 1.8, d + 0.01, 8))
                W.poly(hc, W.rect_pts(uc + k * 0.05 - 0.05, uc + k * 0.05 + 0.05,
                                      zc + 2.4, zc + 3.3, d + 0.01))
        pin = _rot_rect(uc, zc + 6, 1, 1, 0, d + 0.02)
        W.poly((220, 64, 64) if what != "sun" else (70, 110, 220), pin)
    for uc, zc, c in ((0.72, 36, (250, 232, 120)), (0.22, 34, (170, 230, 206))):   # notes
        W.poly(c, _rot_rect(uc, zc, 9, 9, 0.08, d + 0.01))
        for k in range(3):
            W.poly(_dk(c, 0.6), _rot_rect(uc, zc + 2 - k * 2, 6, 0.6, 0.08, d + 0.012))
        W.poly((96, 180, 96), W.oval_pts(uc, zc + 4.5, 1, 1, d + 0.02, 6))


def _hanging_plant(W, color):
    metal = (96, 90, 96)
    W.shadow(W.rect_pts(0.44, 0.56, 56, 64, 0), a=40)
    W.slab(0.44, 0.56, 56, 64, 0, 0.03, metal)                             # wall plate
    W.slab(0.48, 0.52, 61, 63, 0.03, 0.40, metal)                          # arm
    W.poly(metal, [(0.5, 0.03, 57), (0.5, 0.03, 60), (0.5, 0.22, 61)])     # brace
    hook = (0.5, 0.36, 61)
    pot_c, pot_d, z0, z1 = 0.5, 0.36, 30, 38
    lo = [W.L(*p) for p in W.flat_oval(pot_c, pot_d, z0, 0.10)]
    hi = [W.L(*p) for p in W.flat_oval(pot_c, pot_d, z1, 0.15)]
    # trailing vines behind the pot first (the far ones)
    vines = [(-0.12, 0.06, 14), (0.13, -0.02, 18), (-0.02, 0.14, 10), (0.08, 0.12, 16),
             (-0.14, -0.06, 20)]

    def vine(du, dd, zend):
        pts = []
        for k in range(8):
            t = k / 7
            pts.append((pot_c + du * (1 + t * 0.4), pot_d + dd, z1 - 2 - t * (z1 - 2 - zend)))
        pygame.draw.lines(W.s, (74, 132, 74), False, [W.L(*p) for p in pts], 1)
        for k, p in enumerate(pts[1:]):
            s = 1.9 - k * 0.12
            c = (84, 164, 92) if k % 2 else (62, 136, 76)
            W.poly(c, W.oval_pts(p[0] + (0.02 if k % 2 else -0.02), p[2], s, s * 0.8, p[1], 8))
    back = [v for v in vines if (v[1] < 0.05)]
    front = [v for v in vines if v not in back]
    for v in back:
        vine(*v)
    hull_pts = _hull(lo + hi)
    pygame.draw.polygon(W.s, _dk(color, 0.82), hull_pts)
    half = [p for p in lo + hi if p[0] <= W.L(pot_c, pot_d, z0)[0]]
    if len(half) >= 3:
        pygame.draw.polygon(W.s, color, _hull(half))
    pygame.draw.polygon(W.s, _dk(color, 0.5), hull_pts, 1)
    pygame.draw.polygon(W.s, (86, 64, 46), hi)                             # soil
    pygame.draw.polygon(W.s, _lt(color, 1.15), hi, 2)
    for a in (0.2, 2.3, 4.3):                                              # ropes
        rim = (pot_c + math.cos(a) * 0.15, pot_d + math.sin(a) * 0.15, z1)
        W.poly((226, 214, 190), [hook, rim], 1)
    for du, dd, z, r in ((-0.06, 0.0, 41, 3.2), (0.06, 0.02, 42, 3.0), (0.0, -0.04, 44, 3.4),
                         (0.02, 0.06, 40, 2.8)):
        W.poly((70, 150, 84), W.oval_pts(pot_c + du, z, r, r * 0.8, pot_d + dd, 10))
        W.poly((104, 186, 110), W.oval_pts(pot_c + du - 0.01, z + 0.8, r * 0.5, r * 0.4,
                                           pot_d + dd, 8))
    for v in front:
        vine(*v)
    W.poly((150, 150, 156), W.oval_pts(0.5, 60, 1.2, 1.4, 0.36, 8), 1)   # hook ring


def _generic(W, color):
    fr = W.rect_pts(0.2, 0.8, 32, 56, 0)
    W.shadow(fr)
    W.slab(0.2, 0.8, 32, 56, 0, 0.06, color)


# ------------------------------------------------------------------ API
# optional lookup: fn(kind, side, foot) -> the art string (studio.encode) a
# piece shows, or None -- set by systems/showpiece_system.py so a Painting can
# display a gallery artwork painted at the easel
ART_FOR = None


def _art_for(kind, side, foot):
    if ART_FOR is None or kind != "painting":
        return None
    try:
        return ART_FOR(kind, side, foot)
    except Exception:
        from .systems import hooks as _hooks    # logged / strict like any hook
        _hooks._log_hook_error("_show_wall_art")
        if _hooks._STRICT:
            raise
        return None


def sprite(kind, color, side, on=True, sky=("day", "sunny"), bare=False, art=None):
    """Cached local sprite of one wall piece (see ORG for its anchor).
    `bare`: a wall shelf without its built-in clutter (the player's decor
    stands on it instead). `art`: a gallery artwork a Painting shows."""
    color = tuple(color[:3])
    key = (kind, color, side, bool(on), sky if kind == "window" else None,
           bool(bare) and kind == "wall_shelf", art)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((SPR_W, SPR_H), pygame.SRCALPHA)
        W = _Wall(s, side)
        if kind == "painting" and art:
            if not _painting_art(W, color, art):
                s.fill((0, 0, 0, 0))
                _painting(W, color)
        elif kind == "painting":
            _painting(W, color)
        elif kind == "clock":
            _clock(W, color)
        elif kind == "window":
            _window(W, color, sky)
        elif kind == "wall_shelf":
            _wall_shelf(W, color, bare)
        elif kind == "wall_lamp":
            _wall_lamp(W, color, on)
        elif kind == "wall_mirror":
            _wall_mirror(W, color)
        elif kind == "neon_sign":
            _neon(W, color, on)
        elif kind == "spice_rack":                  # 2026-09 catalogue expansion
            _spice_rack(W, color)
        elif kind == "towel_rack":
            _towel_rack(W, color)
        elif kind == "string_lights":
            _string_lights(W, color, on)
        elif kind == "wall_calendar":
            _wall_calendar(W, color)
        elif kind == "memory_board":
            _memory_board(W, color)
        elif kind == "hanging_plant":
            _hanging_plant(W, color)
        else:
            _generic(W, color)
        if len(_cache) > 160:
            _cache.clear()
        _cache[key] = s
    return s


def blit(scr, foot, kind, color, side, on=True, sky=("day", "sunny"), minutes=None,
         alpha=255, bare=False):
    """Draw a wall piece whose wall cell starts at screen point `foot` (the
    cell's floor-level corner: P(c, 1) on the back wall, P(1, c+1) on the
    left). `minutes` (game clock) drives a clock's hands."""
    spr = sprite(kind, color, side, on, sky, bare, art=_art_for(kind, side, foot))
    top_left = (foot[0] - ORG[0], foot[1] - ORG[1])
    if alpha < 255:
        spr = spr.copy()
        spr.set_alpha(alpha)
    scr.blit(spr, top_left)
    if kind == "clock":
        lay = pygame.Surface((SPR_W, SPR_H), pygame.SRCALPHA)
        clock_hands(_Wall(lay, side), 10 * 60 + 10 if minutes is None else minutes)
        if alpha < 255:
            lay.set_alpha(alpha)
        scr.blit(lay, top_left)
