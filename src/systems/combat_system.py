"""Combat, monster rewards, gems and bombs.

Owner: "Combat, Mining & Progression" chat.
Related modules: progress.py, monsters.py (+ monster_ai.py / monster_shapes.py),
loot.py, craft.py, entities.Monster.

Level-up (2026-09):
  * juicy melee: damage numbers, crits (8% + luck), knockback, death poofs,
    reads the ``combat`` buff; armored monsters shrug off part of the hit
  * monster AI side effects (``mon.fx`` queue from monster_ai) -> SFX/particles
  * boss intro roar + screen boss bar, boss victory toast
  * gems & relics (icons painted here) + biome gem bonus on every broken rock
  * bombs + mega bombs (crafted at the Workbench) that blast rocks/monsters in
    the mine, and the Rope Ladder (drop to the next mine level)
  * sword slash trail
"""
import math
import random
import weakref
import pygame
from ..settings import TILE, SCREEN_W, AREA_MINE
from .. import loot
from .. import assets
from .. import ui_kit
from ..assets import terrain as _terrain
from .. import monsters as MDEF
from ..particles import Particle
from ..progress import XP as SKILL_XP

BOMB_FUSE = 1.6
BOMB_RADIUS = 2.25          # tiles (rocks)
BOMB_MON_RADIUS = 2.6       # tiles (monsters)
# item id -> (rock radius tiles, monster radius tiles, damage multiplier, shake)
BOMB_TYPES = {"bomb": (BOMB_RADIUS, BOMB_MON_RADIUS, 1.0, 16),
              "mega_bomb": (3.3, 3.6, 1.8, 16)}
KNOCKBACK = TILE * 0.4


# ============================================================ gem / relic icons
def _gem_painter(base, shape="oval"):
    lt = tuple(min(255, c + 70) for c in base)
    dk = tuple(max(0, c - 70) for c in base)
    dk2 = tuple(max(0, c - 110) for c in base)

    def paint(s):
        cx, cy = 14, 15
        if shape == "oval":            # amethyst: tall cut oval
            pts = [(cx, 4), (cx + 7, 9), (cx + 7, 20), (cx, 25), (cx - 7, 20), (cx - 7, 9)]
        elif shape == "heart":         # ruby: rounded cushion
            pts = [(cx - 4, 5), (cx + 4, 5), (cx + 9, 11), (cx + 6, 20), (cx, 25), (cx - 6, 20), (cx - 9, 11)]
        elif shape == "square":        # emerald: step cut
            pts = [(cx - 5, 5), (cx + 5, 5), (cx + 9, 9), (cx + 9, 20), (cx + 5, 24), (cx - 5, 24),
                   (cx - 9, 20), (cx - 9, 9)]
        else:                          # diamond: brilliant cut
            pts = [(cx - 6, 6), (cx + 6, 6), (cx + 11, 11), (cx, 25), (cx - 11, 11)]
        pygame.draw.polygon(s, base, pts)
        # facets: light upper-left, dark lower-right
        pygame.draw.polygon(s, lt, [pts[0], pts[1], (cx, cy - 1), pts[-1]])
        pygame.draw.polygon(s, dk, [(cx, cy - 1)] + pts[len(pts) // 2 - 1:len(pts) // 2 + 2])
        if shape == "diamond":
            pygame.draw.line(s, dk, (cx - 11, 11), (cx + 11, 11), 1)
            pygame.draw.line(s, lt, (cx - 3, 6), (cx - 5, 11), 1)
        pygame.draw.polygon(s, dk2, pts, 1)
        pygame.draw.line(s, (255, 255, 255), (cx - 4, 8), (cx - 2, 7), 2)
        pygame.draw.circle(s, (255, 255, 255), (cx + 5, 8), 1)
    return paint


def _paint_prismatic(s):
    cols = [(255, 120, 150), (255, 200, 110), (140, 230, 140), (120, 190, 255), (200, 140, 255)]
    cx, cy = 14, 14
    for i, c in enumerate(cols):
        a0 = i * math.tau / 5 - math.pi / 2
        a1 = a0 + math.tau / 5
        pygame.draw.polygon(s, c, [(cx, cy), (cx + math.cos(a0) * 11, cy + math.sin(a0) * 12),
                                   (cx + math.cos(a1) * 11, cy + math.sin(a1) * 12)])
    pts = [(cx + math.cos(i * math.tau / 5 - math.pi / 2) * 11,
            cy + math.sin(i * math.tau / 5 - math.pi / 2) * 12) for i in range(5)]
    pygame.draw.polygon(s, (255, 255, 255), pts, 1)
    pygame.draw.circle(s, (255, 255, 255), (cx, cy), 3)
    pygame.draw.line(s, (255, 255, 255), (cx - 5, cy - 6), (cx - 2, cy - 8), 2)


def _paint_relic(s):
    gold, gd, gl = (214, 180, 96), (140, 108, 50), (250, 226, 150)
    # an old engraved medallion on a worn tablet
    pygame.draw.rect(s, (150, 138, 116), (5, 5, 18, 20), border_radius=3)
    pygame.draw.rect(s, (104, 94, 78), (5, 5, 18, 20), 1, border_radius=3)
    pygame.draw.circle(s, gold, (14, 14), 8)
    pygame.draw.circle(s, gd, (14, 14), 8, 1)
    pygame.draw.circle(s, gl, (12, 12), 3)
    pygame.draw.circle(s, (110, 220, 210), (14, 14), 2)
    for a in range(4):
        ang = a * math.pi / 2 + 0.78
        pygame.draw.line(s, gd, (14 + math.cos(ang) * 4, 14 + math.sin(ang) * 4),
                         (14 + math.cos(ang) * 7, 14 + math.sin(ang) * 7), 1)
    pygame.draw.line(s, (104, 94, 78), (7, 22), (11, 19), 1)


def _paint_bomb(s, mega=False):
    body, dk = ((206, 72, 72), (120, 36, 44)) if mega else ((70, 66, 84), (36, 34, 46))
    pygame.draw.circle(s, dk, (13, 17), 10)
    pygame.draw.circle(s, body, (13, 16), 9)
    if mega:                                   # gold band + stud
        pygame.draw.line(s, (246, 204, 90), (5, 18), (21, 18), 3)
        pygame.draw.circle(s, (255, 236, 150), (13, 18), 2)
    pygame.draw.circle(s, (255, 170, 170) if mega else (130, 126, 150), (10, 13), 3)
    pygame.draw.circle(s, (200, 198, 214), (9, 12), 1)
    pygame.draw.rect(s, (150, 146, 160), (15, 5, 6, 5), border_radius=1)
    pygame.draw.lines(s, (186, 150, 100), False, [(18, 5), (20, 2), (23, 3)], 2)
    pygame.draw.circle(s, (255, 210, 90), (24, 3), 2)
    pygame.draw.circle(s, (255, 255, 220), (24, 3), 1)


for _gid, _shape in (("amethyst", "oval"), ("ruby", "heart"), ("emerald", "square"),
                     ("diamond", "diamond")):
    assets.register_item_icon(_gid, _gem_painter(loot.color(_gid), _shape))
assets.register_item_icon("prismatic_shard", _paint_prismatic)
assets.register_item_icon("ancient_relic", _paint_relic)
assets.register_item_icon("bomb", _paint_bomb)
assets.register_item_icon("mega_bomb", lambda s: _paint_bomb(s, True))


def _paint_rope_ladder(s):
    rope, rope_d, rung = (214, 180, 120), (150, 112, 64), (150, 100, 55)
    for x in (8, 20):
        pygame.draw.line(s, rope_d, (x + 1, 3), (x + 1, 26), 2)
        pygame.draw.line(s, rope, (x, 3), (x, 25), 2)
    for y in range(6, 25, 5):
        pygame.draw.line(s, rung, (8, y), (20, y), 3)
        pygame.draw.line(s, (196, 142, 86), (9, y - 1), (19, y - 1), 1)
    pygame.draw.circle(s, rope, (8, 3), 2)
    pygame.draw.circle(s, rope, (20, 3), 2)


assets.register_item_icon("rope_ladder", _paint_rope_ladder)

_BOMB_SPR = {}
_FONTS = {}
_SLASH = {}
_SLASH_STEPS = 6


def _slash_sprite(fx, fy, step, tint):
    """Cached crescent sword-trail for a facing + animation step (0.._SLASH_STEPS-1)."""
    key = (fx, fy, step, tint)
    s = _SLASH.get(key)
    if s is None:
        R = int(TILE * 0.95)
        s = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
        c = R + 4
        base = math.atan2(-fy, fx)                   # pygame arcs: y axis points up
        prog = (step + 1) / _SLASH_STEPS
        span = 2.2 * prog
        a0 = base - 1.1
        fade = 1.0 - max(0.0, prog - 0.7) / 0.3 * 0.8
        for k, (w, a, mix) in enumerate(((11, 120, 0.8), (6, 210, 0.45), (3, 255, 0.1))):
            col = tuple(min(255, int(t * mix + 255 * (1 - mix))) for t in tint) + (int(a * fade),)
            rr = R - k * 3
            pygame.draw.arc(s, col, (c - rr, c - rr, rr * 2, rr * 2), a0, a0 + span, w)
        _SLASH[key] = s
    return s


def _num_font(big):
    """Bold damage-number fonts (created once)."""
    f = _FONTS.get(big)
    if f is None:
        f = _FONTS[big] = pygame.font.SysFont("consolas", 26 if big else 16, bold=True)
    return f


def _bomb_sprite(lit, mega=False):
    s = _BOMB_SPR.get((lit, mega))
    if s is None:
        s = pygame.Surface((30, 32), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 70), (4, 25, 22, 6))
        body = (255, 150, 120) if lit else ((206, 72, 72) if mega else (70, 66, 84))
        pygame.draw.circle(s, (36, 34, 46), (15, 18), 11)
        pygame.draw.circle(s, body, (15, 17), 10)
        if mega:
            pygame.draw.line(s, (246, 204, 90), (6, 19), (24, 19), 3)
        pygame.draw.circle(s, (255, 190, 190) if lit else (130, 126, 150), (11, 13), 3)
        pygame.draw.circle(s, (255, 255, 255), (10, 12), 1)
        pygame.draw.rect(s, (150, 146, 160), (17, 5, 6, 5), border_radius=1)
        pygame.draw.lines(s, (186, 150, 100), False, [(20, 5), (22, 2), (25, 2)], 2)
        _BOMB_SPR[(lit, mega)] = s
    return s


def _a_an(noun):
    """'a Ruby' / 'an Amethyst' (by the first letter's vowel sound; the few
    exceptions -- 'an hour', 'a unicorn' -- don't occur among the gem names)."""
    noun = str(noun)
    return ("an " if noun[:1].lower() in "aeiou" and noun else "a ") + noun


BOSS_BAR_Y = 166           # top of the boss HP bar (name above, subtitle below)


class CombatMixin:
    """Melee combat, loot/XP/gold on kills, gems, bombs and combat juice."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_combat(self):
        self._cb_nums = []          # floating damage numbers [x, y, vy, surf, life, max, big]
        self._cb_bombs = []         # lit bombs {x, y, t, owner}
        self._cb_boss_seen = None   # boss monster we already announced
        self._cb_num_cache = {}
        self._cb_area_t = 0.0       # seconds since entering the area (boss bar waits
                                    # for the area title card to clear)
        # mine floors whose boss is already beaten: the boss stays gone when you
        # step back onto the floor (no re-entry boss farming) until the season turns
        self.cb_boss_cleared = set()
        # the boss's in-world name tag hides while the screen boss bar shows it
        _terrain.BOSS_TAG_HIDDEN = weakref.WeakMethod(self._cb_bar_name)

    def _cb_bar_showing(self):
        """The boss whose screen bar is up right now (after the area title card)."""
        if self.state != "play" or getattr(self, "_cb_area_t", 9.0) < 2.4:
            return None
        return self._cb_boss()

    def _cb_bar_name(self):
        boss = self._cb_bar_showing()
        return boss.label if boss is not None else None

    def _on_save_combat(self):
        return {"cb_boss_cleared": sorted(int(d) for d in self.cb_boss_cleared)}

    def _on_load_combat(self, d):
        self.cb_boss_cleared = set()
        for v in d.get("cb_boss_cleared") or []:
            try:
                self.cb_boss_cleared.add(int(v))
            except (TypeError, ValueError):
                pass

    def _on_new_day_combat(self):
        # a new season: the deep bosses regroup on floors you still stand on
        if getattr(self.time, "day", 0) == 1 and self.cb_boss_cleared:
            self.cb_boss_cleared = set()
            self.ui.log("Deep rumbles echo from the mines... the bosses have returned.")

    def _on_area_enter_combat(self):
        self._cb_bombs = []
        self._cb_nums = []
        self._cb_boss_seen = None
        self._cb_area_t = 0.0
        area = self.world.area
        if area.name == AREA_MINE and int(self.world.mine_level) in self.cb_boss_cleared:
            if any(getattr(m, "boss", False) for m in self.monsters):
                self.monsters = [m for m in self.monsters if not getattr(m, "boss", False)]
                self.ui.log("This floor's boss is already defeated - the way down is open.")
        boss = self._cb_boss()
        if boss is not None:
            self._cb_boss_seen = boss
            a = MDEF.ARCHETYPES.get(boss.name, {})
            self._cb_sfx("boss_roar", "levelup")
            self.add_shake(8)
            self.toast(f"BOSS: {boss.label}", a.get("title", "Defeat it for a big reward!"),
                       None, (255, 120, 110), 3.5)

    # ------------------------------------------------------------ helpers
    def _cb_sfx(self, *names):
        """Play the first SFX name the audio bank knows (Core adds new ones)."""
        bank = getattr(self.audio, "sfx", None) or {}
        for n in names:
            if n in bank:
                self.audio.play(n)
                return
        if names:
            self.audio.play(names[-1])

    def _cb_boss(self):
        for m in self.monsters:
            if getattr(m, "boss", False) and m.hp > 0:
                return m
        return None

    def _cb_number(self, x, y, text, color, big=False):
        key = (text, color, big)
        surf = self._cb_num_cache.get(key)
        if surf is None:
            if len(self._cb_num_cache) > 400:
                self._cb_num_cache.clear()
            # a solid outline so the numbers read on snow, ice and lava alike
            # (copied: the draw pass changes its alpha)
            surf = ui_kit.outlined(_num_font(big), text, color, (40, 26, 36), 2).copy()
            self._cb_num_cache[key] = surf
        life = 1.0 if big else 0.8
        # [x, y, vy, surf, life, max, big, spread offset (eased, see _cb_spread)]
        self._cb_nums.append([x + random.uniform(-6, 6), y, -70.0 if big else -55.0,
                              surf, life, life, big, 0.0])
        if len(self._cb_nums) > 40:
            del self._cb_nums[0]

    def _cb_poof(self, x, y, color, big=False):
        """Death poof: soft puffs in the monster's colour + a ring + sparkles."""
        items = self.parts.items
        pale = tuple(min(255, int(c * 0.7 + 255 * 0.3)) for c in color[:3])
        n = 26 if big else 14
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(40, 130 if big else 100)
            items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp * 0.7 - 20,
                                  random.uniform(0.45, 0.85), random.choice((color[:3], pale)),
                                  random.uniform(4, 8 if big else 6), grav=-40))
        items.append(Particle(x, y, 0, 0, 0.55, pale, 10 if big else 7, ring=True))
        self.parts.sparkle(x, y, n=10 if big else 5, color=(255, 250, 230))

    def _cb_knockback(self, m, fromx, fromy, dist=KNOCKBACK):
        a = MDEF.ARCHETYPES.get(m.name, {})
        k = 0.25 if getattr(m, "boss", False) else (0.5 if a.get("armor", 0) >= 0.3 else 1.0)
        dx, dy = m.x - fromx, m.y - fromy
        n = math.hypot(dx, dy) or 1.0
        dur = 0.12
        sp = dist * k / dur
        m.kb = [dx / n * sp, dy / n * sp, dur]

    def _cb_hit(self, p, m, dmg, crit=False, fromx=None, fromy=None, kb=True):
        """Apply melee/blast damage with armor, feedback and kill handling."""
        armor = MDEF.ARCHETYPES.get(m.name, {}).get("armor", 0.0)
        dealt = max(1, int(round(dmg * (1.0 - armor))))
        m.hp -= dealt
        m.flash = 0.15
        cx, cy = m.x, m.y - m.size
        if crit:
            self._cb_number(cx, cy - 6, f"{dealt}!", (255, 222, 70), big=True)
        else:
            self._cb_number(cx, cy, str(dealt), (255, 246, 236) if not armor else (206, 214, 230))
        if armor >= 0.3:                     # armour clinks: white sparks
            self.parts.sparkle(m.x, m.y - m.size * 0.4, n=4, color=(236, 240, 250))
        if kb and fromx is not None:
            self._cb_knockback(m, fromx, fromy)
        if m.hp <= 0 and not m.rewarded:
            self._reward_kill(p, m)
        return dealt

    # ------------------------------------------------------------ kills
    def _reward_kill(self, p, m):
        m.rewarded = True
        gold = random.randint(*m.gold)
        self.gold += gold
        # today's temple fortune tilts the loot for this player
        idx = self.players.index(p)
        fort = self.fortune.get(idx)
        luck = p.skills.level("combat") * 0.05 + (0.5 if fort == "lucky" else 0.0) \
            + p.buff("luck") * 0.5
        drops = loot.roll_drops(m.drops, luck=luck)
        got, missed = [], []
        doubled = False
        gem_y = m.y - 48                  # gem / relic lines stack above the gold line
        for item, qty in drops.items():
            if fort == "unlucky" and random.random() < 0.40:        # bad luck: drop slips away
                missed.append(loot.label(item))
                continue
            if fort == "lucky" and random.random() < 0.5:           # good luck: doubled haul
                qty *= 2
                doubled = True
                got.append(f"{qty} {loot.label(item)} (x2!)")
            else:
                got.append(f"{qty} {loot.label(item)}")
            p.inv.add(item, qty)
            if loot.MATERIALS.get(item, {}).get("cat") in ("gem", "relic"):
                self._popup(m.x, gem_y, f"{loot.label(item)}!", loot.color(item))
                gem_y -= 20
        boss = getattr(m, "boss", False)
        self._cb_poof(m.x, m.y, m.color, big=boss)
        self.parts.sparkle(m.x, m.y, n=24 if boss else 10, color=(255, 220, 120))
        # gold + luck on one line, just below the damage numbers
        if doubled:
            self._popup(m.x, m.y - 4, f"+{gold}g  LUCKY x2!", (255, 224, 120))
        else:
            self._popup(m.x, m.y - 4, f"+{gold}g", (255, 220, 120))
        if missed:
            self._popup(m.x, m.y - 26, "MISSED!", (180, 130, 210))
        self.add_shake(12 if boss else 7)
        self._grant_xp(p, "combat", m.xp)
        tail = (" - " + ", ".join(got)) if got else ""
        if missed:
            tail += f"  (lost: {', '.join(missed)})"
        self.ui.log(f"{'BOSS DOWN! ' if boss else 'Defeated '}{m.label}! +{gold}g{tail}")
        if boss:
            self._cb_sfx("achievement", "levelup")
            conf = getattr(self.parts, "confetti", None)
            if conf:
                for _ in range(6):
                    conf(m.x + random.uniform(-40, 40), m.y - 40, n=6)
            self.toast("BOSS DEFEATED!", f"{m.label}  +{gold}g", "prismatic_shard",
                       (255, 214, 110), 4.5)
            area = self.world.area
            if area.name == AREA_MINE:
                self.cb_boss_cleared.add(int(self.world.mine_level))
            lad = getattr(area, "ladder", None)
            if area.name == AREA_MINE and lad and not any(
                    getattr(o, "boss", False) and o.hp > 0 for o in self.monsters):
                lx, ly = lad[0] * TILE + TILE / 2, lad[1] * TILE + TILE / 2
                self.parts.warp(lx, ly, color=(255, 230, 150))
                self._popup(lx, ly - 30, "The way down is open!", (255, 230, 150))
                self.ui.log("The way down is open - find the ladder!")
        self.emit("monster_killed", p=p, kind=m.name, boss=bool(boss))

    # ------------------------------------------------------------ melee
    def sword_attack(self, p):
        ax = p.x + p.fx * TILE
        ay = p.y + p.fy * TILE
        p.trigger_swing()
        p.cb_slash = 0.28                  # sword trail (drawn by _draw_world_combat)
        tier = p.tool_tiers.get("sword", 0)
        reach = TILE * (1.0 + 0.12 * tier)
        hit = pygame.Rect(ax - reach / 2, ay - reach / 2, reach, reach)
        self.audio.play("sword")
        base = (6 + p.skills.sword_bonus + tier * 4) * (1.0 + p.buff("combat"))
        crit_ch = 0.08 + p.buff("luck") * 0.1 + getattr(p.skills, "crit_bonus", 0.0)
        landed = False
        for m in self.monsters:
            if m.hp > 0 and hit.colliderect(m.rect()):
                crit = random.random() < crit_ch
                dmg = base * (2.0 if crit else 1.0) * random.uniform(0.9, 1.1)
                landed = True
                self.parts.hit(m.x, m.y)
                if crit:
                    self.parts.sparkle(m.x, m.y - 6, n=10, color=(255, 230, 110))
                    self._cb_sfx("crit", "hit")
                    self.add_shake(6)
                else:
                    self.audio.play("hit")
                    self.add_shake(2.5)
                self._cb_hit(p, m, dmg, crit, p.x, p.y)
        self.ui.log("Swing!" if not landed else "Hit!")

    # ------------------------------------------------------------ per frame
    def _on_update_combat(self, dt):
        area = self.world.area
        self._cb_area_t += dt
        for p in self.players:
            if p.__dict__.get("cb_slash", 0.0) > 0:
                p.cb_slash -= dt
        # monster AI side effects + knockback slides
        for m in self.monsters:
            fx = m.__dict__.get("fx")
            if fx:
                for ev in fx:
                    self._cb_fx(m, ev)
                fx.clear()
            kb = m.__dict__.get("kb")
            if kb and kb[2] > 0:
                step = min(dt, kb[2])
                kb[2] -= dt
                nx, ny = m.x + kb[0] * step, m.y + kb[1] * step
                if not area.is_solid(int(nx // TILE), int(m.y // TILE)):
                    m.x = nx
                if not area.is_solid(int(m.x // TILE), int(ny // TILE)):
                    m.y = ny
        # floating numbers
        if self._cb_nums:
            for n in self._cb_nums:
                n[1] += n[2] * dt
                n[2] += 90 * dt
                n[4] -= dt
            self._cb_nums = [n for n in self._cb_nums if n[4] > 0]
            self._cb_spread(dt)
        # boss entering mid-floor (e.g. spawned later) -> announce once
        boss = self._cb_boss()
        if boss is not None and boss is not self._cb_boss_seen:
            self._cb_boss_seen = boss
            self._cb_sfx("boss_roar", "levelup")
        # bombs
        if self._cb_bombs:
            self._cb_update_bombs(dt, area)

    def _cb_spread(self, dt):
        """Keep damage numbers off each other, the +gold popups and the farmers:
        stack them upward from their natural spots (the spread_rects rule, with
        fixed obstacles) and ease each toward its slot so the stack never jumps."""
        rects = []
        f = getattr(self, "_ui_player_rects", None)         # never over a farmer
        if f:
            cam = self.cam
            rects += [r.move(int(cam.x), int(cam.y)) for r in f()]   # screen -> world
        small = getattr(self.ui, "small", None)
        if small is not None:                   # world popups are fixed obstacles
            for pu in getattr(self, "popups", ()):
                w, h = small.size(str(pu[2]))
                rects.append(pygame.Rect(int(pu[0] - w / 2), int(pu[1]), w, h))
        # obstacles stay put (spread_rects would also shuffle them among
        # themselves); each number steps up past anything already placed
        placed = rects
        mine, tops = [], []
        for n in self._cb_nums:
            w, h = n[3].get_size()
            tops.append(int(n[1] - h / 2))
            # digits have no descenders: the surface's bottom rows are empty
            r = pygame.Rect(int(n[0] - w / 2), tops[-1], w, h - 4)
            for _ in range(40):
                hit = next((p for p in placed if r.colliderect(p.inflate(2, 2))), None)
                if hit is None:
                    break
                r.bottom = hit.top - 1
            placed.append(r)
            mine.append(r)
        ease = min(1.0, dt * 14)
        for n, r, top in zip(self._cb_nums, mine, tops):
            if len(n) < 8:
                n.append(0.0)
            n[7] += ((r.top - top) - n[7]) * ease

    def _cb_fx(self, m, ev):
        kind = ev[0]
        if kind == "roar":
            self._cb_sfx("boss_roar", "levelup")
            self.add_shake(9)
            self.parts.items.append(Particle(ev[1], ev[2], 0, 0, 0.7, (255, 150, 150), 12, ring=True))
        elif kind == "phase":
            self._popup(ev[1], ev[2] - m.size - 30, "ENRAGED!", (255, 110, 110))
            self.ui.log(ev[3])
        elif kind == "fire":
            self._cb_sfx("fireball", "cast")
            self.parts.flame(ev[1], ev[2], n=4)
        elif kind == "burst":
            self.parts.hit(ev[1], ev[2], n=8, color=ev[3])
        elif kind == "blink":
            self.parts.warp(ev[1], ev[2], color=ev[3])
            self._cb_sfx("blink", "warp")
        elif kind == "charge":
            self.parts.dust(ev[1], ev[2] + 10, n=6)
            self._cb_sfx("whoosh", "sword")
        elif kind == "dust":
            self.parts.dust(ev[1], ev[2] + 10, n=8)
        elif kind == "slam":
            r = ev[3]
            self.add_shake(14)
            self._cb_sfx("slam", "thunder", "mine")
            for k in range(18):
                a = k / 18 * math.tau
                self.parts.dust(ev[1] + math.cos(a) * r * 0.9, ev[2] + math.sin(a) * r * 0.6, n=2)
            self.parts.chips(ev[1], ev[2], n=10, color=(170, 160, 140))
        elif kind == "ember":
            self.parts.ember(ev[1], ev[2], n=2)

    # ------------------------------------------------------------ drawing
    def _draw_world_combat(self):
        cam = self.cam
        # sword slash trails (a crescent that sweeps with the swing)
        for p in self.players:
            sl = p.__dict__.get("cb_slash", 0.0)
            if sl <= 0:
                continue
            prog = 1.0 - sl / 0.28
            step = max(0, min(_SLASH_STEPS - 1, int(prog * _SLASH_STEPS)))
            tier = p.tool_tiers.get("sword", 0)
            from ..craft import TIER_COLORS
            tint = TIER_COLORS[min(tier, len(TIER_COLORS) - 1)]
            spr = _slash_sprite(p.fx, p.fy, step, tint)
            self.screen.blit(spr, (int(p.x + p.fx * 10 - cam.x - spr.get_width() / 2),
                                   int(p.y - 6 + p.fy * 10 - cam.y - spr.get_height() / 2)))
        if not self._cb_nums:
            return
        for n in self._cb_nums:
            x, y, vy, surf, life, mx, big = n[:7]
            if len(n) > 7:
                y += n[7]                           # spread offset (_cb_spread)
            t = 1.0 - life / mx
            scale = 1.0 + (0.6 if big else 0.3) * max(0.0, 1.0 - t * 6)   # quick pop
            a = 255 if life > 0.3 else int(255 * life / 0.3)
            s = surf
            if scale > 1.02:
                s = pygame.transform.scale(surf, (int(surf.get_width() * scale),
                                                  int(surf.get_height() * scale)))
            s.set_alpha(a)
            self.screen.blit(s, (int(x - cam.x - s.get_width() / 2), int(y - cam.y - s.get_height() / 2)))
            if s is surf:
                surf.set_alpha(255)

    def _draw_hud_combat(self):
        boss = self._cb_bar_showing()          # (waits for the area title card)
        if boss is None:
            return
        t = getattr(self, "_cb_area_t", 9.0)
        a = MDEF.ARCHETYPES.get(boss.name, {})
        scr = self.screen
        sub = a.get("title")
        # one dark HUD plate (the clock card's plum) holding name, bar, subtitle;
        # below the centred "In Sync" chip (y 102-126); slides in from the top
        pw, ph = 500, 70 if sub else 54
        y = BOSS_BAR_Y - 32 - int(26 * max(0.0, 1.0 - (t - 2.4) / 0.3))
        plate = pygame.Rect(SCREEN_W // 2 - pw // 2, y, pw, ph)
        ui_kit.pill(scr, plate.move(2, 3), (0, 0, 0), radius=12, alpha=70)          # shadow
        ui_kit.pill(scr, plate, (34, 28, 44), (104, 92, 128), radius=12, alpha=240)
        mad = (boss.__dict__.get("ai") or {}).get("phase2")
        accent = (236, 92, 92) if mad else (236, 170, 70)
        pygame.draw.rect(scr, accent, (plate.x + 16, plate.y + 1, pw - 32, 3), border_radius=2)
        # name (the in-world nameplate hides meanwhile -- this says it already)
        name = boss.label.upper() + ("  -  ENRAGED" if mad else "")
        nf = ui_kit.font(18, True)
        ui_kit.blit_text(scr, nf, name, (255, 150, 140) if mad else (255, 240, 220),
                         (plate.centerx, plate.y + 17))
        # health bar
        bar = pygame.Rect(plate.x + 18, plate.y + 30, pw - 36, 14)
        ratio = max(0.0, min(1.0, boss.hp / max(1, boss.max_hp)))
        pygame.draw.rect(scr, (70, 30, 40), bar, border_radius=7)
        col = (255, 96, 96) if mad else (246, 196, 84)
        fw = int(bar.w * ratio)
        if fw > 0:
            pygame.draw.rect(scr, col, (bar.x, bar.y, max(8, fw), bar.h), border_radius=7)
            if fw > 12:
                pygame.draw.rect(scr, tuple(min(255, c + 50) for c in col),
                                 (bar.x + 4, bar.y + 2, fw - 8, 3), border_radius=2)
        pygame.draw.rect(scr, (150, 132, 168), bar, 1, border_radius=7)
        if sub:
            ui_kit.blit_text(scr, ui_kit.font(14), sub, (214, 204, 232),
                             (plate.centerx, plate.y + 56))
        f = getattr(self, "hud_reserve", None)
        f and f(plate)

    # ------------------------------------------------------------ gems
    def _on_event_combat_rock_broken(self, event, data):
        """Biome gem bonus on every broken mine rock (pickaxe or bomb)."""
        if event != "rock_broken":
            return
        p = data.get("p")
        area = data.get("area")
        aname = getattr(area, "name", area)
        if p is None or aname != AREA_MINE:
            return
        depth = getattr(self.world, "mine_level", 1)
        biome = getattr(self.world.area, "biome", None)
        if biome not in MDEF.BIOMES:
            biome = MDEF.biome_for_depth(depth)
        luck = (p.skills.mining_luck if getattr(p, "skills", None) else 0.0) + p.buff("luck") \
            + p.buff("mining") * 0.5
        gem = loot.roll_rock_gem(biome, luck)
        if not gem:
            return
        p.inv.add(gem, 1)
        x, y = p.x + p.fx * TILE, p.y + p.fy * TILE
        col = loot.color(gem)
        self.parts.sparkle(x, y - 6, n=16, color=col)
        self._popup(x, y - 26, f"{loot.label(gem)}!", col)
        self._cb_sfx("coin", "sell")
        self.ui.log(f"{p.name} found {_a_an(loot.label(gem))}!")

    # ------------------------------------------------------------ bombs
    def _on_tool_combat_bomb(self, idx, p, tool, gx, gy):
        if tool not in BOMB_TYPES:
            return False
        area = self.world.area
        if area.name != AREA_MINE:
            self.ui.log("Bombs only work down in the mines.")
            self._cb_sfx("error", "ui_move")
            return True
        if p.inv.count(tool) <= 0:
            return True
        if area.is_solid(gx, gy):
            gx, gy = int(p.x // TILE), int(p.y // TILE)
        for b in self._cb_bombs:
            if int(b["x"] // TILE) == gx and int(b["y"] // TILE) == gy:
                return True
        p.inv.remove(tool, 1)
        p.trigger_item_use(tool, "place", 0.4)
        self._cb_bombs.append({"x": gx * TILE + TILE / 2, "y": gy * TILE + TILE / 2,
                               "t": BOMB_FUSE, "owner": idx, "kind": tool})
        self._cb_sfx("fuse", "ui_select")
        self.ui.log("Bomb placed - stand back!")
        return True

    def _on_tool_combat_ladder(self, idx, p, tool, gx, gy):
        """Rope Ladder (Workbench craft): drop straight to the next mine level."""
        if tool != "rope_ladder":
            return False
        area = self.world.area
        if area.name != AREA_MINE:
            self.ui.log("A rope ladder only helps down in the mines.")
            self._cb_sfx("error", "ui_move")
            return True
        if self._cb_boss() is not None:
            self.ui.log("A boss guards the way down - defeat it first!")
            self._cb_sfx("error", "ui_move")
            return True
        if p.inv.count(tool) <= 0:
            return True
        p.inv.remove(tool, 1)
        self.parts.dust(p.x, p.y + 8, n=10)
        self.world.regen_mine(self.world.mine_level + 1)
        self.warp(AREA_MINE, (5, 3))
        self._cb_sfx("ladder", "warp")
        self.ui.log(f"{p.name} climbed down a rope ladder to mine level {self.world.mine_level}!")
        self.emit("mine_depth", level=self.world.mine_level)
        return True

    def _cb_update_bombs(self, dt, area):
        keep = []
        for b in self._cb_bombs:
            b["t"] -= dt
            fx, fy = b["x"] + 9, b["y"] - 16
            if random.random() < 0.7:
                self.parts.flame(fx, fy, n=1, color=(255, 210, 90))
            if b["t"] <= 0:
                self._cb_explode(b, area)
            else:
                keep.append(b)
        self._cb_bombs = keep

    def _cb_break_rock(self, p, gx, gy, area):
        """Same yield as a pickaxe blow (actions_system.use_tool) + rock_broken."""
        ore = area.rocks.pop((gx, gy))
        tier = p.tool_tiers.get("pickaxe", 0)
        p.inv.add("stone", 1 + tier // 2)
        if ore:
            item = loot.ROCK_ORE_ITEM.get(ore)
            qty = 1 + (1 if random.random() < (0.18 * tier + p.skills.mining_luck) else 0)
            if item:
                p.inv.add(item, qty)
            self._grant_xp(p, "mining", SKILL_XP["mine_ore"])
        else:
            self._grant_xp(p, "mining", SKILL_XP["mine_rock"])
        self.parts.chips(gx * TILE + TILE / 2, gy * TILE + TILE / 2, n=6)
        self.emit("rock_broken", p=p, area=area.name)
        return ore

    def _cb_explode(self, b, area):
        p = self.players[b["owner"]] if b["owner"] < len(self.players) else self.players[0]
        x, y = b["x"], b["y"]
        rr, mr, dmul, shake = BOMB_TYPES.get(b.get("kind", "bomb"), BOMB_TYPES["bomb"])
        mega = rr > BOMB_RADIUS
        bgx, bgy = int(x // TILE), int(y // TILE)
        broken, ores = 0, 0
        if area.name == AREA_MINE:
            r = int(math.ceil(rr))
            for gx in range(bgx - r, bgx + r + 1):
                for gy in range(bgy - r, bgy + r + 1):
                    if (gx - bgx) ** 2 + (gy - bgy) ** 2 <= rr ** 2 and (gx, gy) in area.rocks:
                        if self._cb_break_rock(p, gx, gy, area):
                            ores += 1
                        broken += 1
        depth = getattr(self.world, "mine_level", 1)
        dmg = (28 + depth * 2) * dmul
        for m in self.monsters:
            if m.hp > 0 and (m.x - x) ** 2 + (m.y - y) ** 2 <= (mr * TILE) ** 2:
                self._cb_hit(p, m, dmg * (0.6 if getattr(m, "boss", False) else 1.0), False, x, y)
        for q in self.players:
            if (q.x - x) ** 2 + (q.y - y) ** 2 <= (TILE * 1.6) ** 2:
                q.take_damage(10)
        # juice
        items = self.parts.items
        items.append(Particle(x, y, 0, 0, 0.5, (255, 220, 150), 14, ring=True))
        items.append(Particle(x, y, 0, 0, 0.7, (255, 150, 80), 30 if mega else 22, ring=True))
        for _ in range(60 if mega else 34):
            a = random.uniform(0, math.tau)
            sp = random.uniform(60, 220)
            items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp * 0.75,
                                  random.uniform(0.25, 0.6), random.choice(((255, 200, 90), (255, 130, 60),
                                                                             (255, 240, 180))),
                                  random.uniform(3, 7), grav=60, glow=True))
        self.parts.smoke(x, y, n=10, color=(120, 116, 124))
        self.parts.chips(x, y, n=14, color=(150, 140, 130))
        self.add_shake(shake)
        self._cb_sfx("explosion", "bomb", "thunder", "mine")
        if broken:
            self._popup(x, y - 30, f"BOOM! {broken} rocks", (255, 210, 120))
            self.ui.log(f"Boom! Blasted {broken} rocks ({ores} with ore).")

    def _world_sprites_combat(self):
        if not self._cb_bombs:
            return []
        out = []
        cam = self.cam
        for b in self._cb_bombs:
            blink = b["t"] < 0.6 and int(b["t"] * 14) % 2 == 0
            spr = _bomb_sprite(blink, b.get("kind") == "mega_bomb")
            wob = math.sin(b["t"] * 30) * (1.5 if b["t"] < 0.6 else 0.5)
            out.append((b["y"] + 10, spr, (int(b["x"] - cam.x - 15 + wob), int(b["y"] - cam.y - 20))))
        return out

    def _lights_combat(self):
        out = []
        for b in self._cb_bombs:
            out.append((b["x"] + 9, b["y"] - 16, 46 if b["t"] < 0.6 else 32, (255, 170, 80)))
        for m in self.monsters:
            shots = m.__dict__.get("shots")
            if shots:
                for s in shots:
                    col = (200, 130, 255) if s["kind"] == "void" else (255, 150, 70)
                    out.append((s["x"], s["y"], 40, col))
            if m.shape in ("magma", "imp"):
                out.append((m.x, m.y, 44, (255, 130, 60)))
            elif m.boss and m.shape in ("colossus", "wyrm"):
                out.append((m.x, m.y, 64, tuple(m.color)))
            elif m.shape == "prism":
                out.append((m.x, m.y, 30, tuple(m.color)))
            st = m.__dict__.get("ai")
            if st:                               # telegraphs glow so they read in the dark
                mode = st.get("mode")
                if mode in ("windup", "coil", "raise", "tell"):
                    out.append((m.x, m.y, 70 if m.boss else 40, (255, 90, 100)))
                elif st.get("charge", 0) > 0 or st.get("blink", 0) > 0:
                    out.append((m.x, m.y - 8, 36, (255, 200, 140)))
        return out
