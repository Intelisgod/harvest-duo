"""Mist City zones 2 and 3 — the Old Factory and the Clock Tower courtyard.

Owner: Chat 7 (Mist City). A run chains three side-scrolling zones:

    0  Main Street   (world2d.MistWorld)      ruined shops, cars, awnings
    1  Old Factory   (FactoryWorld)           conveyors, acid, crumbling catwalks, live wires
    2  Clock Tower   (TowerWorld)             one-screen boss arena: The Bell Keeper

Every zone world duck-types ``world2d.ZoneMixin`` (platforms, crates, covers,
exit door, update(dt, run) for hazards, draw_back/draw_main/draw_front/draw_fog).
Palettes stay pastel: the factory is rust-orange and amber, the courtyard a dusky
plum with mint lanterns — spooky-cute, never gory.
"""
import math
import random
import pygame
from ..settings import SCREEN_W, SCREEN_H
from .world2d import (MistWorld, ZoneMixin, Crate, GROUND_Y, NEON_MINT, NEON_PINK,
                      NEON_AMBER, draw_exit_door, sign_font)

# ------------------------------------------------------------------ palette --
F_SKY_TOP = (70, 48, 46)
F_SKY_BOT = (152, 100, 74)
F_FAR = (96, 64, 54)
F_MID = (112, 76, 62)
F_FLOOR = (120, 100, 90)
F_FLOOR_EDGE = (156, 128, 110)
F_FLOOR_DK = (92, 76, 70)
RUST = (184, 108, 66)
RUST_DK = (124, 72, 50)
STEEL = (146, 136, 130)
STEEL_DK = (98, 90, 88)
ACID = (156, 236, 116)
ACID_DK = (86, 152, 74)
WALL = (104, 72, 62)
WALL_DK = (84, 58, 52)
F_FOG = (210, 170, 142)

T_SKY_TOP = (46, 38, 64)
T_SKY_BOT = (120, 96, 124)
T_STONE = (112, 104, 132)
T_STONE_DK = (84, 76, 104)
T_STONE_LT = (146, 138, 166)
T_FOG = (190, 180, 206)

FACT_W = 2900

ACID_DMG = 9
WIRE_DMG = 12
WIRE_CYCLE = 3.2
WIRE_TELL = 2.0          # sparks start (telegraph)
WIRE_LIVE = 2.7          # arc reaches the floor until the cycle ends
CATWALK_SHAKE = 0.55
CATWALK_BACK = 5.0

_CACHE = {}


def _gradient(top, bot, key):
    if key in _CACHE:
        return _CACHE[key]
    s = pygame.Surface((SCREEN_W, SCREEN_H))
    for y in range(0, SCREEN_H, 4):
        k = y / SCREEN_H
        s.fill(tuple(int(a + (b - a) * k) for a, b in zip(top, bot)), (0, y, SCREEN_W, 4))
    _CACHE[key] = s
    return s


def _puff():
    if "puff" not in _CACHE:
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        for r, a in ((30, 26), (22, 30), (13, 34)):
            pygame.draw.circle(s, (206, 176, 160, a), (32, 32), r)
        _CACHE["puff"] = s
    return _CACHE["puff"]


class Catwalk:
    """Grated steel walkway. ``broken`` ones shudder when stood on, drop away,
    then clank back into place a few seconds later."""

    def __init__(self, x1, x2, h, broken=False):
        self.rect = pygame.Rect(x1, GROUND_Y - h, x2 - x1, 10)
        self.broken = broken
        self.state = "ok"            # ok | shake | gone
        self.t = 0.0
        self.drop = 0.0              # falling-debris offset while gone

    @property
    def solid(self):
        return self.state != "gone"


class FactoryWorld(ZoneMixin):
    key = "factory"
    name = "The Old Factory"
    subtitle = "Mind the belts, the acid and the live wires"
    level_w = FACT_W
    exit_style = "shutter"
    exit_label = "CLOCK TOWER >"
    home_gate = False
    fog_col = F_FOG
    zombie_mix = (("walker", 0.26), ("runner", 0.24), ("worker", 0.30), ("hazmat", 0.20))
    first_zombie_x = 520.0

    def __init__(self):
        rng = random.Random(1907)
        self.gate_x = 100
        self.exit_x = FACT_W - 80
        self.conveyors = [(380, 640, -150.0), (1640, 1930, 170.0)]
        self.acids = [(780, 880), (1960, 2070), (2300, 2370)]
        self.wires = [[1050, 0.0], [2200, 1.1], [2440, 2.2]]      # x, phase offset
        self.wire_top = 44
        self.wire_tip = GROUND_Y - 176
        self.catwalks = [Catwalk(740, 930, 112), Catwalk(1130, 1240, 112, broken=True),
                         Catwalk(1280, 1430, 214), Catwalk(1470, 1580, 124, broken=True),
                         Catwalk(2500, 2680, 112)]
        self.roofs = [pygame.Rect(200, GROUND_Y - 318, 400, 16),
                      pygame.Rect(1560, GROUND_Y - 318, 420, 16)]
        self.crates = [
            Crate(300, GROUND_Y), Crate(700, GROUND_Y), Crate(990, GROUND_Y),
            Crate(2130, GROUND_Y), Crate(2720, GROUND_Y),
            Crate(835, GROUND_Y - 112), Crate(2590, GROUND_Y - 112),
            Crate(1355, GROUND_Y - 214, rare=True),              # top of the high catwalk
        ]
        self.platforms = []
        self.covers = []
        self._rebuild()
        # parallax silhouettes
        self.stacks = []
        x = 40
        while x < FACT_W * 0.3 + SCREEN_W + 100:
            self.stacks.append((x, rng.randint(34, 52), rng.randint(260, 380), rng.uniform(0, 6)))
            x += rng.randint(220, 360)
        self.halls = []
        x = -40
        while x < FACT_W * 0.6 + SCREEN_W + 120:
            w = rng.randint(200, 320)
            h = rng.randint(150, 230)
            wins = [(wx, rng.uniform(0, 6.28)) for wx in range(18, w - 24, 34)
                    if rng.random() < 0.55]
            self.halls.append((x, w, h, wins))
            x += w + rng.randint(20, 70)
        self.fog_blobs = [(rng.uniform(0, FACT_W), GROUND_Y - rng.uniform(0, 26),
                           rng.uniform(8, 26), rng.uniform(0.6, 1.4), rng.uniform(0, 6.28))
                          for _ in range(24)]
        spr = MistWorld._make_fog_sprite(self)
        tint = pygame.Surface(spr.get_size(), pygame.SRCALPHA)
        tint.fill((255, 214, 180, 255))
        spr.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._fog_imgs = [pygame.transform.scale(spr, (int(128 * b[3]), int(128 * b[3] * 0.45)))
                          for b in self.fog_blobs]
        self.hot = []            # [x, y, vx, vy, life] live-wire sparks
        self.spills = []         # [x1, x2, ttl] hazmat acid spills (temporary)

    def add_spill(self, x):
        """A fallen hazmat zombie leaks a small acid puddle for a few seconds."""
        self.spills.append([x - 34, x + 34, 6.0])

    def _rebuild(self):
        self.platforms = [c.rect for c in self.catwalks if c.solid]
        self.covers = list(self.roofs) + [c.rect for c in self.catwalks if c.solid]

    def medkit_positions(self):
        return [965.0, 2110.0, 2760.0]

    def wire_state(self, i, t):
        """("idle"|"tell"|"live", phase) for wire ``i`` at run-time ``t``."""
        ph = (t + self.wires[i][1]) % WIRE_CYCLE
        if ph >= WIRE_LIVE:
            return "live", ph
        if ph >= WIRE_TELL:
            return "tell", ph
        return "idle", ph

    # ---------------------------------------------------------- hazards --
    def update(self, dt, run):
        t = run.elapsed
        changed = False
        for c in self.catwalks:
            if c.state == "shake":
                c.t -= dt
                if c.t <= 0:
                    c.state, c.t, c.drop = "gone", CATWALK_BACK, 0.0
                    changed = True
                    run._snd("mine")
                    run._burst(c.rect.centerx, c.rect.top, STEEL, n=14, up=False)
            elif c.state == "gone":
                c.t -= dt
                c.drop += dt * 520
                if c.t <= 0:
                    c.state = "ok"
                    changed = True
                    run._burst(c.rect.centerx, c.rect.top, (230, 214, 190), n=8)
        living = [q for q in run.p2 if not q.ghost]
        for q in living:
            if q.stand is not None:
                for c in self.catwalks:
                    if c.broken and c.state == "ok" and q.stand is c.rect:
                        c.state, c.t = "shake", CATWALK_SHAKE
                        run._snd("ui_toggle")
            if not (q.on_ground and q.stand is None):
                continue
            for x1, x2, spd in self.conveyors:
                if x1 < q.x < x2:
                    q.push = spd
            for x1, x2 in self.acids + [(s[0], s[1]) for s in self.spills if s[2] > 0.4]:
                if x1 + 6 < q.x < x2 - 6:
                    if run._hurt_player(q, ACID_DMG, "acid"):
                        run._pop(q.x, q.y - 56, "ACID!", ACID)
                        run._burst(q.x, GROUND_Y - 4, ACID, n=10)
        for z in run.zombies:                       # the belts carry the dead too
            for x1, x2, spd in self.conveyors:
                if x1 < z.x < x2:
                    z.x += spd * dt * 0.8
        for i, (wx, _ph) in enumerate(self.wires):
            st, ph = self.wire_state(i, t)
            if st == "live":
                col = pygame.Rect(wx - 18, self.wire_tip, 36, GROUND_Y - self.wire_tip)
                for q in living:
                    if col.colliderect(q.rect()) and run._hurt_player(q, WIRE_DMG, "wire"):
                        run._pop(q.x, q.y - 56, "ZAP!", (160, 220, 255))
                        run._burst(q.x, q.y - 26, (190, 230, 255), n=12)
            if st != "idle" and run.rng.random() < (0.5 if st == "tell" else 0.9):
                self.hot.append([wx + run.rng.uniform(-3, 3), self.wire_tip,
                                 run.rng.uniform(-90, 90), run.rng.uniform(-60, 60),
                                 run.rng.uniform(0.15, 0.35)])
        for sp in self.spills:
            sp[2] -= dt
        self.spills = [sp for sp in self.spills if sp[2] > 0]
        for s in self.hot:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 600 * dt
            s[4] -= dt
        self.hot = [s for s in self.hot if s[4] > 0][-80:]
        if changed:
            self._rebuild()

    # ------------------------------------------------------------- draw --
    def draw_back(self, surf, camx, t):
        surf.blit(_gradient(F_SKY_TOP, F_SKY_BOT, "fsky"), (0, 0))
        ox = camx * 0.3
        puff = _puff()
        for x, w, h, ph in self.stacks:                     # smokestacks + slow smoke
            sx = int(x - ox)
            if -80 < sx < SCREEN_W + 40:
                pygame.draw.rect(surf, F_FAR, (sx, GROUND_Y - h, w, h))
                pygame.draw.rect(surf, (112, 72, 58), (sx - 3, GROUND_Y - h, w + 6, 10))
                for band in range(GROUND_Y - h + 40, GROUND_Y - 60, 70):
                    pygame.draw.rect(surf, (110, 74, 60), (sx, band, w, 6))
                for k in range(3):
                    a = ((t * 14 + k * 53 + ph * 20) % 160) / 160.0
                    surf.blit(puff, (sx + w // 2 - 32 + int(a * 40), GROUND_Y - h - 40 - int(a * 120)))
        ox = camx * 0.6
        for x, w, h, wins in self.halls:                    # saw-tooth factory halls
            sx = int(x - ox)
            if sx < -340 or sx > SCREEN_W + 20:
                continue
            top = GROUND_Y - h
            pygame.draw.rect(surf, F_MID, (sx, top, w, h))
            teeth = []
            for k in range(0, w, 40):
                teeth += [(sx + k, top), (sx + k + 28, top - 26), (sx + k + 32, top)]
            pygame.draw.polygon(surf, F_MID, [(sx, top)] + teeth + [(sx + w, top)])
            for wx, ph in wins:
                lit = math.sin(t * 0.8 + ph) > -0.4
                surf.fill((236, 178, 104) if lit else (92, 64, 54), (sx + wx, top + 30, 16, 22))

    def _draw_catwalk(self, surf, c, cx, t):
        r = c.rect.move(-cx, 0)
        if c.state == "gone":
            if c.drop < 260:                                 # debris tumbling away
                for k in range(0, r.w, 22):
                    pygame.draw.rect(surf, STEEL_DK, (r.left + k, r.top + int(c.drop * (0.8 + k % 3 * 0.2)),
                                                      16, 5))
            return
        if r.right < -10 or r.left > SCREEN_W + 10:
            return
        jig = int(math.sin(t * 60) * 2) if c.state == "shake" else 0
        r = r.move(jig, 0)
        # support struts down to the floor (broken ones hang from snapped cables)
        if c.broken:
            for ax in (r.left + 10, r.right - 10):
                pygame.draw.line(surf, (70, 64, 62), (ax, 0), (ax, r.top), 1)
        else:
            for ax in (r.left + 12, r.right - 12):
                pygame.draw.rect(surf, STEEL_DK, (ax - 3, r.bottom, 6, GROUND_Y - r.bottom))
        pygame.draw.rect(surf, STEEL, r)
        for k in range(r.left + 4, r.right - 2, 8):          # grating
            pygame.draw.line(surf, STEEL_DK, (k, r.top + 2), (k, r.bottom - 2), 1)
        pygame.draw.rect(surf, STEEL_DK, r, 2)
        pygame.draw.line(surf, STEEL_DK, (r.left, r.top - 16), (r.right, r.top - 16), 2)   # rail
        for k in range(r.left, r.right + 1, 30):
            pygame.draw.line(surf, STEEL_DK, (k, r.top - 16), (k, r.top), 2)
        if c.broken:                                          # rusted, missing slats
            pygame.draw.rect(surf, RUST, (r.left + r.w // 3, r.top + 1, 14, r.h - 2))
            pygame.draw.line(surf, (60, 44, 40), (r.centerx + 6, r.top), (r.centerx - 2, r.bottom), 2)
            if c.state == "shake":
                pygame.draw.circle(surf, NEON_AMBER, (r.centerx, r.top - 26), 4)

    def draw_main(self, surf, camx, t):
        cx = int(camx)
        # low back wall + pipes
        pygame.draw.rect(surf, WALL, (0, GROUND_Y - 150, SCREEN_W, 150))
        for bx in range(-(cx % 64), SCREEN_W, 64):
            pygame.draw.line(surf, WALL_DK, (bx, GROUND_Y - 150), (bx, GROUND_Y), 1)
        for y in (GROUND_Y - 150, GROUND_Y - 100, GROUND_Y - 50):
            pygame.draw.line(surf, WALL_DK, (0, y), (SCREEN_W, y), 1)
        pygame.draw.rect(surf, RUST_DK, (0, GROUND_Y - 132, SCREEN_W, 12))       # big pipe
        pygame.draw.line(surf, RUST, (0, GROUND_Y - 130), (SCREEN_W, GROUND_Y - 130), 2)
        for vx in range(-(cx % 360) + 140, SCREEN_W, 360):                          # valves
            pygame.draw.circle(surf, (170, 80, 70), (vx, GROUND_Y - 126), 9, 3)
        # roof girder with truss + steel columns
        pygame.draw.rect(surf, STEEL_DK, (0, 30, SCREEN_W, 14))
        for k in range(-(cx % 80), SCREEN_W, 80):
            pygame.draw.line(surf, STEEL_DK, (k, 44), (k + 40, 70), 3)
            pygame.draw.line(surf, STEEL_DK, (k + 40, 70), (k + 80, 44), 3)
        pygame.draw.line(surf, STEEL_DK, (0, 70), (SCREEN_W, 70), 3)
        for colx in range(-(cx % 300) + 60, SCREEN_W + 30, 300):
            pygame.draw.rect(surf, STEEL_DK, (colx - 9, 44, 18, GROUND_Y - 44))
            pygame.draw.rect(surf, STEEL, (colx - 3, 44, 6, GROUND_Y - 44))
        # rusted roof sheets (acid-rain shelter)
        for r in self.roofs:
            rr = r.move(-cx, 0)
            if rr.right < 0 or rr.left > SCREEN_W:
                continue
            pygame.draw.rect(surf, RUST_DK, rr)
            for k in range(rr.left, rr.right, 12):
                pygame.draw.line(surf, RUST, (k, rr.top), (k, rr.bottom), 2)
            pygame.draw.rect(surf, (90, 56, 44), rr, 2)
        # floor
        pygame.draw.rect(surf, F_FLOOR, (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
        pygame.draw.line(surf, F_FLOOR_EDGE, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 3)
        for k in range(-(cx % 40), SCREEN_W, 40):                                   # hazard stripe
            pygame.draw.polygon(surf, (214, 176, 96), [(k, GROUND_Y + 6), (k + 18, GROUND_Y + 6),
                                                       (k + 10, GROUND_Y + 14), (k - 8, GROUND_Y + 14)])
        for k in range(-(cx % 120), SCREEN_W, 120):
            pygame.draw.line(surf, F_FLOOR_DK, (k, GROUND_Y + 20), (k + 30, SCREEN_H), 1)
        # entry shutter (closed behind us)
        ex = 40 - cx
        if ex > -80:
            pygame.draw.rect(surf, STEEL_DK, (ex - 36, GROUND_Y - 150, 72, 150))
            for sy in range(GROUND_Y - 142, GROUND_Y, 9):
                pygame.draw.line(surf, STEEL, (ex - 30, sy), (ex + 30, sy), 2)
        # conveyors
        for x1, x2, spd in self.conveyors:
            if x2 - cx < -20 or x1 - cx > SCREEN_W + 20:
                continue
            r = pygame.Rect(x1 - cx, GROUND_Y - 4, x2 - x1, 18)
            pygame.draw.rect(surf, (58, 52, 54), r, border_radius=8)
            off = int((t * spd * 0.5) % 24)
            d = 1 if spd > 0 else -1
            for k in range(r.left - 24 + off, r.right, 24):                          # chevrons
                if r.left + 4 < k < r.right - 12:
                    pygame.draw.lines(surf, (230, 190, 104), False,
                                      [(k, r.top + 4), (k + 6 * d, r.centery), (k, r.bottom - 4)], 2)
            for wx in (r.left + 9, r.right - 9):
                pygame.draw.circle(surf, STEEL, (wx, r.centery), 7)
                a = t * spd * 0.08
                pygame.draw.line(surf, STEEL_DK, (wx, r.centery),
                                 (wx + int(6 * math.cos(a)), r.centery + int(6 * math.sin(a))), 2)
        # acid pools (sunken, bubbling)
        for x1, x2 in self.acids:
            if x2 - cx < -20 or x1 - cx > SCREEN_W + 20:
                continue
            r = pygame.Rect(x1 - cx, GROUND_Y - 2, x2 - x1, 26)
            pygame.draw.rect(surf, ACID_DK, r.inflate(8, 4), border_radius=10)
            pygame.draw.rect(surf, ACID, r.inflate(0, -6).move(0, 2), border_radius=8)
            for k in range(4):
                bx = r.left + 10 + int(((k * 37 + t * 22) % max(1, r.w - 20)))
                by = r.top + 6 - int((t * 1.7 + k * 0.4) % 1.0 * 10)
                pygame.draw.circle(surf, (214, 252, 180), (bx, by), 3, 1)
            glow = int(40 + 20 * math.sin(t * 3 + x1))
            pygame.draw.line(surf, (190, 250, 150 + glow // 4), (r.left + 6, r.top + 3),
                             (r.right - 6, r.top + 3), 2)
        for x1, x2, ttl in self.spills:                                         # hazmat spills
            k = min(1.0, ttl / 0.8, (6.0 - ttl) / 0.4)
            w = int((x2 - x1) * k)
            if w > 4:
                mx = (x1 + x2) // 2 - cx
                pygame.draw.ellipse(surf, ACID_DK, (mx - w // 2 - 3, GROUND_Y - 5, w + 6, 12))
                pygame.draw.ellipse(surf, ACID, (mx - w // 2, GROUND_Y - 3, w, 8))
                if int(t * 6 + x1) % 3 == 0:
                    bx = mx + int(math.sin(t * 5 + x1) * w * 0.3)
                    pygame.draw.circle(surf, (214, 252, 180), (bx, GROUND_Y - 4), 2, 1)
        for c in self.catwalks:
            self._draw_catwalk(surf, c, cx, t)
        # live wires hanging from the girder
        for i, (wx, _ph) in enumerate(self.wires):
            sx = wx - cx
            if sx < -60 or sx > SCREEN_W + 60:
                continue
            st, ph = self.wire_state(i, t)
            sag = int(4 * math.sin(t * 1.3 + i))
            pygame.draw.lines(surf, (40, 36, 40), False,
                              [(sx - 30, 60), (sx - 8 + sag, self.wire_tip - 60), (sx, self.wire_tip)], 3)
            pygame.draw.rect(surf, (200, 150, 80), (sx - 4, self.wire_tip - 6, 8, 8), border_radius=2)
            if st == "tell" and int(t * 20) % 2:
                pygame.draw.circle(surf, (210, 236, 255), (sx, self.wire_tip + 2), 7, 2)
            if st == "live":
                rng = random.Random(int(t * 30) + i * 7)
                pts = [(sx, self.wire_tip)]
                y = self.wire_tip
                while y < GROUND_Y:
                    y = min(GROUND_Y, y + rng.randint(20, 34))
                    pts.append((sx + rng.randint(-14, 14), y))
                pygame.draw.lines(surf, (150, 210, 255), False, pts, 5)
                pygame.draw.lines(surf, (245, 252, 255), False, pts, 2)
                pygame.draw.ellipse(surf, (180, 226, 255), (sx - 22, GROUND_Y - 5, 44, 10), 2)
        for x, y, vx, vy, life in self.hot:
            surf.fill((236, 246, 255) if life > 0.2 else (150, 200, 250),
                      (int(x - cx), int(y), 3, 3))
        # exit blast door
        ex = self.exit_x - cx
        if -90 < ex < SCREEN_W + 90:
            draw_exit_door(surf, ex, t, self.exit_style, self.exit_label, self.door_active)
        for c in self.crates:
            if c.hp > 0:
                c.draw(surf, camx, t)

    def draw_fog(self, surf, camx, t):
        MistWorld.draw_fog(self, surf, camx, t)


class TowerWorld(ZoneMixin):
    """One-screen courtyard under the frozen clock — The Bell Keeper's arena."""
    key = "tower"
    name = "Clock Tower Courtyard"
    subtitle = "Something rings in the belfry..."
    level_w = SCREEN_W
    exit_x = None
    home_gate = False
    fog_col = T_FOG
    trickle = False
    events_ok = False
    first_zombie_x = None

    def __init__(self):
        self.gate_x = 110
        self.portal_x = SCREEN_W // 2
        self.portal_open = False
        self.portal_t = 0.0
        self.clock_spin = 0.0          # hands start moving again once the bell falls
        self.ledges = [pygame.Rect(170, GROUND_Y - 128, 170, 14),
                       pygame.Rect(SCREEN_W - 340, GROUND_Y - 128, 170, 14)]
        self.platforms = list(self.ledges)
        self.covers = list(self.ledges)
        self.crates = [Crate(40, GROUND_Y), Crate(SCREEN_W - 40, GROUND_Y),
                       Crate(255, GROUND_Y - 128)]
        rng = random.Random(12)
        self.fog_blobs = [(rng.uniform(0, SCREEN_W), GROUND_Y - rng.uniform(0, 20),
                           rng.uniform(6, 18), rng.uniform(0.6, 1.3), rng.uniform(0, 6.28))
                          for _ in range(12)]
        spr = MistWorld._make_fog_sprite(self)
        self._fog_imgs = [pygame.transform.scale(spr, (int(128 * b[3]), int(128 * b[3] * 0.45)))
                          for b in self.fog_blobs]
        self.clock_c = (SCREEN_W // 2, 176)
        self.toll = 0.0                  # belfry glow after each boss toll

    def medkit_positions(self):
        return [255.0, SCREEN_W - 255.0]

    def update(self, dt, run):
        self.toll = max(0.0, self.toll - dt)
        if self.portal_open:
            self.portal_t += dt
            self.clock_spin += dt

    def _background(self):
        if "tower_bg" in _CACHE:
            return _CACHE["tower_bg"]
        s = _gradient(T_SKY_TOP, T_SKY_BOT, "tsky").copy()
        pygame.draw.circle(s, (232, 226, 240), (1080, 110), 46)                   # moon
        pygame.draw.circle(s, (206, 198, 222), (1066, 100), 9)
        pygame.draw.circle(s, (206, 198, 222), (1094, 124), 6)
        rng = random.Random(5)
        x = -20
        while x < SCREEN_W:                                                       # far roofs
            w, h = rng.randint(80, 150), rng.randint(90, 200)
            pygame.draw.rect(s, (70, 58, 90), (x, GROUND_Y - h, w, h))
            pygame.draw.polygon(s, (70, 58, 90), [(x - 6, GROUND_Y - h), (x + w // 2, GROUND_Y - h - 30),
                                                  (x + w + 6, GROUND_Y - h)])
            x += w + rng.randint(4, 30)
        cx = SCREEN_W // 2
        tw = 320
        pygame.draw.rect(s, T_STONE, (cx - tw // 2, 60, tw, GROUND_Y - 60))       # the tower
        pygame.draw.polygon(s, T_STONE_DK, [(cx - tw // 2 - 20, 64), (cx + tw // 2 + 20, 64),
                                            (cx, -80)])
        for by in range(80, GROUND_Y, 28):                                        # brick rows
            off = 0 if (by // 28) % 2 else 20
            pygame.draw.line(s, T_STONE_DK, (cx - tw // 2, by), (cx + tw // 2, by), 1)
            for bx in range(cx - tw // 2 + off, cx + tw // 2, 40):
                pygame.draw.line(s, T_STONE_DK, (bx, by), (bx, by + 28), 1)
        pygame.draw.rect(s, T_STONE_DK, (cx - tw // 2, 60, tw, GROUND_Y - 60), 4)
        # empty belfry arch (the bell climbed down...)
        arch = pygame.Rect(cx - 70, 292, 140, 150)
        pygame.draw.rect(s, (36, 30, 48), arch.inflate(0, -40).move(0, 20))
        pygame.draw.ellipse(s, (36, 30, 48), (arch.left, arch.top, arch.w, 90))
        pygame.draw.line(s, (60, 52, 72), (cx, arch.top + 8), (cx, arch.top + 60), 3)  # snapped rope
        pygame.draw.rect(s, T_STONE_LT, (cx - 84, 440, 168, 12))
        # clock face frame
        ccx, ccy = self.clock_c
        pygame.draw.circle(s, T_STONE_LT, (ccx, ccy), 96)
        pygame.draw.circle(s, (238, 232, 214), (ccx, ccy), 84)
        pygame.draw.circle(s, T_STONE_DK, (ccx, ccy), 84, 3)
        for k in range(12):
            a = k * math.pi / 6
            r0, r1 = (68, 80) if k % 3 else (62, 80)
            pygame.draw.line(s, (96, 88, 110), (ccx + int(math.cos(a) * r0), ccy + int(math.sin(a) * r0)),
                             (ccx + int(math.cos(a) * r1), ccy + int(math.sin(a) * r1)), 3 if k % 3 == 0 else 2)
        pygame.draw.line(s, (150, 140, 150), (ccx - 60, ccy + 20), (ccx - 20, ccy + 64), 1)   # crack
        # cobbled courtyard
        pygame.draw.rect(s, (98, 90, 112), (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
        pygame.draw.line(s, T_STONE_LT, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 3)
        for row, y in enumerate(range(GROUND_Y + 6, SCREEN_H, 22)):
            off = 0 if row % 2 else 24
            for x in range(-off, SCREEN_W, 48):
                pygame.draw.rect(s, (112, 104, 128), (x + 2, y, 44, 18), border_radius=6)
        # lamp posts
        for lx in (80, SCREEN_W - 80):
            pygame.draw.rect(s, (54, 48, 66), (lx - 4, GROUND_Y - 190, 8, 190))
            pygame.draw.rect(s, (54, 48, 66), (lx - 14, GROUND_Y - 200, 28, 12), border_radius=3)
        _CACHE["tower_bg"] = s
        return s

    def draw_back(self, surf, camx, t):
        surf.blit(self._background(), (0, 0))
        ccx, ccy = self.clock_c
        if self.toll > 0:                                                # toll glow rings
            k = self.toll / 0.35
            col = (int(96 + 44 * k), int(120 + 115 * k), int(120 + 70 * k))
            pygame.draw.circle(surf, col, (ccx, ccy), 98 + int(10 * (1 - k)), 3)
            pygame.draw.ellipse(surf, col, (ccx - 74, 288, 148, 96), 2)
        # hands: frozen at 12:07 until the bell falls silent, then they race on
        spin = self.clock_spin
        ma = -math.pi / 2 + 7 / 60 * 2 * math.pi + spin * 4.0
        ha = -math.pi / 2 + spin * 0.33
        pygame.draw.line(surf, (70, 62, 86), (ccx, ccy),
                         (ccx + int(math.cos(ha) * 44), ccy + int(math.sin(ha) * 44)), 6)
        pygame.draw.line(surf, (70, 62, 86), (ccx, ccy),
                         (ccx + int(math.cos(ma) * 66), ccy + int(math.sin(ma) * 66)), 4)
        pygame.draw.circle(surf, NEON_MINT if not self.portal_open else NEON_AMBER, (ccx, ccy), 6)
        for lx in (80, SCREEN_W - 80):                                   # lantern glow
            k = 0.5 + 0.5 * math.sin(t * 2.2 + lx)
            pygame.draw.circle(surf, (120 + int(40 * k), 220, 190), (lx, GROUND_Y - 176), 9)
            pygame.draw.circle(surf, (220, 255, 236), (lx, GROUND_Y - 176), 4)

    def draw_main(self, surf, camx, t):
        for r in self.ledges:                                           # hanging stone ledges
            for ax in (r.left + 14, r.right - 14):
                pygame.draw.line(surf, (70, 64, 84), (ax, 0), (ax, r.top), 2)
                for cy in range(10, r.top, 16):
                    pygame.draw.ellipse(surf, (90, 84, 104), (ax - 3, cy, 6, 10), 1)
            pygame.draw.rect(surf, T_STONE, r, border_radius=4)
            pygame.draw.rect(surf, T_STONE_DK, r, 2, border_radius=4)
            pygame.draw.line(surf, T_STONE_LT, (r.left + 4, r.top + 2), (r.right - 4, r.top + 2), 2)
        if self.portal_open:                                            # the way home
            k = min(1.0, self.portal_t / 0.8)
            px = self.portal_x
            h = int(130 * k)
            glow = pygame.Surface((110, 160), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*NEON_MINT, int(70 + 30 * math.sin(t * 3))),
                                (55 - int(40 * k), 80 - h // 2, int(80 * k), h))
            surf.blit(glow, (px - 55, GROUND_Y - 150))
            pygame.draw.ellipse(surf, (230, 255, 240), (px - int(36 * k), GROUND_Y - 70 - h // 2,
                                                        int(72 * k) + 1, h + 1), 3)
            for j in range(5):
                a = t * 2.4 + j * 1.26
                pygame.draw.circle(surf, NEON_MINT, (px + int(24 * k * math.cos(a)),
                                                     GROUND_Y - 70 + int(50 * k * math.sin(a * 0.8))), 3)
            from .. import ui_kit
            lab = ui_kit.outlined(sign_font(), "HOME", NEON_MINT, (24, 30, 34), 2)
            surf.blit(lab, (px - lab.get_width() // 2, GROUND_Y - 164 + int(3 * math.sin(t * 4))))
        for c in self.crates:
            if c.hp > 0:
                c.draw(surf, camx, t)

    def draw_fog(self, surf, camx, t):
        MistWorld.draw_fog(self, surf, camx, t)


ZONES = [MistWorld, FactoryWorld, TowerWorld]


def make_world(idx):
    return ZONES[max(0, min(len(ZONES) - 1, idx))]()


def zone_name(idx):
    return ZONES[max(0, min(len(ZONES) - 1, idx))].name
