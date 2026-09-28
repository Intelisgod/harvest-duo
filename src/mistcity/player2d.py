"""Mist City player controller — platformer physics over the shared Player.

Owner: Chat 7 (Mist City). ``Player2D`` *wraps* the main-game
``entities.Player`` (the very same object), so HP / energy / inventory /
tool tiers carry over in both directions automatically. This file adds the
side-view physics (gravity, jump, one-way platforms), the co-op ghost/revive
rule, and side-view rendering that reuses the player's existing sprite frames
so both farmers look like themselves in the mist.
"""
import math
import pygame
from ..settings import TILE
from .world2d import GRAVITY, GROUND_Y, LEVEL_W, NEON_MINT, mist_font

MOVE_SPEED = 235.0
JUMP_V = 650.0            # apex ~124 px — enough for awnings (116) and car roofs
W, H = 22, 42
SWING_T = 0.25            # seconds of sword-swipe animation
HURT_INVULN = 0.8


class Player2D:
    def __init__(self, p, x):
        self.p = p                      # the shared entities.Player
        self.x = float(x)
        self.y = float(GROUND_Y)        # y = feet
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.facing = 1
        self.swing = 0.0
        self.ghost = False
        self.anim = 0.0
        self.spawn_x = float(x)         # ghosts drift back here and wait
        self.kills = 0
        self.loot_n = 0
        self.push = 0.0                 # external x-velocity this frame (conveyors)
        self.stand = None               # platform Rect we stand on (None = street)
        self.landed = False             # touched down this frame (dust puff)

    # ------------------------------------------------------------ queries --
    def rect(self):
        return pygame.Rect(int(self.x - W / 2), int(self.y - H), W, H)

    def damage(self):
        tier = self.p.tool_tiers.get("sword", 0) if self.p.tool_tiers else 0
        bonus = self.p.skills.sword_bonus if self.p.skills else 0
        return 6 + bonus + tier * 4     # same formula as CombatMixin.sword_attack

    def attack_box(self):
        tier = self.p.tool_tiers.get("sword", 0) if self.p.tool_tiers else 0
        reach = int(TILE * (0.9 + 0.12 * tier))
        r = self.rect()
        if self.facing > 0:
            return pygame.Rect(r.right - 4, r.top - 6, reach, H + 6)
        return pygame.Rect(r.left + 4 - reach, r.top - 6, reach, H + 6)

    # ------------------------------------------------------------ actions --
    def jump(self):
        if not self.ghost and self.on_ground:
            self.vy = -JUMP_V
            self.on_ground = False
            return True
        return False

    def start_swing(self):
        if self.ghost or self.swing > 0.06:
            return False
        self.swing = SWING_T
        return True

    def hurt(self, dmg, knock=True):
        """Apply damage; returns True if it landed (not ghost / not invulnerable).
        The shared ``defense`` buff (Player.buff) shaves damage like in the farm."""
        if self.ghost or self.p.hurt_cd > 0:
            return False
        try:
            dmg = max(1, int(round(dmg * (1.0 - min(0.6, self.p.buff("defense"))))))
        except Exception:
            pass
        self.p.health -= dmg
        self.p.hurt_cd = HURT_INVULN
        if knock:
            self.vy = min(self.vy, -220.0)   # a little pop of knockback
            self.on_ground = False
            self.stand = None
        return True

    def place(self, x):
        """Drop onto the street at ``x`` (zone change): fresh physics, same state."""
        self.x = self.spawn_x = float(x)
        self.y = float(GROUND_Y)
        self.vx = self.vy = 0.0
        self.on_ground = True
        self.stand = None
        if self.ghost:
            self.y = GROUND_Y - 26.0

    def die(self):
        """Down -> ghost. Drifts home to the gate and bobs there until touched."""
        self.ghost = True
        self.p.health = 0
        self.vy = 0.0

    def revive(self, at_x=None):
        self.ghost = False
        self.p.health = max(1, int(self.p.max_health * 0.5))
        if at_x is not None:
            self.x = float(at_x)
        self.y = float(GROUND_Y)
        self.vy = 0.0
        self.on_ground = True

    # ------------------------------------------------------------- update --
    def update(self, dt, keys, world):
        self.p.hurt_cd = max(0.0, self.p.hurt_cd - dt)   # main loop isn't ticking him
        if self.swing > 0:
            self.swing -= dt
        if self.ghost:
            # float home and hover at the gate, waiting for a friendly touch
            if abs(self.x - self.spawn_x) > 6:
                self.x += math.copysign(min(110 * dt, abs(self.x - self.spawn_x)),
                                        self.spawn_x - self.x)
            self.anim += dt
            self.y = GROUND_Y - 26 + math.sin(self.anim * 2.6) * 7
            return
        K = self.p.keys
        ax = (1 if keys[K["right"]] else 0) - (1 if keys[K["left"]] else 0)
        spd = MOVE_SPEED * (0.55 if self.p.energy <= 0 else 1.0)
        try:
            spd *= 1.0 + max(0.0, min(0.5, self.p.buff("speed")))   # shared speed buff
        except Exception:
            pass
        self.vx = ax * spd
        if ax:
            self.facing = ax
        lw = getattr(world, "level_w", LEVEL_W)
        self.x = max(W / 2, min(lw - W / 2, self.x + (self.vx + self.push) * dt))
        self.push = 0.0                          # conveyors re-apply it each frame
        prev_feet = self.y
        was_ground = self.on_ground
        self.vy = min(self.vy + GRAVITY * dt, 900.0)
        self.y += self.vy * dt
        self.on_ground = False
        self.stand = None
        if self.y >= GROUND_Y:
            self.y, self.vy, self.on_ground = float(GROUND_Y), 0.0, True
        elif self.vy >= 0:
            r = self.rect()
            for pl in world.platforms:               # one-way: only land from above
                if prev_feet <= pl.top + 1 and r.bottom >= pl.top and \
                        r.right > pl.left + 4 and r.left < pl.right - 4:
                    self.y, self.vy, self.on_ground = float(pl.top), 0.0, True
                    self.stand = pl
                    break
        self.landed = self.on_ground and not was_ground
        self.anim += dt * (1.7 if ax else 0.55)

    # --------------------------------------------------------------- draw --
    def _tag(self):
        """Cached little "P1"/"P2" label (mint / pink) drawn over the head."""
        tag = getattr(self, "_tag_img", None)
        if tag is None:
            idx = getattr(self, "idx", 0)
            col = NEON_MINT if idx == 0 else (236, 152, 202)
            f = mist_font(12, True)
            txt = f.render(f"P{idx + 1}", True, col)
            tag = pygame.Surface((txt.get_width() + 8, txt.get_height() + 2), pygame.SRCALPHA)
            tag.fill((24, 26, 30, 150))
            tag.blit(txt, (4, 1))
            self._tag_img = tag
        return tag

    def draw(self, surf, camx, t):
        p = self.p
        dirname = "right" if self.facing > 0 else "left"
        frames = p.frames.get(dirname) or next(iter(p.frames.values()))
        if self.ghost or not frames:
            fi = 0
        elif not self.on_ground:
            fi = 1 % len(frames)
        elif abs(self.vx) > 1:
            fi = int(self.anim * 6) % len(frames)
        else:
            fi = 0
        img = frames[fi]
        sx = int(self.x - TILE / 2 - camx)
        sy = int(self.y - TILE + 2)
        if self.ghost:
            halo = pygame.Surface((56, 56), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*NEON_MINT, 36), (28, 28), 26)
            surf.blit(halo, (int(self.x - camx) - 28, int(self.y) - 54))
            g = img.copy()
            g.set_alpha(120)
            surf.blit(g, (sx, sy))
            return
        # soft shadow on whatever we stand over
        sh = pygame.Surface((36, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (20, 22, 26, 90), sh.get_rect())
        surf.blit(sh, (int(self.x - camx) - 18, int(self.y) - 6))
        if p.hurt_cd > HURT_INVULN - 0.25 and int(t * 24) % 2:
            f = img.copy()
            f.fill((255, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(f, (sx, sy))
        else:
            surf.blit(img, (sx, sy))
        # tiny co-op tag so the duo never loses track of who is who in the fog
        tag = self._tag()
        if tag is not None:
            surf.blit(tag, (int(self.x - camx) - tag.get_width() // 2, sy - 14))
        if self.swing > 0:                      # sword swipe arc
            prog = 1.0 - self.swing / SWING_T
            cx = int(self.x + self.facing * 14 - camx)
            cy = int(self.y - H * 0.55)
            r0 = 16 + int(14 * prog)
            a0 = -1.4 if self.facing > 0 else math.pi - 1.4
            sweep = (2.2 * prog) * self.facing
            for k, col in ((0, (250, 250, 240)), (3, (210, 230, 220))):
                rect = pygame.Rect(cx - r0 - k, cy - r0 - k, (r0 + k) * 2, (r0 + k) * 2)
                try:
                    if self.facing > 0:
                        pygame.draw.arc(surf, col, rect, a0 - sweep, a0, 3)
                    else:
                        pygame.draw.arc(surf, col, rect, a0, a0 + abs(sweep) + 0.01, 3)
                except Exception:
                    pass
