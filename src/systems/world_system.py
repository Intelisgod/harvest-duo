"""World-side runtime behaviour: hazards, outdoor decor mode, new areas.

Owner: World, Areas & Build (Chat 5). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

2026-09 level-up features living here:
  * mine hazards   -- lava pools (lava biome) / void rifts (abyss) hurt ~6 HP/s,
                      glow via _lights_world_*; drawn as flat animated decals
  * farm dressing  -- the walk-over fence frame + lamp/tree/lantern glows
  * Flower Meadow  -- the Promise Tree couple moment (both press together ->
                      hearts, golden glow, +energy once a day, initials carved)
                      and the lookout deck; winter snow grid swap
  * decor mode     -- press B on the farm: place / sell outdoor decor stored in
                      world.farm_objects as "decor_<name>" (solid ones block via
                      Area.dyn_solid)
"""
import math
import random
import time
import pygame
from ..settings import (TILE, SCREEN_W, SCREEN_H, AREA_FARM, AREA_MEADOW, AREA_MINE,
                        P1_KEYS, P2_KEYS, MAX_ENERGY, BUILD_KEY)
from ..ui import key_label
from .. import world as W
from .. import world_art as WA

try:                                     # register the World props (farm/meadow/mine)
    from .. import assets as _assets
    for _k, _fn in WA.prop_painters().items():
        _assets.register_prop(_k, _fn)
except Exception:                        # pragma: no cover - art never blocks boot
    _assets = None

# orchard fruit (farm fruit trees can be shaken once a day in summer / fall)
ORCHARD_FRUIT = {"Summer": "apple", "Fall": "persimmon"}
ORCHARD_CHANCE = 0.65      # chance a shaken tree drops a fruit (keeps the economy gentle)
DECOR_HEAD_GAP = 30        # decor bar: px between 'OUTDOOR DECOR' and the picked piece


def _paint_apple(s):
    pygame.draw.circle(s, (170, 40, 44), (14, 16), 9)
    pygame.draw.circle(s, (222, 64, 64), (13, 15), 8)
    pygame.draw.circle(s, (255, 200, 200), (10, 12), 2)
    pygame.draw.line(s, (110, 80, 50), (14, 8), (15, 4), 2)
    pygame.draw.ellipse(s, (110, 180, 90), (15, 3, 8, 5))


def _paint_persimmon(s):
    pygame.draw.ellipse(s, (196, 96, 30), (5, 9, 19, 15))
    pygame.draw.ellipse(s, (244, 146, 50), (5, 8, 18, 14))
    pygame.draw.circle(s, (255, 214, 160), (10, 12), 2)
    for dx in (-4, 0, 4):
        pygame.draw.polygon(s, (98, 150, 70), [(14, 9), (14 + dx, 4), (14 + dx // 2 + 2, 9)])


try:
    from .. import loot as _loot
    _loot.register_item("apple", "Orchard Apple", 25, (222, 64, 64), "forage")
    _loot.register_item("persimmon", "Persimmon", 30, (244, 146, 50), "forage")
    if _assets is not None:
        _assets.register_item_icon("apple", _paint_apple)
        _assets.register_item_icon("persimmon", _paint_persimmon)
except Exception:                        # pragma: no cover
    pass

PROMISE_WINDOW = 2.0       # s: both partners must press within this window
PROMISE_MILESTONES = (7, 30, 100)   # promises -> ribbons / lanterns / golden blossoms
_MILESTONE_TEXT = {1: "Red ribbons now flutter on its boughs",
                   2: "Paper lanterns now glow beneath its leaves",
                   3: "Golden blossoms crown the tree -- a hundred promises kept"}


def _promise_tier(count):
    return sum(1 for m in PROMISE_MILESTONES if count >= m)
PROMISE_ENERGY = 40
LOOKOUT_ENERGY = 15
DECOR_PREFIX = "decor_"
_FLAT_BASE = -1_000_000    # y-sort key for flat decals (drawn under every actor)

_LOOKOUT_LINES = [
    "The whole valley glows below -- the farm, the river, the tiny town roofs.",
    "Clouds drift over the hills. You can almost see the sea from here.",
    "A hawk circles lazily. Everything feels a little smaller and kinder.",
    "The wind smells of wildflowers and warm grass.",
]


def _radial(r, col):
    key = ("wglow", r, col)
    s = WA._cache.get(key)
    if s is None:
        # additive glow: the RGB itself must fall off towards the rim
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(16, 0, -1):
            f = (1.0 - i / 16.0) ** 1.6 + 0.02
            c = tuple(min(255, int(v * f)) for v in col)
            pygame.draw.circle(s, (*c, 255), (r, r), int(r * i / 16))
        WA._cache[key] = s
    return s


def _heart_icon():
    s = WA._cache.get("w_heart_icon")
    if s is None:
        s = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(s, (200, 70, 100), (9, 11), 7)
        pygame.draw.circle(s, (200, 70, 100), (19, 11), 7)
        pygame.draw.polygon(s, (200, 70, 100), [(2, 13), (26, 13), (14, 26)])
        pygame.draw.circle(s, (255, 130, 160), (9, 10), 6)
        pygame.draw.circle(s, (255, 130, 160), (19, 10), 6)
        pygame.draw.polygon(s, (255, 130, 160), [(3, 12), (25, 12), (14, 24)])
        pygame.draw.circle(s, (255, 220, 230), (8, 8), 2)
        WA._cache["w_heart_icon"] = s
    return s


class WorldMixin:
    """World-side runtime behaviour: hazards, outdoor decor mode, new areas."""

    # ------------------------------------------------------------------ lifecycle
    def _on_reset_world(self):
        self.world_promise = {"carved": "", "day": "", "count": 0}
        self._wp_press = [-99.0, -99.0]     # monotonic stamp of each partner's press
        self._wp_glow = 0.0                 # golden glow timer after a promise
        self._wp_hint_t = 0.0
        self._wl_seen = set()               # (day, player) lookout breathers today
        self._w_swing_amp = 1.0             # rope-swing sway amplitude (px)
        self._w_swing_seen = set()          # (day, player) swing energy today
        self.world_orchard = {"day": "", "shaken": []}   # fruit trees shaken today
        self._wh_warned = set()             # one-time area hints shown (saved: world_hints)
        self._wh_quiet = False
        self._w_fx_t = 0.0
        self._w_clean_t = 0.0
        self._w_decor_sig = None
        self._wd = {"sel": 0, "cx": 12, "cy": 12, "msg": "", "msg_t": 0.0,
                    "msg_ok": True, "hover": None}
        self._w_pop = {}                    # (gx, gy) -> anim_t when a decor piece landed
        self._world_sync_decor(force=True)
        self._world_apply_season()

    def _on_load_world(self, d):
        wp = d.get("world_promise") or {}
        if not isinstance(wp, dict):
            wp = {}
        self.world_promise = {"carved": str(wp.get("carved", "") or ""),
                              "day": str(wp.get("day", "") or ""),
                              "count": int(wp.get("count", 0) or 0)}
        orc = d.get("world_orchard") or {}
        if not isinstance(orc, dict):
            orc = {}
        self.world_orchard = {"day": str(orc.get("day", "") or ""),
                              "shaken": sorted([int(c[0]), int(c[1])]
                                               for c in (orc.get("shaken") or [])
                                               if isinstance(c, (list, tuple)) and len(c) == 2)}
        # today's once-a-day meadow breathers (lookout / swing / bench): only
        # restored when the save was made today, so a relaunch can't re-grant them
        self._world_load_daily(d.get("world_daily"))
        # one-time area hints already shown (meadow lore, decor tip, hazard
        # warnings). A real load restores them exactly; a LAN client's resync
        # merges, so it never re-arms a hint the client has already seen.
        hints = d.get("world_hints")
        hints = {h for h in hints if isinstance(h, str) and h} \
            if isinstance(hints, (list, tuple)) else set()
        if getattr(self, "_net_applying_world", False):
            self._wh_warned = set(getattr(self, "_wh_warned", ())) | hints
        else:
            self._wh_warned = hints
            # the area entry _apply_save runs next is the load itself, not a
            # visit: don't hint (or record a hint) there -- keeps the round-trip exact
            self._wh_quiet = True
        self._world_sync_decor(force=True)
        self._world_unblock_tilled()
        self._world_apply_season()
        self._world_unstick_players()

    def _world_unstick_players(self):
        """A save made before the 2026-09 map changes may park a player on a tile
        that is now solid (a lamp post, an orchard tree): hop to the nearest free one."""
        area = self.world.area
        for p in self.players:
            gx, gy = int(p.x // TILE), int(p.y // TILE)
            if not area.is_solid(gx, gy):
                continue
            for r in range(1, 6):
                ring = [(gx + dx, gy + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                        if max(abs(dx), abs(dy)) == r]
                free = [c for c in ring if 0 < c[0] < area.w - 1 and 0 < c[1] < area.h - 1
                        and not area.is_solid(*c)]
                if free:
                    fx, fy = min(free, key=lambda c: abs(c[0] - gx) + abs(c[1] - gy))
                    p.x, p.y = fx * TILE + TILE / 2, fy * TILE + TILE / 2
                    break

    def _on_save_world(self):
        return {"world_promise": {"carved": self.world_promise.get("carved", ""),
                                  "day": self.world_promise.get("day", ""),
                                  "count": int(self.world_promise.get("count", 0))},
                "world_orchard": {"day": self.world_orchard.get("day", ""),
                                  "shaken": sorted([int(c[0]), int(c[1])] for c in
                                                   self.world_orchard.get("shaken", []))},
                "world_daily": self._world_daily_dict(),
                "world_hints": sorted(str(h) for h in self._wh_warned if h)}

    def _world_daily_dict(self):
        """Today's used once-a-day meadow energy spots, as a JSON-safe dict."""
        day = self._w_day_key()
        look = sorted({int(k[1]) for k in self._wl_seen if k[0] == day})
        swing = sorted({int(k[1]) for k in self._w_swing_seen
                        if k[0] == day and len(k) == 2})
        bench = sorted({int(k[2]) for k in self._w_swing_seen
                        if k[0] == day and len(k) == 3 and k[1] == "bench"})
        return {"day": day, "lookout": look, "swing": swing, "bench": bench}

    def _world_load_daily(self, dd):
        self._wl_seen = set()
        self._w_swing_seen = set()
        if not isinstance(dd, dict):
            return
        day = self._w_day_key()
        if str(dd.get("day", "")) != day:
            return                                    # a save from an earlier day
        try:
            self._wl_seen = {(day, int(i)) for i in (dd.get("lookout") or [])}
            self._w_swing_seen = ({(day, int(i)) for i in (dd.get("swing") or [])}
                                  | {(day, "bench", int(i)) for i in (dd.get("bench") or [])})
        except (TypeError, ValueError):
            self._wl_seen, self._w_swing_seen = set(), set()

    def _on_area_enter_world(self):
        self._world_apply_season()
        self._world_sync_decor(force=True)
        area = self.world.area
        if getattr(self, "_wh_quiet", False):
            self._wh_quiet = False                    # entry replayed by a save load
            return
        if area.name == AREA_MEADOW and "meadow" not in self._wh_warned:
            self._wh_warned.add("meadow")
            self.ui.log("They say a promise made together under the old tree lasts forever...")
        elif (area.name == AREA_FARM and "farm" not in self._wh_warned
              and getattr(self, "started", False)
              and getattr(self, "net_mode", None) != "client"     # decor mode is host-side
              and self._w_decor_key_free()):
            self._wh_warned.add("farm")
            self.ui.log(f"Tip: press {key_label(BUILD_KEY)} on the farm to decorate outdoors.")
        if area.name == AREA_MINE and getattr(area, "hazards", None):
            biome = getattr(area, "biome", "")
            if biome not in self._wh_warned:
                self._wh_warned.add(biome)
                self.ui.log("Careful -- molten lava pools burn!" if biome == "lava"
                            else "Void rifts crackle in the dark -- they sap your health.")

    def _on_new_day_world(self):
        self._wl_seen = set()
        self._w_swing_seen = set()
        self._world_apply_season()

    # ------------------------------------------------------------------ helpers
    def _w_day_key(self):
        t = self.time
        return f"{getattr(t, 'year', 1)}|{getattr(t, 'season_idx', 0)}|{getattr(t, 'day', 1)}"

    @staticmethod
    def _w_decor_key_free():
        """True while no player action is bound to the decor hotkey (B)."""
        return not any(c == BUILD_KEY for K in (P1_KEYS, P2_KEYS) for c in K.values())

    @staticmethod
    def _w_near(p, cell, r):
        return (abs(int(p.x // TILE) - cell[0]) <= r and abs(int(p.y // TILE) - cell[1]) <= r)

    def _world_apply_season(self):
        """Seasonal art key + the meadow's winter snow grid."""
        season = getattr(self.time, "season", "Spring")
        WA.SEASON = season
        wp = getattr(self, "world_promise", None) or {}
        WA.CARVE = wp.get("carved", "")
        WA.TIER = _promise_tier(int(wp.get("count", 0) or 0))
        m = self.world.areas.get(AREA_MEADOW)
        if m is not None and getattr(m, "grid_green", None):
            want = m.grid_snow if season == "Winter" else m.grid_green
            if m.grid is not want:
                m.grid = want
                mm = getattr(getattr(self, "ui", None), "_mm_cache", None)
                if isinstance(mm, dict):           # minimap re-bakes the new ground
                    mm.pop(AREA_MEADOW, None)

    def _world_sync_decor(self, force=False):
        """Feed the farm's solid decor pieces into Area.dyn_solid (collision)."""
        farm = self.world.areas.get(AREA_FARM)
        fo = self.world.farm_objects
        sig = (id(fo), len(fo), id(farm))
        if not force and sig == self._w_decor_sig:
            return
        self._w_decor_sig = sig
        cells = set()
        for cell, kind in fo.items():
            if isinstance(kind, str) and kind.startswith(DECOR_PREFIX):
                info = WA.DECOR_INFO.get(kind[len(DECOR_PREFIX):])
                if info and info["solid"]:
                    cells.add(tuple(cell))
        if farm is not None:
            farm.dyn_solid = cells

    def _world_unblock_tilled(self):
        """Old saves may have tilled / planted where a new solid farm feature now
        stands -- free those tiles so no crop is ever walled in."""
        farm = self.world.areas.get(AREA_FARM)
        if farm is None:
            return
        for (gx, gy) in list(farm.solid_extra):
            k = (AREA_FARM, gx, gy)
            if k in self.world.tilled or k in self.world.crops:
                farm.solid_extra.discard((gx, gy))

    # ------------------------------------------------------------------ per frame
    def _on_update_world(self, dt):
        self._wh_quiet = False            # a load without an area re-entry (respawn=False)
        self._world_apply_season()
        self._world_sync_decor()
        if self._wp_glow > 0:
            self._wp_glow = max(0.0, self._wp_glow - dt)
        if self._w_swing_amp > 1.0:                        # swing settles back
            self._w_swing_amp = max(1.0, self._w_swing_amp - dt * 2.2)
        area = self.world.area
        self._w_fx_t += dt
        if self._w_fx_t >= 0.12:
            self._w_fx_t = 0.0
            self._world_ambient(area)
        # tidy: soil can't be hoed under decor (AOE swings could reach it)
        self._w_clean_t += dt
        if self._w_clean_t >= 0.5 and area.name == AREA_FARM:
            self._w_clean_t = 0.0
            for cell, kind in list(self.world.farm_objects.items()):
                if isinstance(kind, str) and kind.startswith(DECOR_PREFIX):
                    k = (AREA_FARM, cell[0], cell[1])
                    if k in self.world.tilled and k not in self.world.crops:
                        self.world.tilled.discard(k)
                        self.world.watered.discard(k)

    def _on_update_world_hazards(self, dt):
        area = self.world.area
        hz = getattr(area, "hazards", None)
        if not hz:
            return
        for p in self.players:
            kind = hz.get((int(p.x // TILE), int(p.y // TILE)))
            if not kind or p.health <= 0 or p.hurt_cd > 0:
                continue
            dmg = W.HAZARD_DPS.get(kind, 6)
            p.take_damage(dmg)
            lava = kind == "lava"
            self._popup(p.x, p.y - 34, f"-{dmg}", (255, 130, 90) if lava else (206, 160, 255))
            self.audio.play("hit")
            if lava:
                self.parts.ember(p.x, p.y + 8, n=6)
                self.parts.flame(p.x, p.y + 10, n=2)
            else:
                self.parts.sparkle(p.x, p.y, n=8, color=(190, 140, 255))

    def _world_ambient(self, area):
        name = area.name
        cam = self.cam
        if name == AREA_MINE and area.hazards:
            cells = list(area.hazards.items())
            for _ in range(2):
                (gx, gy), kind = random.choice(cells)
                wx, wy = gx * TILE + random.uniform(8, TILE - 8), gy * TILE + TILE * 0.5
                if not (cam.x - 40 < wx < cam.x + SCREEN_W + 40 and cam.y - 40 < wy < cam.y + SCREEN_H + 40):
                    continue
                if kind == "lava":
                    self.parts.ember(wx, wy, n=1)
                else:
                    self.parts.sparkle(wx, wy, n=1, color=(180, 120, 255))
        elif name == AREA_MEADOW:
            night = getattr(self, "night", 0.0)
            wx = cam.x + random.uniform(0, SCREEN_W)
            wy = cam.y + random.uniform(0, SCREEN_H)
            if night > 0.35:                                   # fireflies
                self.parts.sparkle(wx, wy, n=1, color=(226, 255, 150))
            elif self.time.season == "Fall" and random.random() < 0.5:
                self.parts.leaf(wx, wy, color=random.choice([(232, 150, 70), (214, 110, 70),
                                                             (240, 196, 100)]))
            elif self.time.season != "Winter" and random.random() < 0.5:
                col = random.choice([(250, 200, 220), (255, 236, 160), (220, 206, 250)])
                petal = getattr(self.parts, "petal", None)
                if petal:
                    try:
                        petal(wx, wy)
                    except TypeError:
                        self.parts.leaf(wx, wy, color=col)
                else:
                    self.parts.leaf(wx, wy, color=col)
            if self._wp_glow > 0:
                tree = getattr(area, "promise_tree", None)
                if tree:
                    tx = tree[0] * TILE + TILE / 2 + random.uniform(-60, 60)
                    ty = tree[1] * TILE - random.uniform(20, 140)
                    self.parts.sparkle(tx, ty, n=2, color=(255, 222, 140))
                    if random.random() < 0.5:
                        self.parts.heart_float(tx, ty)

    # ------------------------------------------------------------------ drawing
    def _w_view(self):
        cam = self.cam
        x0 = int(cam.x // TILE) - 2
        y0 = int(cam.y // TILE) - 2
        return x0, y0, x0 + SCREEN_W // TILE + 5, y0 + SCREEN_H // TILE + 6

    def _world_sprites_world(self):
        """Hazard decals (mine), the farm fence frame and placed outdoor decor."""
        area = self.world.area
        cam = self.cam
        out = []
        x0, y0, x1, y1 = self._w_view()
        name = area.name
        if name == AREA_MINE and area.hazards:
            lf, rf = WA.lava_frames(), WA.rift_frames()
            t = self.anim_t
            for (gx, gy), kind in area.hazards.items():
                if not (x0 <= gx <= x1 and y0 <= gy <= y1):
                    continue
                frames = lf if kind == "lava" else rf
                fr = frames[int(t * 5 + gx * 1.3 + gy) % len(frames)]
                out.append((_FLAT_BASE + gy, fr, (gx * TILE - cam.x, gy * TILE - cam.y)))
        elif name == AREA_MEADOW and getattr(area, "swing", None):
            sx, sy = area.swing
            off = math.sin(self.anim_t * 3.2) * self._w_swing_amp
            out.append(((sy + 1) * TILE, WA.swing_frame(off),
                        (sx * TILE - cam.x, (sy - 1) * TILE - cam.y)))
        elif name == AREA_FARM:
            tilled, crops = self.world.tilled, self.world.crops
            fh, fv = WA.fence("h"), WA.fence("v")
            for (gx, gy) in W.FARM_FENCE:
                if not (x0 <= gx <= x1 and y0 <= gy <= y1):
                    continue
                k = (AREA_FARM, gx, gy)
                if k in tilled or k in crops:
                    continue                      # never draw over someone's soil
                spr = fh if gy in (10, 27) else fv
                out.append((gy * TILE + 8, spr, (gx * TILE - cam.x, gy * TILE - cam.y)))
            sx, sy = W.FARM_NAME_SIGN                  # personal welcome sign
            if x0 <= sx <= x1 and y0 <= sy <= y1:
                spr = WA.text_sign(self._world_farm_title())
                out.append(((sy + 1) * TILE, spr,
                            (sx * TILE + TILE / 2 - spr.get_width() / 2 - cam.x,
                             (sy + 1) * TILE - spr.get_height() - cam.y)))
            fo = self.world.farm_objects
            for (gx, gy), kind in fo.items():
                if not (isinstance(kind, str) and kind.startswith(DECOR_PREFIX)):
                    continue
                if not (x0 <= gx <= x1 and y0 <= gy <= y1):
                    continue
                dn = kind[len(DECOR_PREFIX):]
                var = ""
                if dn in WA.CONNECTS:                 # fences join their neighbours
                    vert = fo.get((gx, gy - 1)) == kind or fo.get((gx, gy + 1)) == kind
                    horiz = fo.get((gx - 1, gy)) == kind or fo.get((gx + 1, gy)) == kind
                    if vert and not horiz:
                        var = "v"
                spr = WA.decor_sprite(dn, var)
                oy = spr.get_height() - TILE
                pos = (gx * TILE - cam.x, gy * TILE - cam.y - oy)
                t0 = self._w_pop.get((gx, gy))
                if t0 is not None:                    # freshly placed: a springy pop
                    age = self.anim_t - t0
                    if 0 <= age < 0.32:
                        k = 1.0 + 0.28 * math.sin(age / 0.32 * math.pi)
                        w0, h0 = spr.get_size()
                        spr = pygame.transform.scale(spr, (int(w0 * k), int(h0 * k)))
                        pos = (gx * TILE + (w0 - spr.get_width()) / 2 - cam.x,
                               (gy + 1) * TILE - spr.get_height() - cam.y)
                    else:
                        self._w_pop.pop((gx, gy), None)
                base = _FLAT_BASE + gy if dn in WA.FLAT_DECOR else (gy + 1) * TILE
                out.append((base, spr, pos))
        return out

    def _draw_world_world_glow(self):
        """Soft golden bloom around the Promise Tree right after a promise."""
        if self._wp_glow <= 0 or self.world.current != AREA_MEADOW:
            return
        tree = getattr(self.world.area, "promise_tree", None)
        if not tree:
            return
        k = min(1.0, self._wp_glow / 1.5)
        pulse = 0.8 + 0.2 * math.sin(self.anim_t * 5)
        col = tuple(int(c * k * pulse) // 8 * 8 for c in (150, 118, 52))
        if not any(col):
            return
        r = 176
        g = _radial(r, col)
        cx = tree[0] * TILE + TILE / 2 - self.cam.x
        cy = tree[1] * TILE - TILE * 1.4 - self.cam.y
        self.screen.blit(g, (int(cx - r), int(cy - r)), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_world_world_prompts(self):
        """Floating hint bubbles over the Promise Tree / lookout when someone is near
        (the core prompt pass only knows shops/beds/NPCs)."""
        area = self.world.area
        if area.name != AREA_MEADOW or self.state != "play":
            return
        cam = self.cam
        bob = int(math.sin(self.anim_t * 3) * 3)
        spots = []
        tree = getattr(area, "promise_tree", None)
        if tree and any(self._w_near(p, tree, 2) for p in self.players):
            done = self.world_promise.get("day") == self._w_day_key()
            if done:
                key, txt = None, "Promised today"
            else:
                key = f"{key_label(P1_KEYS['action'])} + {key_label(P2_KEYS['action'])}"
                txt = "together"
            # beside the trunk (not over the carved heart), under the right bough
            spots.append((tree[0] * TILE + TILE * 1.75, tree[1] * TILE - TILE * 0.35, "heart",
                          key, txt))
        lk = getattr(area, "lookout", None)
        if lk:
            near = [i for i, p in enumerate(self.players) if self._w_near(p, lk, 1)]
            if near:
                keys = P1_KEYS if near[0] == 0 else P2_KEYS
                spots.append((lk[0] * TILE + TILE / 2, lk[1] * TILE - TILE * 0.4, "eye",
                              key_label(keys['action']), "enjoy the view"))
        for wx, wy, icon, key, txt in spots:
            sx, sy = int(wx - cam.x), int(wy - cam.y) + bob
            self._w_draw_hint(sx, sy, icon, txt, key)

    def _w_hint_pill_pos(self, sx, sy, icon, pill):
        """Top-left of a hint prompt anchored at (sx, sy): the pill (its icon
        inside, at the left) is centred on the anchor, then nudged clear of
        the HUD cards at the top of the screen (8 px under the clock card) and
        kept on screen.  One rule for both the Promise Tree and the lookout."""
        w, h = pill.get_width(), pill.get_height()
        r = pygame.Rect(0, 0, w, h)
        r.center = (sx, sy)
        for z in self._HUD_ZONES:
            if z.top == 0 and r.right > z.left and r.left < z.right and r.top < z.bottom + 8:
                r.top = z.bottom + 8
        r.left = max(4, min(SCREEN_W - 4 - w, r.left))
        return r.topleft

    def _w_draw_hint(self, sx, sy, icon, txt, key=None):
        """One floating world prompt in ui_kit.key_pill's style, centred on
        its anchor (sx, sy)."""
        pill = self._w_hint_pill(txt, icon, key)
        r = pygame.Rect(self._w_hint_pill_pos(sx, sy, icon, pill), pill.get_size())
        # the swing's "~" bubble floats just above the swing, right beside the
        # tree's pill: step the pill left of it (the bubble also avoids the
        # reserved rect below)
        sw = getattr(self.world.area, "swing", None)
        if sw and icon == "heart":
            bx = int(sw[0] * TILE + TILE / 2 - self.cam.x)
            by = int(sw[1] * TILE + TILE / 2 - self.cam.y - TILE * 0.95)
            span = pygame.Rect(bx - 26, by - 16, 52, 62)
            if r.colliderect(span):
                r.right = span.left - 4
                r.left = max(4, r.left)
        self.screen.blit(pill, r.topleft)
        res = getattr(self, "hud_reserve", None)
        if res:
            res(r.inflate(4, 4))

    def _w_hint_pill(self, txt, rim=None, key=None):
        """A world prompt drawn exactly like ui_kit.key_pill (cream pill, wooden
        rim, the key in a wooden inset box, dark ink label), with the spot's
        little icon (heart / eye) inside the pill at its left.  ``rim`` may be
        the icon name ("heart" / "eye"); any other value means no icon.
        Cached per text."""
        from .. import ui_kit as K
        icon = rim if rim in ("heart", "eye") else None
        ck = ("whint2", txt, icon, key)
        pill = WA._cache.get(ck)
        if pill is not None:
            return pill
        fnt = K.font(14, True)
        h = max(24, fnt.get_height() + 10)
        iw = 22 if icon else 0
        kw = fnt.size(str(key))[0] + 12 if key else 0
        lw = fnt.size(txt)[0] if txt else 0
        w = 6 + iw + (kw + 8 if key else 4) + lw + 12
        pill = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(pill, (*K.WOOD, 235), pill.get_rect(), border_radius=h // 2)
        pygame.draw.rect(pill, (*K.CREAM, 235), pill.get_rect().inflate(-4, -4),
                         border_radius=h // 2 - 2)
        x = 6
        if icon:
            c = (x + 9, h // 2)
            if icon == "heart":
                col = (220, 92, 124)
                pygame.draw.circle(pill, col, (c[0] - 3, c[1] - 2), 4)
                pygame.draw.circle(pill, col, (c[0] + 3, c[1] - 2), 4)
                pygame.draw.polygon(pill, col, [(c[0] - 7, c[1]), (c[0] + 7, c[1]), (c[0], c[1] + 7)])
            else:
                pygame.draw.ellipse(pill, K.WOOD_DK, (c[0] - 9, c[1] - 6, 18, 12))
                pygame.draw.ellipse(pill, (236, 244, 250), (c[0] - 7, c[1] - 4, 14, 8))
                pygame.draw.circle(pill, (60, 96, 150), c, 3)
            x += iw
        if key:
            kbox = pygame.Rect(x, 4, kw, h - 8)
            pygame.draw.rect(pill, K.WOOD, kbox, border_radius=6)
            K.blit_text(pill, fnt, str(key), K.CREAM_HI, kbox.center)
            x = kbox.right + 8
        else:
            x += 4
        if txt:
            K.blit_text(pill, fnt, txt, K.INK, (x, h // 2), align="left")
        WA._cache[ck] = pill
        return pill

    # screen zones the HUD owns -- lamp halos (drawn after the night grade) skip them:
    # minimap, both hotbar rows (x 386-862), clock card, player panels, the
    # "In Sync" pill under the hotbars and the message feed between the panels
    _HUD_ZONES = (pygame.Rect(0, 0, 222, 190), pygame.Rect(386, 0, 478, 104),
                  pygame.Rect(978, 0, 302, 110), pygame.Rect(0, 622, 266, 98),
                  pygame.Rect(1014, 622, 266, 98))
    _HUD_ZONES_EXTRA = (pygame.Rect(560, 96, 160, 36), pygame.Rect(266, 620, 748, 100))

    def _w_no_glow_zones(self):
        """Every screen rect a lamp halo must not brighten this frame: the fixed
        HUD cards + whatever the HUD reserved (toasts, banners, bars...) + the
        area title card while it shows."""
        zones = list(self._HUD_ZONES) + list(self._HUD_ZONES_EXTRA)
        res = getattr(self, "hud_reserved", None)
        if res:
            try:
                zones += [pygame.Rect(r) for r in res()]
            except Exception:
                pass
        card = getattr(self, "area_card_rect", None)
        if card:
            try:
                c = card()
                if c:
                    zones.append(pygame.Rect(c).inflate(8, 8))
            except Exception:
                pass
        return zones

    def _draw_hud_world_lamps(self):
        """Lit lamp heads: the night grade dims additive lights a lot, so after it we
        add a small warm halo on each lamp's glass so lamps visibly shine at night."""
        night = getattr(self, "night", 0.0)
        if night < 0.3 or self.state not in ("play", "decor"):
            return
        area = self.world.area
        cells = list(getattr(area, "lamps", ()))
        if area.name == AREA_FARM:
            cells += [c for c, k in self.world.farm_objects.items() if k == "decor_lamp_post"]
        k = min(1.0, (night - 0.3) / 0.4)
        cam = self.cam
        zones = self._w_no_glow_zones()
        tree = getattr(area, "promise_tree", None) if area.name == AREA_MEADOW else None
        if tree:                                   # the Promise Tree's fairy lights twinkle
            ox = (tree[0] - 1) * TILE + TILE * 3 // 2 - cam.x
            oy = (tree[1] + 1) * TILE - cam.y
            for i, (dx, dy) in enumerate(((-64, -90), (-36, -82), (-8, -88), (20, -80),
                                          (48, -86), (64, -92))):
                tw = 0.6 + 0.4 * math.sin(self.anim_t * 3 + i * 1.7)
                c = [(150, 120, 60), (150, 90, 110), (100, 120, 150)][i % 3]
                col = tuple(int(v * k * tw) // 8 * 8 for v in c)
                if any(col):
                    r = pygame.Rect(int(ox + dx) - 14, int(oy + dy) - 14, 28, 28)
                    if not any(r.colliderect(z) for z in zones):
                        self.screen.blit(_radial(14, col), r.topleft,
                                         special_flags=pygame.BLEND_RGBA_ADD)
        if not cells:
            return
        col = tuple(int(c * k) // 8 * 8 for c in (150, 120, 60))
        if not any(col):
            return
        halo = _radial(30, col)
        for (gx, gy) in cells:
            sx = gx * TILE + TILE / 2 - cam.x
            sy = gy * TILE - TILE * 0.2 - cam.y
            if not (-40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40):
                continue
            r = pygame.Rect(int(sx) - 30, int(sy) - 30, 60, 60)
            if any(r.colliderect(z) for z in zones):
                continue
            self.screen.blit(halo, r.topleft, special_flags=pygame.BLEND_RGBA_ADD)

    def _lights_world(self):
        area = self.world.area
        cam = self.cam
        out = []
        vx0, vy0 = cam.x - 200, cam.y - 200
        vx1, vy1 = cam.x + SCREEN_W + 200, cam.y + SCREEN_H + 200

        def add(wx, wy, r, col):
            if vx0 < wx < vx1 and vy0 < wy < vy1:
                out.append((wx, wy, r, col))
        name = area.name
        if name == AREA_MINE:
            for (gx, gy), kind in getattr(area, "hazards", {}).items():
                if kind == "lava":
                    add(gx * TILE + TILE / 2, gy * TILE + TILE / 2, 80, (255, 120, 40))
                else:
                    add(gx * TILE + TILE / 2, gy * TILE + TILE / 2, 64, (160, 80, 255))
            for (kind, gx, gy) in area.props:
                if kind == "ruin_glyph":
                    add(gx * TILE + TILE / 2, gy * TILE + TILE / 2, 48, (90, 230, 200))
            return out
        for (gx, gy) in getattr(area, "lamps", ()):
            add(gx * TILE + TILE / 2, gy * TILE - TILE * 0.2, 112, (255, 214, 140))
        if name == AREA_FARM:
            for (gx, gy), kind in self.world.farm_objects.items():
                if kind == "decor_lamp_post":
                    add(gx * TILE + TILE / 2, gy * TILE - TILE * 0.2, 112, (255, 214, 140))
                elif kind == "decor_lantern_string":
                    add(gx * TILE + TILE / 2, gy * TILE - TILE * 0.3, 80, (255, 180, 170))
        elif name == AREA_MEADOW:
            tree = getattr(area, "promise_tree", None)
            if tree:
                boost = 1.0 + (0.6 if self._wp_glow > 0 else 0.0)
                add(tree[0] * TILE + TILE / 2, tree[1] * TILE - TILE * 1.6, int(150 * boost),
                    (255, 200, 150))
        return out

    # ------------------------------------------------------------------ interactions
    def _world_npc_close(self, p):
        return any(abs(n.x - p.x) < TILE * 1.1 and abs(n.y - p.y) < TILE * 1.1
                   for n in getattr(self, "npcs", ()))

    def _w_at_promise_tree(self, p):
        """Is player ``p`` pressing action AT the Promise Tree?  Near the trunk
        (2 tiles) -- but a player right next to the swing / bench / lookout who
        isn't facing the tree itself is using that spot instead."""
        area = self.world.area
        tree = getattr(area, "promise_tree", None)
        if area.name != AREA_MEADOW or not tree or not self._w_near(p, tree, 2):
            return False
        tx, ty = p.target_tile()
        if tree[0] - 1 <= tx <= tree[0] + 1 and tree[1] - 3 <= ty <= tree[1]:
            return True                               # facing the trunk / canopy
        return not any(spot and self._w_near(p, spot, 1)
                       for spot in (getattr(area, "swing", None), getattr(area, "bench", None),
                                    getattr(area, "lookout", None)))

    def _interact_early_world_promise(self, idx, p):
        area = self.world.area
        tree = getattr(area, "promise_tree", None)
        if not self._w_at_promise_tree(p):
            return False
        if self._world_npc_close(p):
            return False                              # let them chat to a visitor
        now = time.monotonic()
        self._wp_press[idx] = now
        other = 1 - idx
        q = self.players[other]
        cx, cy = tree[0] * TILE + TILE / 2, tree[1] * TILE
        if now - self._wp_press[other] <= PROMISE_WINDOW and self._w_near(q, tree, 2):
            self._wp_press = [-99.0, -99.0]
            self._world_promise_moment(cx, cy)
            return True
        # a lone press: a gentle nudge that this needs both of you (the words are
        # throttled, but every press still gets a little heart so none feels lost)
        self.parts.heart_float(p.x, p.y - 30)
        if now - self._wp_hint_t >= 1.0:
            self._wp_hint_t = now
            self.parts.heart_float(cx, cy - TILE)
            self.audio.play("ui_move")
            self._popup(p.x, p.y - 40, "It takes two...", (255, 190, 210))
            keys = P2_KEYS if idx == 0 else P1_KEYS
            if self._w_near(q, tree, 2):
                self.ui.log(f"Now {q.name} presses {key_label(keys['action'])} too -- together!")
            else:
                self.ui.log(f"The Promise Tree waits for two. Bring {q.name} here and press together.")
        return True

    def _world_promise_moment(self, cx, cy):
        day = self._w_day_key()
        self.parts.heart_burst(cx, cy - TILE * 1.2, n=26)
        star = getattr(self.parts, "star_burst", None)
        if star:
            try:
                star(cx, cy - TILE * 1.6)
            except Exception:
                pass
        self.add_shake(2)
        self.audio.play("bell")
        wp = self.world_promise
        if wp.get("day") == day:
            self._popup(cx, cy - TILE * 1.8, "Still yours, today and always", (255, 200, 220))
            self.ui.log("You renew today's promise under the tree. <3")
            return
        first = not wp.get("carved")
        tier0 = _promise_tier(int(wp.get("count", 0)))
        wp["day"] = day
        wp["count"] = int(wp.get("count", 0)) + 1
        tier1 = _promise_tier(wp["count"])
        WA.TIER = tier1
        self._wp_glow = 3.5
        self.audio.play("levelup")
        for p in self.players:
            p.energy = min(MAX_ENERGY, p.energy + PROMISE_ENERGY)
            self._popup(p.x, p.y - 44, f"+{PROMISE_ENERGY} energy", (255, 226, 140))
            self.parts.sparkle(p.x, p.y - 10, n=10, color=(255, 220, 150))
        sub = f"Promise #{wp['count']}  -  both of you +{PROMISE_ENERGY} energy"
        if first:
            a = (str(self.players[0].name).strip()[:1] or "?").upper()
            b = (str(self.players[1].name).strip()[:1] or "?").upper()
            wp["carved"] = f"{a}+{b}"
            WA.CARVE = wp["carved"]
            sub = f"Your initials {wp['carved']} are carved into the trunk"
        toast = getattr(self, "toast", None)
        if toast:
            toast("A promise under the tree", sub, icon=_heart_icon(), color=(255, 130, 165))
        self.ui.log("A promise under the tree. " + sub + ".")
        if tier1 > tier0:                                  # a milestone adornment appears
            self.parts.confetti(cx, cy - TILE * 2, n=16)
            self.audio.play("achievement")
            if toast:
                toast("The Promise Tree grows lovelier", _MILESTONE_TEXT.get(tier1, ""),
                      icon=_heart_icon(), color=(255, 206, 110))
            self.ui.log(_MILESTONE_TEXT.get(tier1, "") + ".")
        self.emit("promise", day=day, count=wp["count"], first=first)

    def _interact_early_world_lookout(self, idx, p):
        area = self.world.area
        lk = getattr(area, "lookout", None)
        if area.name != AREA_MEADOW or not lk or not self._w_near(p, lk, 1):
            return False
        if self._world_npc_close(p):
            return False
        key = (self._w_day_key(), idx)
        self.audio.play("ui_select")
        self.parts.sparkle(lk[0] * TILE + TILE / 2, lk[1] * TILE, n=8, color=(200, 230, 255))
        if key not in self._wl_seen:
            self._wl_seen.add(key)
            p.energy = min(MAX_ENERGY, p.energy + LOOKOUT_ENERGY)
            # warm energy-gold (the pale blue vanished on the wooden deck); the
            # popup pass outlines it
            self._popup(p.x, p.y - 40, f"What a view! +{LOOKOUT_ENERGY}", (255, 226, 140))
        else:
            self._popup(p.x, p.y - 40, "What a view!", (255, 226, 140))
        self.ui.log(random.choice(_LOOKOUT_LINES))
        return True

    def _interact_early_world_swing(self, idx, p):
        area = self.world.area
        sw = getattr(area, "swing", None)
        if area.name != AREA_MEADOW or not sw or not self._w_near(p, sw, 1):
            return False
        if self._world_npc_close(p):
            return False
        self._w_swing_amp = 9.0
        wx, wy = sw[0] * TILE + TILE / 2, sw[1] * TILE + TILE * 0.4
        self.parts.heart_float(wx, wy - 10)
        self.audio.play("ui_select")
        q = self.players[1 - idx]
        if self._w_near(q, sw, 2):
            self._popup(wx, wy - 40, f"{q.name} gives a gentle push!", (255, 200, 220))
            self.parts.heart_burst(wx, wy - 20, n=8)
        else:
            self._popup(wx, wy - 40, "Wheee!", (255, 226, 160))
        key = (self._w_day_key(), idx)
        if key not in self._w_swing_seen:
            self._w_swing_seen.add(key)
            p.energy = min(MAX_ENERGY, p.energy + 8)
            self._popup(p.x, p.y - 24, "+8 energy", (255, 226, 140))
        return True

    def _interact_early_world_bench(self, idx, p):
        """The meadow's love bench: sit a while -- together it's a little moment."""
        area = self.world.area
        b = getattr(area, "bench", None)
        if area.name != AREA_MEADOW or not b or not self._w_near(p, b, 1):
            return False
        if self._w_at_promise_tree(p) or self._world_npc_close(p):
            return False                              # the Promise Tree has priority
        wx, wy = b[0] * TILE, b[1] * TILE
        q = self.players[1 - idx]
        key = (self._w_day_key(), "bench", idx)
        gain = 0 if key in self._w_swing_seen else 10
        self._w_swing_seen.add(key)
        if self._w_near(q, b, 1):
            self.parts.heart_burst(wx, wy - 20, n=10)
            self._popup(wx, wy - 44, "Watching the clouds together", (255, 200, 220))
            self.ui.log(f"{p.name} and {q.name} sit close and watch the clouds drift by.")
        else:
            self.parts.heart_float(wx, wy - 16)
            self._popup(wx, wy - 44, "A quiet moment", (230, 220, 250))
            self.ui.log(f"{p.name} rests on the bench. It'd be nicer with {q.name}...")
        if gain:
            p.energy = min(MAX_ENERGY, p.energy + gain)
            self._popup(p.x, p.y - 24, f"+{gain} energy", (255, 226, 140))
        self.audio.play("ui_select")
        return True

    def _interact_late_world_orchard(self, idx, p):
        """Face an orchard tree and press action: shake it for fruit once a day
        (summer apples, fall persimmons).  Spring/winter: a gentle rustle."""
        area = self.world.area
        if area.name != AREA_FARM:
            return False
        tx, ty = p.target_tile()
        if ("fruit_tree", tx, ty) not in area.props:
            return False
        wx, wy = tx * TILE + TILE / 2, ty * TILE - TILE * 0.3
        self.parts.leaf(wx - 8, wy, color=(150, 200, 130))
        self.parts.leaf(wx + 8, wy - 6, color=(150, 200, 130))
        self.add_shake(1)
        season = self.time.season
        fruit = ORCHARD_FRUIT.get(season)
        day = self._w_day_key()
        if self.world_orchard.get("day") != day:
            self.world_orchard = {"day": day, "shaken": []}
        if not fruit:
            self.audio.play("ui_move")
            self._popup(wx, wy - 10, "Blossoms..." if season == "Spring" else "Resting for winter",
                        (220, 230, 210))
            return True
        if [tx, ty] in self.world_orchard["shaken"]:
            self.audio.play("ui_move")
            self._popup(wx, wy - 10, "Already shaken today", (220, 230, 210))
            return True
        self.world_orchard["shaken"] = sorted(self.world_orchard["shaken"] + [[tx, ty]])
        luck = 0.15 if self.fortune.get(idx) == "lucky" else 0.0
        if random.random() < ORCHARD_CHANCE + luck:
            p.inv.add(fruit, 1)
            self.audio.play("forage")
            self.parts.sparkle(wx, wy, n=8, color=(255, 200, 150))
            label = "Apple" if fruit == "apple" else "Persimmon"
            self._popup(wx, wy - 10, f"+1 {label}", (255, 214, 150))
            self.ui.log(f"{p.name} shakes the tree -- a ripe {label.lower()} drops!")
            self._grant_xp(p, "foraging", 2)
            self.emit("foraged", p=p, item=fruit)
        else:
            self.audio.play("ui_move")
            self._popup(wx, wy - 10, "Nothing ripe yet", (220, 230, 210))
        return True

    def _on_tool_world_decor(self, idx, p, tool, gx, gy):
        if self.world.current != AREA_FARM:
            return False
        kind = self.world.farm_objects.get((gx, gy))
        if tool == "hoe" and isinstance(kind, str) and kind.startswith(DECOR_PREFIX):
            self.ui.log(f"There's decor there -- press {key_label(BUILD_KEY)} to rearrange it.")
            return True
        return False

    # ------------------------------------------------------------------ decor mode
    def _on_keydown_world_decor(self, key):
        if key != BUILD_KEY or self.world.current != AREA_FARM or self.state != "play":
            return False
        # a player who rebound one of their actions to B keeps that action --
        # the decor hotkey never steals a bound key (same rule as the emote key)
        if not self._w_decor_key_free():
            return False
        if getattr(self, "net_mode", None) == "client":
            return False
        p = self.players[0]
        tx, ty = p.target_tile()
        farm = self.world.area
        self._wd["cx"] = max(1, min(farm.w - 2, tx))
        self._wd["cy"] = max(1, min(farm.h - 2, ty))
        self._wd["msg"] = ""
        self.state = "decor"
        self.audio.play("ui_select")
        return True

    def _world_farm_title(self):
        """'Ploy & Nat's Farm' (initials when the names are long)."""
        a = str(self.players[0].name).strip() or "P1"
        b = str(self.players[1].name).strip() or "P2"
        t = f"{a} & {b}'s Farm"
        if len(t) > 24:
            t = f"{a[:1].upper()} & {b[:1].upper()}'s Farm"
        return t

    def _world_decor_protected(self):
        """Tiles decor may never cover: warps, arrival spots, shop/bin, coop."""
        farm = self.world.areas[AREA_FARM]
        prot = {(w["gx"], w["gy"]) for w in farm.warps}
        for a in self.world.areas.values():
            for w in a.warps:
                if w["to"] == AREA_FARM:
                    sx, sy = w["spawn"]
                    prot |= {(sx, sy), (sx + 1, sy)}
        prot |= {(12, 12), (13, 12)}                  # faint / respawn spot
        for attr in ("shop", "coop", "bed"):
            v = getattr(farm, attr, None)
            if v:
                prot.add(tuple(v))
        prot |= {(gx, gy) for (_k, gx, gy) in farm.props}
        prot |= set(W.FARM_FENCE)                     # the field's fence frame
        prot.add(W.FARM_NAME_SIGN)
        return prot

    def _world_decor_check(self, gx, gy):
        """(ok, reason) for placing a decor piece on the farm tile (gx, gy)."""
        farm = self.world.areas[AREA_FARM]
        if not (1 <= gx < farm.w - 1 and 1 <= gy < farm.h - 1):
            return False, "Too close to the edge."
        here = self.world.farm_objects.get((gx, gy))
        if here is not None:
            if isinstance(here, str) and here.startswith(DECOR_PREFIX):
                return False, f"Occupied -- {key_label(pygame.K_x)} picks it up."
            return False, "Something is already here."
        if farm.is_solid(gx, gy) or farm.tile(gx, gy) in W.SOLID_TILES:
            return False, "Blocked."
        if farm.tile(gx, gy) == W.COBBLE:
            return False, "Keep the paths clear."
        k = (AREA_FARM, gx, gy)
        if k in self.world.tilled or k in self.world.crops:
            return False, "That's farmland."
        if (gx, gy) in self._world_decor_protected():
            return False, "Keep this spot clear."
        for p in self.players:
            if (int(p.x // TILE), int(p.y // TILE)) == (gx, gy):
                return False, "Someone is standing there."
        return True, ""

    def _world_decor_msg(self, text, ok=True):
        self._wd["msg"] = text
        self._wd["msg_ok"] = ok
        self._wd["msg_t"] = 2.2

    def _world_decor_place(self, gx, gy):
        name = WA.DECOR[self._wd["sel"] % len(WA.DECOR)][0]
        info = WA.DECOR_INFO[name]
        ok, why = self._world_decor_check(gx, gy)
        if not ok:
            self.audio.play("error")
            self._world_decor_msg(why, False)
            return False
        if self.gold < info["price"]:
            self.audio.play("error")
            self._world_decor_msg(f"Need {info['price']}g for a {info['label']}.", False)
            return False
        self.gold -= info["price"]
        self.world.farm_objects[(gx, gy)] = DECOR_PREFIX + name
        self._w_pop[(gx, gy)] = self.anim_t
        self._world_sync_decor(force=True)
        wx, wy = gx * TILE + TILE / 2, gy * TILE + TILE / 2
        self.parts.dust(wx, wy + 10, n=8)
        self.parts.sparkle(wx, wy - 8, n=8, color=(255, 236, 170))
        self.audio.play("craft")
        self._popup(wx, wy - 30, f"-{info['price']}g", (255, 214, 120))
        self._world_decor_msg(f"Placed {info['label']} (-{info['price']}g)")
        self.emit("decor_placed", item=name, gx=gx, gy=gy)
        return True

    def _world_decor_sell(self, gx, gy):
        kind = self.world.farm_objects.get((gx, gy))
        if not (isinstance(kind, str) and kind.startswith(DECOR_PREFIX)):
            self.audio.play("error")
            self._world_decor_msg("No decor here to pick up.", False)
            return False
        name = kind[len(DECOR_PREFIX):]
        info = WA.DECOR_INFO.get(name, {"label": name, "price": 0})
        refund = info["price"] // 2
        del self.world.farm_objects[(gx, gy)]
        self._world_sync_decor(force=True)
        self.gold += refund
        wx, wy = gx * TILE + TILE / 2, gy * TILE + TILE / 2
        self.parts.dust(wx, wy + 8, n=10)
        coin = getattr(self.parts, "coin_burst", None)
        if coin:
            try:
                coin(wx, wy - 10)
            except Exception:
                pass
        self.audio.play("sell")
        self._popup(wx, wy - 30, f"+{refund}g", (255, 236, 140))
        self._world_decor_msg(f"Sold {info['label']} (+{refund}g)")
        return True

    def _world_decor_close(self):
        self.state = "play"
        self.audio.play("ui_move")

    _DECOR_BAR_H = 128

    def _world_decor_slots(self):
        n = len(WA.DECOR)
        sw = 80
        x0 = SCREEN_W // 2 - (n * sw) // 2
        y0 = SCREEN_H - self._DECOR_BAR_H + 30
        return [pygame.Rect(x0 + i * sw + 3, y0, sw - 6, 92) for i in range(n)]

    def _w_decor_bar_bg(self):
        """Opaque catalogue bar (cached) -- the HUD's player panels sit under it."""
        bh = self._DECOR_BAR_H
        key = ("wdecor_bar", SCREEN_W, bh)
        bar = WA._cache.get(key)
        if bar is None:
            bar = pygame.Surface((SCREEN_W, bh))
            bar.fill((36, 29, 25))
            pygame.draw.rect(bar, (29, 23, 20), (0, 0, SCREEN_W, 27))
            pygame.draw.line(bar, (214, 176, 110), (0, 0), (SCREEN_W, 0), 2)
            pygame.draw.line(bar, (92, 72, 54), (0, 3), (SCREEN_W, 3), 1)
            pygame.draw.line(bar, (58, 46, 38), (0, 27), (SCREEN_W, 27), 1)
            WA._cache[key] = bar
        return bar

    def _w_decor_label(self, text, width, col):
        """A catalogue label word-wrapped onto (at most) two centred lines."""
        key = ("wdecor_lbl", text, width, col)
        surf = WA._cache.get(key)
        if surf is None:
            f = self.ui.tiny
            lines, cur = [], ""
            for word in text.split():
                trial = (cur + " " + word).strip()
                if cur and f.size(trial)[0] > width and len(lines) < 1:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
            rs = [f.render(ln, True, col) for ln in lines]
            lh = f.get_height()                       # tight leading: 2 lines fit the card
            surf = pygame.Surface((max(r.get_width() for r in rs), lh * len(rs)), pygame.SRCALPHA)
            for i, r in enumerate(rs):
                surf.blit(r, ((surf.get_width() - r.get_width()) // 2, i * lh))
            WA._cache[key] = surf
        return surf

    def _state_event_decor(self, e):
        if self.world.current != AREA_FARM:
            self.state = "play"
            return
        wd = self._wd
        farm = self.world.area
        n = len(WA.DECOR)
        if e.type == pygame.KEYDOWN:
            k = e.key
            mv = {P1_KEYS["up"]: (0, -1), P1_KEYS["down"]: (0, 1), P1_KEYS["left"]: (-1, 0),
                  P1_KEYS["right"]: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
                  pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}
            if k in (pygame.K_ESCAPE, BUILD_KEY):
                self._world_decor_close()
            elif k in mv:
                dx, dy = mv[k]
                wd["cx"] = max(1, min(farm.w - 2, wd["cx"] + dx))
                wd["cy"] = max(1, min(farm.h - 2, wd["cy"] + dy))
            elif k in (P1_KEYS["prev"], P2_KEYS["prev"], pygame.K_q, pygame.K_LEFTBRACKET):
                wd["sel"] = (wd["sel"] - 1) % n
                self.audio.play("ui_move")
            elif k in (P1_KEYS["next"], P2_KEYS["next"], pygame.K_e, pygame.K_RIGHTBRACKET,
                       pygame.K_TAB):
                wd["sel"] = (wd["sel"] + 1) % n
                self.audio.play("ui_move")
            elif k in (P1_KEYS["action"], P2_KEYS["action"], pygame.K_RETURN, pygame.K_KP_ENTER):
                self._world_decor_place(wd["cx"], wd["cy"])
            elif k in (pygame.K_x, pygame.K_DELETE, pygame.K_BACKSPACE):
                self._world_decor_sell(wd["cx"], wd["cy"])
        elif e.type == pygame.MOUSEMOTION:
            pos = getattr(e, "pos", (0, 0))
            wd["hover"] = None
            for i, r in enumerate(self._world_decor_slots()):
                if r.collidepoint(pos):
                    wd["hover"] = i
            if pos[1] < SCREEN_H - self._DECOR_BAR_H:
                wd["cx"] = max(1, min(farm.w - 2, int((pos[0] + self.cam.x) // TILE)))
                wd["cy"] = max(1, min(farm.h - 2, int((pos[1] + self.cam.y) // TILE)))
        elif e.type == pygame.MOUSEBUTTONDOWN:
            pos = getattr(e, "pos", (0, 0))
            btn = getattr(e, "button", 1)
            if btn in (4, 5):
                wd["sel"] = (wd["sel"] + (-1 if btn == 4 else 1)) % n
                return
            if pos[1] >= SCREEN_H - self._DECOR_BAR_H:
                for i, r in enumerate(self._world_decor_slots()):
                    if r.collidepoint(pos):
                        wd["sel"] = i
                        self.audio.play("ui_move")
                return
            gx = int((pos[0] + self.cam.x) // TILE)
            gy = int((pos[1] + self.cam.y) // TILE)
            wd["cx"] = max(1, min(farm.w - 2, gx))
            wd["cy"] = max(1, min(farm.h - 2, gy))
            if btn == 1:
                self._world_decor_place(wd["cx"], wd["cy"])
            elif btn == 3:
                self._world_decor_sell(wd["cx"], wd["cy"])
        elif e.type == pygame.MOUSEWHEEL:
            wd["sel"] = (wd["sel"] - getattr(e, "y", 0)) % n

    def _state_update_decor(self, dt):
        if self.world.current != AREA_FARM:
            self.state = "play"
            return
        wd = self._wd
        wd["msg_t"] = max(0.0, wd["msg_t"] - dt)
        self.anim_t += dt
        self.parts.update(dt)
        # the warp iris only opens in Game.update ("play"): B pressed right after
        # arriving must not freeze it dark over the farm while decorating
        if getattr(self, "fade", 0) > 0:
            self.fade = max(0.0, self.fade - dt * 2.2)
        farm = self.world.area
        # camera glides to keep the cursor comfortably on screen
        tx = wd["cx"] * TILE + TILE / 2 - SCREEN_W / 2
        ty = wd["cy"] * TILE + TILE / 2 - (SCREEN_H - self._DECOR_BAR_H) / 2
        tx = min(max(0, tx), max(0, farm.w * TILE - SCREEN_W))
        ty = min(max(0, ty), max(0, farm.h * TILE - SCREEN_H + self._DECOR_BAR_H))
        k = min(1.0, dt * 8)
        self.cam.x += (tx - self.cam.x) * k
        self.cam.y += (ty - self.cam.y) * k

    def _state_draw_decor(self):
        if self.world.current != AREA_FARM:
            return
        scr = self.screen
        ui = self.ui
        wd = self._wd
        cam = self.cam
        name, label, price, solid, _g = WA.DECOR[wd["sel"] % len(WA.DECOR)]
        gx, gy = wd["cx"], wd["cy"]
        ok, why = self._world_decor_check(gx, gy)
        afford = self.gold >= price
        good = ok and afford
        # --- cursor: tile highlight + tinted ghost
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 180.0)
        rx, ry = gx * TILE - cam.x, gy * TILE - cam.y
        box = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        box.fill((90, 230, 120, 60) if good else (240, 80, 80, 60))
        scr.blit(box, (rx, ry))
        pygame.draw.rect(scr, (140, 255, 160) if good else (255, 120, 120),
                         (rx, ry, TILE, TILE), 2 + int(pulse * 1.5), border_radius=4)
        existing = self.world.farm_objects.get((gx, gy))
        if not (isinstance(existing, str) and existing.startswith(DECOR_PREFIX)):
            gh = WA.ghost(name, good)
            scr.blit(gh, (rx, ry - (gh.get_height() - TILE)))
        else:
            from .. import ui_kit as K
            K.key_pill(scr, key_label(pygame.K_x), "sell", (rx + TILE // 2, ry - 16))
        # floating cost texts ("-20g") were drawn with the world, under the
        # cursor square / ghost: redraw the ones the cursor covers on top
        rects = getattr(self, "_popup_rects_last", None) or []
        psurf = getattr(self, "_popup_surf", None)
        if rects and psurf:
            cur = pygame.Rect(rx - 8, ry - TILE * 2, TILE + 16, TILE * 3)
            for pop, pr in zip(reversed(self.popups), rects):
                if pr.colliderect(cur):
                    try:
                        s = psurf(str(pop[2]), pop[3])
                        s.set_alpha(max(0, min(255, int(pop[4] * 255))))
                        scr.blit(s, pr.topleft)
                    except Exception:
                        pass
        # --- bottom catalogue bar
        bh = self._DECOR_BAR_H
        by = SCREEN_H - bh
        scr.blit(self._w_decor_bar_bg(), (0, by))       # opaque: hides the HUD panels
        head = ui.font.render("OUTDOOR DECOR", True, (255, 236, 180))
        scr.blit(head, (16, by + 5))
        cur = ui.small.render(f"{label}  -  {price}g", True,
                              (255, 214, 120) if afford else (230, 140, 120))
        # title, a clear gap, a small gold diamond, another gap, then the pick
        cx0 = 16 + head.get_width() + DECOR_HEAD_GAP
        dx, dy = 16 + head.get_width() + DECOR_HEAD_GAP // 2, by + 5 + head.get_height() // 2
        pygame.draw.polygon(scr, (214, 176, 110), [(dx, dy - 4), (dx + 4, dy), (dx, dy + 4),
                                                   (dx - 4, dy)])
        scr.blit(cur, (cx0, by + 5 + (head.get_height() - cur.get_height()) // 2))
        gold = ui.font.render(f"Gold: {self.gold:,}g", True, (255, 214, 110))
        scr.blit(gold, (SCREEN_W - gold.get_width() - 16, by + 5))
        K = P1_KEYS
        hint = (f"{key_label(K['up'])}{key_label(K['left'])}{key_label(K['down'])}{key_label(K['right'])}"
                f"/mouse move   {key_label(K['prev'])}/{key_label(K['next'])} choose   "
                f"{key_label(K['action'])}/click place   {key_label(pygame.K_x)}/right-click sell (half back)"
                f"   {key_label(BUILD_KEY)}/{key_label(pygame.K_ESCAPE)} done")
        ht = ui.tiny.render(hint, True, (206, 196, 178))
        hx = SCREEN_W - gold.get_width() - 36 - ht.get_width()
        hx = max(cx0 + cur.get_width() + 24, hx)
        scr.blit(ht, (hx, by + 5 + (head.get_height() - ht.get_height()) // 2))
        for i, r in enumerate(self._world_decor_slots()):
            dn, dl, dp, _s, _gg = WA.DECOR[i]
            sel = i == wd["sel"] % len(WA.DECOR)
            can = self.gold >= dp
            bg = (78, 63, 48) if sel else ((52, 44, 36) if wd.get("hover") != i else (62, 52, 42))
            pygame.draw.rect(scr, bg, r, border_radius=8)
            pygame.draw.rect(scr, (255, 214, 120) if sel else (110, 92, 70), r,
                             3 if sel else 1, border_radius=8)
            ic = WA.decor_icon(dn, 40)
            ix = r.centerx - ic.get_width() // 2
            iy = r.y + 4 + (40 - ic.get_height())
            if sel:
                iy -= int(pulse * 3)
            scr.blit(ic, (ix, iy))
            # prices share one row; the name (1 or 2 lines) is vertically centred
            # in the space under it (two-line names used to hug the bottom edge)
            pt = ui.tiny.render(f"{dp}g", True, (255, 220, 120) if can else (200, 110, 100))
            lt = self._w_decor_label(dl, r.w - 6, (250, 244, 230) if sel else (196, 186, 170))
            py0 = r.y + 47
            scr.blit(pt, (r.centerx - pt.get_width() // 2, py0))
            top, bot = py0 + pt.get_height(), r.bottom - 1
            scr.blit(lt, (r.centerx - lt.get_width() // 2, top + (bot - top - lt.get_height()) // 2))
        # --- status line: selected piece + validity / last action
        if wd["msg_t"] > 0 and wd["msg"]:
            txt, col = wd["msg"], ((170, 240, 170) if wd["msg_ok"] else (255, 150, 140))
        else:
            kind = "blocks the way" if solid else "walk-over"
            txt = f"{label}  -  {price}g  ({kind})"
            col = (230, 222, 206)
            if not ok:
                txt += f"   [{why}]"
                col = (255, 170, 150)
            elif not afford:
                txt += "   [not enough gold]"
                col = (255, 170, 150)
        from .. import ui_kit as K
        pw_ = ui.small.size(txt)[0] + 28
        ph_ = ui.small.get_height() + 12
        pr = pygame.Rect(SCREEN_W // 2 - pw_ // 2, SCREEN_H - bh - ph_ - 8, pw_, ph_)
        K.pill(scr, pr, (20, 16, 14), outline=(110, 92, 70), alpha=215)
        K.blit_text(scr, ui.small, txt, col, pr.center)

    # ------------------------------------------------------------------ journal
    def _journal_tab_55_world(self):
        return {"title": "Places", "draw": self._world_journal_draw}

    # the mine's biome bands, for the Places page (label, levels, lo, hi, note, chip colour)
    _W_BIOMES = (("Rock", "1-4", 1, 4, "", (150, 132, 114)),
                 ("Ice", "5-9", 5, 9, "", (112, 164, 206)),
                 ("Lava", "10-14", 10, 14, "lava pools!", (206, 92, 52)),
                 ("Crystal", "15-19", 15, 19, "", (160, 102, 204)),
                 ("Abyss", "20-29", 20, 29, "void rifts!", (84, 64, 132)),
                 ("Ancient Ruins", "30+", 30, 10 ** 9, "", (150, 136, 78)))

    def _world_journal_draw(self, surf, rect):
        """Places: on the cream journal page, in ui_kit ink.  Two cards side by
        side on top (the Promise Tree | our farm), the mine's six biome bands
        across the full width underneath -- balanced, no half-empty side."""
        from .. import ui_kit as K
        wp = self.world_promise
        count = int(wp.get("count", 0))
        decor = sum(1 for k in self.world.farm_objects.values()
                    if isinstance(k, str) and k.startswith(DECOR_PREFIX))
        f_head, f_body, f_big = K.font(18, True), K.font(15), K.font(30, True)
        f_small = K.font(13, True)
        gap = 18
        x0, w = rect.x + 4, rect.w - 8
        top_h = min(236, max(200, rect.h // 2 - 10))
        cw = (w - gap) // 2

        def heading(r, text):
            K.blit_text(surf, f_head, text, K.SPROUT, (r.x + 18, r.y + 20), align="left")
            pygame.draw.line(surf, K.WELL_LINE, (r.x + 16, r.y + 36), (r.right - 16, r.y + 36), 2)

        def para(r, y, text, col=K.INK_SOFT, fnt=f_body):
            for ln in K.wrap(fnt, text, r.w - 36):
                K.blit_text(surf, fnt, ln, col, (r.x + 18, y), align="left")
                y += fnt.get_linesize()
            return y

        # ---- the Promise Tree
        a = pygame.Rect(x0, rect.y + 6, cw, top_h)
        K.well(surf, a, radius=12)
        heading(a, "THE PROMISE TREE")
        carved = wp.get("carved")
        K.blit_text(surf, f_body, "Initials carved", K.INK_SOFT, (a.x + 18, a.y + 62), align="left")
        K.blit_text(surf, f_big if carved else f_body, carved or "not yet",
                    (176, 76, 112) if carved else K.INK_FAINT, (a.right - 20, a.y + 62), align="right")
        nxt = next((m for m in PROMISE_MILESTONES if count < m), None)
        K.blit_text(surf, f_body, f"Promises made: {count}", K.INK, (a.x + 18, a.y + 98), align="left")
        K.blit_text(surf, f_small, f"next surprise at {nxt}" if nxt else "every milestone reached!",
                    K.GOLD_TXT, (a.right - 20, a.y + 98), align="right")
        prev = max([0] + [m for m in PROMISE_MILESTONES if m <= count])
        k = 1.0 if nxt is None else (count - prev) / max(1, nxt - prev)
        bar = pygame.Rect(a.x + 18, a.y + 114, a.w - 38, 12)
        pygame.draw.rect(surf, K.CREAM_HI, bar, border_radius=6)
        if k > 0:
            pygame.draw.rect(surf, K.HEART, (bar.x, bar.y, max(12, int(bar.w * k)), bar.h),
                             border_radius=6)
        pygame.draw.rect(surf, K.WELL_LINE, bar, 2, border_radius=6)
        para(a, a.y + 150, "Stand by the tree in the Flower Meadow and both press action together.")

        # ---- our farm
        b = pygame.Rect(a.right + gap, a.y, cw, top_h)
        K.well(surf, b, radius=12)
        heading(b, "OUR FARM")
        K.blit_text(surf, f_body, "Outdoor decor placed", K.INK_SOFT, (b.x + 18, b.y + 62),
                    align="left")
        K.blit_text(surf, f_big, str(decor), K.GOLD_TXT, (b.right - 20, b.y + 62), align="right")
        para(b, b.y + 98, f"Press {key_label(BUILD_KEY)} on the farm to open the decor catalogue: "
                          "fences, paths, flower beds, lamps and more.")
        para(b, b.y + 150, "Each piece sells back for half its price.", K.INK_SOFT)

        # ---- the mines: six biome bands across the full width
        m = pygame.Rect(x0, a.bottom + gap, w, max(150, rect.bottom - 6 - (a.bottom + gap)))
        K.well(surf, m, radius=12)
        heading(m, "THE MINES")
        deep = int(self.world.mine_level)
        K.blit_text(surf, f_small, f"Deepest visited this trip: level {deep}", K.INK_SOFT,
                    (m.right - 20, m.y + 20), align="right")
        n = len(self._W_BIOMES)
        cg = 10
        chip_w = (m.w - 36 - cg * (n - 1)) // n
        chip_h = min(96, m.h - 64)
        cy0 = m.y + 48 + (m.h - 48 - 10 - chip_h) // 2
        for i, (name, lv, lo, hi, note, col) in enumerate(self._W_BIOMES):
            c = pygame.Rect(m.x + 18 + i * (chip_w + cg), cy0, chip_w, chip_h)
            here = lo <= deep <= hi
            pygame.draw.rect(surf, K.HILITE if here else K.CREAM_HI, c, border_radius=10)
            pygame.draw.rect(surf, K.GOLD_RIM if here else K.WELL_LINE, c, 3 if here else 2,
                             border_radius=10)
            pygame.draw.rect(surf, col, (c.x + 10, c.y + 10, c.w - 20, 10), border_radius=5)
            fn = K.fit_font(name, c.w - 14, (16, 15, 14, 13, 12), bold=True)
            K.blit_text(surf, fn, name, K.INK, (c.centerx, c.y + 38))
            K.blit_text(surf, f_small, f"levels {lv}", K.INK_SOFT, (c.centerx, c.y + 58))
            if note:
                K.blit_text(surf, K.font(12, True), note, K.WARN, (c.centerx, c.y + 78))

