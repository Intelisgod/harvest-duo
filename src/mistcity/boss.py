"""The Bell Keeper — Mist City's clock-tower boss.

Owner: Chat 7 (Mist City). A hunched bronze bell that climbed down from the
belfry, dragging a clapper-mallet. Everything it does is on the beat of its
own toll, so the fight is a rhythm game:

  * every toll = a ring pulse from the bell (+ "bell" SFX) — the metronome;
  * "tele_wave"  -> the mallet rises and a pink ring spreads on the floor;
    "wave"       -> SLAM: shockwaves run left & right along the floor. JUMP them;
  * "gears"      -> shadows bloom on the floor, then rusty gears crash down;
  * "summon"     -> the toll wakes a few zombies that claw out of the cobbles;
  * phases at 66% / 33% HP: faster beats, faster waves, more gears (phase 3
    slams twice). Touching the bell itself also hurts.

Pure logic + drawing; MistRun (mist_system) calls ``update(dt, run)`` and routes
player hits through ``hit(dmg)``. All art is procedural pastel (dusty bronze,
mint glow eyes, a tiny clock on its chest).
"""
import math
import pygame
from .world2d import GROUND_Y, NEON_MINT, NEON_PINK, NEON_AMBER

NAME = "THE BELL KEEPER"
W, H = 112, 150
CONTACT_DMG = 11
WAVE_DMG = 14
GEAR_DMG = 12

BEAT = {1: 1.45, 2: 1.15, 3: 0.92}
WAVE_SPEED = {1: 380.0, 2: 460.0, 3: 540.0}
MOVE_SPEED = {1: 46.0, 2: 64.0, 3: 84.0}
GEARS = {1: 3, 2: 4, 3: 5}
PATTERN = {
    1: ["tele_wave", "wave", "rest", "gears", "rest", "tele_wave", "wave", "summon", "rest"],
    2: ["tele_wave", "wave", "gears", "rest", "tele_wave", "wave", "summon", "gears", "rest"],
    3: ["tele_wave", "wave2", "gears", "tele_wave", "wave", "gears", "summon", "rest"],
}

BRONZE = (206, 164, 106)
BRONZE_DK = (150, 110, 70)
BRONZE_LT = (238, 208, 152)

_BODY = {}


def _body(flash):
    """Cached bell-body sprite (normal / white hit-flash)."""
    key = bool(flash)
    if key in _BODY:
        return _BODY[key]
    s = pygame.Surface((W + 24, H + 10), pygame.SRCALPHA)
    cx = s.get_width() // 2
    col = (250, 244, 236) if flash else BRONZE
    dk = (220, 210, 200) if flash else BRONZE_DK
    lt = (255, 255, 255) if flash else BRONZE_LT
    top = 16
    # crown loop (hanger)
    pygame.draw.circle(s, dk, (cx, top + 2), 12, 5)
    # dome + flared skirt silhouette
    pts = [(cx - 30, top + 12), (cx + 30, top + 12), (cx + 42, top + 50), (cx + 46, top + 100),
           (cx + 60, H - 6), (cx - 60, H - 6), (cx - 46, top + 100), (cx - 42, top + 50)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.ellipse(s, col, (cx - 34, top + 2, 68, 30))
    pygame.draw.polygon(s, dk, pts, 3)
    # lip band + highlight stripe
    pygame.draw.rect(s, dk, (cx - 58, H - 22, 116, 10), border_radius=4)
    pygame.draw.line(s, lt, (cx - 22, top + 20), (cx - 34, top + 96), 4)
    pygame.draw.line(s, dk, (cx - 44, top + 104), (cx + 44, top + 104), 2)
    # dark mouth under the lip (eyes are drawn live on top)
    pygame.draw.ellipse(s, (40, 32, 50), (cx - 52, H - 18, 104, 22))
    # chest clock (face only; hands drawn live)
    pygame.draw.circle(s, (240, 232, 212), (cx, top + 64), 17)
    pygame.draw.circle(s, dk, (cx, top + 64), 17, 3)
    # rivets
    for rx in (-36, -18, 0, 18, 36):
        pygame.draw.circle(s, dk, (cx + rx, H - 17), 2)
    _BODY[key] = s
    return s


class BellKeeper:
    def __init__(self, x, max_hp, rng):
        self.rng = rng
        self.x = float(x)
        self.y = float(GROUND_Y)
        self.max_hp = self.hp = int(max_hp)
        self.phase = 1
        self.pi = 0
        self.beat_t = 2.4               # first toll comes after the entrance
        self.wait = 2.6                 # lets the zone title card breathe first
        self.intro = 1.6                # dropping in from the belfry
        self.drop = -520.0              # y offset while dropping
        self.facing = -1
        self.flash = 0.0
        self.invuln = 0.0
        self.toll_t = 0.0               # vibration after each toll
        self.raise_t = 0.0              # mallet raised (telegraph)
        self.slam_t = 0.0               # mallet slammed
        self.rings = []                 # [age, colour, floor?]
        self.waves = []                 # [x, dir, speed, hit ids]
        self.gears = []                 # [x, delay, y, vy, spin, total]
        self.pending = []               # [delay, action] (half-beat follow-ups)
        self.dead = False
        self.death_t = 0.0
        self.done = False               # death animation finished -> rewards paid
        self.last_hitter = None
        self.anim = 0.0

    # ------------------------------------------------------------ queries --
    def rect(self):
        return pygame.Rect(int(self.x - W / 2 + 6), int(self.y + self.drop - H + 12), W - 12, H - 16)

    def frac(self):
        return max(0.0, self.hp / float(self.max_hp))

    def beat_len(self):
        return BEAT[self.phase]

    # ------------------------------------------------------------ actions --
    def hit(self, dmg, q=None):
        """Player sword hit. Returns damage dealt (0 while invulnerable/dead)."""
        if self.dead or self.invuln > 0 or self.intro > 0 or self.wait > 0:
            return 0
        self.hp -= dmg
        self.flash = 0.12
        if q is not None:
            self.last_hitter = q
        return dmg

    # ------------------------------------------------------------- update --
    def update(self, dt, run):
        self.anim += dt
        self.flash = max(0.0, self.flash - dt)
        self.toll_t = max(0.0, self.toll_t - dt)
        self.slam_t = max(0.0, self.slam_t - dt)
        self.raise_t = max(0.0, self.raise_t - dt)
        self.invuln = max(0.0, self.invuln - dt)
        for r in self.rings:
            r[0] += dt
        self.rings = [r for r in self.rings if r[0] < 0.9]
        if self.wait > 0:                                   # dust sifts from the belfry
            self.wait -= dt
            if run.rng.random() < dt * 8:
                run._burst(self.x + run.rng.uniform(-40, 40), 40, (170, 160, 180), n=2, up=False)
            if self.wait <= 0:
                run._snd("bell")
            return
        if self.intro > 0:                                  # crash-landing entrance
            self.intro -= dt
            self.drop = min(0.0, self.drop + dt * 700)
            if self.intro <= 0 or self.drop >= 0:
                if self.intro > -1:
                    run.shake = max(run.shake, 12.0)
                    run._snd("boss_roar")
                    run._burst(self.x, GROUND_Y - 6, (200, 190, 210), n=24, up=True)
                    self.rings.append([0.0, NEON_PINK, True])
                    run.banner = [NAME, 3.6]          # the boss bar hides its own name meanwhile
                    run.sub = ["Jump the floor waves on the toll - dodge the gear shadows", 3.6]
                self.intro, self.drop = 0.0, 0.0
            return
        if self.dead:
            if self.done:                                   # rewards paid: rest in peace
                self._tick_projectiles(dt, run)
                return
            self.death_t += dt
            if int(self.death_t * 10) % 3 == 0:
                run._burst(self.x + self.rng.uniform(-50, 50), self.y - self.rng.uniform(20, 130),
                           self.rng.choice([NEON_MINT, NEON_AMBER, BRONZE_LT]), n=3)
            run.shake = max(run.shake, 3.0)
            if self.death_t >= 2.2 and not self.done:
                self.done = True
                run._boss_defeated(self)
            self._tick_projectiles(dt, run)
            return
        # phase changes
        f = self.frac()
        want = 3 if f <= 0.33 else (2 if f <= 0.66 else 1)
        if want > self.phase:
            self.phase = want
            self.pi = 0
            self.invuln = 1.2
            self.beat_t = 1.3
            self.pending = []
            run.shake = max(run.shake, 10.0)
            run.white = 0.3
            run._snd("boss_roar")
            run.banner = ["THE BELL KEEPER QUICKENS!" if want == 2 else "THE BELL TOLLS FOR YOU!", 2.0]
            for k in range(3):
                self.rings.append([-0.12 * k, NEON_PINK, False])
            run._burst(self.x, self.y - 80, NEON_PINK, n=26)
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            self.death_t = 0.0
            self.waves, self.pending = [], []
            run.white = 0.35
            run._snd("boss_roar")
            run.banner = ["THE BELL CRACKS...", 2.2]
            return
        # slow slide toward the nearest living player (keeps a little distance)
        living = [q for q in run.p2 if not q.ghost]
        if living and self.slam_t <= 0 and self.raise_t <= 0:
            tgt = min(living, key=lambda q: abs(q.x - self.x))
            dx = tgt.x - self.x
            self.facing = 1 if dx > 0 else -1
            if abs(dx) > 40:
                self.x += math.copysign(MOVE_SPEED[self.phase] * dt, dx)
        self.x = max(W / 2 + 40, min(run.world.level_w - W / 2 - 40, self.x))
        # the metronome
        self.beat_t -= dt
        if self.beat_t <= 0:
            self.beat_t += self.beat_len()
            self._toll(run)
        for pnd in self.pending:
            pnd[0] -= dt
        due = [p for p in self.pending if p[0] <= 0]
        self.pending = [p for p in self.pending if p[0] > 0]
        for _d, act in due:
            self._do(act, run)
        # contact damage
        body = self.rect()
        for q in living:
            if body.colliderect(q.rect()) and q.y > body.top + 24:   # ledge-top brushes are safe
                if run._hurt_player(q, CONTACT_DMG, "bell"):
                    q.vy = -360.0
                    q.x += 26 if q.x > self.x else -26
        self._tick_projectiles(dt, run)

    def _toll(self, run):
        self.toll_t = 0.25
        if hasattr(run.world, "toll"):
            run.world.toll = 0.35                    # the belfry glows on every toll
        self.rings.append([0.0, NEON_MINT, False])
        run._snd("bell")
        act = PATTERN[self.phase][self.pi % len(PATTERN[self.phase])]
        self.pi += 1
        self._do(act, run)

    def _do(self, act, run):
        if act == "tele_wave":
            self.raise_t = self.beat_len()
            self.rings.append([0.0, NEON_PINK, True])
        elif act in ("wave", "wave2"):
            self._slam(run)
            if act == "wave2":                              # phase 3: a second slam
                self.pending.append([self.beat_len() * 0.5, "wave"])
        elif act == "gears":
            living = [q for q in run.p2 if not q.ghost]
            n = GEARS[self.phase]
            xs = [q.x for q in living][:2]
            while len(xs) < n:
                xs.append(self.rng.uniform(60, run.world.level_w - 60))
            delay = self.beat_len() * 0.95
            for x in xs:
                x = max(30.0, min(run.world.level_w - 30.0, x + self.rng.uniform(-30, 30)))
                floor = float(GROUND_Y)                     # lands on a ledge if one is below
                for pl in run.world.platforms:
                    if pl.left + 6 < x < pl.right - 6:
                        floor = min(floor, float(pl.top))
                self.gears.append([x, delay, -60.0, 0.0, self.rng.uniform(0, 6.28), delay, floor])
            run._snd("ui_toggle")
        elif act == "summon":
            self.rings.append([0.0, NEON_AMBER, True])
            n = 2 if self.phase < 3 else 3
            run._boss_summon(n)

    def _slam(self, run):
        self.slam_t = 0.3
        self.raise_t = 0.0
        run.shake = max(run.shake, 8.0)
        run._snd("hit")
        spd = WAVE_SPEED[self.phase]
        fx = self.x + self.facing * 30
        self.waves.append([fx, -1, spd, set()])
        self.waves.append([fx, 1, spd, set()])
        run._burst(fx, GROUND_Y - 4, (230, 210, 230), n=16, up=True)

    def _tick_projectiles(self, dt, run):
        lw = run.world.level_w
        living = [q for q in run.p2 if not q.ghost]
        for w in self.waves:
            w[0] += w[1] * w[2] * dt
            for q in living:
                if id(q) in w[3]:
                    continue
                if abs(q.x - w[0]) < 20 and q.y > GROUND_Y - 30:
                    w[3].add(id(q))
                    if run._hurt_player(q, WAVE_DMG, "wave"):
                        run._pop(q.x, q.y - 56, "JUMP!", NEON_PINK)
        self.waves = [w for w in self.waves if -40 < w[0] < lw + 40]
        for gr in self.gears:
            if gr[1] > 0:
                gr[1] -= dt
                continue
            gr[3] += 2600 * dt
            gr[2] += gr[3] * dt
            gr[4] += dt * 9
            if gr[2] >= gr[6] - 18:
                gr[2] = 99999.0                              # landed -> removed below
                run.shake = max(run.shake, 4.0)
                run._burst(gr[0], gr[6] - 8, (190, 150, 110), n=12)
                box = pygame.Rect(int(gr[0] - 24), int(gr[6]) - 60, 48, 60)
                for q in living:
                    if box.colliderect(q.rect()) and run._hurt_player(q, GEAR_DMG, "gear"):
                        run._pop(q.x, q.y - 56, "CLANG!", NEON_AMBER)
        self.gears = [g for g in self.gears if g[2] < 99999.0]

    # --------------------------------------------------------------- draw --
    def draw(self, surf, camx, t):
        # floor telegraphs first (gear shadows / pink ring)
        for x, delay, y, vy, spin, total, floor in self.gears:
            k = 1.0 - max(0.0, delay) / max(0.01, total)
            w = int(12 + 40 * k)
            sx = int(x - camx)
            fy = int(floor)
            pygame.draw.ellipse(surf, (40, 30, 48), (sx - w // 2, fy - 5, w, 10))
            if delay > 0 and int(t * 12) % 2:
                pygame.draw.ellipse(surf, NEON_AMBER, (sx - w // 2, fy - 5, w, 10), 1)
        bx = int(self.x - camx)
        by = int(self.y + self.drop)
        # shadow (grows while it falls from the belfry)
        if self.wait > 0:
            sw = int(24 + 40 * (1.0 - self.wait / 2.6))
        else:
            sw = 120 if self.drop > -300 else 80
        pygame.draw.ellipse(surf, (34, 28, 44), (bx - sw // 2, GROUND_Y - 8, sw, 16))
        if self.wait > 0:
            return
        # rings (toll pulses): mint around the bell, pink/amber on the floor
        for age, col, floor in self.rings:
            if age < 0:
                continue
            k = age / 0.9
            fade = tuple(int(c * (1 - k) + 90 * k) for c in col)
            if floor:
                rw = int(60 + 380 * k)
                pygame.draw.ellipse(surf, fade, (bx - rw, GROUND_Y - 10 - int(8 * k), rw * 2, 20 + int(16 * k)), 3)
            else:
                rr = int(50 + 110 * k)
                pygame.draw.circle(surf, fade, (bx, by - 86), rr, 3)
        # body (vibrates on the toll, wobbles when dying)
        vib = int(math.sin(t * 90) * 3 * (self.toll_t / 0.25)) if self.toll_t > 0 else 0
        if self.dead:
            vib = int(math.sin(t * 50) * 4)
        sway = int(math.sin(self.anim * 1.6) * 3)
        img = _body(self.flash > 0 or (self.dead and int(t * 14) % 2))
        ix = bx - img.get_width() // 2 + vib + sway
        iy = by - img.get_height() + 6
        # arms + clapper mallet behind the bell on the facing side
        f = self.facing
        shoulder = (bx + f * 40 + sway, by - 92)
        if self.raise_t > 0:
            hand = (bx + f * 70 + sway, by - 176)
        elif self.slam_t > 0:
            hand = (bx + f * 92 + sway, by - 30)
        else:
            hand = (bx + f * 78 + sway, by - 70 + int(math.sin(self.anim * 3) * 4))
        pygame.draw.line(surf, (70, 58, 64), shoulder, hand, 7)
        head = (hand[0] + f * 6, hand[1] - (22 if self.raise_t > 0 else -6))
        pygame.draw.line(surf, (96, 76, 60), hand, head, 6)
        pygame.draw.circle(surf, BRONZE_DK, head, 15)
        pygame.draw.circle(surf, BRONZE_LT, (head[0] - 4, head[1] - 4), 5)
        surf.blit(img, (ix, iy))
        # other arm hugging the bell
        pygame.draw.line(surf, (70, 58, 64), (bx - f * 40 + sway, by - 92),
                         (bx - f * 58 + sway, by - 40), 7)
        # chest clock hands spin faster each phase (frozen when dead)
        ccx, ccy = ix + img.get_width() // 2, iy + 16 + 64
        spd = 0.0 if self.dead else (0.6, 2.0, 5.0)[self.phase - 1]
        a = t * spd
        pygame.draw.line(surf, (70, 62, 86), (ccx, ccy), (ccx + int(11 * math.cos(a)), ccy + int(11 * math.sin(a))), 2)
        pygame.draw.line(surf, (70, 62, 86), (ccx, ccy),
                         (ccx + int(7 * math.cos(a / 12 - 1.2)), ccy + int(7 * math.sin(a / 12 - 1.2))), 3)
        # glowing eyes in the dark mouth (turn pink when enraged)
        ecol = NEON_MINT if self.phase == 1 else (NEON_AMBER if self.phase == 2 else NEON_PINK)
        if self.dead:
            ecol = (90, 90, 100)
        blink = int(self.anim * 1.3) % 5 == 0 and (self.anim * 1.3) % 1 < 0.15
        ey = iy + img.get_height() - 22
        for ex in (-16, 16):
            if blink:
                pygame.draw.line(surf, ecol, (ccx + ex - 5, ey), (ccx + ex + 5, ey), 2)
            else:
                pygame.draw.ellipse(surf, ecol, (ccx + ex - 6, ey - 4, 12, 8))
                surf.fill((255, 255, 255), (ccx + ex - 2 + f * 2, ey - 2, 2, 2))
        if self.dead:                                      # crack spreading down the bell
            k = min(1.0, self.death_t / 1.6)
            pts = [(ccx + 8, iy + 18), (ccx - 4, iy + 18 + int(40 * k)),
                   (ccx + 10, iy + 18 + int(80 * k)), (ccx - 2, iy + 18 + int(120 * k))]
            pygame.draw.lines(surf, (60, 40, 40), False, pts, 3)
        if self.invuln > 0 and int(t * 16) % 2:
            pygame.draw.circle(surf, (250, 220, 240), (bx, by - 80), 92, 2)
        # shockwaves (bright crests racing along the floor)
        for x, d, spd, _hit in self.waves:
            sx = int(x - camx)
            pts = [(sx - 20 * d, GROUND_Y), (sx - 8 * d, GROUND_Y - 22), (sx, GROUND_Y - 28),
                   (sx + 8 * d, GROUND_Y - 16), (sx + 18 * d, GROUND_Y)]
            pygame.draw.polygon(surf, (246, 176, 214), pts)
            pygame.draw.lines(surf, (255, 240, 250), False, pts[1:4], 2)
            pygame.draw.line(surf, (220, 150, 196), (sx - 44 * d, GROUND_Y - 2), (sx - 20 * d, GROUND_Y - 2), 3)
        # falling gears
        for x, delay, y, vy, spin, total, _floor in self.gears:
            if delay > 0:
                continue
            sx, sy = int(x - camx), int(y)
            for k in range(8):
                a = spin + k * math.pi / 4
                pygame.draw.circle(surf, (150, 112, 80), (sx + int(18 * math.cos(a)), sy + int(18 * math.sin(a))), 6)
            pygame.draw.circle(surf, (176, 132, 90), (sx, sy), 17)
            pygame.draw.circle(surf, (120, 86, 60), (sx, sy), 17, 3)
            pygame.draw.circle(surf, (70, 52, 44), (sx, sy), 6)
