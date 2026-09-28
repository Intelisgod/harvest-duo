"""Lightweight particle system for dust, splashes, sparkles and hit effects.

Shaped emitters (2026-09, Core): ``star_burst``, ``coin_burst``, ``ring``,
``petal``, ``poof``, ``rain_splash`` -- shapes are small cached sprites, so a
burst costs a blit per particle and no Surface allocation per frame. Callers in
other domains should guard with ``getattr(self.parts, "star_burst", None)``.
"""
import math
import random
import pygame


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "maxlife", "color", "size",
                 "grav", "fade", "glow", "ring", "heart", "shape", "ang", "spin",
                 "sway", "drag")

    def __init__(self, x, y, vx, vy, life, color, size, grav=0.0, fade=True,
                 glow=False, ring=False, heart=False, shape=None, spin=0.0,
                 sway=0.0, drag=0.0):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.life = life; self.maxlife = life
        self.color = color; self.size = size
        self.grav = grav; self.fade = fade
        self.glow = glow; self.ring = ring
        self.heart = heart
        self.shape = shape              # None | "star" | "coin" | "petal" | "puff"
        self.ang = random.uniform(0, 360) if shape else 0.0
        self.spin = spin                # deg/sec (petals, coins)
        self.sway = sway                # sideways flutter amplitude (px/s)
        self.drag = drag                # 0..~4: velocity damping per second

    def update(self, dt):
        self.life -= dt
        self.vy += self.grav * dt
        if self.drag:
            k = max(0.0, 1.0 - self.drag * dt)
            self.vx *= k
            self.vy *= k
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.sway:
            self.x += math.sin(self.life * 5.0 + self.maxlife * 7.0) * self.sway * dt
        if self.spin:
            self.ang = (self.ang + self.spin * dt) % 360


class _SpawnList(list):
    """The particle list. While ``xform`` is set (the ISO home room), every NEW
    particle's spawn point is mapped world -> iso screen(+cam), so emitters keep
    passing plain world coordinates and still appear on the right tile; the
    particle then moves in screen space (rising hearts rise straight up)."""
    __slots__ = ("xform",)

    def __init__(self, *a):
        super().__init__(*a)
        self.xform = None

    def append(self, p):
        f = self.xform
        if f is not None:
            try:
                p.x, p.y = f(p.x, p.y)
            except Exception:
                pass
        list.append(self, p)


class Particles:
    def __init__(self):
        self.items = _SpawnList()

    def set_projection(self, fn):
        """``fn(world_x, world_y) -> (x, y)`` applied to new spawns, or None."""
        if not isinstance(self.items, _SpawnList):
            self.items = _SpawnList(self.items)
        self.items.xform = fn

    def update(self, dt):
        for p in self.items:
            p.update(dt)
        self.items[:] = [p for p in self.items if p.life > 0]

    def draw(self, surf, cam):
        # Every shape is a cached full-alpha sprite keyed by (shape, size, rgb);
        # the per-particle fade is applied with set_alpha right before its blit,
        # so drawing allocates no Surfaces (was one Surface per particle/frame).
        if len(_SPR) > 900:              # bounded cache (random colours/sizes)
            _SPR.clear()
        cx, cy = cam.x, cam.y
        add = pygame.BLEND_RGBA_ADD
        for p in self.items:
            t = max(0.0, p.life / p.maxlife)
            col = p.color
            if p.ring:
                # an expanding, fading ring outline (water ripples / warp burst)
                rr = max(2, int(p.size * (1.0 + (1.0 - t) * 2.6)))
                rs = _sprite("ring", rr, col)
                rs.set_alpha(int(220 * t))
                surf.blit(rs, (p.x - cx - rr - 1, p.y - cy - rr - 1))
                continue
            a = int(255 * t) if p.fade else 255
            if p.heart:
                # a soft little heart (anniversary-cabana aura / "opened together" burst)
                hs = _sprite("heart", max(2, int(p.size)), col)
                hs.set_alpha(a)
                surf.blit(hs, (p.x - cx - hs.get_width() // 2,
                               p.y - cy - hs.get_height() // 2),
                          special_flags=add if p.glow else 0)
                continue
            if p.shape:
                if p.shape == "puff":
                    sz = max(2, int(p.size * (1.0 + (1.0 - t) * 0.9)))
                elif p.shape == "star":
                    sz = max(2, int(p.size * (0.55 + 0.45 * t)))
                else:
                    sz = max(1, int(p.size))
                spr = _sprite(p.shape, sz, col)
                if p.shape == "coin":           # coins flip (x-squash)
                    w = max(1, int(spr.get_width() * abs(math.cos(math.radians(p.ang)))))
                    spr = pygame.transform.scale(spr, (w, spr.get_height()))
                elif p.shape == "petal":        # petals tumble (15-degree steps)
                    spr = _rotated(spr, sz, col, int(p.ang) // 15 * 15)
                spr.set_alpha(a)
                surf.blit(spr, (p.x - cx - spr.get_width() // 2,
                                p.y - cy - spr.get_height() // 2),
                          special_flags=add if p.glow else 0)
                continue
            r = max(1, int(p.size * (t if p.fade else 1)))
            s = _sprite("dot", r, col)
            if p.glow:
                # additive glow ignores alpha (matches the old behaviour)
                s.set_alpha(255)
                surf.blit(s, (p.x - cx - r, p.y - cy - r), special_flags=add)
            else:
                s.set_alpha(a)
                surf.blit(s, (p.x - cx - r, p.y - cy - r))

    # ---- emitters ----
    def dust(self, x, y, n=8, color=(150, 120, 80)):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(20, 70)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp - 20,
                                        random.uniform(0.3, 0.6), color,
                                        random.uniform(2, 4), grav=120))

    def splash(self, x, y, n=10, color=(120, 180, 230)):
        for _ in range(n):
            self.items.append(Particle(x, y, random.uniform(-60, 60), random.uniform(-120, -40),
                                        random.uniform(0.4, 0.8), color,
                                        random.uniform(2, 4), grav=300))

    def sparkle(self, x, y, n=12, color=(255, 230, 120)):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(30, 90)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp,
                                        random.uniform(0.4, 0.8), color,
                                        random.uniform(2, 4)))

    def hit(self, x, y, n=10, color=(255, 90, 70)):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(60, 160)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp,
                                        random.uniform(0.2, 0.4), color,
                                        random.uniform(2, 5), grav=200))

    def chips(self, x, y, n=8, color=(140, 140, 150)):
        for _ in range(n):
            self.items.append(Particle(x, y, random.uniform(-90, 90), random.uniform(-160, -40),
                                        random.uniform(0.4, 0.7), color,
                                        random.uniform(2, 4), grav=400))

    def footstep(self, x, y, color=(170, 156, 120)):
        self.items.append(Particle(x, y, random.uniform(-10, 10), -10,
                                    0.3, color, random.uniform(2, 3), grav=40))

    def mote(self, x, y, night=0.0):
        """Ambient drifting speck. By day a pale pollen mote; at night a warm,
        glowing firefly that slowly bobs."""
        if night > 0.4:
            col = (255, 224, 150)
            self.items.append(Particle(x, y, random.uniform(-12, 12), random.uniform(-18, -4),
                                        random.uniform(2.4, 4.0), col,
                                        random.uniform(1.5, 2.5), grav=0.0, glow=True))
        else:
            col = (255, 250, 226)
            self.items.append(Particle(x, y, random.uniform(-14, 14), random.uniform(-22, -6),
                                        random.uniform(2.0, 3.4), col,
                                        random.uniform(1.0, 2.0), grav=6.0))

    def leaf(self, x, y, color=(186, 210, 150)):
        self.items.append(Particle(x, y, random.uniform(-24, -6), random.uniform(8, 22),
                                    random.uniform(1.6, 2.6), color,
                                    random.uniform(2, 3), grav=10.0))

    def smoke(self, x, y, n=1, color=(150, 150, 158)):
        """Soft grey puffs that drift upward (chimneys, kilns)."""
        for _ in range(n):
            self.items.append(Particle(x + random.uniform(-3, 3), y,
                                        random.uniform(-8, 8), random.uniform(-26, -16),
                                        random.uniform(1.2, 2.2), color,
                                        random.uniform(3, 5), grav=-6.0))

    def flame(self, x, y, n=1, color=(255, 172, 64)):
        """Tiny flickering candle/torch flame licks (glowing, short-lived)."""
        for _ in range(n):
            self.items.append(Particle(x + random.uniform(-1.5, 1.5), y,
                                        random.uniform(-4, 4), random.uniform(-22, -12),
                                        random.uniform(0.25, 0.5), color,
                                        random.uniform(2, 3), grav=-10.0, glow=True))

    def ember(self, x, y, n=1, color=(255, 140, 50)):
        """Rising glowing sparks (lava depths)."""
        for _ in range(n):
            self.items.append(Particle(x, y, random.uniform(-10, 10), random.uniform(-30, -12),
                                        random.uniform(0.8, 1.6), color,
                                        random.uniform(1.5, 2.5), grav=-4.0, glow=True))

    def bubble(self, x, y, n=6, color=(184, 222, 246)):
        """Little bubbles rising off the bobber when a fish bites."""
        for _ in range(n):
            self.items.append(Particle(x + random.uniform(-6, 6), y + random.uniform(-3, 3),
                                        random.uniform(-8, 8), random.uniform(-32, -14),
                                        random.uniform(0.5, 0.9), color,
                                        random.uniform(1.5, 3)))

    def ripple(self, x, y, n=1, color=(176, 212, 240)):
        """Expanding ring(s) on the water surface (fishing)."""
        for _ in range(n):
            self.items.append(Particle(x, y, 0, 0, random.uniform(0.5, 0.8), color,
                                        random.uniform(4, 6), grav=0.0, ring=True))

    def warp(self, x, y, color=(150, 220, 245)):
        """Teleport burst: a glowing ring + a spray of glowing sparks."""
        self.items.append(Particle(x, y, 0, 0, 0.6, color, 7, grav=0.0, ring=True))
        self.items.append(Particle(x, y, 0, 0, 0.45, (235, 250, 255), 4, grav=0.0, ring=True))
        for _ in range(16):
            a = random.uniform(0, math.tau)
            sp = random.uniform(40, 120)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp,
                                        random.uniform(0.4, 0.8), color,
                                        random.uniform(2, 4), glow=True))

    def confetti(self, x, y, n=4):
        """Falling festival confetti in assorted bright colours."""
        for _ in range(n):
            c = random.choice(_CONFETTI)
            self.items.append(Particle(x + random.uniform(-12, 12), y,
                                        random.uniform(-30, 30), random.uniform(20, 60),
                                        random.uniform(1.4, 2.4), c,
                                        random.uniform(2, 4), grav=120))

    def note_float(self, x, y, color=(120, 90, 200)):
        """A little music note (quaver) swaying upward -- record player, piano."""
        self.items.append(Particle(x + random.uniform(-4, 4), y,
                                   random.uniform(-9, 9), random.uniform(-30, -18),
                                   random.uniform(1.3, 2.0), color,
                                   random.choice((7, 8)), grav=-4.0, shape="note",
                                   sway=14.0))

    def heart_float(self, x, y, color=(255, 130, 165)):
        """A single soft heart drifting gently upward -- the 'special' aura that
        marks the anniversary cabana so players notice it (spawned continuously)."""
        self.items.append(Particle(x + random.uniform(-3, 3), y,
                                    random.uniform(-7, 7), random.uniform(-22, -12),
                                    random.uniform(1.6, 2.6), color,
                                    random.uniform(4, 6), grav=-3.0, heart=True))

    # ---- shaped emitters (2026-09) ----
    def star_burst(self, x, y, color=(255, 226, 120), n=10):
        """Five-point stars spraying outward then settling (achievements, crits,
        level-ups), plus a quick bright ring at the origin."""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(50, 150)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp - 40,
                                        random.uniform(0.6, 1.1), color,
                                        random.uniform(4, 7), grav=140, shape="star",
                                        spin=random.uniform(-200, 200), drag=1.2))
        self.items.append(Particle(x, y, 0, 0, 0.35, (255, 250, 230), 5, ring=True))

    def coin_burst(self, x, y, n=8):
        """Little gold coins hop out, flip and fall (selling, rewards)."""
        for _ in range(n):
            self.items.append(Particle(x + random.uniform(-4, 4), y,
                                        random.uniform(-70, 70), random.uniform(-190, -110),
                                        random.uniform(0.7, 1.0), (246, 204, 92),
                                        random.randint(4, 5), grav=420, shape="coin",
                                        spin=random.uniform(300, 600)))

    def ring(self, x, y, color=(255, 240, 200), radius=10):
        """One expanding, fading ring outline (shockwaves, pickups, unlocks)."""
        self.items.append(Particle(x, y, 0, 0, 0.55, color, max(2, radius // 2),
                                    grav=0.0, ring=True))

    def petal(self, x, y, color=(255, 196, 214), vx=None, vy=None):
        """A tumbling petal / leaf that flutters on the breeze (windy days)."""
        self.items.append(Particle(x, y,
                                    random.uniform(60, 140) if vx is None else vx,
                                    random.uniform(10, 40) if vy is None else vy,
                                    random.uniform(2.6, 4.2), color,
                                    random.randint(4, 6), grav=8.0, shape="petal",
                                    spin=random.uniform(-260, 260), sway=40.0))

    def poof(self, x, y, color=(236, 232, 240), n=8):
        """Soft round puffs that swell and fade (spawn/vanish, dust clouds)."""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(20, 60)
            self.items.append(Particle(x + math.cos(a) * 4, y + math.sin(a) * 4,
                                        math.cos(a) * sp, math.sin(a) * sp - 10,
                                        random.uniform(0.45, 0.8), color,
                                        random.uniform(4, 7), grav=-10.0, shape="puff",
                                        drag=2.5))

    def rain_splash(self, x, y, color=(178, 206, 236)):
        """A raindrop hitting the ground: tiny ring + two droplets."""
        self.items.append(Particle(x, y, 0, 0, 0.3, color, 2, ring=True))
        for _ in range(2):
            self.items.append(Particle(x, y, random.uniform(-30, 30), random.uniform(-70, -35),
                                        0.28, color, 1.5, grav=320))

    def heart_burst(self, x, y, n=16, color=None):
        """A celebratory spray of hearts, fired when BOTH players open the
        cabana together. Mixes warm tones for a 'confetti of hearts' feel."""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(40, 130)
            c = color or random.choice(_HEARTS)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp - 30,
                                        random.uniform(0.7, 1.3), c,
                                        random.uniform(4, 7), grav=80, heart=True))


_CONFETTI = [(245, 90, 90), (245, 200, 80), (110, 200, 120),
             (110, 180, 240), (210, 120, 235), (255, 255, 255)]

_HEARTS = [(255, 90, 130), (255, 130, 165), (255, 170, 190),
           (255, 120, 100), (255, 205, 150)]


def _draw_heart(surf, cx, cy, r, color):
    """Draw a chunky pixel heart (two top lobes + a bottom point) centred at
    (cx, cy) on ``surf``. Used by the heart particles (heart_float / heart_burst)."""
    lobe = max(1, int(round(r * 0.55)))
    off = max(1, int(round(r * 0.42)))
    ly = cy - int(round(r * 0.22))
    pygame.draw.circle(surf, color, (cx - off, ly), lobe)
    pygame.draw.circle(surf, color, (cx + off, ly), lobe)
    span = max(2, int(round(r * 0.95)))
    pygame.draw.polygon(surf, color, [(cx - span, ly + lobe // 2),
                                      (cx + span, ly + lobe // 2),
                                      (cx, cy + int(round(r * 1.05)))])


_SPR = {}


def _sprite(shape, r, col):
    """Cached particle sprite (full alpha; callers set_alpha before blitting)."""
    key = (shape, r, col[0], col[1], col[2])
    s = _SPR.get(key)
    if s is not None:
        return s
    rgb = (col[0], col[1], col[2])
    if shape == "dot":
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, rgb, (r, r), r)
    elif shape == "ring":
        s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, rgb, (r + 1, r + 1), r, 2)
    elif shape == "heart":
        s = _heart_surface(r, rgb + (255,))
    elif shape == "star":
        s = _star_surface(r, rgb)
    elif shape == "coin":
        w = r * 2 + 2
        s = pygame.Surface((w, w), pygame.SRCALPHA)
        c = w // 2
        pygame.draw.circle(s, (176, 128, 40), (c, c), r)
        pygame.draw.circle(s, rgb, (c, c), max(1, r - 1))
        pygame.draw.circle(s, (255, 240, 170), (c - max(1, r // 3), c - max(1, r // 3)),
                           max(1, r // 3))
    elif shape == "note":
        s = _note_surface(r, rgb)
    elif shape == "petal":
        s = pygame.Surface((r * 2 + 2, r + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, rgb, (1, 1, r * 2, r))
        hi = tuple(min(255, v + 40) for v in rgb)
        pygame.draw.ellipse(s, hi, (r // 2 + 1, 1 + r // 4, r, max(1, r // 2)))
    else:  # "puff"
        s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, rgb + (150,), (r + 1, r + 1), r)
        pygame.draw.circle(s, rgb + (205,), (r + 1, r + 1), max(1, int(r * 0.6)))
    _SPR[key] = s
    return s


def _note_surface(r, rgb):
    """A quaver: round head, stem, little flag, dark outline so it reads on
    any floor or wall."""
    w, h = r * 2 + 5, r * 3 + 4
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    ink = tuple(max(0, int(v * 0.45)) for v in rgb)
    hx, hy = r + 1, h - r - 1                      # note head centre
    sx = hx + r - 1                                # stem on the head's right
    for col, grow in ((ink, 1), (rgb, 0)):
        pygame.draw.ellipse(s, col, (hx - r - grow, hy - int(r * 0.8) - grow,
                                     r * 2 + grow * 2, int(r * 1.6) + grow * 2))
        pygame.draw.line(s, col, (sx, hy), (sx, 1), 2 + grow)
        pygame.draw.line(s, col, (sx, 1), (min(w - 1, sx + r), r + 1), 2 + grow)
    return s


def _rotated(spr, r, col, ang):
    """Cached rotation of a sprite in 15-degree steps (petals)."""
    key = ("rot", r, col[0], col[1], col[2], ang)
    s = _SPR.get(key)
    if s is None:
        s = pygame.transform.rotate(spr, ang)
        _SPR[key] = s
    return s


def _star_surface(r, rgb):
    """A chunky five-point star with a paler core (reads as a star even at 4px)."""
    w = r * 2 + 3
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    c = w / 2
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((c + math.cos(ang) * rad, c + math.sin(ang) * rad))
    pygame.draw.polygon(s, rgb, pts)
    if r >= 4:
        core = tuple(min(255, v + 60) for v in rgb)
        pygame.draw.circle(s, core, (int(c), int(c)), max(1, r // 3))
    return s


def _heart_surface(r, rgba):
    """A small SRCALPHA surface containing one heart, sized to the particle."""
    w = int(r * 2.6) + 4
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    _draw_heart(s, w // 2, w // 2, r, rgba)
    return s
