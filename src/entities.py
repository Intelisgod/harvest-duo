"""Player and Monster entities (animated)."""
import math
import random
import pygame
from .settings import TILE, PLAYER_SPEED, MAX_ENERGY, MAX_HEALTH
from . import assets
from .assets import terrain as _terrain
from . import monsters as MDEF
from . import critters
from .craft import TIER_COLORS

_DIR = {(0, 1): "down", (0, -1): "up", (-1, 0): "left", (1, 0): "right"}

# how far (radians, screen space) the tool head sweeps from 'up' to the strike,
# chosen per facing so it always arcs toward the side we're facing
_SWING_DELTA = {(0, 1): math.pi, (1, 0): math.pi / 2, (-1, 0): -math.pi / 2, (0, -1): 0.0}


def _swing_theta(prog, fx, fy):
    """Tool head angle over a use-swing: starts overhead, sweeps to the facing side."""
    k = prog * prog * (3 - 2 * prog)               # smoothstep
    return -math.pi / 2 + _SWING_DELTA[(fx, fy)] * k


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)                      # smoothstep


# items eaten/drunk with a raise-to-mouth animation; everything else is just held
_DRINK_ITEMS = {"milk", "milk_tea"}


class Player:
    def __init__(self, name, keys, appearance, gx, gy):
        self.name = name
        self.keys = keys
        self.appearance = dict(appearance)
        self.x = gx * TILE + TILE / 2
        self.y = gy * TILE + TILE / 2
        self.fx, self.fy = 0, 1
        self.energy = MAX_ENERGY
        self.health = MAX_HEALTH
        self.inv = None
        self.skills = None             # progress.Skills, attached by Game
        self.tool_tiers = {}           # tool -> tier index, attached by Game
        self.hurt_cd = 0.0
        # timed buffs (food, perks, events): kind -> [amount, seconds_left, label]
        # kinds used across the game: "speed" (+fraction move speed), "luck",
        # "mining", "fishing", "farming", "combat" (+fraction damage),
        # "defense" (fraction damage taken removed), "regen" (energy/sec)
        self.buffs = {}
        # animation
        self.frames = assets.frames_for(self.appearance, arms=False)
        self.dirname = "down"
        self.anim_t = 0.0
        self.frame = 0
        self.idle_t = 0.0
        self.moving = False
        self.swing = 0.0           # >0 while a tool swing animation plays
        self.step_acc = 0.0        # footstep dust timer
        self.emit_step = False     # flag read by game to spawn dust
        # item-use animation (eat / drink / sow / place / generic)
        self.item_use = 0.0        # seconds remaining
        self.item_use_dur = 0.0    # total duration of the current item-use
        self.item_use_kind = None  # "eat" | "drink" | "sow" | "place" | "generic"
        self.item_use_name = None  # item id being animated (kept past stack-empty)
        # happy little hop (emotes / gifts / love boost); ticked by CoopMixin
        self.hop_t = 0.0
        self.hop_dur = 0.3

    def hop(self, dur=0.3):
        """Start a small cosmetic jump (drawn by draw(); no gameplay effect)."""
        self.hop_t = self.hop_dur = max(0.05, dur)

    def set_appearance(self, appearance, name=None):
        self.appearance = dict(appearance)
        if name:
            self.name = name
        self.frames = assets.frames_for(self.appearance, arms=False)

    # ---- buffs (see self.buffs) ----
    def add_buff(self, kind, seconds, amount, label=None):
        """Grant/refresh a timed buff. Re-applying keeps the stronger amount and
        the longer remaining time."""
        cur = self.buffs.get(kind)
        if cur:
            cur[0] = max(cur[0], amount)
            cur[1] = max(cur[1], seconds)
            cur[2] = label or cur[2]
        else:
            self.buffs[kind] = [amount, seconds, label or kind.title()]

    def buff(self, kind):
        """Current amount of a buff (0.0 when inactive)."""
        b = self.buffs.get(kind)
        return b[0] if b else 0.0

    def _tick_buffs(self, dt):
        if not self.buffs:
            return
        for k in list(self.buffs):
            self.buffs[k][1] -= dt
            if self.buffs[k][1] <= 0:
                del self.buffs[k]
        regen = self.buff("regen")
        if regen:
            self.energy = min(MAX_ENERGY, self.energy + regen * dt)

    @property
    def max_health(self):
        bonus = self.skills.max_hp_bonus if self.skills else 0
        return MAX_HEALTH + bonus

    def rect(self):
        return pygame.Rect(self.x - 12, self.y - 6, 24, 18)

    def target_tile(self):
        gx = int(self.x // TILE) + self.fx
        gy = int(self.y // TILE) + self.fy
        return gx, gy

    def update(self, dt, pressed, area):
        self._tick_buffs(dt)
        if self.hurt_cd > 0:
            self.hurt_cd -= dt
        if self.swing > 0:
            self.swing -= dt
        if self.item_use > 0:
            self.item_use -= dt
            if self.item_use <= 0:
                self.item_use = 0.0
                self.item_use_kind = self.item_use_name = None
        self.idle_t += dt
        self.emit_step = False

        dx = dy = 0
        if pressed[self.keys["left"]]:
            dx -= 1
        if pressed[self.keys["right"]]:
            dx += 1
        if pressed[self.keys["up"]]:
            dy -= 1
        if pressed[self.keys["down"]]:
            dy += 1

        self.moving = bool(dx or dy)
        if self.moving:
            self.fx, self.fy = (dx, 0) if dx else (0, dy)
            self.dirname = _DIR.get((self.fx, self.fy), self.dirname)
            mag = (dx * dx + dy * dy) ** 0.5
            spd = PLAYER_SPEED * (0.55 if self.energy <= 0 else 1.0) * (1.0 + self.buff("speed"))
            self._move(dx / mag * spd * dt, 0, area)
            self._move(0, dy / mag * spd * dt, area)
            # walk-cycle animation
            self.anim_t += dt * (spd / 26)
            self.frame = int(self.anim_t) % 4
            # footstep dust cadence
            self.step_acc += dt
            if self.step_acc > 0.28:
                self.step_acc = 0.0
                self.emit_step = True
        else:
            self.frame = 0
            self.anim_t = 0.0

    def _move(self, ddx, ddy, area):
        self.x += ddx
        r = self.rect()
        for gx in range(int(r.left // TILE), int(r.right // TILE) + 1):
            for gy in range(int(r.top // TILE), int(r.bottom // TILE) + 1):
                if area.is_solid(gx, gy):
                    tr = pygame.Rect(gx * TILE, gy * TILE, TILE, TILE)
                    if r.colliderect(tr):
                        if ddx > 0:
                            self.x = tr.left - 12
                        elif ddx < 0:
                            self.x = tr.right + 12
                        r = self.rect()
        self.y += ddy
        r = self.rect()
        for gx in range(int(r.left // TILE), int(r.right // TILE) + 1):
            for gy in range(int(r.top // TILE), int(r.bottom // TILE) + 1):
                if area.is_solid(gx, gy):
                    tr = pygame.Rect(gx * TILE, gy * TILE, TILE, TILE)
                    if r.colliderect(tr):
                        if ddy > 0:
                            self.y = tr.top - 12
                        elif ddy < 0:
                            self.y = tr.bottom + 6
                        r = self.rect()

    def take_damage(self, amount):
        if self.hurt_cd <= 0:
            amount = amount * max(0.0, 1.0 - min(0.8, self.buff("defense")))
            self.health = max(0, self.health - max(1, int(round(amount))))
            self.hurt_cd = 1.0

    def trigger_swing(self):
        self.swing = 0.28

    def trigger_item_use(self, name, kind="generic", dur=0.6):
        """Start an item-use animation (raise-to-mouth, sow, place, ...). Purely
        cosmetic — the game has already applied the item's effect."""
        self.item_use_name = name
        self.item_use_kind = kind
        self.item_use_dur = dur
        self.item_use = dur

    def draw(self, surf, cam):
        bob = 0 if self.moving else int(math.sin(self.idle_t * 3) * 1.5)
        if self.hop_t > 0:
            bob -= int(math.sin(math.pi * (1.0 - self.hop_t / self.hop_dur)) * 7)
        sx = self.x - TILE / 2 - cam.x
        sy = self.y - TILE / 2 - 12 - cam.y + bob
        # shadow
        sh = assets.shadow()
        surf.blit(sh, (self.x - cam.x - 13, self.y - cam.y + 4))
        # flash red when recently hurt -- RGB only: adding alpha (BLEND_RGBA_ADD)
        # also lit up the frame's transparent pixels as a hard red square
        frame = self.frames[self.dirname][self.frame]
        if self.hurt_cd > 0.6:
            frame = frame.copy()
            frame.fill((110, 34, 34), special_flags=pygame.BLEND_RGB_ADD)
        # held tool goes behind the body when facing away (up), else in front
        if self.dirname == "up":
            self._draw_held(surf, cam, bob)
            surf.blit(frame, (sx, sy))
        else:
            surf.blit(frame, (sx, sy))
            self._draw_held(surf, cam, bob)

    def _draw_held(self, surf, cam, bob):
        """Dispatch held rendering. An active item-use animation takes priority so
        it completes even if eating emptied the stack; otherwise the current hotbar
        selection is shown — tools swing, every other item is held in hand."""
        if not self.inv:
            return
        if self.item_use > 0 and self.item_use_name:
            self._draw_held_item(surf, cam, bob, self.item_use_name)
            return
        entry = self.inv.selected_entry()
        if not entry:
            return
        kind, name = entry
        if kind == "tool":
            self._draw_held_tool(surf, cam, bob, name)
        else:
            self._draw_held_item(surf, cam, bob, name)

    def _draw_held_item(self, surf, cam, bob, name):
        """Hold ANY inventory item in hand, with a use animation when active:
        food rises to the mouth in bites, drinks tip back, seeds sweep low to sow,
        sprinkler/placeables lower to the ground; otherwise it rests at the side."""
        skin, _st, _h, shirt = assets.resolve_appearance(self.appearance)
        fx, fy = self.fx, self.fy
        cxp = self.x - cam.x
        cyp = self.y - cam.y + bob
        lead_right = (fx >= 0)
        lsh = (cxp - 8, cyp - 6)
        rsh = (cxp + 8, cyp - 6)
        hold_sh = rsh if lead_right else lsh         # shoulder of the holding arm
        rest_sh = lsh if lead_right else rsh

        def arm(sh, h):
            pygame.draw.line(surf, shirt, sh, (int(h[0]), int(h[1])), 5)

        prog = -1.0
        if self.item_use > 0 and self.item_use_name == name and self.item_use_dur > 0:
            prog = 1 - (self.item_use / self.item_use_dur)
        kind = self.item_use_kind if prog >= 0 else None

        # rest pose: item held out a bit in the facing direction, by the waist
        hx = cxp + (11 if lead_right else -11) + fx * 2
        hy = cyp + 3
        scale = 0.72
        tilt = 0.0
        rest_hand = (cxp + (-11 if lead_right else 11), cyp + 4)

        if kind == "eat":
            mouth = (cxp + fx * 2, cyp - 13)
            e = _ease(min(1.0, prog * 1.3))
            hx += (mouth[0] - hx) * e
            hy += (mouth[1] - hy) * e
            bites = int(min(2, prog * 3))            # shrink in 3 visible bites
            scale = 0.72 * (1.0 - 0.22 * bites)
        elif kind == "drink":
            mouth = (cxp + fx * 2, cyp - 12)
            e = _ease(min(1.0, prog * 1.3))
            hx += (mouth[0] - hx) * e
            hy += (mouth[1] - hy) * e
            tilt = (-fx if fx else 1) * 0.7 * math.sin(min(1.0, prog) * math.pi)
        elif kind == "sow":
            sweep = math.sin(prog * math.pi)
            hx = cxp + fx * (5 + 9 * sweep)
            hy = cyp + 5 + 2 * sweep
            scale = 0.6
        elif kind == "place":
            hy = cyp + 3 + 9 * _ease(prog)
            scale = 0.62
        elif kind == "generic":
            hy = cyp + 3 - 7 * math.sin(min(1.0, prog) * math.pi)

        hand = (hx, hy + 2)
        arm(hold_sh, hand)
        arm(rest_sh, rest_hand)
        assets.draw_held_item(surf, name, hx, hy, scale, tilt)
        for hpt in (hand, rest_hand):
            pygame.draw.circle(surf, skin, (int(hpt[0]), int(hpt[1])), 3)

    def _draw_held_tool(self, surf, cam, bob, name):
        """Draw the held tool live, oriented along a direction vector so the wooden
        handle stays in the hands and the head leads the strike. The arms reach to
        grip it (two hands for hoe/axe/pickaxe, one for the rest)."""
        fx, fy = self.fx, self.fy
        skin, _st, _h, shirt = assets.resolve_appearance(self.appearance)
        cxp = self.x - cam.x
        cyp = self.y - cam.y + bob
        two = name in assets.HELD_TWO_HAND
        lead_right = (fx >= 0)
        lsh = (cxp - 8, cyp - 6)
        rsh = (cxp + 8, cyp - 6)
        prog = (1 - (self.swing / 0.28)) if self.swing > 0 else -1.0

        def arm(sh, h):
            pygame.draw.line(surf, shirt, sh, (int(h[0]), int(h[1])), 5)

        if name == "watering_can":
            gx = cxp + (9 if lead_right else -9)
            gy = cyp + (2 if prog < 0 else 6)
            tilt = 0.0 if prog < 0 else math.sin(min(1.0, prog * 1.4) * math.pi)
            assets.draw_can(surf, gx, gy, fx, fy, tilt)
            hand = (gx - fx * 3 if fx else gx - 4, gy)
            rest_hand = (cxp + (-11 if lead_right else 11), cyp + 4)
            arm(rsh if lead_right else lsh, hand)
            arm(lsh if lead_right else rsh, rest_hand)
            hands = [hand, rest_hand]
        else:
            if prog < 0:                       # REST: shouldered (handle in hand, head up)
                gx, gy = cxp + (7 if lead_right else -7), cyp + 1
                dx, dy = 0.0, -1.0
            else:                              # USE: swing arc, head leads toward the tile
                th = _swing_theta(prog, fx, fy)
                dx, dy = math.cos(th), math.sin(th)
                gx, gy = cxp + fx * 2, cyp - 1
            tier = self.tool_tiers.get(name, 0) if self.tool_tiers else 0
            head = TIER_COLORS[tier] if tier > 0 else None
            assets.draw_tool(surf, name, gx, gy, dx, dy, head)
            h1 = (gx + dx * 1, gy + dy * 1)    # front hand on the handle, at the grip
            if two:
                h2 = (gx + dx * 6, gy + dy * 6)
                if (h1[0] - lsh[0]) ** 2 < (h1[0] - rsh[0]) ** 2:
                    arm(lsh, h1); arm(rsh, h2)
                else:
                    arm(rsh, h1); arm(lsh, h2)
                hands = [h1, h2]
            else:
                rest_hand = (cxp + (-11 if lead_right else 11), cyp + 4)
                arm(rsh if lead_right else lsh, h1)
                arm(lsh if lead_right else rsh, rest_hand)
                hands = [h1, rest_hand]
        for hpt in hands:
            pygame.draw.circle(surf, skin, (int(hpt[0]), int(hpt[1])), 3)


class Monster:
    """Depth-scaled monster built from a monsters.ARCHETYPES entry. Drops, XP and
    gold live on the instance so the game can reward whoever lands the kill."""

    def __init__(self, gx, gy, arche="green_slime", depth=1):
        if isinstance(arche, (int, float)):     # legacy Monster(gx,gy,hp) -> slime
            arche = "green_slime"
        a = MDEF.ARCHETYPES.get(arche, MDEF.ARCHETYPES["green_slime"])
        self.name = arche if arche in MDEF.ARCHETYPES else "green_slime"
        self.label = a["label"]
        self.shape = a["shape"]
        self.color = a["color"]
        self.size = a["size"]
        self.behavior = a["behavior"]
        self.x = gx * TILE + TILE / 2
        self.y = gy * TILE + TILE / 2
        self.max_hp = self.hp = MDEF.hp_for(self.name, depth)
        self.speed = a["speed"]
        self.damage = MDEF.damage_for(self.name, depth)
        self.xp = a["xp"]
        self.gold = a["gold"]
        self.drops = a["drops"]
        self.boss = a.get("boss", False)
        self.frames = (MDEF.slime_frames(self.color, self.size, crown=a.get("boss", False))
                       if self.shape == "slime" else None)
        self.anim_t = 0.0
        self.hit_cd = 0.0
        self.flash = 0.0
        self.phase = random.random() * 6.28
        self.facing_left = False
        self.rewarded = False                   # set True once killed & loot granted

    def rect(self):
        s = self.size
        return pygame.Rect(self.x - s, self.y - s + 4, s * 2, s * 2 - 4)

    def update(self, dt, players, area):
        self.hit_cd = max(0, self.hit_cd - dt)
        self.flash = max(0, self.flash - dt)
        self.anim_t += dt * 6
        target = min(players, key=lambda p: (p.x - self.x) ** 2 + (p.y - self.y) ** 2)
        dx, dy = target.x - self.x, target.y - self.y
        d = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / d, dy / d
        custom = MDEF.BEHAVIORS.get(self.behavior)      # registry (monsters.py)
        if custom is not None:
            # a custom behaviour steers the monster: it returns the (ux, uy)
            # direction to move this frame (or None to stand still) and may
            # set extra fields on ``self`` (charge timers, projectiles, ...).
            r = custom(self, dt, players, area, target, ux, uy, d)
            ux, uy = r if r else (0.0, 0.0)
        elif self.behavior == "erratic":
            self.phase += dt * 6
            wob = math.sin(self.phase) * 0.7
            px, py = -uy, ux
            ux, uy = ux + px * wob, uy + py * wob
            n = (ux * ux + uy * uy) ** 0.5 or 1
            ux, uy = ux / n, uy / n
        elif self.behavior == "flee":
            # skittish prey: run from the nearest player (only when close)
            if d < TILE * 5:
                ux, uy = -ux, -uy
            else:
                self.phase += dt * 2
                ux, uy = math.cos(self.phase), math.sin(self.phase)
        self.facing_left = ux < 0
        nx = self.x + ux * self.speed * dt
        ny = self.y + uy * self.speed * dt
        if not area.is_solid(int(nx // TILE), int(ny // TILE)):
            self.x, self.y = nx, ny
        if self.damage > 0:
            for p in players:
                if self.rect().colliderect(p.rect()) and self.hit_cd <= 0:
                    p.take_damage(self.damage)
                    self.hit_cd = 0.8

    def draw(self, surf, cam):
        cx = self.x - cam.x
        cy = self.y - cam.y
        sz = self.size
        surf.blit(assets.shadow(int(sz * 1.8), int(sz * 0.7)),
                  (cx - sz * 0.9, cy + sz * 0.55))
        self._draw_body(surf, cx, cy)
        if self.flash > 0:
            fl = pygame.Surface((sz * 2 + 6, sz * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(fl, (255, 255, 255, 150), (sz + 3, sz + 3), sz)
            surf.blit(fl, (cx - sz - 3, cy - sz - 3))
        # health bar (wider for bosses); a boss's steps aside while the screen
        # boss plate shows its name + HP
        if self.boss and _terrain.boss_on_screen_bar(self.label):
            return
        w = int(sz * (3.2 if self.boss else 1.9))
        h = 5 if self.boss else 4
        ratio = max(0.0, min(1.0, self.hp / self.max_hp))
        bx, by = int(cx - w / 2), int(cy - sz - (16 if self.boss else 10))
        back = pygame.Rect(bx - 1, by - 1, w + 2, h + 2)            # dark rounded backing
        pygame.draw.rect(surf, (34, 20, 28), back, border_radius=back.h // 2)
        pygame.draw.rect(surf, (86, 30, 36), (bx, by, w, h), border_radius=h // 2)
        fw = int(w * ratio)
        if fw > 0:
            bar_col = (240, 180, 60) if self.boss else (220, 60, 60)
            pygame.draw.rect(surf, bar_col, (bx, by, max(h, fw), h), border_radius=h // 2)
        if self.boss:
            t = assets.boss_label(self.label)
            surf.blit(t, (int(cx - t.get_width() / 2), int(by - 17)))

    def _draw_body(self, surf, cx, cy):
        painter = MDEF.SHAPE_PAINTERS.get(self.shape)    # registry (monsters.py)
        if painter is not None:
            painter(self, surf, cx, cy)
            return
        col = self.color
        dk = tuple(max(0, c - 50) for c in col)
        if self.shape == "slime":
            frame = self.frames[int(self.anim_t) % len(self.frames)]
            surf.blit(frame, (cx - frame.get_width() / 2, cy - frame.get_height() / 2))
            return
        if self.shape == "bat":
            flap = math.sin(self.anim_t * 1.6) * 5
            pygame.draw.polygon(surf, col, [(cx - 2, cy), (cx - 15, cy - 7 - flap), (cx - 9, cy + 5)])
            pygame.draw.polygon(surf, col, [(cx + 2, cy), (cx + 15, cy - 7 - flap), (cx + 9, cy + 5)])
            pygame.draw.circle(surf, (54, 44, 66), (int(cx), int(cy)), 7)
            pygame.draw.circle(surf, (255, 220, 90), (int(cx - 3), int(cy - 1)), 1)
            pygame.draw.circle(surf, (255, 220, 90), (int(cx + 3), int(cy - 1)), 1)
        elif self.shape == "skeleton":
            # skull (sockets/nose/jaw+teeth) + spine, curved ribcage, limb bones, pelvis
            bob = math.sin(self.anim_t) * 1.2
            sway = math.sin(self.anim_t * 0.8) * 1.0
            bone = col
            bone_d = tuple(max(0, c - 78) for c in col)
            socket = (30, 28, 36)
            cxx = cx + sway
            sky = int(cy - 11 + bob)                       # skull centre
            # spine (vertebrae) from neck to pelvis
            for i in range(3):
                vy = cy - 3 + i * 3 + bob
                pygame.draw.line(surf, bone, (cxx, vy), (cxx, vy + 2), 2)
            # ribcage: 3 curved rib pairs, tapering downward
            for k in range(3):
                ry = cy - 4 + k * 3 + bob
                rw = 6 - k
                pygame.draw.arc(surf, bone, (cxx - rw, ry - 2, rw * 2, 7), 3.4, 6.0, 2)
                pygame.draw.arc(surf, bone, (cxx - rw, ry - 2, rw * 2, 7), 0.28, 2.88, 2)
            # arms: shoulder -> elbow -> hand (both sides)
            for sgn in (-1, 1):
                shx = cxx + sgn * 6
                ex, ey = shx + sgn * 2, cy + 2 + bob
                pygame.draw.line(surf, bone, (shx, cy - 4 + bob), (ex, ey), 2)
                pygame.draw.line(surf, bone, (ex, ey), (ex + sgn * 1, cy + 7 + bob), 2)
                pygame.draw.circle(surf, bone, (int(ex + sgn * 1), int(cy + 8 + bob)), 1)
            # pelvis
            pygame.draw.arc(surf, bone, (cxx - 4, cy + 5 + bob, 8, 6), 3.3, 6.1, 2)
            # legs: hip -> knee -> foot (both sides)
            for sgn in (-1, 1):
                hpx = cxx + sgn * 2
                ky = cy + 12 + bob
                pygame.draw.line(surf, bone, (hpx, cy + 8 + bob), (hpx, ky), 2)
                pygame.draw.line(surf, bone, (hpx, ky), (hpx, cy + 16 + bob), 2)
                pygame.draw.line(surf, bone, (hpx, cy + 16 + bob), (hpx + sgn * 3, cy + 16 + bob), 2)
            # skull
            skx = int(cxx)
            pygame.draw.circle(surf, bone, (skx, sky), 6)
            pygame.draw.circle(surf, bone_d, (skx, sky), 6, 1)
            pygame.draw.rect(surf, bone, (skx - 4, sky + 2, 8, 5), border_radius=2)   # jaw
            pygame.draw.line(surf, bone_d, (skx - 3, sky + 4), (skx + 3, sky + 4), 1)  # jaw seam
            for tx in (-2, 0, 2):                                                       # teeth
                pygame.draw.line(surf, bone_d, (skx + tx, sky + 2), (skx + tx, sky + 6), 1)
            pygame.draw.circle(surf, socket, (skx - 2, sky - 1), 2)                     # eye sockets
            pygame.draw.circle(surf, socket, (skx + 2, sky - 1), 2)
            pygame.draw.polygon(surf, socket, [(skx, sky + 1), (skx - 1, sky + 2), (skx + 1, sky + 2)])  # nasal
        elif self.shape == "golem":
            # a cluster of boulders with glowing eyes (scales for boss size)
            s = self.size
            lt = tuple(min(255, c + 28) for c in col)
            for ox, oy, r in [(-0.55, 0.22, 0.5), (0.5, 0.26, 0.5), (0.0, -0.5, 0.55),
                              (-0.32, -0.12, 0.55), (0.32, -0.08, 0.55), (0.0, 0.28, 0.62),
                              (-0.72, -0.38, 0.3), (0.68, -0.42, 0.3)]:
                rr = max(2, int(s * r)); bxx = int(cx + ox * s); byy = int(cy + oy * s)
                pygame.draw.circle(surf, col, (bxx, byy), rr)
                pygame.draw.circle(surf, lt, (bxx - rr // 3, byy - rr // 3), max(1, rr // 3))
                pygame.draw.circle(surf, dk, (bxx, byy), rr, 1)
            ex = max(3, int(s * 0.2))
            for sgn in (-1, 1):
                pygame.draw.circle(surf, (60, 30, 10), (int(cx + sgn * ex), int(cy - 2)), 4)
                pygame.draw.circle(surf, (255, 170, 70), (int(cx + sgn * ex), int(cy - 2)), 3)
                pygame.draw.circle(surf, (255, 240, 205), (int(cx + sgn * ex), int(cy - 3)), 1)
        elif self.shape == "spirit":
            # swirling vortex with a bright core
            s = self.size
            bob = math.sin(self.anim_t) * 2
            ccx, ccy = int(cx), int(cy + bob)
            glow = pygame.Surface((s * 3, s * 3), pygame.SRCALPHA)
            pygame.draw.circle(glow, (col[0], col[1], col[2], 60), (s * 3 // 2, s * 3 // 2), s)
            surf.blit(glow, (cx - s * 1.5, ccy - s * 1.5), special_flags=pygame.BLEND_RGBA_ADD)
            lt = tuple(min(255, c + 55) for c in col)
            ang = self.anim_t * 2.2
            for k in range(4):
                rad = int(s * (0.42 + 0.18 * k))
                a0 = ang + k * 0.85
                pygame.draw.arc(surf, lt if k % 2 else col,
                                (ccx - rad, ccy - rad, rad * 2, rad * 2), a0, a0 + 4.2, 2)
            pygame.draw.circle(surf, (120, 70, 162), (ccx, ccy), max(3, int(s * 0.42)))
            pygame.draw.circle(surf, (255, 190, 90), (ccx, ccy), max(2, int(s * 0.26)))
            pygame.draw.circle(surf, (255, 246, 212), (ccx, ccy), max(1, int(s * 0.12)))
        elif self.shape in ("boar", "wolf", "bear", "tiger", "deer"):
            fl = -1 if self.facing_left else 1
            bob = math.sin(self.anim_t * 1.4) * 1.2
            critters.draw_beast(surf, cx, cy + bob, self.size, fl, self.shape, self.color)
        elif self.shape == "wildman":
            fl = -1 if self.facing_left else 1
            bob = math.sin(self.anim_t * 1.4) * 1.0
            critters.wildman(surf, cx, cy + bob, self.size, fl, self.color)
        elif self.shape == "__legacy_beast__":
            fl = -1 if self.facing_left else 1
            s = self.size
            bob = math.sin(self.anim_t * 1.4) * 1.2
            lt = tuple(min(255, c + 30) for c in col)
            hx = cx + fl * s * 0.85
            hy = cy - s * 0.15 + bob
            for lx in (-0.62, -0.3, 0.28, 0.58):                 # 4 legs
                pygame.draw.rect(surf, dk, (int(cx + lx * s), int(cy + s * 0.35), 3, int(s * 0.55)),
                                 border_radius=1)
            pygame.draw.ellipse(surf, col, (cx - s, cy - s * 0.55 + bob, s * 1.95, s * 1.05))
            pygame.draw.ellipse(surf, lt, (cx - s * 0.8, cy - s * 0.5 + bob, s * 1.4, s * 0.45))
            if self.shape in ("wolf", "tiger", "bear"):           # tail
                pygame.draw.line(surf, col, (cx - fl * s * 0.95, cy - s * 0.05 + bob),
                                 (cx - fl * s * 1.3, cy - s * 0.4 + bob), max(2, int(s * 0.18)))
            elif self.shape == "deer":
                pygame.draw.circle(surf, (245, 240, 232), (int(cx - fl * s * 1.0), int(cy + bob)), 3)
            else:
                pygame.draw.line(surf, dk, (cx - fl * s * 0.95, cy + bob),
                                 (cx - fl * s * 1.15, cy - s * 0.3 + bob), 2)
            pygame.draw.circle(surf, col, (int(hx), int(hy)), int(s * 0.55))
            if self.shape == "boar":
                sxp = int(hx + (fl * s * 0.2 if fl > 0 else fl * s * 0.7))
                pygame.draw.ellipse(surf, dk, (sxp, int(hy + s * 0.05), int(s * 0.5), int(s * 0.34)))
                pygame.draw.line(surf, (245, 245, 235), (hx + fl * s * 0.35, hy + s * 0.2),
                                 (hx + fl * s * 0.5, hy - s * 0.05), 2)
                pygame.draw.polygon(surf, dk, [(hx - fl * s * 0.1, hy - s * 0.4), (hx, hy - s * 0.8),
                                               (hx + fl * s * 0.2, hy - s * 0.35)])
                for i in range(4):
                    mx = cx - s * 0.5 + i * s * 0.32
                    pygame.draw.line(surf, dk, (mx, cy - s * 0.5 + bob), (mx - fl * 2, cy - s * 0.82 + bob), 2)
            elif self.shape == "wolf":
                pygame.draw.polygon(surf, col, [(hx + fl * s * 0.2, hy), (hx + fl * s * 0.75, hy + s * 0.12),
                                                (hx + fl * s * 0.2, hy + s * 0.3)])
                pygame.draw.polygon(surf, col, [(hx - fl * s * 0.2, hy - s * 0.4), (hx - fl * s * 0.05, hy - s * 0.85),
                                                (hx + fl * s * 0.15, hy - s * 0.4)])
                pygame.draw.polygon(surf, col, [(hx + fl * s * 0.1, hy - s * 0.4), (hx + fl * s * 0.25, hy - s * 0.85),
                                                (hx + fl * s * 0.4, hy - s * 0.4)])
            elif self.shape == "bear":
                pygame.draw.circle(surf, col, (int(hx - fl * s * 0.25), int(hy - s * 0.45)), int(s * 0.22))
                pygame.draw.circle(surf, col, (int(hx + fl * s * 0.25), int(hy - s * 0.45)), int(s * 0.22))
                pygame.draw.ellipse(surf, lt, (int(hx + (fl * s * 0.1 if fl > 0 else fl * s * 0.6)),
                                               int(hy + s * 0.05), int(s * 0.45), int(s * 0.3)))
                pygame.draw.circle(surf, (30, 24, 22), (int(hx + fl * s * 0.45), int(hy + s * 0.12)), 1)
            elif self.shape == "tiger":
                bcy = cy + bob
                rx, ry = s * 0.97, s * 0.52
                stripe = (40, 28, 22)
                # white belly
                pygame.draw.ellipse(surf, (250, 244, 232), (cx - s * 0.55, cy + s * 0.06 + bob, s * 1.0, s * 0.38))
                # striped tail (drawn behind body edge)
                pygame.draw.line(surf, col, (cx - fl * s * 0.95, cy - s * 0.05 + bob),
                                 (cx - fl * s * 1.35, cy - s * 0.5 + bob), max(2, int(s * 0.2)))
                pygame.draw.circle(surf, stripe, (int(cx - fl * s * 1.18), int(cy - s * 0.32 + bob)), 2)
                # body stripes, each clipped to the body ellipse so none pokes out
                for dxr in (-0.66, -0.42, -0.18, 0.08, 0.34, 0.56):
                    xx = cx + dxr * s
                    frac = 1.0 - (dxr * s / rx) ** 2
                    if frac <= 0:
                        continue
                    hh = ry * (frac ** 0.5) * 0.92
                    pygame.draw.line(surf, stripe, (xx, bcy - hh), (xx, bcy + hh * 0.5), 2)
                # ears
                pygame.draw.polygon(surf, col, [(hx - fl * s * 0.1, hy - s * 0.4), (hx, hy - s * 0.82),
                                                (hx + fl * s * 0.12, hy - s * 0.42)])
                pygame.draw.polygon(surf, col, [(hx + fl * s * 0.2, hy - s * 0.42), (hx + fl * s * 0.34, hy - s * 0.78),
                                                (hx + fl * s * 0.46, hy - s * 0.38)])
                # muzzle + face stripes + nose
                mx = hx if fl > 0 else hx - s * 0.5
                pygame.draw.ellipse(surf, (250, 244, 232), (int(mx), int(hy + s * 0.04), int(s * 0.5), int(s * 0.32)))
                pygame.draw.line(surf, stripe, (hx - fl * s * 0.08, hy - s * 0.34), (hx - fl * s * 0.08, hy - s * 0.06), 1)
                pygame.draw.line(surf, stripe, (hx + fl * s * 0.16, hy - s * 0.32), (hx + fl * s * 0.16, hy - s * 0.06), 1)
                pygame.draw.circle(surf, (30, 20, 18), (int(hx + fl * s * 0.42), int(hy + s * 0.14)), 1)
            elif self.shape == "deer":
                pygame.draw.ellipse(surf, (245, 240, 232), (cx - s * 0.5, cy + s * 0.1 + bob, s * 0.9, s * 0.4))
                ax, ay = hx, hy - s * 0.45
                ac = (150, 118, 76)
                pygame.draw.line(surf, ac, (ax, ay), (ax + fl * s * 0.2, ay - s * 0.7), 2)
                pygame.draw.line(surf, ac, (ax + fl * s * 0.2, ay - s * 0.7), (ax + fl * s * 0.45, ay - s * 0.55), 2)
                pygame.draw.line(surf, ac, (ax + fl * s * 0.2, ay - s * 0.7), (ax + fl * s * 0.05, ay - s * 1.0), 2)
                pygame.draw.line(surf, ac, (ax - fl * s * 0.15, ay + s * 0.05), (ax - fl * s * 0.05, ay - s * 0.6), 2)
                pygame.draw.polygon(surf, col, [(hx - fl * s * 0.1, hy - s * 0.35), (hx, hy - s * 0.7),
                                                (hx + fl * s * 0.15, hy - s * 0.3)])
                pygame.draw.circle(surf, dk, (int(hx + fl * s * 0.45), int(hy + s * 0.05)), 2)
            pygame.draw.circle(surf, (24, 20, 22), (int(hx + fl * s * 0.2), int(hy - s * 0.12)), max(1, int(s * 0.09)))
            pygame.draw.circle(surf, (255, 255, 255), (int(hx + fl * s * 0.22), int(hy - s * 0.16)), 1)
        elif self.shape == "wildman":
            fl = -1 if self.facing_left else 1
            bob = math.sin(self.anim_t * 1.4) * 1.0
            skin, skin_d, hair = (224, 188, 150), (190, 150, 116), (84, 64, 44)
            pygame.draw.rect(surf, skin_d, (cx - 6, cy + 6, 4, 9))
            pygame.draw.rect(surf, skin_d, (cx + 2, cy + 6, 4, 9))
            pygame.draw.ellipse(surf, skin, (cx - 7, cy - 6 + bob, 14, 18))
            pygame.draw.rect(surf, (96, 140, 86), (cx - 8, cy + 4 + bob, 16, 7), border_radius=2)
            pygame.draw.line(surf, skin, (cx - 6, cy - 2 + bob), (cx - 12, cy + 5 + bob), 4)
            pygame.draw.line(surf, skin, (cx + 6, cy - 2 + bob), (cx + 12, cy - 1 + bob), 4)
            pygame.draw.circle(surf, skin, (int(cx), int(cy - 12 + bob)), 7)
            pygame.draw.circle(surf, hair, (int(cx), int(cy - 15 + bob)), 7)
            for hx2 in range(-6, 7, 3):
                pygame.draw.line(surf, hair, (cx + hx2, cy - 18 + bob), (cx + hx2, cy - 22 + bob), 2)
            pygame.draw.arc(surf, hair, (cx - 6, cy - 12 + bob, 12, 12), 3.4, 6.0, 3)
            pygame.draw.circle(surf, (30, 26, 28), (int(cx - 2), int(cy - 12 + bob)), 1)
            pygame.draw.circle(surf, (30, 26, 28), (int(cx + 2), int(cy - 12 + bob)), 1)
            pygame.draw.line(surf, (120, 90, 60), (cx + 12, cy - 1 + bob), (cx + 17, cy - 9 + bob), 3)
            pygame.draw.circle(surf, (120, 90, 60), (int(cx + 17), int(cy - 9 + bob)), 3)
        elif self.shape == "zombie":
            # slow hunched green undead lugging a wide steel cleaver
            fl = -1 if self.facing_left else 1
            bob = math.sin(self.anim_t * 0.9) * 1.2          # slow shamble
            sway = math.sin(self.anim_t * 0.45) * 2.0        # drunken stagger lean
            skin = col                                        # sickly green skin tone
            skin_d = tuple(max(0, c - 40) for c in col)
            shirt = (54, 60, 52)                              # dark tattered shirt
            shirt_d = tuple(max(0, c - 18) for c in shirt)
            steel = (176, 184, 196)
            steel_d = (118, 126, 138)
            steel_lt = (224, 230, 240)
            wood = (120, 86, 52)
            bx = cx + sway
            # legs
            pygame.draw.rect(surf, skin_d, (bx - 6, cy + 6, 4, 9))
            pygame.draw.rect(surf, skin_d, (bx + 2, cy + 6, 4, 9))
            # torn shirt torso (hunched -> slightly squat ellipse)
            pygame.draw.ellipse(surf, shirt, (bx - 7, cy - 5 + bob, 14, 16))
            pygame.draw.line(surf, shirt_d, (bx - 4, cy + 8 + bob), (bx - 1, cy + 2 + bob), 2)
            pygame.draw.line(surf, shirt_d, (bx + 3, cy + 9 + bob), (bx + 5, cy + 3 + bob), 2)
            # front-reaching arm (toward facing dir)
            pygame.draw.line(surf, skin, (bx + fl * 3, cy - 2 + bob),
                             (bx + fl * 13, cy + 1 + bob), 4)
            pygame.draw.circle(surf, skin, (int(bx + fl * 13), int(cy + 1 + bob)), 2)
            # cleaver arm (other side) holding the blade out
            hx = bx - fl * 9
            hy = cy + 2 + bob
            pygame.draw.line(surf, skin, (bx - fl * 3, cy - 1 + bob), (hx, hy), 4)
            # --- mattock (อีเต้อ): long wooden shaft + steel head mounted crosswise ---
            wood_d = (84, 58, 34)
            sx, sy = hx, hy                                   # grip at the off-hand
            tx = int(hx - fl * 4); ty = int(hy - 19)          # shaft top, raised over shoulder
            pygame.draw.line(surf, wood, (sx, sy), (tx, ty), 3)          # shaft
            pygame.draw.line(surf, wood_d, (sx, sy), (tx, ty), 1)        # shaft shade
            # broad adze blade flaring forward + down (perpendicular to the shaft)
            adze = [(tx + fl * 1, ty - 3), (tx + fl * 11, ty),
                    (tx + fl * 11, ty + 5), (tx + fl * 1, ty + 5)]
            pygame.draw.polygon(surf, steel, adze)
            pygame.draw.polygon(surf, steel_d, adze, 1)
            pygame.draw.line(surf, steel_lt, (tx + fl * 2, ty - 2),
                             (tx + fl * 9, ty), 1)                       # top bevel glint
            # short pick/poll on the back of the head
            pygame.draw.polygon(surf, steel_d, [
                (tx - fl * 1, ty - 1), (tx - fl * 6, ty + 1), (tx - fl * 1, ty + 4)])
            # hunched head with sunken dark eyes
            hdx = bx + fl * 2                                  # head pokes forward
            pygame.draw.circle(surf, skin, (int(hdx), int(cy - 11 + bob)), 7)
            pygame.draw.circle(surf, skin_d, (int(hdx), int(cy - 8 + bob)), 7, 1)
            for sgn in (-1, 1):
                pygame.draw.circle(surf, (24, 30, 22),
                                   (int(hdx + sgn * 3), int(cy - 11 + bob)), 2)
                pygame.draw.circle(surf, (150, 200, 120),
                                   (int(hdx + sgn * 3), int(cy - 11 + bob)), 1)
            pygame.draw.line(surf, skin_d, (hdx - 3, cy - 6 + bob), (hdx + 3, cy - 6 + bob), 1)
        else:
            pygame.draw.circle(surf, col, (int(cx), int(cy)), self.size)
