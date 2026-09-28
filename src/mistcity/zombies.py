"""Mist City zombies — walker / runner / hard-hat worker.

Owner: Chat 7 (Mist City). Stats, drop tables and procedural sprites for the
three V1 archetypes. Drops use item ids registered in ``loot.MATERIALS`` by
Chat 1 (never ores — the city gives *parts*, the mine gives rocks).
Art direction: cute-spooky pastel — minty grey skin, hollow-but-glinting
eyes, no gore. Scaling by "runs cleared" can hook in later via ``level``.
"""
import math
import random
import pygame
from .world2d import GROUND_Y, LEVEL_W

W, H = 24, 44
AGGRO_X = 540          # how far (px) a zombie notices a living player
ATTACK_CD = 0.9
DYING_T = 0.35         # seconds a slain zombie takes to melt into the mist

ARCHETYPES = {
    # slow, middling HP — the streets' bread and butter
    "walker": dict(label="Mist Walker", hp=34, speed=42, dmg=10, armor=0.0,
                   xp=8, gold=(4, 9),
                   skin=(166, 198, 174), shirt=(96, 110, 128), pants=(70, 78, 88),
                   drops=[("scrap_iron", 0.50, (1, 2)), ("wire", 0.30, (1, 1)),
                          ("old_coin", 0.22, (1, 1)), ("tainted_crystal", 0.01, (1, 1))]),
    # fast, fragile — keeps you off the ground
    "runner": dict(label="Mist Runner", hp=18, speed=118, dmg=8, armor=0.0,
                   xp=10, gold=(6, 12),
                   skin=(172, 204, 170), shirt=(116, 128, 92), pants=(64, 74, 70),
                   drops=[("wire", 0.45, (1, 2)), ("mutant_herb", 0.30, (1, 1)),
                          ("old_coin", 0.22, (1, 1)), ("tainted_crystal", 0.01, (1, 1))]),
    # armoured: incoming damage reduced 30% by the hard hat
    "worker": dict(label="Mist Worker", hp=46, speed=36, dmg=14, armor=0.30,
                   xp=16, gold=(10, 18),
                   skin=(160, 192, 168), shirt=(214, 150, 84), pants=(82, 88, 96),
                   drops=[("gear_scrap", 0.55, (1, 2)), ("old_battery", 0.35, (1, 1)),
                          ("scrap_iron", 0.30, (1, 2)), ("tainted_crystal", 0.02, (1, 1))]),
    # Old Factory only: a sealed hazmat suit (tough) that bursts into a short-lived
    # acid puddle when it drops - don't stand where it fell
    "hazmat": dict(label="Mist Hazmat", hp=42, speed=33, dmg=12, armor=0.15,
                   xp=14, gold=(8, 16),
                   skin=(168, 200, 172), shirt=(222, 206, 104), pants=(196, 180, 88),
                   drops=[("old_battery", 0.40, (1, 1)), ("mutant_herb", 0.35, (1, 1)),
                          ("wire", 0.30, (1, 2)), ("tainted_crystal", 0.02, (1, 1))]),
}


def _mix(c, k):
    """Lerp a colour toward white by k (hit-flash)."""
    return tuple(int(a + (255 - a) * k) for a in c)


class Zombie:
    def __init__(self, x, kind, level=0, rng=None):
        rng = rng or random
        a = ARCHETYPES[kind]
        self.kind = kind
        self.label = a["label"]
        self.x = float(x)
        self.y = float(GROUND_Y)
        scale = 1.0 + 0.15 * level            # future: runs-cleared scaling
        self.max_hp = self.hp = int(a["hp"] * scale)
        self.speed = a["speed"] * rng.uniform(0.88, 1.15)
        self.dmg = int(a["dmg"] * scale)
        self.armor = a["armor"]
        self.xp = a["xp"]
        self.gold = a["gold"]
        self.drops = a["drops"]
        self.skin, self.shirt, self.pants = a["skin"], a["shirt"], a["pants"]
        self.facing = -1
        self.atk_cd = rng.uniform(0.2, ATTACK_CD)
        self.flash = 0.0
        self.anim = rng.uniform(0, 9.0)
        self.rewarded = False
        self.groan_t = rng.uniform(2, 8)
        self.rise = 0.0                        # >0: summoned, still climbing out
        self.dying = 0.0                       # >0: melting back into the street

    def eye_points(self):
        """World-space eye glints (drawn over the power-outage darkness)."""
        f = self.facing
        lean = 6 if self.kind == "runner" else 0
        hx = self.x + f * (3 + lean)
        hy = self.y - 42 + math.sin(self.anim * (6.0 if self.kind == "runner" else 3.2))
        hy += self._sink()
        return [(hx + f * 2, hy), (hx + f * 7, hy)]

    def _sink(self):
        """Pixels below the street line (rising out / melting back in)."""
        if self.dying > 0:
            return (1.0 - self.dying / DYING_T) * 46
        return self.rise * 40

    def rect(self):
        return pygame.Rect(int(self.x - W / 2), int(self.y - H), W, H)

    def hit(self, dmg):
        """Take a sword hit; helmet armour shaves 30% off. Returns damage dealt."""
        eff = max(1, int(round(dmg * (1.0 - self.armor))))
        self.hp -= eff
        self.flash = 0.15
        return eff

    def update(self, dt, players, level_w=LEVEL_W, aggro=AGGRO_X):
        """Shamble at the nearest living player; returns [(player2d, dmg), ...]
        for every bite that connects this frame. ``aggro`` grows with the run's
        noise meter (loud duos get noticed from further away)."""
        self.atk_cd = max(0.0, self.atk_cd - dt)
        self.flash = max(0.0, self.flash - dt)
        events = []
        if self.rise > 0:                                # clawing up out of the street
            self.rise = max(0.0, self.rise - dt)
            self.anim += dt
            return events
        targets = [q for q in players if not q.ghost]
        if targets:
            tgt = min(targets, key=lambda q: abs(q.x - self.x))
            dx = tgt.x - self.x
            if abs(dx) <= aggro:
                if abs(dx) > 12:
                    sway = 1.0
                    if self.kind == "walker":            # lurching gait
                        sway = 0.72 + 0.28 * math.sin(self.anim * 2.4)
                    self.x += math.copysign(self.speed * sway * dt, dx)
                    self.facing = 1 if dx > 0 else -1
                # bite anything overlapping (only hurts players ON the ground line —
                # platforms are safe vantage points, that's the point of them)
                if self.atk_cd <= 0:
                    zr = self.rect().inflate(8, 0)
                    for q in targets:
                        if q.y >= GROUND_Y - 4 and zr.colliderect(q.rect()):
                            events.append((q, self.dmg))
                            self.atk_cd = ATTACK_CD
                            break
            else:                                        # idle drift
                self.x += math.sin(self.anim * 0.6) * self.speed * 0.12 * dt
        self.x = max(W / 2, min(level_w - W / 2, self.x))
        self.anim += dt * (2.0 if self.kind == "runner" else 1.0)
        return events

    # --------------------------------------------------------------- draw --
    def draw(self, surf, camx, t):
        sink = self._sink()
        if sink <= 0:
            self._draw(surf, camx, t)
            return
        old = surf.get_clip()                       # climbing out: hide below the street
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), GROUND_Y + 2))
        self._draw(surf, camx, t)
        surf.set_clip(old)
        sx = int(self.x - camx)
        if self.dying > 0:                          # a wisp of mist where it sank
            k = self.dying / DYING_T
            pygame.draw.circle(surf, (190, 214, 204), (sx, GROUND_Y - 6 - int((1 - k) * 18)),
                               4 + int((1 - k) * 10), 2)
            return
        for k in range(3):                          # kicked-up rubble
            pygame.draw.circle(surf, (104, 108, 110),
                               (sx - 12 + k * 12, GROUND_Y + 2 - int(self.rise * 10) % 5), 3)

    def _draw(self, surf, camx, t):
        sx = int(self.x - camx)
        if sx < -40 or sx > surf.get_width() + 40:
            return
        sy = int(self.y + self._sink())
        k = min(1.0, self.flash / 0.15) * 0.7
        skin, shirt, pants = _mix(self.skin, k), _mix(self.shirt, k), _mix(self.pants, k)
        bob = math.sin(self.anim * (6.0 if self.kind == "runner" else 3.2))
        lean = 6 if self.kind == "runner" else 0          # runners lunge forward
        f = self.facing
        # shadow
        sh = pygame.Surface((34, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (20, 22, 26, 80), sh.get_rect())
        surf.blit(sh, (sx - 17, sy - 5))
        # legs (alternating shuffle)
        lo = int(3 * bob)
        pygame.draw.rect(surf, pants, (sx - 8, sy - 16 + max(0, lo), 7, 16 - max(0, lo)))
        pygame.draw.rect(surf, pants, (sx + 1, sy - 16 + max(0, -lo), 7, 16 - max(0, -lo)))
        # torso (workers wear a hi-vis vest)
        torso = pygame.Rect(sx - 9, sy - 34, 18, 19)
        pygame.draw.rect(surf, shirt, torso, border_radius=3)
        if self.kind == "worker":
            pygame.draw.rect(surf, _mix((250, 214, 96), k), (torso.x + 2, torso.y, 4, torso.h))
            pygame.draw.rect(surf, _mix((250, 214, 96), k), (torso.right - 6, torso.y, 4, torso.h))
        # arms out in front (classic shamble), waving slightly
        ay = sy - 30 + int(2 * bob)
        pygame.draw.rect(surf, skin, (sx + (1 if f > 0 else -13) + f * lean // 2, ay, 12, 5),
                         border_radius=2)
        pygame.draw.rect(surf, skin, (sx + (2 if f > 0 else -14) + f * lean // 2, ay + 7, 12, 5),
                         border_radius=2)
        # head
        hx = sx + f * (3 + lean)
        hy = sy - 42 + int(bob)
        pygame.draw.circle(surf, skin, (hx, hy), 9)
        # messy hair tuft / helmet / hazmat hood
        if self.kind == "hazmat":
            suit = _mix((222, 206, 104), k)
            pygame.draw.circle(surf, suit, (hx, hy), 11)
            pygame.draw.ellipse(surf, (60, 86, 90), (hx - 7 + f * 2, hy - 5, 13, 10))     # visor
            pygame.draw.ellipse(surf, (150, 235, 190), (hx - 7 + f * 2, hy - 5, 13, 10), 1)
            surf.fill((220, 250, 236), (hx - 3 + f * 3, hy - 3, 2, 2))
            pygame.draw.rect(surf, (120, 128, 120), (hx - f * 12 - 3, hy + 6, 7, 13), border_radius=3)
            pygame.draw.circle(surf, (160, 236, 120), (hx - f * 12, hy + 5), 2)
            pygame.draw.line(surf, (70, 72, 70), (hx - f * 9, hy + 2), (hx - f * 2, hy + 5), 2)
        elif self.kind == "worker":
            pygame.draw.rect(surf, _mix((246, 200, 70), k), (hx - 10, hy - 9, 20, 7),
                             border_radius=3)
            pygame.draw.rect(surf, _mix((246, 200, 70), k), (hx - 12, hy - 3, 24, 3),
                             border_radius=2)
        else:
            pygame.draw.circle(surf, _mix((74, 84, 80), k), (hx - f * 3, hy - 6), 5)
        # hollow eyes with a tiny glint (cute-spooky, not gory)
        for ex in ((hx + f * 2, hx + f * 7) if self.kind != "hazmat" else ()):
            pygame.draw.rect(surf, (36, 42, 44), (ex - 1, hy - 2, 3, 4))
            surf.fill((220, 245, 230), (ex, hy - 1, 1, 1))
        if self.kind != "hazmat":
            pygame.draw.line(surf, (60, 72, 68), (hx + f * 2, hy + 5), (hx + f * 6, hy + 6), 1)
        # hp bar once damaged
        if 0 < self.hp < self.max_hp:
            w = 24
            frac = self.hp / self.max_hp
            pygame.draw.rect(surf, (40, 40, 46), (sx - w // 2, sy - H - 10, w, 4))
            pygame.draw.rect(surf, (224, 110, 110), (sx - w // 2, sy - H - 10, int(w * frac), 4))
