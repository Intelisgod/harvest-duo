"""Mist City world — Main Street, the first of three side-scrolling zones.

``ZoneMixin`` is the shared zone interface (exit door, acid-rain covers, hazards
hook, zombie mix); zones.py adds the Old Factory and the Clock Tower courtyard.

Owner: Chat 7 (Mist City). Geometry (ground line, one-way platforms,
breakable crates) plus the painted backdrop: silhouetted towers, a frozen
clock face, ruined shopfronts (pharmacy / mechanic / gas), wrecked cars and
drifting ground fog. Palette is pastel-horror — murky grey-greens with soft
neon accents — so it still sits comfortably next to the sunny top-down art.

No game state lives here; ``MistRun`` (mist_system) owns the run.
"""
import math
import random
import pygame
from ..settings import SCREEN_W, SCREEN_H

LEVEL_W = 3360
GROUND_Y = 600                  # top of the road surface (feet line)
GRAVITY = 1700.0                # px/s^2 — shared by players & anything that falls

# ---- palette (pastel-horror) ----
SKY_TOP = (50, 56, 66)
SKY_BOT = (86, 96, 94)
FAR_COL = (42, 48, 56)
MID_COL = (58, 66, 68)
ROAD = (94, 100, 104)
ROAD_EDGE = (122, 128, 130)
ROAD_CRACK = (72, 78, 82)
FACADE = (78, 84, 88)
FACADE_DARK = (62, 68, 72)
NEON_MINT = (140, 235, 190)
NEON_PINK = (236, 152, 202)
NEON_AMBER = (242, 206, 130)
FOG_COL = (172, 192, 182)

AWNING_H = 116                  # platform height of shop awnings (jump apex ~124)

# crate drop tables — item ids registered in loot.MATERIALS (Chat 1)
CRATE_DROPS = [
    ("scrap_iron", 0.50, (1, 2)),
    ("wire", 0.35, (1, 2)),
    ("old_coin", 0.30, (1, 1)),
    ("old_battery", 0.12, (1, 1)),
]
RARE_CRATE_DROPS = [
    ("tainted_crystal", 0.70, (1, 1)),
    ("gear_scrap", 0.60, (1, 2)),
    ("old_battery", 0.50, (1, 2)),
    ("mutant_herb", 0.40, (1, 1)),
]


class Crate:
    """Breakable scenery — whack it with the sword until it pops."""

    def __init__(self, x, y, rare=False):
        self.w, self.h = (40, 34) if rare else (34, 30)
        self.x, self.y = float(x), float(y)     # x = centre, y = bottom (rests on a surface)
        self.rare = rare
        self.max_hp = 4 if rare else 2
        self.hp = self.max_hp
        self.drops = RARE_CRATE_DROPS if rare else CRATE_DROPS

    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h), self.w, self.h)

    def draw(self, surf, camx, t):
        r = self.rect().move(-int(camx), 0)
        if r.right < -8 or r.left > SCREEN_W + 8:
            return
        if getattr(self, "supply", False):                          # air-dropped supplies
            pygame.draw.rect(surf, (128, 140, 100), r, border_radius=4)
            pygame.draw.rect(surf, (88, 98, 70), r, 2, border_radius=4)
            pygame.draw.rect(surf, (238, 236, 226), (r.centerx - 3, r.top + 6, 6, r.h - 12))
            pygame.draw.rect(surf, (238, 236, 226), (r.left + 8, r.centery - 3, r.w - 16, 6))
            pygame.draw.rect(surf, NEON_PINK, (r.left, r.top + 4, r.w, 3))
        elif self.rare:
            g = int(3 + 2 * math.sin(t * 3.0))
            pygame.draw.rect(surf, (88, 142, 128), r.inflate(g, g), border_radius=6)
            pygame.draw.rect(surf, (50, 90, 86), r, border_radius=4)
            pygame.draw.rect(surf, (86, 132, 122), r, 2, border_radius=4)
            pygame.draw.rect(surf, NEON_PINK, (r.centerx - 4, r.centery - 2, 8, 9),
                             border_radius=2)                      # pink lock plate
        else:
            pygame.draw.rect(surf, (150, 122, 92), r, border_radius=3)
            pygame.draw.rect(surf, (112, 88, 64), r, 2, border_radius=3)
            pygame.draw.line(surf, (112, 88, 64), (r.left + 4, r.top + 4),
                             (r.right - 5, r.bottom - 5), 2)
            pygame.draw.line(surf, (112, 88, 64), (r.right - 5, r.top + 4),
                             (r.left + 4, r.bottom - 5), 2)
        if self.hp < self.max_hp:                                  # cracks once damaged
            pygame.draw.line(surf, (38, 34, 30), (r.left + 6, r.top + 5),
                             (r.centerx, r.centery), 1)
            pygame.draw.line(surf, (38, 34, 30), (r.centerx, r.centery),
                             (r.right - 6, r.top + 8), 1)


# ---------------------------------------------------------------- zones --
_FONTS = {}


def mist_font(size, bold=False):
    """Cached Mist City font — the same Consolas family src/ui.py and the other
    HUD overlays use, so the mode reads like the rest of Harvest Duo (falls
    back to pygame's default font only if no system font can be loaded)."""
    key = (int(size), bool(bold))
    f = _FONTS.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont("consolas", key[0], bold=key[1])
        except Exception:
            f = pygame.font.Font(None, int(key[0] * 1.45))
        _FONTS[key] = f
    return f


def sign_font():
    """Small bold font for door plates / the HOME portal label."""
    return mist_font(15, True)


_DOOR_CACHE = {}


def door_surface(style, label):
    """Static sprite of a zone-exit door (cached). ``style``: "fence" (street ->
    factory chain-link gate) or "shutter" (factory -> clock tower blast door)."""
    key = (style, label)
    if key in _DOOR_CACHE:
        return _DOOR_CACHE[key]
    w, h = 140, 176
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if style == "fence":
        post, post_dk = (128, 124, 120), (92, 88, 86)
        for px in (8, w - 22):
            pygame.draw.rect(s, post, (px, 34, 14, h - 34), border_radius=2)
            pygame.draw.rect(s, post_dk, (px, 34, 14, h - 34), 2, border_radius=2)
            pygame.draw.rect(s, post_dk, (px - 2, 30, 18, 8), border_radius=2)
        mesh = pygame.Rect(22, 52, w - 44, h - 56)
        pygame.draw.rect(s, (60, 64, 66, 150), mesh)
        for k in range(-mesh.h, mesh.w, 10):              # chain-link cross-hatch
            pygame.draw.line(s, (150, 156, 150), (mesh.left + k, mesh.bottom),
                             (mesh.left + k + mesh.h, mesh.top), 1)
            pygame.draw.line(s, (150, 156, 150), (mesh.left + k, mesh.top),
                             (mesh.left + k + mesh.h, mesh.bottom), 1)
        s.fill((0, 0, 0, 0), (mesh.centerx - 4, mesh.top, 30, mesh.h))   # ajar gap
        pygame.draw.rect(s, (150, 156, 150), (8, 52, w - 16, 3))
        pygame.draw.line(s, (196, 120, 84), (mesh.left, mesh.top + 20),
                         (mesh.right, mesh.top + 28), 3)                  # rusty chain
    else:                                                                  # shutter
        frame, frame_dk = (132, 96, 78), (86, 60, 50)
        pygame.draw.rect(s, frame, (4, 30, w - 8, h - 30), border_radius=4)
        pygame.draw.rect(s, frame_dk, (4, 30, w - 8, h - 30), 3, border_radius=4)
        inner = pygame.Rect(16, 44, w - 32, h - 44)
        pygame.draw.rect(s, (30, 24, 26), inner)
        for sy in range(inner.top, inner.top + int(inner.h * 0.62), 8):   # raised slats
            pygame.draw.rect(s, (156, 132, 116), (inner.left, sy, inner.w, 6))
            pygame.draw.line(s, (112, 92, 80), (inner.left, sy + 6), (inner.right, sy + 6), 1)
        gap = pygame.Rect(inner.left, inner.top + int(inner.h * 0.62) + 2, inner.w,
                          inner.h - int(inner.h * 0.62) - 2)
        pygame.draw.rect(s, (70, 44, 36), gap)                              # ember glow
        for k in range(0, inner.w, 14):                                     # hazard band
            pygame.draw.polygon(s, (232, 190, 96), [(inner.left + k, gap.top - 8),
                                                    (inner.left + k + 7, gap.top - 8),
                                                    (inner.left + k + 3, gap.top - 2),
                                                    (inner.left + k - 4, gap.top - 2)])
    # sign plate
    f = sign_font()
    txt = f.render(label, True, NEON_AMBER if style == "fence" else (250, 214, 150))
    pw = txt.get_width() + 18
    plate = pygame.Rect(w // 2 - pw // 2, 2, pw, 26)
    pygame.draw.rect(s, (40, 40, 46), plate, border_radius=4)
    pygame.draw.rect(s, NEON_AMBER, plate, 2, border_radius=4)
    cap = f.metrics("H")[0][3]                       # optically centred on the plate
    s.blit(txt, (plate.centerx - txt.get_width() // 2, plate.centery - f.get_ascent() + (cap + 1) // 2))
    _DOOR_CACHE[key] = s
    return s


def draw_exit_door(surf, sx, t, style, label, active=False):
    """Blit a cached exit door centred on screen-x ``sx`` + a bobbing arrow."""
    img = door_surface(style, label)
    surf.blit(img, (int(sx - img.get_width() / 2), GROUND_Y - img.get_height()))
    bob = int(4 * math.sin(t * 5.0))
    col = NEON_MINT if active else (170, 190, 180)
    ay = GROUND_Y - img.get_height() - 18 + bob
    pts = [(sx - 10, ay - 8), (sx + 10, ay - 8), (sx, ay + 4)]
    pygame.draw.polygon(surf, col, pts)
    if active:
        pygame.draw.polygon(surf, (250, 255, 250), pts, 2)


class ZoneMixin:
    """Shared zone interface (duck-typed by MistRun): every zone world has these."""
    key = "street"
    name = "Main Street"
    subtitle = "Scavenge the ruined shops"
    level_w = LEVEL_W
    exit_x = None                 # right-end door to the next zone (None = last zone)
    exit_style = "fence"
    exit_label = ""
    home_gate = True              # the broken warp arch home stands at gate_x
    fog_col = FOG_COL
    zombie_mix = (("walker", 0.50), ("runner", 0.30), ("worker", 0.20))   # weighted
    first_zombie_x = 620.0
    trickle = True                # zombies keep trickling in from the edges
    events_ok = True              # random run events may fire here
    covers = ()                   # rects that shelter from acid rain
    door_active = False

    def update(self, dt, run):
        """Per-frame zone hazards (conveyors, acid, wires...). Street: none."""

    def draw_front(self, surf, camx, t):
        """Foreground layer drawn over the actors (pipes, chains...)."""

    def crate_hit(self, hitbox):
        """First unbroken crate intersecting ``hitbox`` (or None)."""
        for c in self.crates:
            if c.hp > 0 and hitbox.colliderect(c.rect()):
                return c
        return None

    def is_covered(self, x, feet_y):
        """True if a player at (x, feet) stands under a roof / awning / catwalk."""
        for c in self.covers:
            if c.left - 2 < x < c.right + 2 and feet_y >= c.bottom:
                return True
        return False

    def medkit_positions(self):
        return [self.level_w * f for f in (0.30, 0.55, 0.80)]


class MistWorld(ZoneMixin):
    """Level geometry + the whole painted backdrop for the street zone."""

    exit_style = "fence"
    exit_label = "OLD FACTORY >"

    def __init__(self):
        rng = random.Random(77)
        self.gate_x = 90
        self.exit_x = LEVEL_W - 70     # chain-link gate -> the Old Factory

        # ---- one-way platforms (land on top, jump up through) ----
        self.platforms = []      # pygame.Rect, top = stand line
        self.plat_kind = []      # parallel: "car" | "bus" | "awning"
        self.cars = []           # (rect, body colour) for drawing
        car_cols = [(122, 130, 148), (150, 122, 128), (118, 142, 132), (146, 138, 110)]
        for i, cx in enumerate((540, 1180, 2280, 3020)):
            r = pygame.Rect(cx - 70, GROUND_Y - 52, 140, 52)
            self.platforms.append(r)
            self.plat_kind.append("car")
            self.cars.append((r, car_cols[i % len(car_cols)]))
        self.bus = pygame.Rect(1700 - 125, GROUND_Y - 88, 250, 88)
        self.platforms.append(self.bus)
        self.plat_kind.append("bus")

        # ---- shopfronts: (x centre, kind) — awning above each door ----
        self.shops = [(820, "pharmacy"), (1420, "mechanic"),
                      (2040, "gas"), (2620, "pharmacy")]
        self.awnings = []
        for sx, _kind in self.shops:
            a = pygame.Rect(sx - 65, GROUND_Y - AWNING_H, 130, 12)
            self.platforms.append(a)
            self.plat_kind.append("awning")
            self.awnings.append(a)

        self.covers = list(self.awnings)   # acid rain: shelter under a canopy

        # ---- crates (ground / roofs / awnings; 2 rare) ----
        self.crates = [
            Crate(420, GROUND_Y), Crate(980, GROUND_Y), Crate(1560, GROUND_Y),
            Crate(1880, GROUND_Y), Crate(2450, GROUND_Y), Crate(3140, GROUND_Y),
            Crate(1690, self.bus.top),                       # on the bus roof
            Crate(840, GROUND_Y - AWNING_H),                 # on awnings
            Crate(2640, GROUND_Y - AWNING_H),
            Crate(2040, GROUND_Y - AWNING_H, rare=True),     # locked: gas canopy
            Crate(3020, GROUND_Y - 52, rare=True),           # locked: on the last car roof
        ]

        # ---- backdrop: two parallax building rows + flickering windows ----
        self.far, self.mid = [], []
        x = -60
        while x < LEVEL_W * 0.35 + SCREEN_W + 120:
            w = rng.randint(90, 170)
            h = rng.randint(180, 330)
            self.far.append((x, w, h))
            x += w + rng.randint(8, 40)
        x = -60
        while x < LEVEL_W * 0.6 + SCREEN_W + 120:
            w = rng.randint(110, 200)
            h = rng.randint(120, 260)
            wins = []
            for wy in range(28, h - 20, 34):
                for wx in range(14, w - 16, 26):
                    if rng.random() < 0.30:
                        col = NEON_MINT if rng.random() < 0.6 else NEON_PINK
                        wins.append((wx, wy, rng.uniform(0, 6.28), rng.uniform(0.6, 2.4), col))
            self.mid.append((x, w, h, wins))
            x += w + rng.randint(10, 50)
        # the frozen clock tower (far layer, roughly mid-level)
        self.tower_x = int(LEVEL_W * 0.35 * 0.55)

        # road cracks + faded lane dashes
        self.cracks = []
        for _ in range(34):
            cx = rng.randint(0, LEVEL_W)
            pts = [(cx, GROUND_Y + rng.randint(4, 14))]
            for _s in range(rng.randint(2, 4)):
                px, py = pts[-1]
                pts.append((px + rng.randint(-26, 26), py + rng.randint(8, 26)))
            self.cracks.append(pts)

        # drifting ground-fog blobs: (base_x, y, speed, scale, phase)
        self.fog_blobs = [(rng.uniform(0, LEVEL_W), GROUND_Y - rng.uniform(0, 26),
                           rng.uniform(8, 30), rng.uniform(0.6, 1.5), rng.uniform(0, 6.28))
                          for _ in range(30)]

        # cached surfaces
        self._sky = self._make_sky()
        self._fog_spr = self._make_fog_sprite()
        self._fog_imgs = [pygame.transform.scale(self._fog_spr, (int(128 * b[3]),
                                                                  int(128 * b[3] * 0.45)))
                          for b in self.fog_blobs]

    # ------------------------------------------------------------- caches --
    def _make_sky(self):
        s = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(0, SCREEN_H, 4):
            k = y / SCREEN_H
            col = tuple(int(a + (b - a) * k) for a, b in zip(SKY_TOP, SKY_BOT))
            s.fill(col, (0, y, SCREEN_W, 4))
        return s

    def _make_fog_sprite(self):
        r = 64
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for rad, a in ((r, 14), (int(r * 0.7), 16), (int(r * 0.42), 18)):
            pygame.draw.circle(s, (*FOG_COL, a), (r, r), rad)
        return s

    # --------------------------------------------------------------- draw --
    def draw_back(self, surf, camx, t):
        surf.blit(self._sky, (0, 0))
        # far row (slow parallax) + the stopped clock tower
        ox = camx * 0.35
        for x, w, h in self.far:
            sx = int(x - ox)
            if -200 < sx < SCREEN_W + 40:
                pygame.draw.rect(surf, FAR_COL, (sx, GROUND_Y - h, w, h))
        tx = int(self.tower_x - ox)
        if -160 < tx < SCREEN_W + 60:
            pygame.draw.rect(surf, FAR_COL, (tx, GROUND_Y - 420, 96, 420))
            pygame.draw.polygon(surf, FAR_COL, [(tx - 8, GROUND_Y - 420),
                                                (tx + 104, GROUND_Y - 420),
                                                (tx + 48, GROUND_Y - 470)])
            cx, cy = tx + 48, GROUND_Y - 360
            glow = 60 + int(18 * math.sin(t * 1.3))
            pygame.draw.circle(surf, (96, 118, 110), (cx, cy), 36)
            pygame.draw.circle(surf, (208, 220, 206), (cx, cy), 30)
            pygame.draw.circle(surf, (*NEON_MINT[:2], 150), (cx, cy), 30, 2)
            # hands frozen forever at 12:07
            pygame.draw.line(surf, (70, 80, 78), (cx, cy), (cx, cy - 20), 3)
            pygame.draw.line(surf, (70, 80, 78), (cx, cy), (cx + 12, cy - 5), 3)
            pygame.draw.circle(surf, (glow + 60, 235, 190), (cx, cy), 3)
        # mid row (windows flicker)
        ox = camx * 0.6
        for x, w, h, wins in self.mid:
            sx = int(x - ox)
            if sx < -240 or sx > SCREEN_W + 40:
                continue
            pygame.draw.rect(surf, MID_COL, (sx, GROUND_Y - h, w, h))
            for wx, wy, ph, spd, col in wins:
                if math.sin(t * spd + ph) > 0.25:
                    surf.fill(col, (sx + wx, GROUND_Y - h + wy, 5, 7))

    def _draw_shop(self, surf, sx, kind, t):
        """One ruined shopfront. ``sx`` is the screen-space centre x."""
        w, h = 190, 178
        r = pygame.Rect(sx - w // 2, GROUND_Y - h, w, h)
        pygame.draw.rect(surf, FACADE, r)
        pygame.draw.rect(surf, FACADE_DARK, r, 3)
        # doorway (dark) + boarded window with cracks
        pygame.draw.rect(surf, (34, 38, 42), (sx - 22, GROUND_Y - 76, 44, 76))
        win = pygame.Rect(r.left + 14, GROUND_Y - 86, 52, 56)
        pygame.draw.rect(surf, (40, 50, 54), win)
        pygame.draw.line(surf, (130, 140, 138), win.topleft, win.bottomright, 1)
        pygame.draw.line(surf, (130, 140, 138), (win.centerx, win.top), (win.left, win.centery), 1)
        pygame.draw.rect(surf, (96, 80, 60), (win.left - 2, win.centery - 4, win.w + 4, 8))
        # neon sign — flickers off now and then
        on = math.sin(t * 7.0 + sx * 0.13) > -0.55
        sign = pygame.Rect(sx - 52, r.top + 10, 104, 26)
        pygame.draw.rect(surf, (44, 48, 52), sign, border_radius=4)
        if kind == "pharmacy":
            col = NEON_MINT
            if on:
                pygame.draw.rect(surf, col, (sx - 7, sign.centery - 8, 14, 16))
                pygame.draw.rect(surf, col, (sx - 12, sign.centery - 3, 24, 6))
        elif kind == "mechanic":
            col = NEON_PINK
            if on:
                pygame.draw.circle(surf, col, (sx - 8, sign.centery), 7, 3)
                pygame.draw.line(surf, col, (sx - 3, sign.centery + 4), (sx + 14, sign.centery - 7), 3)
        else:                                    # gas
            col = NEON_AMBER
            if on:
                pygame.draw.rect(surf, col, (sx - 10, sign.centery - 8, 13, 16), border_radius=2)
                pygame.draw.line(surf, col, (sx + 5, sign.centery - 6), (sx + 11, sign.centery + 6), 2)
        if on:
            pygame.draw.rect(surf, col, sign, 2, border_radius=4)

    def draw_main(self, surf, camx, t):
        cx = int(camx)
        # road bed
        pygame.draw.rect(surf, ROAD, (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
        pygame.draw.line(surf, ROAD_EDGE, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 3)
        for dx in range(-(cx % 90), SCREEN_W, 90):         # faded centre dashes
            pygame.draw.rect(surf, (134, 138, 134), (dx, GROUND_Y + 56, 36, 6))
        for pts in self.cracks:
            sp = [(x - cx, y) for x, y in pts]
            if -60 < sp[0][0] < SCREEN_W + 60:
                pygame.draw.lines(surf, ROAD_CRACK, False, sp, 2)
        # shopfronts (behind everything that stands on the street)
        for sx, kind in self.shops:
            if -220 < sx - cx < SCREEN_W + 220:
                self._draw_shop(surf, sx - cx, kind, t)
        # awnings (striped canopies bolted to the facades)
        for a in self.awnings:
            r = a.move(-cx, 0)
            if r.right < -8 or r.left > SCREEN_W + 8:
                continue
            pygame.draw.rect(surf, (108, 96, 110), r.inflate(0, 2), border_radius=3)
            for i, wx in enumerate(range(r.left, r.right, 18)):
                col = (146, 130, 148) if i % 2 else (120, 106, 124)
                pygame.draw.rect(surf, col, (wx, r.top, min(18, r.right - wx), r.h))
            pygame.draw.line(surf, FACADE_DARK, (r.left + 4, r.bottom), (r.left + 14, r.bottom + 10), 2)
            pygame.draw.line(surf, FACADE_DARK, (r.right - 4, r.bottom), (r.right - 14, r.bottom + 10), 2)
        # street lamps (some flicker)
        for i, lx in enumerate(range(300, LEVEL_W, 480)):
            sx = lx - cx
            if sx < -30 or sx > SCREEN_W + 30:
                continue
            pygame.draw.rect(surf, (58, 64, 68), (sx - 3, GROUND_Y - 170, 6, 170))
            pygame.draw.rect(surf, (58, 64, 68), (sx - 3, GROUND_Y - 170, 26, 6))
            lit = math.sin(t * (3.1 + i * 0.7) + i * 2.1) > (-0.2 if i % 3 else 0.75)
            head = (NEON_AMBER if lit else (70, 74, 70))
            pygame.draw.circle(surf, head, (sx + 23, GROUND_Y - 161), 6)
        # wrecked cars + the bus
        for r, col in self.cars:
            rr = r.move(-cx, 0)
            if rr.right < -8 or rr.left > SCREEN_W + 8:
                continue
            body = pygame.Rect(rr.left, rr.top + 18, rr.w, rr.h - 26)
            pygame.draw.rect(surf, col, body, border_radius=8)
            cab = pygame.Rect(rr.left + 26, rr.top, rr.w - 64, 24)
            pygame.draw.rect(surf, col, cab, border_radius=6)
            pygame.draw.rect(surf, (40, 46, 52), cab.inflate(-12, -8), border_radius=4)
            for wx in (rr.left + 26, rr.right - 26):
                pygame.draw.circle(surf, (38, 40, 44), (wx, rr.bottom - 6), 11)
                pygame.draw.circle(surf, (90, 94, 98), (wx, rr.bottom - 6), 4)
        rb = self.bus.move(-cx, 0)
        if rb.right > -8 and rb.left < SCREEN_W + 8:
            pygame.draw.rect(surf, (132, 148, 136), rb.inflate(0, -6).move(0, 3), border_radius=10)
            for wx in range(rb.left + 16, rb.right - 24, 38):
                pygame.draw.rect(surf, (44, 52, 56), (wx, rb.top + 16, 26, 22), border_radius=3)
            for wx in (rb.left + 36, rb.right - 36):
                pygame.draw.circle(surf, (38, 40, 44), (wx, rb.bottom - 8), 13)
                pygame.draw.circle(surf, (90, 94, 98), (wx, rb.bottom - 8), 5)
        # the warp gate home (broken stone arch + glowing mint portal)
        gx = self.gate_x - cx
        if -90 < gx < SCREEN_W + 90:
            stone, sdk = (124, 128, 140), (92, 96, 108)
            # soft portal glow between the pillars
            glow = pygame.Surface((92, 130), pygame.SRCALPHA)
            ga = 46 + int(18 * math.sin(t * 2.4))
            pygame.draw.ellipse(glow, (*NEON_MINT, ga), (10, 8, 72, 118))
            surf.blit(glow, (gx - 46, GROUND_Y - 134))
            for px_, h_ in ((-42, 126), (24, 110)):              # two pillars
                pygame.draw.rect(surf, stone, (gx + px_, GROUND_Y - h_, 18, h_),
                                 border_radius=3)
                pygame.draw.rect(surf, sdk, (gx + px_, GROUND_Y - h_, 18, h_),
                                 2, border_radius=3)
            pygame.draw.rect(surf, stone, (gx - 48, GROUND_Y - 138, 78, 16), border_radius=3)
            pygame.draw.rect(surf, sdk, (gx - 48, GROUND_Y - 138, 78, 16), 2, border_radius=3)
            for ry in range(GROUND_Y - 110, GROUND_Y - 30, 22):  # pulsing runes
                if math.sin(t * 3.0 + ry) > -0.3:
                    pygame.draw.line(surf, NEON_MINT, (gx - 36, ry), (gx - 30, ry), 2)
            for k in range(4):                                   # the swirl itself
                a = t * 2.2 + k * 1.6
                px_ = gx - 2 + int(14 * math.cos(a))
                py_ = GROUND_Y - 64 + int(34 * math.sin(a * 0.7))
                pygame.draw.circle(surf, NEON_MINT, (px_, py_), 4 - k % 2)
        # chain-link gate at the far end of the street -> the Old Factory
        ex = self.exit_x - cx
        if -90 < ex < SCREEN_W + 90:
            draw_exit_door(surf, ex, t, self.exit_style, self.exit_label, self.door_active)
        # crates last (they sit on surfaces)
        for c in self.crates:
            if c.hp > 0:
                c.draw(surf, camx, t)

    def draw_fog(self, surf, camx, t):
        """Drifting knee-high street fog (always on; the timer overlay is separate)."""
        span = self.level_w + 240
        for (bx, by, spd, sc, ph), img in zip(self.fog_blobs, self._fog_imgs):
            x = (bx + t * spd) % span - 120 - camx
            if x < -160 or x > SCREEN_W + 160:
                continue
            y = by + math.sin(t * 0.5 + ph) * 6
            w = img.get_width()
            surf.blit(img, (int(x - w / 2), int(y - w * 0.18)))
