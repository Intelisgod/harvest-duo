"""Mist City mode driver — enter/exit, zones, the clock, fog, noise, events,
the Bell Keeper, HUD, co-op and persistent run records.

Owner: Chat 7 (Mist City). ``MistMixin`` is mixed into Game by core through a
*guarded* import, and every state hook (``_mist_update`` / ``_mist_handle_event``
/ ``_mist_draw``) is looked up with getattr — so this module fully owns the
"mistcity" state without touching any file outside ``src/mistcity/``.

A run chains three zones (see zones.py): Main Street -> the Old Factory ->
the Clock Tower courtyard, where The Bell Keeper waits (boss.py). A door at the
right end of each zone leads on once every living player stands at it (ghosts
simply follow). The countdown carries across zones (+0:45 per new zone). One
random event per run (events.py) and a noise meter that draws extra zombies.

All run state lives on a transient ``MistRun`` created on enter and dropped on
exit. Only the lifetime records persist (save key ``mist_records``).

Public API for other chats:
    game.mist_enter()        — warp both players in (the forest gate calls this)
    game.mist_exit(reason)   — early-out; also used internally on timeout/wipe
    game.mist_records        — {"runs", "best_time", "deepest", "boss_kills", ...}
Events emitted: monster_killed(p, kind="mist_<walker|runner|worker>"|"bell_keeper",
boss), mist_run_end(kills, loot, reason, zone, zone_index, boss, time).
"""
import math
import random
import pygame
from ..settings import SCREEN_W, SCREEN_H, TOOL_ENERGY, MAX_ENERGY
from .. import loot
from .. import ui_kit as uk
from .world2d import GROUND_Y, NEON_MINT, NEON_PINK, NEON_AMBER, FOG_COL, mist_font
from .player2d import Player2D
from .zones import make_world, ZONES, zone_name
from .boss import BellKeeper, NAME as BOSS_NAME
from . import events as mev
try:
    from . import items as _mist_items      # noqa: F401  registers cursed_gear / city_key
except Exception:                           # pragma: no cover - never block the mode
    _mist_items = None

DURATION = 300.0            # 5:00 on the broken clock
ZONE_BONUS = 45.0           # each new zone winds the clock back a little
SPAWN_EVERY = 6.0           # respawn cadence while under the population cap
ALIVE_CAP = 9
TOTAL_CAP = 60              # per zone
ARENA_CAP = 4               # summoned zombies alive at once in the boss arena
REVIVE_T = 0.8             # seconds beside a ghost to bring them back
GATE_RANGE = 70             # px from the gate/portal that counts as "at the gate"
DOOR_RANGE = 90             # px from a zone door
BOSS_GOLD = 200
MAX_THREAT = 4             # +15% zombie/boss HP & zombie bite per Bell Keeper win (cap)
BOSS_HP_MIN = 800          # ~60-80 s for a real duo (bot sim: ~35 s flawless)
BOSS_HP_PER_DMG = 150      # scales with the party's average sword hit
EXIT_T = 3.0               # results card time before warping home

NOISE_RUN = 3.0             # per second per running player
NOISE_SWING = 1.5
NOISE_HIT = 1.0
NOISE_CRATE_HIT = 2.0
NOISE_CRATE_BREAK = 8.0
NOISE_DECAY = 4.5           # per second
NOISE_ALERT_CD = 14.0

_MSG = {
    "timeout": "The mist flooded the city!",
    "wipe": "The duo was overwhelmed by the mist...",
    "leave": "Back through the broken gate.",
    "victory": "The Bell Keeper falls silent - the city clock ticks again!",
}
# toast titles are clipped at ~330 px (about 32 Consolas-18 chars) - keep them short
_TOAST = {
    "timeout": "The mist flooded the city!",
    "wipe": "Overwhelmed by the mist...",
    "leave": "Back through the broken gate.",
}

REC_DEFAULT = {"runs": 0, "best_time": None, "deepest": 0, "boss_kills": 0,
               "best_kills": 0, "total_kills": 0, "total_loot": 0}

_MEDKIT = None


def medkit_surface():
    """The first-aid kit sprite — single source shared by the run AND the Gallery."""
    global _MEDKIT
    if _MEDKIT is None:
        s = pygame.Surface((26, 20), pygame.SRCALPHA)
        pygame.draw.rect(s, (238, 240, 244), (2, 2, 22, 16), border_radius=3)
        pygame.draw.rect(s, (196, 72, 72), (11, 5, 4, 10))
        pygame.draw.rect(s, (196, 72, 72), (6, 8, 14, 4))
        pygame.draw.rect(s, (150, 152, 160), (2, 2, 22, 16), 1, border_radius=3)
        _MEDKIT = s
    return _MEDKIT


_BUFF_ICON = []


def _buff_icon_fn():
    """assets.hud.buff_icon (the farm HUD's buff badges), looked up once; None if
    the asset module is unavailable (chips then fall back to a plain dot)."""
    if not _BUFF_ICON:
        try:
            from ..assets import hud as _hud
            _BUFF_ICON.append(getattr(_hud, "buff_icon", None))
        except Exception:
            _BUFF_ICON.append(None)
    return _BUFF_ICON[0]


def _text_top(fnt, cy):
    """Blit-y that puts ``fnt``'s capitals optically centred on ``cy`` (the
    same maths as ui_kit.blit_text, for texts that need their own alpha)."""
    cap = fnt.metrics("H")[0][3]
    return cy - fnt.get_ascent() + (cap + 1) // 2


def fmt_time(sec):
    m, s = divmod(int(sec + 0.5), 60)
    return f"{m}:{s:02d}"


def clean_records(d):
    """Records dict with every key present and JSON-stable types (old saves: {})."""
    out = dict(REC_DEFAULT)
    if not isinstance(d, dict):
        return out
    for k, dv in REC_DEFAULT.items():
        v = d.get(k, dv)
        try:
            if k == "best_time":
                out[k] = None if not v else round(float(v), 2)
            else:
                out[k] = max(0, int(v))
        except (TypeError, ValueError):
            out[k] = dv
    out["deepest"] = min(out["deepest"], len(ZONES) - 1)
    return out


class MistRun:
    """Everything one excursion into the city owns: zone world, both side-view
    players, zombies, boss, the countdown, noise, event, camera and FX."""

    def __init__(self, game, event=None):
        self.g = game
        self.rng = random.Random()
        # the game's Consolas UI family (same faces/sizes as src/ui.py where they overlap)
        self.font = mist_font(18)                 # = ui.font
        self.font_small = mist_font(14, True)
        self.font_pop = mist_font(16, True)       # floating numbers, like combat's
        self.font_big = mist_font(30, True)       # = ui.big
        self.font_huge = mist_font(44, True)
        self.font_clock = mist_font(28, True)
        self.zone_idx = 0
        self.deepest = 0
        rec = clean_records(getattr(game, "mist_records", None))
        self.threat = min(MAX_THREAT, rec["boss_kills"])   # the mist thickens after each win
        self.world = make_world(0)
        self.p2 = [Player2D(p, self.world.gate_x + 30 + i * 34) for i, p in enumerate(game.players)]
        for i, q in enumerate(self.p2):
            q.idx = i                                   # "P1"/"P2" head tags
        self.t_left = DURATION
        self.elapsed = 0.0
        self.camx = 0.0
        self.shake = 0.0
        self.over = None
        self.exit_t = 0.0
        self.intro = 0.7            # warp-flash as we tear through the gate into the mist
        self.popups = []            # [x, y, text, color, age]
        self.sparks = []            # [x, y, vx, vy, life, color, size]
        self.banner = ["MIST CITY - THE CLOCK STANDS STILL", 4.0]
        self.sub = [self._records_line(), 4.0]
        self.hint_msg = None
        self.zone_card = None       # [title, subtitle, t]
        self.trans = None           # [t, swapped]
        self.noise = 0.0
        self.noise_cd = 0.0
        self._noise_tip = False
        self.white = 0.0            # full-screen white flash (boss phase / death)
        self.esc_armed = 0.0        # ESC once arms the bail-out, twice leaves
        self.boss = None
        self.victory = False
        self.boss_killed = False
        self.new_best = False
        self.clear_time = None
        self.event_kind = event or self.rng.choice(mev.KINDS)
        self.event_at = self.rng.uniform(16.0, 30.0)
        self.event = None
        self.event_fired = False
        self._ov = pygame.Surface((SCREEN_W, SCREEN_H))
        self._ov_col = None
        self._black = pygame.Surface((SCREEN_W, SCREEN_H))
        self._flash = pygame.Surface((SCREEN_W, SCREEN_H))
        self._flash.fill((224, 240, 255))
        self._panels = {}
        self._setup_zone()

    # ------------------------------------------------------------ helpers --
    @property
    def banner(self):
        return self._banner

    @banner.setter
    def banner(self, value):
        """A sub-line belongs to the banner it was set with: any new banner (or
        the banner ending) drops the old sub-line.  Set ``sub`` AFTER ``banner``."""
        self._banner = value
        self.sub = None

    def _records_line(self):
        rec = clean_records(getattr(self.g, "mist_records", None))
        if not rec["runs"]:
            return "First visit - reach the Clock Tower and silence the bell"
        best = fmt_time(rec["best_time"]) if rec["best_time"] else "--"
        line = (f"Best clear {best}   |   Deepest: {zone_name(rec['deepest'])}   |   "
                f"Bell Keeper x{rec['boss_kills']}   |   Runs {rec['runs']}")
        threat = min(MAX_THREAT, rec["boss_kills"])
        return line + (f"   |   Threat Lv {threat}" if threat else "")

    def _setup_zone(self):
        w = self.world
        self.zombies = []
        self.total_spawned = 0
        self.spawn_cd = SPAWN_EVERY
        if w.first_zombie_x is not None:
            x = w.first_zombie_x
            end = (w.exit_x - 200) if w.exit_x else w.level_w - 140
            while x < end:
                self.zombies.append(self._make_zombie(x))
                x += self.rng.uniform(170, 290)
        self.medkits = [[float(x), float(GROUND_Y), True] for x in w.medkit_positions()]
        for i, q in enumerate(self.p2):
            q.place(w.gate_x + 30 + i * 34)
        self.camx = 0.0
        self.boss = None
        if w.key == "tower":
            avg = sum(q.damage() for q in self.p2) / max(1, len(self.p2))
            hp = max(BOSS_HP_MIN, int(BOSS_HP_PER_DMG * avg)) * (1.0 + 0.15 * self.threat)
            self.boss = BellKeeper(w.level_w * 0.72, int(hp), self.rng)

    def _make_zombie(self, x, kind=None):
        from .zombies import Zombie
        if kind is None:
            mix = self.world.zombie_mix
            r = self.rng.random() * sum(wt for _k, wt in mix)
            kind = mix[-1][0]
            for k, wt in mix:
                if r < wt:
                    kind = k
                    break
                r -= wt
        self.total_spawned += 1
        return Zombie(x, kind, level=self.threat, rng=self.rng)

    def _snd(self, name):
        try:
            self.g.audio.play(name)
        except Exception:
            pass

    def _pop(self, x, y, text, color=(255, 235, 150)):
        self.popups.append([x, y, text, color, 0.0])

    def _burst(self, x, y, color, n=8, up=True):
        for _ in range(n):
            self.sparks.append([x, y, self.rng.uniform(-90, 90),
                                self.rng.uniform(-160, -40) if up else self.rng.uniform(-40, 40),
                                self.rng.uniform(0.3, 0.7), color, self.rng.randint(2, 4)])

    def hint(self, text, secs=2.5):
        self.hint_msg = [text, secs]

    def _noise(self, amount):
        if self.world.trickle and not self.victory:
            self.noise = min(100.0, self.noise + amount)
            if self.noise >= 50 and not self._noise_tip:
                self._noise_tip = True
                self.hint("Careful - noise draws more zombies (sneak along the rooftops)", 3.5)

    def aggro(self):
        return 540 + 4.0 * self.noise

    def _panel(self, w, h, a=165, radius=8, outline=None):
        """Dark HUD card: fill and (optional) rim share one corner radius, so no
        square corners poke out past the rounded border."""
        key = (w, h, a, radius, outline)
        s = self._panels.get(key)
        if s is None:
            if len(self._panels) > 48:            # text-sized panels: keep the cache small
                self._panels.clear()
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            r = min(radius, h // 2)
            pygame.draw.rect(s, (30, 34, 38, a), s.get_rect(), border_radius=r)
            if outline:
                pygame.draw.rect(s, (*outline[:3], 255), s.get_rect(), 2, border_radius=r)
            self._panels[key] = s
        return s

    # ---------------------------------------------------------- damage --
    def _hurt_player(self, q, dmg, src="", knock=True):
        """Every hazard / zombie / boss hit goes through here."""
        if self.over or not q.hurt(dmg, knock):
            return False
        self._snd("hit")
        self.shake = max(self.shake, 6.0)
        self._burst(q.x, q.y - 32, (240, 130, 130), n=8)
        if q.p.health <= 0:
            self._down(q)
        return True

    def _down(self, q):
        q.die()
        self._pop(q.x, q.y - 60, "DOWN!", (240, 120, 120))
        self.banner = [f"{q.p.name} IS DOWN - stand by the ghost to revive!", 3.2]

    # ------------------------------------------------------------ actions --
    def jump(self, i):
        if self.over or self.trans:
            return
        if self.p2[i].jump():
            self._snd("ui_select")

    def attack(self, i):
        if self.over or self.trans:
            return
        q = self.p2[i]
        if not q.start_swing():
            return
        p = q.p
        p.energy = max(0, p.energy - TOOL_ENERGY)
        self._snd("sword")
        self._noise(NOISE_SWING)
        box = q.attack_box()
        dmg = q.damage()
        try:
            dmg = int(round(dmg * (1.0 + max(0.0, p.buff("combat")))))
        except Exception:
            pass
        for z in self.zombies:
            if z.hp > 0 and z.rise <= 0 and box.colliderect(z.rect()):
                eff = z.hit(dmg)
                z.x += q.facing * (7 if z.armor else 14)      # a little shove
                self._snd("hit")
                self._noise(NOISE_HIT)
                self.shake = max(self.shake, 3.0)
                self._burst(z.x, z.y - 30, (235, 245, 235), n=6)
                self._pop(z.x, z.y - 52, f"-{eff}", (255, 200, 140))
                if z.hp <= 0 and not z.rewarded:
                    self._kill(q, z)
        b = self.boss
        if b is not None and not b.dead and box.colliderect(b.rect()):
            eff = b.hit(dmg, q)
            if eff:
                self._snd("hit")
                self.shake = max(self.shake, 4.0)
                self._burst(q.x + q.facing * 30, q.y - 34, (250, 226, 170), n=8)
                self._pop(b.x + self.rng.uniform(-30, 30), b.y - 150, f"-{eff}", NEON_AMBER)
            else:
                self._pop(b.x, b.y - 160, "CLANG", (200, 200, 214))
        crate = self.world.crate_hit(box)
        if crate is not None:
            crate.hp -= 1
            if crate.rare and crate.hp > 0 and not getattr(crate, "supply", False):
                try:
                    has_key = p.inv.count("city_key") > 0
                except Exception:
                    has_key = False
                if has_key:                        # the Bell Keeper's key fits every lock
                    crate.hp = 0
                    self._pop(crate.x, crate.y - 40, "Unlocked!", NEON_AMBER)
                    self._snd("unlock")
            self._snd("hit")
            self._noise(NOISE_CRATE_HIT)
            self._burst(crate.x, crate.y - 14, (170, 140, 104), n=6)
            if crate.hp <= 0:
                self._noise(NOISE_CRATE_BREAK)
                label = "Supplies!" if getattr(crate, "supply", False) else (
                    "Crate!" if crate.rare else None)
                self._give_drops(q, crate.drops, crate.x, crate.y - 18, bonus_label=label)

    def _kill(self, q, z):
        z.rewarded = True
        from .zombies import DYING_T
        z.dying = DYING_T
        q.kills += 1
        gold = self.rng.randint(*z.gold)
        self.g.gold += gold
        self._pop(z.x, z.y - 64, f"+{gold}g", (255, 220, 120))
        self._burst(z.x, z.y - 28, NEON_MINT, n=12)
        self.shake = max(self.shake, 5.0)
        self._give_drops(q, z.drops, z.x, z.y - 30)
        try:
            self.g._grant_xp(q.p, "combat", z.xp)     # core helper (popups land in
        except Exception:                              # world coords; harmless here)
            pass
        if z.kind == "hazmat" and hasattr(self.world, "add_spill"):
            self.world.add_spill(z.x)
            self._burst(z.x, GROUND_Y - 6, (170, 240, 120), n=12)
            self._pop(z.x, z.y - 80, "Acid spill!", (170, 240, 120))
        emit = getattr(self.g, "emit", None)
        if emit:
            emit("monster_killed", p=q.p, kind="mist_" + z.kind, boss=False)

    def _give_drops(self, q, table, x, y, bonus_label=None):
        luck = (q.p.skills.level("combat") * 0.05) if q.p.skills else 0.0
        drops = loot.roll_drops(table, luck=luck, rng=self.rng)
        dy = 0
        if bonus_label:
            self._pop(x, y - 14, bonus_label, NEON_PINK)
        for item, qty in drops.items():
            q.p.inv.add(item, qty)
            q.loot_n += qty
            self._pop(x, y - dy, f"+{qty} {loot.label(item)}", loot.color(item))
            dy += 16
        if drops:
            self._burst(x, y, (250, 230, 160), n=6)

    # ------------------------------------------------ doors, gate, portal --
    def near_door(self, q):
        ex = self.world.exit_x
        return ex is not None and not q.ghost and abs(q.x - ex) <= DOOR_RANGE

    def door_ready(self):
        living = [q for q in self.p2 if not q.ghost]
        return bool(living) and all(self.near_door(q) for q in living)

    def down(self, i):
        """DOWN key: zone door > home gate (street) > victory portal (tower)."""
        if self.over or self.trans:
            return
        q = self.p2[i]
        if q.ghost:
            return
        w = self.world
        if self.near_door(q):
            if self.door_ready():
                self.start_transition()
            else:
                self.hint("Both of you at the door! (a ghost just follows)", 2.2)
                self._snd("ui_move")
            return
        if w.home_gate and abs(q.x - w.gate_x) <= GATE_RANGE:
            self._end("leave")
            return
        if self.victory and abs(q.x - getattr(w, "portal_x", -9999)) <= GATE_RANGE:
            self._end("victory")

    def try_leave(self, i=None, force=False):
        """Walk to the gate and duck out early (or ESC bails the whole run)."""
        if self.over:
            return
        if force:
            self._end("leave")
            return
        self.down(i)

    def start_transition(self):
        if self.trans or self.zone_idx >= len(ZONES) - 1:
            return
        self.trans = [0.0, False]
        self._snd("warp")

    def advance_zone(self):
        """Swap to the next zone (called mid-fade; tests may call it directly)."""
        if self.zone_idx >= len(ZONES) - 1:
            return False
        self.zone_idx += 1
        self.deepest = max(self.deepest, self.zone_idx)
        self.world = make_world(self.zone_idx)
        if self.event and (not self.world.events_ok or self.event.kind == "supply"):
            self.event.stop()                 # the drop stays behind in the old zone
            self.event = None
        self.t_left += ZONE_BONUS
        self.noise = min(self.noise, 30.0)
        self.popups, self.sparks = [], []
        self._setup_zone()
        self.zone_card = [f"ZONE {self.zone_idx + 1} - {self.world.name.upper()}",
                          self.world.subtitle, 3.4]
        self.banner = None
        self.hint(f"The clock slips back +{int(ZONE_BONUS)}s", 3.0)
        self._snd("unlock")
        if self.world.key == "tower":
            self._snd("boss_roar")
        return True

    def _end(self, reason):
        if self.over:
            return
        self.over = reason
        self.exit_t = EXIT_T
        big = {"timeout": "THE MIST FLOODS THE CITY!",
               "wipe": "OVERWHELMED...",
               "leave": "ESCAPED THE MIST",
               "victory": "HOME, VICTORIOUS!"}.get(reason, "ESCAPED THE MIST")
        self.banner = [big, 3.0]
        self._snd("warp")

    # ---------------------------------------------------------- events --
    def start_event(self, kind=None):
        """Fire the run's random event now (tests pass ``kind`` to force one)."""
        if kind:
            self.event_kind = kind
        if self.event is not None:
            self.event.stop()
        self.event_fired = True
        self.event = mev.make(self.event_kind, self)
        self.event.start()
        return self.event

    def _edge_x(self, side):
        lw = self.world.level_w
        x = self.camx - 50 if side < 0 else self.camx + SCREEN_W + 50
        if x < 60 or x > lw - 60:                # no room off-screen: use the far side
            x = self.camx + SCREEN_W + 50 if side < 0 else self.camx - 50
        return max(60.0, min(lw - 60.0, x))

    def _horde(self, n, alert=True):
        """A wave from both screen edges that hunts the duo regardless of range."""
        for k in range(n):
            side = -1 if k % 2 else 1
            kind = "runner" if self.rng.random() < 0.35 else None
            z = self._make_zombie(self._edge_x(side) + self.rng.uniform(-30, 30), kind)
            z.hunt = True
            self.zombies.append(z)
        if alert:
            self._snd("boss_roar")
            self.shake = max(self.shake, 5.0)

    def _boss_summon(self, n):
        alive = sum(1 for z in self.zombies if z.hp > 0)
        n = max(0, min(n, ARENA_CAP - alive))
        lw = self.world.level_w
        for _ in range(n):
            for _try in range(8):
                x = self.rng.uniform(80, lw - 80)
                if all(abs(x - q.x) > 150 for q in self.p2) and \
                        (self.boss is None or abs(x - self.boss.x) > 90):
                    break
            z = self._make_zombie(x, "walker" if self.rng.random() < 0.6 else "runner")
            z.rise = 0.8
            z.hunt = True
            self.zombies.append(z)
            self._burst(x, GROUND_Y - 4, (150, 140, 160), n=10)

    def _noise_alert(self):
        self.noise_cd = NOISE_ALERT_CD
        self.noise = 60.0
        self.banner = ["TOO LOUD! THE DEAD HEARD YOU...", 2.4]
        self._horde(3, alert=False)
        self._snd("boss_roar")

    # ------------------------------------------------------------ boss --
    def _boss_defeated(self, boss):
        """Big drop + records, then the portal home opens in the courtyard."""
        if self.boss_killed:
            return
        self.boss_killed = True
        self.victory = True
        self.clear_time = round(self.elapsed, 2)
        killer = boss.last_hitter if boss.last_hitter in self.p2 else None
        if killer is None or killer.ghost:
            killer = next((q for q in self.p2 if not q.ghost), self.p2[0])
        first, self.new_best = self.g._mist_record_boss(self.clear_time)
        killer.kills += 1
        killer.p.inv.add("cursed_gear", 1)
        killer.loot_n += 1
        got = ["Cursed Gear"]
        if first or self.rng.random() < 0.35:
            killer.p.inv.add("city_key", 1)
            killer.loot_n += 1
            got.append("City Key")
        for q in self.p2:
            if q is not killer:
                q.p.inv.add("gear_scrap", 3)
                q.p.inv.add("old_battery", 1)
                q.loot_n += 4
        self.g.gold += BOSS_GOLD
        bx, by = boss.x, boss.y - 90
        self._pop(bx, by - 40, f"+{BOSS_GOLD}g", (255, 220, 120))
        for k, name in enumerate(got):
            self._pop(bx, by - 10 + k * 18, f"+1 {name}", NEON_AMBER)
        for col in (NEON_MINT, NEON_PINK, NEON_AMBER, (250, 250, 240)):
            self._burst(bx, by, col, n=18)
        for z in self.zombies:                          # the summons crumble to dust
            self._burst(z.x, z.y - 24, (170, 170, 180), n=6)
        self.zombies = []
        self.shake = max(self.shake, 14.0)
        self.white = 0.45
        self.banner = ["THE BELL FALLS SILENT!", 4.5]
        self.sub = [f"Clear time {fmt_time(self.clear_time)}" +
                    ("   -   NEW BEST!" if self.new_best else ""), 4.5]
        self.hint("A portal home opened - press DOWN in it", 6.0)
        if hasattr(self.world, "portal_open"):
            self.world.portal_open = True
        self._snd("achievement")
        self._snd("levelup")
        emit = getattr(self.g, "emit", None)
        if emit:
            emit("monster_killed", p=killer.p, kind="bell_keeper", boss=True)

    # ------------------------------------------------------------- update --
    def update(self, dt):
        g = self.g
        g.fade = max(0.0, g.fade - dt * 1.8)
        self.intro = max(0.0, self.intro - dt)
        self.white = max(0.0, self.white - dt)
        self.esc_armed = max(0.0, self.esc_armed - dt)
        # food / perk buffs (combat, defense, speed, regen) keep counting down in
        # the mist - Player.update, which normally ticks them, never runs here
        for q in self.p2:
            tick = getattr(q.p, "_tick_buffs", None)
            if tick is not None:
                tick(dt)
        for b in (self.banner, self.sub, self.hint_msg, self.zone_card):
            if b:
                b[-1] -= dt
        if self.banner and self.banner[1] <= 0:
            self.banner = None
        if self.sub and self.sub[1] <= 0:
            self.sub = None
        if self.hint_msg and self.hint_msg[1] <= 0:
            self.hint_msg = None
        if self.zone_card and self.zone_card[2] <= 0:
            self.zone_card = None
        if self.over:
            self.exit_t -= dt
            self._tick_fx(dt)
            if self.exit_t <= 0:
                g.mist_exit(self.over)
            return
        if self.trans:
            self.trans[0] += dt
            if not self.trans[1] and self.trans[0] >= 0.45:
                self.trans[1] = True
                self.advance_zone()
            if self.trans[0] >= 0.9:
                self.trans = None
            self._tick_fx(dt)
            return
        if not self.victory:
            self.t_left -= dt
            self.elapsed += dt
            if self.t_left <= 0:
                self.t_left = 0.0
                self._end("timeout")
                return
        keys = pygame.key.get_pressed()
        w = self.world
        for q in self.p2:
            q.update(dt, keys, w)
            if q.landed and not q.ghost:
                self._burst(q.x, q.y - 2, (190, 190, 186), n=3, up=True)
            if not q.ghost and q.on_ground and abs(q.vx) > 1:
                # footsteps on the street echo; rooftops, cars and catwalks are quiet routes
                self._noise(NOISE_RUN * dt * (0.3 if q.stand is not None else 1.0))
        w.update(dt, self)
        w.door_active = self.door_ready() if w.exit_x is not None else False
        # revive: a living player stays beside a waiting ghost for a moment
        for q in self.p2:
            if not q.ghost:
                q.revive_t = 0.0
                continue
            near = any(o is not q and not o.ghost and
                       o.rect().colliderect(q.rect().inflate(30, 40)) for o in self.p2)
            rt = getattr(q, "revive_t", 0.0)
            q.revive_t = min(REVIVE_T, rt + dt) if near else max(0.0, rt - dt * 2)
            if near and int(rt * 8) != int(q.revive_t * 8):
                self._burst(q.x, q.y - 20, NEON_MINT, n=2)
            if q.revive_t >= REVIVE_T:
                q.revive_t = 0.0
                o = next(o for o in self.p2 if o is not q)
                q.revive(at_x=o.x - 20)
                self._snd("levelup")
                self._burst(q.x, q.y - 30, NEON_MINT, n=16)
                self._pop(q.x, q.y - 60, f"{q.p.name} REVIVED!", NEON_MINT)
                self.banner = [f"{q.p.name} IS BACK!", 1.6]
        # first-aid kits: a hurt, living player walks over one to patch up
        for kit in self.medkits:
            if not kit[2]:
                continue
            box = pygame.Rect(int(kit[0] - 16), int(kit[1] - 30), 32, 30)
            for q in self.p2:
                if q.ghost or q.p.health >= q.p.max_health:
                    continue
                if box.colliderect(q.rect()):
                    kit[2] = False
                    heal = int(q.p.max_health * 0.5)
                    q.p.health = min(q.p.max_health, q.p.health + heal)
                    self._snd("levelup")
                    self._burst(kit[0], kit[1] - 22, (140, 230, 150), n=12)
                    self._pop(kit[0], kit[1] - 44, f"+{heal} HP", (140, 230, 150))
                    break
        # zombies move + bite
        aggro = self.aggro()
        for z in self.zombies:
            if z.hp <= 0:
                z.dying = max(0.0, z.dying - dt)
                continue
            reach = 99999 if getattr(z, "hunt", False) else aggro
            for q, dmg in z.update(dt, self.p2, w.level_w, reach):
                self._hurt_player(q, dmg, "bite")
        self.zombies = [z for z in self.zombies if z.hp > 0 or z.dying > 0]
        if self.boss is not None:
            self.boss.update(dt, self)
        # the run's random event
        if not self.event_fired and self.elapsed >= self.event_at and w.events_ok:
            self.start_event()
        if self.event is not None:
            self.event.update(dt)
            if self.event.done:
                self.event = None
        if self.over:
            return
        if all(q.ghost for q in self.p2):
            self._end("wipe")
            return
        # noise: decays, and a full meter summons a pack
        self.noise = max(0.0, self.noise - (NOISE_DECAY if w.trickle else 25.0) * dt)
        self.noise_cd = max(0.0, self.noise_cd - dt)
        if self.noise >= 99.5 and self.noise_cd <= 0 and w.trickle:
            self._noise_alert()
        # trickle respawns from beyond the camera edges (faster + more when loud)
        if w.trickle:
            self.spawn_cd -= dt
            if self.spawn_cd <= 0:
                self.spawn_cd = SPAWN_EVERY * (1.0 - 0.5 * self.noise / 100.0)
                cap = ALIVE_CAP + int(self.noise // 25)
                if len(self.zombies) < cap and self.total_spawned < TOTAL_CAP:
                    left = self.camx - 60
                    right = self.camx + SCREEN_W + 60
                    x = left if (self.rng.random() < 0.5 and left > 160) else right
                    x = max(220.0, min(w.level_w - 40.0, x))
                    self.zombies.append(self._make_zombie(x))
        # co-op camera: follow the living, keep both on screen
        focus = [q for q in self.p2 if not q.ghost] or self.p2
        mid = sum(q.x for q in focus) / len(focus)
        target = max(0.0, min(w.level_w - SCREEN_W, mid - SCREEN_W / 2))
        self.camx += (target - self.camx) * min(1.0, dt * 5.0)
        for q in focus:
            q.x = max(self.camx + 16, min(self.camx + SCREEN_W - 16, q.x))
        self.shake = max(0.0, self.shake - dt * 22)
        self._tick_fx(dt)

    def _tick_fx(self, dt):
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 420 * dt
            s[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0][-400:]
        for p in self.popups:
            p[1] -= 26 * dt
            p[4] += dt
        self.popups = [p for p in self.popups if p[4] < 1.2]

    # --------------------------------------------------------------- draw --
    def draw(self, screen):
        t = pygame.time.get_ticks() / 1000.0
        ox = int(self.rng.uniform(-self.shake, self.shake)) if self.shake > 0.5 else 0
        oy = int(self.rng.uniform(-self.shake, self.shake) * 0.5) if self.shake > 0.5 else 0
        camx = self.camx + ox
        w = self.world
        w.draw_back(screen, camx, t)
        w.draw_main(screen, camx, t)
        # first-aid kits (shared sprite, gentle bob while unused)
        for kx, ky, alive in self.medkits:
            if not alive:
                continue
            x = int(kx - camx)
            if -40 < x < SCREEN_W + 40:
                yy = int(ky) - 22 + int(math.sin(t * 3 + kx) * 2)
                screen.blit(medkit_surface(), (x - 13, yy - 2))
        if self.event is not None:
            self.event.draw_world(screen, camx, t)
        for z in self.zombies:
            z.draw(screen, camx, t)
        if self.boss is not None and not (self.boss.done and self.victory):
            self.boss.draw(screen, camx, t)
        for q in self.p2:
            q.draw(screen, camx, t)
            rt = getattr(q, "revive_t", 0.0)
            if q.ghost and rt > 0:                       # revive progress ring
                cx, cy = int(q.x - camx), int(q.y) - 22
                pygame.draw.circle(screen, (40, 60, 56), (cx, cy), 26, 4)
                pygame.draw.arc(screen, NEON_MINT, (cx - 26, cy - 26, 52, 52),
                                math.pi / 2, math.pi / 2 + 2 * math.pi * rt / REVIVE_T, 4)
        for x, y, vx, vy, life, col, size in self.sparks:
            screen.fill(col, (int(x - camx), int(y + oy), size, size))
        w.draw_front(screen, camx, t)
        w.draw_fog(screen, camx, t)
        # the rising mist: thin film early, near-whiteout by 0:00
        prog = max(0.0, min(1.0, 1.0 - self.t_left / DURATION))
        alpha = 16 + int(120 * prog)
        if self.t_left < 60 and not self.victory:
            alpha += int(26 * (0.5 + 0.5 * math.sin(t * 4.0)))
        if self._ov_col != w.fog_col:
            self._ov_col = w.fog_col
            self._ov.fill(w.fog_col)
        self._ov.set_alpha(min(190, alpha))
        screen.blit(self._ov, (0, 0))
        if self.event is not None:
            self.event.draw_overlay(screen, camx, t)
        # popups: outlined (readable on fog / cobbles) and nudged apart so a
        # burst of loot lines stacks neatly instead of piling on one spot
        if self.popups:
            imgs, rects = [], []
            for x, y, text, col, age in self.popups:
                img = uk.outlined(self.font_pop, text, col, (22, 24, 30), 2)
                r = img.get_rect(center=(int(x - camx), int(y - 40 + oy) + img.get_height() // 2))
                imgs.append((img, max(0, int(255 * (1.0 - age / 1.2)))))
                rects.append(r)
            uk.spread_rects(rects, pad=1, bounds=pygame.Rect(0, 150, SCREEN_W, SCREEN_H))
            for (img, a), r in zip(imgs, rects):
                if r.right < 0 or r.left > SCREEN_W:
                    continue
                img.set_alpha(a)
                screen.blit(img, r.topleft)
                img.set_alpha(255)                     # the surface is ui_kit's cache
        self._draw_hud(screen, t)
        if self.trans:
            k = self.trans[0] / 0.45 if self.trans[0] < 0.45 else 1.0 - (self.trans[0] - 0.45) / 0.45
            self._black.set_alpha(int(255 * max(0.0, min(1.0, k))))
            screen.blit(self._black, (0, 0))
        if self.g.fade > 0:
            self._black.set_alpha(int(self.g.fade * 255))
            screen.blit(self._black, (0, 0))
        if self.white > 0:
            self._flash.set_alpha(int(190 * min(1.0, self.white / 0.3)))
            screen.blit(self._flash, (0, 0))
        # entry warp-flash: a bright burst + cyan warp rings off each player that
        # fades to reveal the dark misty town (the dramatic "lights-out" cut)
        if self.intro > 0:
            k = self.intro / 0.7
            self._flash.set_alpha(int(232 * k))
            screen.blit(self._flash, (0, 0))
            rr = int(40 + (1.0 - k) * 230)
            for q in self.p2:
                pygame.draw.circle(screen, (150, 220, 245), (int(q.x - camx), GROUND_Y - 36), rr, 4)

    def _draw_hud(self, screen, t):
        w = self.world
        if self.over:
            # the results modal owns the screen: no HUD / controls peeking out
            self._draw_results(screen)
            return
        # countdown clock, top centre
        mm, ss = divmod(int(self.t_left + 0.999), 60)
        urgent = self.t_left < 60 and not self.victory
        col = (240, 120, 120) if urgent and int(t * 2) % 2 else (235, 240, 235)
        if self.victory:
            col = NEON_AMBER
        clock_txt = f"{mm:02d}:{ss:02d}"
        bw = max(self.font_clock.size(clock_txt)[0], self.font.size("MIST")[0]) + 26
        box = pygame.Rect(SCREEN_W // 2 - bw // 2, 10, bw, 62)
        screen.blit(self._panel(box.w, box.h, 170, 10, (96, 116, 108)), box.topleft)
        uk.blit_text(screen, self.font, "MIST", NEON_MINT, (box.centerx, box.top + 16))
        uk.blit_text(screen, self.font_clock, clock_txt, col, (box.centerx, box.top + 42))
        # zone chain: three pips + the zone name (on its own backing pill so it
        # stays readable over the clock face / skyline)
        zy = 80
        for k in range(len(ZONES)):
            px = SCREEN_W // 2 - 26 + k * 26
            done = k < self.zone_idx
            cur = k == self.zone_idx
            c = NEON_AMBER if cur else (NEON_MINT if done else (80, 90, 90))
            pygame.draw.circle(screen, (24, 26, 30), (px, zy + 6), 8)
            pygame.draw.circle(screen, c, (px, zy + 6), 6 if cur else 5)
            if k < len(ZONES) - 1:
                pygame.draw.line(screen, (80, 90, 90), (px + 8, zy + 6), (px + 18, zy + 6), 2)
        zlab = w.name.upper() + (f"  -  THREAT {self.threat}" if self.threat else "")
        zw = self.font_small.size(zlab)[0] + 24
        zr = pygame.Rect(SCREEN_W // 2 - zw // 2, zy + 16, zw, 22)
        screen.blit(self._panel(zr.w, zr.h, 175, 11), zr.topleft)
        uk.blit_text(screen, self.font_small, zlab, (228, 232, 220), zr.center)
        ny = zr.bottom + 6
        # noise meter (street + factory)
        if w.trickle:
            nw = 170
            nx = SCREEN_W // 2 - nw // 2
            nr = pygame.Rect(nx - 58, ny - 1, nw + 76, 20)
            screen.blit(self._panel(nr.w, nr.h, 160, 10), nr.topleft)
            uk.blit_text(screen, self.font_small, "NOISE", (206, 206, 196), (nx - 48, nr.centery),
                         align="left")
            f = self.noise / 100.0
            ncol = NEON_MINT if f < 0.4 else (NEON_AMBER if f < 0.75 else NEON_PINK)
            if f >= 0.75 and int(t * 6) % 2:
                ncol = (255, 120, 150)
            bar_y = nr.centery - 5
            pygame.draw.rect(screen, (46, 50, 54), (nx + 8, bar_y, nw, 10), border_radius=5)
            if f > 0:
                pygame.draw.rect(screen, ncol, (nx + 8, bar_y, max(10, int(nw * f)), 10),
                                 border_radius=5)
            for k in (0.4, 0.75):
                pygame.draw.line(screen, (20, 22, 26), (nx + 8 + int(nw * k), bar_y - 1),
                                 (nx + 8 + int(nw * k), bar_y + 10), 1)
            if f >= 0.75:
                lr = pygame.Rect(nr.right + 6, nr.y, self.font_small.size("LOUD!")[0] + 16, nr.h)
                screen.blit(self._panel(lr.w, lr.h, 160, 10), lr.topleft)
                uk.blit_text(screen, self.font_small, "LOUD!", ncol, lr.center)
            ny = nr.bottom + 6
        # active event chip
        ev = self.event
        if ev is not None and not ev.done:
            txt = ev.label.upper()
            if ev.kind in ("outage", "acid"):
                txt += f"  {fmt_time(ev.remaining())}"
            er = pygame.Rect(0, ny, self.font_small.size(txt)[0] + 24, 20)
            er.centerx = SCREEN_W // 2
            screen.blit(self._panel(er.w, er.h, 170, 10), er.topleft)
            uk.blit_text(screen, self.font_small, txt,
                         NEON_PINK if ev.kind == "siren" else NEON_AMBER, er.center)
            ny = er.bottom + 6
        # boss bar
        b = self.boss
        if b is not None and not b.done:
            bw2 = 560
            bx = SCREEN_W // 2 - bw2 // 2
            by = max(ny + 4, 124)
            # while the big intro banner shouts the name, the bar doesn't repeat it
            named = not (self.banner and self.banner[0] == BOSS_NAME)
            blab = (BOSS_NAME if named else "") + (
                "" if b.phase == 1 else ((" - " if named else "") + f"PHASE {b.phase}"))
            if blab:
                screen.blit(self._panel(bw2 + 16, 44, 245, 10), (bx - 8, by - 4))
                uk.blit_text(screen, self.font_small, blab,
                             NEON_PINK if b.phase == 3 else (250, 226, 180), (SCREEN_W // 2, by + 8))
            else:
                screen.blit(self._panel(bw2 + 16, 26, 245, 10), (bx - 8, by + 13))
            pygame.draw.rect(screen, (60, 40, 50), (bx, by + 18, bw2, 16), border_radius=5)
            f = b.frac()
            fc = (236, 120, 150) if b.phase == 3 else ((240, 180, 110) if b.phase == 2 else (226, 110, 110))
            if b.flash > 0:
                fc = (255, 240, 240)
            pygame.draw.rect(screen, fc, (bx, by + 18, int(bw2 * f), 16), border_radius=5)
            for k in (0.33, 0.66):
                pygame.draw.line(screen, (30, 24, 30), (bx + int(bw2 * k), by + 18),
                                 (bx + int(bw2 * k), by + 33), 2)
            pygame.draw.rect(screen, (250, 226, 180), (bx, by + 18, bw2, 16), 2, border_radius=5)
            ny = by + 44
        # player bars (HP red / energy green), kills+loot tally
        pw = 232
        for i, q in enumerate(self.p2):
            p = q.p
            x = 14 if i == 0 else SCREEN_W - 14 - pw
            screen.blit(self._panel(pw, 64, 160, 10), (x, 10))
            uk.blit_text(screen, self.font, str(p.name)[:14],
                         (200, 230, 215) if not q.ghost else (160, 190, 200), (x + 10, 23),
                         align="left")
            if q.ghost:
                uk.blit_text(screen, self.font_small, "(ghost)", (160, 190, 200),
                             (x + pw - 10, 23), align="right")
            hpf = max(0.0, min(1.0, p.health / max(1, p.max_health)))
            pygame.draw.rect(screen, (60, 44, 48), (x + 10, 38, 140, 9), border_radius=3)
            if hpf > 0:
                pygame.draw.rect(screen, (226, 110, 110), (x + 10, 38, max(4, int(140 * hpf)), 9),
                                 border_radius=3)
            enf = max(0.0, min(1.0, p.energy / float(MAX_ENERGY)))
            pygame.draw.rect(screen, (44, 56, 46), (x + 10, 52, 140, 7), border_radius=3)
            if enf > 0:
                pygame.draw.rect(screen, (140, 215, 140), (x + 10, 52, max(4, int(140 * enf)), 7),
                                 border_radius=3)
            # readable tally: kills and parts, right-aligned beside the bars
            tf = mist_font(13, True)
            uk.blit_text(screen, tf, f"Kills {q.kills}", (226, 214, 170), (x + pw - 10, 42),
                         align="right")
            uk.blit_text(screen, tf, f"Parts {q.loot_n}", (200, 206, 190), (x + pw - 10, 56),
                         align="right")
            self._draw_buffs(screen, p, i, x if i == 0 else x + pw, t)
        # context prompts
        prompt = None
        if self.over or self.trans:
            pass
        elif any(self.near_door(q) for q in self.p2):
            nxt = ZONES[min(len(ZONES) - 1, self.zone_idx + 1)].name
            at = sum(1 for q in self.p2 if self.near_door(q))
            living = sum(1 for q in self.p2 if not q.ghost)
            prompt = (f"Press DOWN to enter {nxt}" if w.door_active
                      else f"Both players to the door to go on ({at}/{living} here)")
        elif w.home_gate and self.elapsed > 4.0 and                 any(not q.ghost and abs(q.x - w.gate_x) <= GATE_RANGE for q in self.p2):
            prompt = "Press DOWN to slip back through the gate"
        elif self.victory and any(not q.ghost and abs(q.x - getattr(w, "portal_x", -9999)) <= GATE_RANGE
                                  for q in self.p2):
            prompt = "Press DOWN to go home"
        if prompt:
            if prompt.startswith("Press DOWN to "):          # the game's one world-prompt style
                rest = prompt[len("Press DOWN to "):]
                uk.key_pill(screen, "DOWN", rest[:1].upper() + rest[1:],
                            (SCREEN_W // 2, SCREEN_H - 58), fnt=mist_font(16, True))
            else:
                self._hud_line(screen, self.font, prompt, NEON_MINT, SCREEN_H - 58)
        elif self.hint_msg and not self.over:
            a = min(1.0, self.hint_msg[1] / 0.4)
            self._hud_line(screen, self.font, self.hint_msg[0], (236, 232, 210), SCREEN_H - 58, a)
        # controls reminder on a soft pill (legible on road / cobbles / belts)
        self._hud_line(screen, self.font_small,
                       "UP jump    ACTION attack    DOWN door / gate    ESC x2 bail out",
                       (214, 224, 216), SCREEN_H - 22, 1.0, 130)
        # banners sit BELOW the clock faces (street tower ~y204-276, courtyard
        # clock ~y80-272) and the boss bar, and below the zone card if it shows
        band_y = max(284, ny + 10)
        # zone title card
        if self.zone_card:
            title, sub, tl = self.zone_card
            a = max(0.0, min(1.0, tl / 0.6, (3.4 - tl) / 0.35))
            slide = int((1.0 - min(1.0, (3.4 - tl) / 0.35)) * 40)
            cy = band_y
            card = self._panel(SCREEN_W, 104, 150, 0)
            card.set_alpha(int(255 * a))
            screen.blit(card, (0, cy))
            card.set_alpha(255)
            img = self.font_huge.render(title, True, (246, 240, 226))
            img.set_alpha(int(255 * a))
            screen.blit(img, (SCREEN_W // 2 - img.get_width() // 2 + slide,
                              _text_top(self.font_huge, cy + 40)))
            s2 = self.font.render(sub, True, NEON_AMBER)
            s2.set_alpha(int(255 * a))
            screen.blit(s2, (SCREEN_W // 2 - s2.get_width() // 2 - slide,
                             _text_top(self.font, cy + 80)))
            band_y = cy + 104 + 8
        if self.banner:
            text, tl = self.banner
            # one fade factor for the text AND its backing panel, so the last
            # ~0.8 s never leaves an empty dark bar over the play area
            k = max(0.0, min(1.0, 330.0 * tl / 255.0))
            tw = self.font_big.size(text)[0]
            back = self._panel(tw + 36, self.font_big.get_height() + 14, 150, 12)
            by = band_y
            if k >= 0.05:
                back.set_alpha(int(255 * k))           # scales the panel's own 150 alpha
                screen.blit(back, (SCREEN_W // 2 - back.get_width() // 2, by))
                back.set_alpha(255)                    # restore the cached panel (None = opaque blit)
                img = self.font_big.render(text, True, (240, 244, 238))
                img.set_alpha(int(255 * k))
                screen.blit(img, (SCREEN_W // 2 - img.get_width() // 2,
                                  _text_top(self.font_big, by + back.get_height() // 2)))
            if self.sub:
                self._draw_sub(screen, by + back.get_height() + 6)
        elif self.sub:
            self._draw_sub(screen, band_y)

    def _hud_line(self, screen, fnt, text, col, cy, a=1.0, back_a=150):
        """One line of HUD text centred on a soft dark pill at centre-y ``cy``."""
        a = max(0.0, min(1.0, a))
        if a <= 0.02:
            return
        w = fnt.size(text)[0] + 28
        h = fnt.get_height() + 8
        back = self._panel(w, h, back_a, h // 2)
        back.set_alpha(int(255 * a))
        screen.blit(back, (SCREEN_W // 2 - w // 2, cy - h // 2))
        back.set_alpha(255)
        img = fnt.render(text, True, col)
        img.set_alpha(int(255 * a))
        screen.blit(img, (SCREEN_W // 2 - img.get_width() // 2, _text_top(fnt, cy)))

    def _draw_buffs(self, screen, p, side, x, t):
        """Food / perk buff chips under a player's panel (icon + seconds left),
        the same badges the farm HUD shows, so the countdown is visible here too."""
        buffs = getattr(p, "buffs", None)
        if not buffs:
            return
        icon_fn = _buff_icon_fn()
        y = 78
        for kind, b in sorted(buffs.items()):
            try:
                secs = max(0.0, float(b[1]))
            except (TypeError, ValueError, IndexError):
                continue
            txt = self.font_small.render(f"{int(secs)}s" if secs < 100 else f"{int(secs // 60)}m",
                                         True, (240, 236, 220))
            cw = 36 + txt.get_width()
            cx = x if side == 0 else x - cw
            screen.blit(self._panel(cw, 22, 170, 11), (cx, y))
            ic = None
            if icon_fn is not None:
                try:
                    ic = icon_fn(kind, 18)
                except Exception:
                    ic = None
            if ic is not None:
                if secs < 5 and int(t * 6) % 2 == 0:            # about to run out: blink
                    ic = ic.copy()
                    ic.set_alpha(110)
                screen.blit(ic, (cx + 6, y + 2))
            else:
                pygame.draw.circle(screen, NEON_AMBER, (cx + 15, y + 11), 7)
            screen.blit(txt, (cx + 27, _text_top(self.font_small, y + 11)))
            x = x + cw + 6 if side == 0 else x - cw - 6

    def _draw_results(self, screen):
        """End-of-run card while the mist swallows the screen."""
        k = max(0.0, min(1.0, (EXIT_T - self.exit_t) / 0.4))
        if k <= 0:
            return
        kills = sum(q.kills for q in self.p2)
        parts = sum(q.loot_n for q in self.p2)
        split = "  (" + " / ".join(f"P{i + 1} {q.kills}" for i, q in enumerate(self.p2)) + ")"
        rows = [("Zombies", str(kills) + split), ("Parts", str(parts)),
                ("Reached", self.world.name), ("Time", fmt_time(self.elapsed))]
        if self.boss_killed:
            rows.append(("Bell Keeper", "SILENCED" + ("  - NEW BEST!" if self.new_best else "")))
        title = {"timeout": "THE MIST FLOODS THE CITY!",
                 "wipe": "OVERWHELMED...",
                 "leave": "ESCAPED THE MIST",
                 "victory": "HOME, VICTORIOUS!"}.get(self.over, "ESCAPED THE MIST")
        msg = _MSG.get(self.over, _MSG["leave"])
        f_row = uk.font(18, True)
        f_msg = uk.fit_font(msg, 500, (16, 15, 14, 13))
        row_h, gap = 34, 6
        w = 580
        h = 62 + 30 + len(rows) * (row_h + gap) + 34
        # parchment modal on its own layer so the whole card fades in together
        layer = pygame.Surface((w + 80, h + 70), pygame.SRCALPHA)
        card = pygame.Rect(40, 44, w, h)
        uk.modal(layer, card, title, uk.font(28, True))
        uk.blit_text(layer, f_msg, msg, uk.INK_SOFT, (card.centerx, card.y + 56))
        uk.divider(layer, card.centerx, card.y + 78, w // 2 - 60)
        ry = card.y + 92
        for lab, val in rows:
            band = pygame.Rect(card.x + 34, ry, w - 68, row_h)
            uk.well(layer, band)
            uk.blit_text(layer, f_row, lab, uk.INK_SOFT, (band.x + 16, band.centery), align="left")
            vcol = uk.GOLD_TXT if (lab == "Bell Keeper" or "NEW BEST" in val) else uk.INK
            uk.blit_text(layer, f_row, val, vcol, (band.right - 16, band.centery), align="right")
            ry += row_h + gap
        uk.blit_text(layer, uk.font(14, True), "Heading home through the mist...", uk.INK_FAINT,
                     (card.centerx, card.bottom - 22))
        # dim the world (and everything drawn on it) behind the card
        uk.dim(screen, int(round(160 * k / 10.0)) * 10)
        layer.set_alpha(int(255 * k))
        screen.blit(layer, (SCREEN_W // 2 - layer.get_width() // 2,
                            SCREEN_H // 2 - layer.get_height() // 2))

    def _draw_sub(self, screen, y):
        text, tl = self.sub
        a = min(255, int(330 * min(1.0, tl)))
        s2 = self.font.render(text, True, NEON_AMBER)
        h = self.font.get_height() + 8
        back = self._panel(s2.get_width() + 32, h, 140, h // 2)
        back.set_alpha(a)
        screen.blit(back, (SCREEN_W // 2 - back.get_width() // 2, y))
        back.set_alpha(255)
        s2.set_alpha(a)
        screen.blit(s2, (SCREEN_W // 2 - s2.get_width() // 2, _text_top(self.font, y + h // 2)))


class MistMixin:
    """Game gains the whole Mist City mode from this mixin (no __init__; state
    is created in ``_on_reset_mist`` per the hook contract)."""

    # ---- lifecycle hooks (src/systems/hooks.py) ----
    def _on_reset_mist(self):
        self.mist_run = None
        self.mist_records = dict(REC_DEFAULT)

    def _on_save_mist(self):
        return {"mist_records": clean_records(getattr(self, "mist_records", None))}

    def _on_load_mist(self, d):
        self.mist_records = clean_records(d.get("mist_records"))

    def _mist_record_boss(self, clear_time):
        """Boss kill bookkeeping -> (first_kill, new_best_time)."""
        rec = clean_records(getattr(self, "mist_records", None))
        first = rec["boss_kills"] == 0
        rec["boss_kills"] += 1
        new_best = rec["best_time"] is None or clear_time < rec["best_time"]
        if new_best:
            rec["best_time"] = round(float(clear_time), 2)
        self.mist_records = rec
        return first, new_best

    # ---- public: called by the forest gate (Chat 5) or debug/test code ----
    def mist_enter(self, event=None):
        if getattr(self, "mist_run", None) or self.state == "mistcity":
            return
        f = getattr(self, "together_needed", None)
        if f and f("Mist City"):
            return                   # online: both must stand at the forest gate
        self._mist_return = (self.world.current,
                             [(p.x, p.y) for p in self.players])
        self.mist_run = MistRun(self, event=event)
        self.state = "mistcity"
        self.fade = 1.0
        try:
            self.audio.play("warp")
            self.audio.play_area("mistcity")     # dedicated dread theme (audio.py)
        except Exception:
            pass

    # Chat 5's gate contract names the hook with an underscore — keep both.
    def _mist_enter(self):
        self.mist_enter()

    def mist_exit(self, reason="leave"):
        run = getattr(self, "mist_run", None)
        if run is None:
            if self.state == "mistcity":
                self.state = "play"
            return
        area, pos = getattr(self, "_mist_return",
                            (self.world.current, None))
        if getattr(self, "p_area", None) is not None and self.world.current != area:
            self._ctx_store = {}                     # both come home to the same area
        self.world.current = area
        if getattr(self, "p_area", None) is not None:
            self.p_area = [area, area]
        ret = getattr(self.world.area, "mist_return", None)
        if ret:                                  # forest anchor next to the gate
            from ..settings import TILE
            rx, ry = ret
            self.players[0].x = rx * TILE + TILE / 2
            self.players[0].y = ry * TILE + TILE / 2
            self.players[1].x = (rx + 1) * TILE + TILE / 2
            self.players[1].y = ry * TILE + TILE / 2
        elif pos:
            for p, (x, y) in zip(self.players, pos):
                p.x, p.y = x, y
        for q in run.p2:                          # nobody comes home dead
            if q.ghost:
                q.p.health = max(1, int(q.p.max_health * 0.3))
            q.p.health = max(1, q.p.health)
        kills = sum(q.kills for q in run.p2)
        loot_n = sum(q.loot_n for q in run.p2)
        # lifetime records
        rec = clean_records(getattr(self, "mist_records", None))
        rec["runs"] += 1
        rec["deepest"] = max(rec["deepest"], run.deepest)
        rec["best_kills"] = max(rec["best_kills"], kills)
        rec["total_kills"] += kills
        rec["total_loot"] += loot_n
        self.mist_records = rec
        self.mist_run = None
        self.state = "play"
        self.fade = 1.0
        try:
            self.ui.log(f"{_MSG.get(reason, _MSG['leave'])}  "
                        f"({kills} zombies, {loot_n} parts)")
            self.audio.play("warp")
            self.audio.play_area(self.world.current)
        except Exception:
            pass
        toast = getattr(self, "toast", None)
        if toast:
            try:
                if reason == "victory":
                    toast("The Bell Keeper is silenced!",
                          f"Clear time {fmt_time(run.clear_time or run.elapsed)}"
                          + ("  -  NEW BEST!" if run.new_best else ""),
                          icon="cursed_gear", color=NEON_AMBER, seconds=5.0)
                else:
                    toast(_TOAST.get(reason, _TOAST["leave"]),
                          f"{kills} zombies, {loot_n} parts - reached {zone_name(run.deepest)}",
                          icon="scrap_iron", color=NEON_MINT, seconds=4.0)
            except Exception:
                pass
        emit = getattr(self, "emit", None)
        if emit:
            emit("mist_run_end", kills=kills, loot=loot_n, reason=reason,
                 zone=run.world.key, zone_index=run.deepest, boss=run.boss_killed,
                 time=round(run.elapsed, 1))

    # ---- state hooks (core calls these via guarded getattr) ----
    def _mist_update(self, dt):
        run = getattr(self, "mist_run", None)
        if run is not None:
            run.update(dt)
        else:
            self.state = "play"              # never soft-lock in an empty mist state

    def _mist_handle_event(self, e):
        run = getattr(self, "mist_run", None)
        if run is None or e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            if run.esc_armed > 0 or run.over:
                run.try_leave(force=True)
            else:                                # a stray ESC must not end a boss run
                run.esc_armed = 2.0
                run.hint("Press ESC again to bail out of the mist", 2.0)
                run._snd("ui_move")
            return
        for i, q in enumerate(run.p2):
            K = q.p.keys
            if e.key == K["up"]:
                run.jump(i)
            elif e.key == K["action"]:
                run.attack(i)
            elif e.key == K["down"]:
                run.down(i)

    def _mist_draw(self):
        run = getattr(self, "mist_run", None)
        if run is not None:
            run.draw(self.screen)

    # ---- journal tab (UI owns the Journal; key J) ----
    def _journal_tab_60_mist(self):
        return {"title": "Mist City", "draw": self._mist_journal_draw}

    def _mist_journal_draw(self, surf, rect):
        """Cream journal page: records table (left) + Bell Keeper medallion
        (right), then the zone route and field notes across the full width."""
        rec = clean_records(getattr(self, "mist_records", None))
        f_head = uk.font(20, True)
        f_row = uk.font(16)
        f_tip = uk.font(15)
        pad = 12
        x0, top = rect.x + pad, rect.y + 6
        full_w = rect.w - 2 * pad
        left_w = int(full_w * 0.60)
        best = fmt_time(rec["best_time"]) if rec["best_time"] else "--"
        rows = [("Trips into the mist", str(rec["runs"])),
                ("Deepest zone reached", zone_name(rec["deepest"]) if rec["runs"] else "--"),
                ("Bell Keeper defeated", f"x{rec['boss_kills']}"),
                ("Best Bell Keeper clear", best),
                ("Most zombies in one run", str(rec["best_kills"])),
                ("Zombies laid to rest", str(rec["total_kills"])),
                ("Parts scavenged", str(rec["total_loot"]))]
        # ---- records table (left 60%) ----
        uk.blit_text(surf, f_head, "MIST CITY - RUN RECORDS", uk.INK, (x0 + 4, top + 12), align="left")
        y = top + 32
        row_h = 28
        for i, (lab, val) in enumerate(rows):
            band = pygame.Rect(x0, y, left_w, row_h)
            if i % 2 == 0:
                pygame.draw.rect(surf, uk.WELL, band, border_radius=8)
            uk.blit_text(surf, f_row, lab, uk.INK_SOFT, (band.x + 12, band.centery), align="left")
            vf = uk.fit_font(val, left_w // 2 - 16, (16, 15, 14, 13), bold=True)
            uk.blit_text(surf, vf, val,
                         uk.GOLD_TXT if lab.startswith("Best") and rec["best_time"] else uk.INK,
                         (band.right - 12, band.centery), align="right")
            y += row_h + 3
        table_bottom = y
        # ---- the Bell Keeper medallion (right 40%): silenced = gold rim, tolling = mint eyes ----
        mcx = x0 + left_w + (full_w - left_w) // 2
        silenced = rec["boss_kills"] > 0
        try:
            from .boss import _body
            img = _body(False)
            rad = min((full_w - left_w) // 2 - 12, img.get_height() // 2 + 12)
            mcy = top + 12 + rad
            pygame.draw.circle(surf, uk.WELL, (mcx, mcy), rad)
            pygame.draw.circle(surf, uk.GOLD_RIM if silenced else uk.WELL_LINE, (mcx, mcy), rad, 3)
            if img.get_height() > rad * 2 - 16:
                k = (rad * 2 - 16) / img.get_height()
                img = pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))
            px, py = mcx - img.get_width() // 2, mcy - img.get_height() // 2
            surf.blit(img, (px, py))
            ex, ey = mcx, py + img.get_height() - int(20 * img.get_height() / 160)
            for dx in (-16, 16):
                dx = int(dx * img.get_width() / 136)
                if silenced:
                    pygame.draw.line(surf, (120, 110, 120), (ex + dx - 5, ey), (ex + dx + 5, ey), 2)
                else:
                    pygame.draw.ellipse(surf, NEON_MINT, (ex + dx - 6, ey - 4, 12, 8))
            cap_y = mcy + rad + 16
        except Exception:
            cap_y = top + 40
        uk.blit_text(surf, uk.font(16, True),
                     ("SILENCED x%d" % rec["boss_kills"]) if silenced else "Still tolling...",
                     uk.GOLD_TXT if silenced else uk.INK_SOFT, (mcx, cap_y))
        # ---- the zone route, full width ----
        y = max(table_bottom, cap_y + 12) + 14
        uk.blit_text(surf, uk.font(15, True), "THE ROUTE", uk.SPROUT, (x0 + 4, y + 7), align="left")
        y += 20
        gap = 34
        bw = (full_w - gap * (len(ZONES) - 1)) // len(ZONES)
        for k, Z in enumerate(ZONES):
            box = pygame.Rect(x0 + k * (bw + gap), y, bw, 34)
            reached = bool(rec["runs"]) and k <= rec["deepest"]
            pygame.draw.rect(surf, uk.CREAM_HI if reached else uk.WELL, box, border_radius=8)
            pygame.draw.rect(surf, uk.SPROUT if reached else uk.WELL_LINE, box, 2, border_radius=8)
            lab = f"{k + 1}. {Z.name}"
            lf = uk.fit_font(lab, bw - 16, (16, 15, 14, 13, 12), bold=True)
            uk.blit_text(surf, lf, uk.ellipsize(lf, lab, bw - 12),
                         uk.INK if reached else uk.INK_FAINT, box.center)
            if k < len(ZONES) - 1:                      # little arrow to the next zone
                nxt = bool(rec["runs"]) and k + 1 <= rec["deepest"]
                ac = uk.SPROUT if nxt else uk.WELL_LINE
                ax0, ax1 = box.right + 6, box.right + gap - 6
                pygame.draw.line(surf, ac, (ax0, box.centery), (ax1 - 4, box.centery), 3)
                pygame.draw.polygon(surf, ac, [(ax1, box.centery), (ax1 - 7, box.centery - 6),
                                               (ax1 - 7, box.centery + 6)])
        y += 34 + 18
        # ---- field notes: two balanced columns across the page ----
        uk.blit_text(surf, uk.font(15, True), "FIELD NOTES", uk.SPROUT, (x0 + 4, y + 7), align="left")
        y += 22
        tips = ["Enter through the ruined gate deep in the Forest.",
                "Steps, swings and smashed crates make NOISE; rooftops are quieter.",
                "Both players at a zone door to go on - a ghost just follows.",
                "The Bell Keeper strikes on the toll: jump the floor waves!",
                "Carry a City Key and pink-locked crates open in one hit."]
        col_w = (full_w - 24) // 2
        line_h = f_tip.get_height() + 2
        cols = (tips[:3], tips[3:])
        for c, group in enumerate(cols):
            cx = x0 + c * (col_w + 24)
            yy = y
            for tip in group:
                lines = uk.wrap(f_tip, tip, col_w - 18)
                if yy + line_h * len(lines) > rect.bottom:
                    break
                pygame.draw.circle(surf, uk.SPROUT, (cx + 6, yy + line_h // 2), 3)
                for ln in lines:
                    uk.blit_text(surf, f_tip, ln, uk.INK, (cx + 16, yy + line_h // 2), align="left")
                    yy += line_h
                yy += 6
